import discord
import asyncio

from io import BytesIO
from utils.connection import REDIS, ASYNC_REDIS
from utils.exceptions import ReplayParsingError, ReplayRenderingError
from utils.logging import LOGGER_BOT
from rq import Queue
from rq.job import Job
from rq.worker import Worker
from tasks.dual import render_dual
from discord.ext import commands
from discord import app_commands

QUEUE = Queue(name="single", connection=REDIS)

ORANGE = 0xFF9933
RED = 0xFF0000
YELLOW = 0xFFFF00
GREEN = 0x00FF00

MAX_QUEUE_SIZE = 10
COOLDOWN_SECONDS = 60
JOB_TIMEOUT_PER_ITEM = 300
MAX_FILE_SIZE_MB = 5
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

WOWSREPLAY_MIN_SIZE = 16


def make_embed(
    filename: str,
    color: int,
    status: str | None = None,
    error: str | None = None,
    progress: float | None = None,
) -> discord.Embed:
    embed = discord.Embed(title="Minimap Renderer - Dual", color=color)
    embed.add_field(name="Files", value=filename, inline=False)

    if status:
        embed.add_field(name="Status", value=status, inline=False)

    if error:
        embed.add_field(name="Error", value=error, inline=False)

    if progress is not None:
        blocks = round(10 * progress)
        embed.add_field(
            name="Progress",
            value=f"{'▮' * blocks}{'▯' * (10 - blocks)}",
            inline=False,
        )
    return embed


def validate_replay(filename: str, size: int, data: bytes) -> str | None:
    """
    Validate a replay file before queuing.
    Returns an error message string if invalid, or None if valid.
    """
    if not filename.lower().endswith(".wowsreplay"):
        return "File must be a `.wowsreplay` file."

    if size > MAX_FILE_SIZE_BYTES:
        return f"File is too large ({size / 1024 / 1024:.1f} MB). Maximum size is {MAX_FILE_SIZE_MB} MB."

    if len(data) < WOWSREPLAY_MIN_SIZE:
        return "File is too small to be a valid replay."

    if all(b == 0 for b in data[:WOWSREPLAY_MIN_SIZE]):
        return "File appears to be empty or corrupt."

    return None


