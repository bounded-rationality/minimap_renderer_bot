import os
import asyncio
import discord
from discord.ext import commands
from utils.environ import check_environment_var
from utils.logging import LOGGER_BOT
from bot.cogs.render import CogRender

check_environment_var(["DISCORD_TOKEN"])

intents = discord.Intents.default()
intents.message_content = True

BOT = commands.Bot(command_prefix="!", help_command=None, intents=intents)


@BOT.event
async def on_ready():
    await BOT.tree.sync()
    LOGGER_BOT.info(f"Logged in as {BOT.user} (ID: {BOT.user.id})")
    LOGGER_BOT.info("Slash commands synced.")


async def setup():
    await BOT.add_cog(CogRender(BOT))


def run():
    token = os.environ["DISCORD_TOKEN"]
    asyncio.run(setup())
    BOT.run(token)
