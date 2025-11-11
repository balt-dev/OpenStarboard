from io import BytesIO
import traceback

import discord
from discord.ext import commands

from discord import app_commands, Interaction
from discord.app_commands import errors

from ..types import MiscellaneousError

class EventsCog(commands.Cog, name="Events"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        @bot.tree.error
        async def on_error(
            intr: discord.Interaction, err: discord.app_commands.AppCommandError
        ):
            """Handles errors."""
            if not intr.response.is_done():
                await intr.response.defer(ephemeral=True, thinking=True)

            if isinstance(err, app_commands.CommandInvokeError) or isinstance(err, commands.ExtensionFailed):
                err = err.original

            if isinstance(err, errors.CheckFailure):
                return await intr.followup.send("You're not authorized to do that.", ephemeral=True)

            if isinstance(err, MiscellaneousError):
                return await intr.followup.send(err.args[0], ephemeral=True)

            traceback.print_exception(err)

            tb = "\n".join(traceback.format_exception(err, chain=False, limit=-5))
            await intr.followup.send(f"Unhandled exception occurred! {err}\n```py\n{tb[-1800:]}\n```", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(EventsCog(bot))