class CogDualRender(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self._bot = bot

    async def _check(self, interaction: discord.Interaction) -> bool:
        user = interaction.user
        worker_count = Worker.count(queue=QUEUE)
        cooldown = await ASYNC_REDIS.ttl(f"cooldown_{user.id}")
        ongoing = await ASYNC_REDIS.exists(f"task_request_{user.id}")

        if QUEUE.count >= MAX_QUEUE_SIZE:
            await interaction.followup.send(
                "⚠️ The queue is full. Please try again shortly.", ephemeral=True
            )
            return False

        if worker_count == 0:
            await interaction.followup.send(
                "⚠️ No render workers are available right now.", ephemeral=True
            )
            return False

        if cooldown > 0:
            await interaction.followup.send(
                f"⏳ You're on cooldown. Please wait {cooldown}s before submitting again.",
                ephemeral=True,
            )
            return False

        if ongoing:
            await interaction.followup.send(
                "⚠️ You already have a render in progress.", ephemeral=True
            )
            return False

        return True

    async def _poll_result(
        self,
        interaction: discord.Interaction,
        attachment1: discord.Attachment,
        attachment2: discord.Attachment,
        fps: int,
        quality: int,
        anon: bool,
        green_tag: str | None,
        red_tag: str | None,
    ):
        user = interaction.user
        filenames = f"{attachment1.filename} + {attachment2.filename}"

        await ASYNC_REDIS.set(f"task_request_{user.id}", "", ex=180)

        try:
            replay_bytes_1 = await attachment1.read()
            replay_bytes_2 = await attachment2.read()

            # Validate both files after download
            error1 = validate_replay(attachment1.filename, attachment1.size, replay_bytes_1)
            if error1:
                await interaction.followup.send(f"❌ Replay 1: {error1}", ephemeral=True)
                return

            error2 = validate_replay(attachment2.filename, attachment2.size, replay_bytes_2)
            if error2:
                await interaction.followup.send(f"❌ Replay 2: {error2}", ephemeral=True)
                return

            job_ttl = max(QUEUE.count, 1) * JOB_TIMEOUT_PER_ITEM

            job: Job = QUEUE.enqueue(
                render_dual,
                kwargs={
                    "user_id": user.id,
                    "replay_bytes_1": replay_bytes_1,
                    "replay_bytes_2": replay_bytes_2,
                    "fps": fps,
                    "quality": quality,
                    "anon": anon,
                    "green_tag": green_tag,
                    "red_tag": red_tag,
                },
                failure_ttl=180,
                result_ttl=180,
                ttl=job_ttl,
            )

            msg = await interaction.followup.send(
                embed=make_embed(filenames, ORANGE, status="Queued"), wait=True
            )

            while True:
                status = job.get_status(refresh=True)

                match status:
                    case "queued":
                        position = QUEUE.get_job_position(job.id)
                        status_text = f"Queued (position {position + 1})" if position is not None else "Queued"
                        await msg.edit(embed=make_embed(filenames, ORANGE, status=status_text))

                    case "started":
                        meta = job.get_meta(refresh=True)
                        if progress := meta.get("progress"):
                            await msg.edit(
                                embed=make_embed(filenames, YELLOW, status="Rendering", progress=progress)
                            )
                        elif task_status := meta.get("status"):
                            await msg.edit(
                                embed=make_embed(filenames, YELLOW, status=task_status)
                            )
                        else:
                            await msg.edit(
                                embed=make_embed(filenames, YELLOW, status="Started")
                            )

                    case "finished":
                        result = job.result

                        if isinstance(result, ReplayParsingError):
                            await msg.edit(
                                embed=make_embed(filenames, RED, error="Replay parsing failed. Are both files valid replays?")
                            )
                        elif isinstance(result, ReplayRenderingError):
                            await msg.edit(
                                embed=make_embed(filenames, RED, error="Render failed. Replays may be from an unsupported version or different battles.")
                            )
                        elif isinstance(result, Exception):
                            LOGGER_BOT.exception(f"Unknown error in dual job result: {result}")
                            await msg.edit(
                                embed=make_embed(filenames, RED, error="An unexpected error occurred.")
                            )
                        elif isinstance(result, bytes):
                            file_size_mb = len(result) / (1024 * 1024)

                            if file_size_mb > 25:
                                await msg.edit(
                                    embed=make_embed(
                                        filenames,
                                        RED,
                                        error=f"Rendered file is too large ({file_size_mb:.1f} MB). Try reducing quality or fps.",
                                    )
                                )
                            else:
                                await msg.edit(
                                    embed=make_embed(filenames, GREEN, status="Completed!")
                                )
                                output_filename = attachment1.filename.replace(".wowsreplay", "_dual.mp4")
                                with BytesIO(result) as video_data:
                                    await interaction.followup.send(
                                        file=discord.File(video_data, filename=output_filename)
                                    )
                                await msg.delete()
                                await interaction.delete_original_response()
                        else:
                            await msg.edit(
                                embed=make_embed(filenames, RED, error="Unknown result type.")
                            )
                        break

                    case "failed":
                        await msg.edit(
                            embed=make_embed(filenames, RED, error="Job failed unexpectedly.")
                        )
                        break

                    case _:
                        await msg.edit(
                            embed=make_embed(filenames, RED, error="Render task expired.")
                        )
                        break

                await asyncio.sleep(1)

        except Exception as e:
            LOGGER_BOT.exception(f"Unhandled error in dual _poll_result: {e}")
        finally:
            await ASYNC_REDIS.delete(f"task_request_{user.id}")

    @app_commands.command(name="minimap_dual", description="Renders two WoWS replays from the same battle side by side.")
    @app_commands.describe(
        replay1="First replay file (green team)",
        replay2="Second replay file (red team)",
        fps="Frames per second (20-30, default 30)",
        quality="Video quality 1-9 (default 7, higher = larger file)",
        anon="Hide player names (default: False)",
        green_tag="Label for green team (optional)",
        red_tag="Label for red team (optional)",
    )
    async def minimap_dual(
        self,
        interaction: discord.Interaction,
        replay1: discord.Attachment,
        replay2: discord.Attachment,
        fps: app_commands.Range[int, 20, 30] = 30,
        quality: app_commands.Range[int, 1, 9] = 7,
        anon: bool = False,
        green_tag: str | None = None,
        red_tag: str | None = None,
    ):
        if not replay1.filename.lower().endswith(".wowsreplay"):
            await interaction.response.send_message(
                "❌ Replay 1 must be a `.wowsreplay` file.", ephemeral=True
            )
            return

        if not replay2.filename.lower().endswith(".wowsreplay"):
            await interaction.response.send_message(
                "❌ Replay 2 must be a `.wowsreplay` file.", ephemeral=True
            )
            return

        if replay1.size > MAX_FILE_SIZE_BYTES:
            await interaction.response.send_message(
                f"❌ Replay 1 is too large ({replay1.size / 1024 / 1024:.1f} MB). Maximum size is {MAX_FILE_SIZE_MB} MB.",
                ephemeral=True,
            )
            return

        if replay2.size > MAX_FILE_SIZE_BYTES:
            await interaction.response.send_message(
                f"❌ Replay 2 is too large ({replay2.size / 1024 / 1024:.1f} MB). Maximum size is {MAX_FILE_SIZE_MB} MB.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        if not await self._check(interaction):
            return

        asyncio.create_task(
            self._poll_result(
                interaction=interaction,
                attachment1=replay1,
                attachment2=replay2,
                fps=fps,
                quality=quality,
                anon=anon,
                green_tag=green_tag,
                red_tag=red_tag,
            )
        )
