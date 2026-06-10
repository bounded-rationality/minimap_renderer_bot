import discord
import asyncio

from io import BytesIO
from utils.connection import REDIS, ASYNC_REDIS
from utils.exceptions import ReplayParsingError, ReplayRenderingError
from utils.logging import LOGGER_BOT
from rq import Queue
from rq.job import Job
from rq.worker import Worker
from tasks.single import render_single
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

# .wowsreplay files start with a 4-byte little-endian integer (packet size)
# followed by 0x00 padding. We just check it's not empty or all zeros.
WOWSREPLAY_MIN_SIZE = 16


def make_embed(
    filename: str,
    color: int,
    status: str | None = None,
    error: str | None = None,
    progress: float | None = None,
) -> discord.Embed:
    embed = discord.Embed(title="Minimap Renderer", color=color)
    embed.add_field(name="File", value=filename, inline=False)

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


class CogRender(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self._bot = bot

    async def _check(self, interaction: discord.Interaction) -> bool:
        """Pre-flight checks before accepting a render job."""
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
        attachment: discord.Attachment,
        fps: int,
        quality: int,
        logs: bool,
        chat: bool,
        anon: bool,
    ):
        user = interaction.user
        filename = attachment.filename

        await ASYNC_REDIS.set(f"task_request_{user.id}", "", ex=180)

        try:
            replay_bytes = await attachment.read()

            # Validate file content after download
            error = validate_replay(filename, attachment.size, replay_bytes)
            if error:
                await interaction.followup.send(f"❌ {error}", ephemeral=True)
                return

            job_ttl = max(QUEUE.count, 1) * JOB_TIMEOUT_PER_ITEM

            job: Job = QUEUE.enqueue(
                render_single,
                kwargs={
                    "user_id": user.id,
                    "replay_bytes": replay_bytes,
                    "fps": fps,
                    "quality": quality,
                    "logs": logs,
                    "chat": chat,
                    "anon": anon,
                },
                failure_ttl=180,
                result_ttl=180,
                ttl=job_ttl,
            )

            msg = await interaction.followup.send(
                embed=make_embed(filename, ORANGE, status="Queued"), wait=True
            )

            while True:
                status = job.get_status(refresh=True)

                match status:
                    case "queued":
                        position = QUEUE.get_job_position(job.id)
                        status_text = f"Queued (position {position + 1})" if position is not None else "Queued"
                        await msg.edit(embed=make_embed(filename, ORANGE, status=status_text))

                    case "started":
                        meta = job.get_meta(refresh=True)
                        if progress := meta.get("progress"):
                            await msg.edit(
                                embed=make_embed(filename, YELLOW, status="Rendering", progress=progress)
                            )
                        elif task_status := meta.get("status"):
                            await msg.edit(
                                embed=make_embed(filename, YELLOW, status=task_status)
                            )
                        else:
                            await msg.edit(
                                embed=make_embed(filename, YELLOW, status="Started")
                            )

                    case "finished":
                        result = job.result

                        if isinstance(result, ReplayParsingError):
                            await msg.edit(
                                embed=make_embed(filename, RED, error="Replay parsing failed. Is this a valid replay file?")
                            )
                        elif isinstance(result, ReplayRenderingError):
                            await msg.edit(
                                embed=make_embed(filename, RED, error="Render failed. The replay may be from an unsupported version.")
                            )
                        elif isinstance(result, Exception):
                            LOGGER_BOT.exception(f"Unknown error in job result: {result}")
                            await msg.edit(
                                embed=make_embed(filename, RED, error="An unexpected error occurred.")
                            )
                        elif isinstance(result, bytes):
                            file_size_mb = len(result) / (1024 * 1024)

                            if file_size_mb > 25:
                                await msg.edit(
                                    embed=make_embed(
                                        filename,
                                        RED,
                                        error=f"Rendered file is too large ({file_size_mb:.1f} MB). Try reducing quality or fps.",
                                    )
                                )
                            else:
                                output_filename = filename.replace(".wowsreplay", ".mp4")
                                with BytesIO(result) as video_data:
                                    await interaction.followup.send(
                                        file=discord.File(video_data, filename=output_filename)
                                    )
                                await msg.delete()
                                await interaction.delete_original_response()
                        else:
                            await msg.edit(
                                embed=make_embed(filename, RED, error="Unknown result type.")
                            )
                        break

                    case "failed":
                        await msg.edit(
                            embed=make_embed(filename, RED, error="Job failed unexpectedly.")
                        )
                        break

                    case _:
                        await msg.edit(
                            embed=make_embed(filename, RED, error="Render task expired.")
                        )
                        break

                await asyncio.sleep(1)

        except Exception as e:
            LOGGER_BOT.exception(f"Unhandled error in _poll_result: {e}")
        finally:
            await ASYNC_REDIS.delete(f"task_request_{user.id}")

    @app_commands.command(name="minimap", description="Renders a WoWS replay into a minimap video.")
    @app_commands.describe(
        attachment="Your .wowsreplay file",
        fps="Frames per second (20-30, default 30)",
        quality="Video quality 1-9 (default 7, higher = larger file)",
        logs="Show event log overlay (default: True)",
        chat="Show chat in log overlay (default: True)",
        anon="Hide player names (default: False)",
    )
    async def render(
        self,
        interaction: discord.Interaction,
        attachment: discord.Attachment,
        fps: app_commands.Range[int, 20, 30] = 30,
        quality: app_commands.Range[int, 1, 9] = 7,
        logs: bool = True,
        chat: bool = True,
        anon: bool = False,
    ):
        if not attachment.filename.lower().endswith(".wowsreplay"):
            await interaction.response.send_message(
                "❌ Please attach a `.wowsreplay` file.", ephemeral=True
            )
            return

        if attachment.size > MAX_FILE_SIZE_BYTES:
            await interaction.response.send_message(
                f"❌ File is too large ({attachment.size / 1024 / 1024:.1f} MB). Maximum size is {MAX_FILE_SIZE_MB} MB.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        if not await self._check(interaction):
            return

        asyncio.create_task(
            self._poll_result(
                interaction=interaction,
                attachment=attachment,
                fps=fps,
                quality=quality,
                logs=logs,
                chat=chat,
                anon=anon,
            )
        )
