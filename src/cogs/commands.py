import io

import emoji as em
import discord
from discord.ext import commands
from discord import app_commands, Interaction
from discord.app_commands import Choice, errors
from asqlite import sqlite3

import config
from ..types import MiscellaneousError, ReactionChannel

class SetupBox(discord.ui.Modal, title='Starboard Setup'):
    cog: "CommandsCog"

    def __init__(
        self, intr: Interaction, cog: "CommandsCog",
        emoji: str, threshold: int
    ):
        super().__init__()
        self.cog = cog
        self.emoji = emoji
        self.threshold = threshold
        self.label = discord.ui.TextDisplay(content = f"Setting up starboard for emoji {emoji}")
    
    dest_channel_label = discord.ui.Label (
        text = "Destination Channel",
        description = "The channel to put starboarded messages into",
        component = discord.ui.ChannelSelect(
            required = True,
            channel_types = [discord.ChannelType.text, discord.ChannelType.news]
        )
    )

    channel_list_label = discord.ui.Label (
        text = "Channel Blacklist/Whitelist",
        description = "The channel to get starboarded messages from",
        component = discord.ui.ChannelSelect(
            required = False,
            channel_types = [
                discord.ChannelType.text, discord.ChannelType.news,
                discord.ChannelType.voice, discord.ChannelType.public_thread,
            ],
            min_values = 0,
            max_values = 25,
        )
    )

    is_blacklist_label = discord.ui.Label (
        text = "Blacklist/Whitelist?",
        description = "Whether the above list is a blacklist or a whitelist",
        component = discord.ui.Select(
            required = True,
            options = [
                discord.SelectOption(label = "Blacklist", value = "blacklist", default = True, emoji = "❌"),
                discord.SelectOption(label = "Whitelist", value = "whitelist", emoji = "✅")
            ]    
        )
    )

    async def on_submit(self, intr: discord.Interaction):
        await intr.response.defer(ephemeral=True, thinking=False)
        try:
            dest_channel = self.dest_channel_label.component.values[0]
            await self.cog.bot.db.add_reaction_channel(
                ReactionChannel(
                    intr.guild, dest_channel,
                    self.emoji, self.threshold,
                    self.is_blacklist_label.component.values[0] == "whitelist",
                    self.channel_list_label.component.values
                )
            )
            await intr.followup.send(f"Set up starboard for emoji {self.emoji} in channel <#{dest_channel.id}>.", ephemeral=True)
        except Exception as err:
            return await self.cog.bot.tree.on_error(intr, err)

def validate_emoji(bot: commands.Bot, guild: discord.Guild, emoji: discord.PartialEmoji):
    if emoji.is_unicode_emoji():
        if not em.is_emoji(emoji.name):
            return None
        return emoji.name
    else:
        raise MiscellaneousError("Custom emoji are currently unsupported.")

class CommandsCog(commands.Cog, name="Commands"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        @bot.tree.command()
        @discord.app_commands.checks.has_permissions(manage_channels = True)
        async def setup(
            intr: Interaction, emoji: str, threshold: app_commands.Range[int, 1, None]
        ):
            """Set up a starboard."""
            emoji = validate_emoji(bot, intr.guild, discord.PartialEmoji.from_str(emoji))
            if emoji is None:
                raise MiscellaneousError("The specified emoji is either not valid or not available for use by the bot.")

            if threshold <= 0:
                raise MiscellaneousError("The specified threshold must be greater than or equal to 1.")
            starboards_in_guild = await self.bot.db.starboard_count_for_guild(intr.guild)
            if  starboards_in_guild >= config.MAX_STARBOARDS:
                raise MiscellaneousError(
                    f"You've reached the maximum amount of starboards per server ({config.MAX_STARBOARDS}).\n" \
                    f"Remove one of your starboards before setting up another one."
                )
                
            box = SetupBox(intr, self, emoji, threshold)
            await intr.response.send_modal(box)
            await box.wait()

        @bot.tree.command()
        @discord.app_commands.checks.has_permissions(manage_channels = True)
        async def remove(
            intr: Interaction, emoji: str
        ):
            """Remove a starboard."""
            emoji = validate_emoji(bot, intr.guild, discord.PartialEmoji.from_str(emoji))
            if emoji is None:
                raise MiscellaneousError("The specified emoji is either not valid or not available for use by the bot.")
            await bot.db.try_remove_emoji(intr.guild, emoji)
            await intr.followup.send(f"Removed starboard for emoji `{emoji}`.")

        @bot.tree.command()
        @discord.app_commands.checks.has_permissions(manage_channels = True)
        async def set_threshold(
            intr: Interaction, emoji: str, threshold: app_commands.Range[int, 1, None]
        ):
            """Set the reaction threshold of a starboard."""
            emoji = validate_emoji(bot, intr.guild, discord.PartialEmoji.from_str(emoji))
            if emoji is None:
                raise MiscellaneousError("The specified emoji is either not valid or not available for use by the bot.")
            await bot.db.set_emoji_threshold(intr.guild, emoji, threshold)
            await intr.followup.send(f"Set threshold of starboard for emoji `{emoji}` to `{threshold}`.")
        
        @remove.autocomplete("emoji")
        @set_threshold.autocomplete("emoji")
        async def autocomplete_remove_emoji(intr: Interaction, _emoji: str):
            emojis = await bot.db.get_emojis_in_guild(intr.guild)
            return [Choice(name=emoji, value=emoji) for emoji in sorted(emojis)]
        
        @bot.tree.command()
        async def sync_tree(intr: Interaction):
            if not await bot.is_owner(intr.user):
                raise errors.CheckFailure()

            await intr.response.defer(thinking=True, ephemeral=True)
            await bot.tree.sync()
            await intr.followup.send("Synced!", ephemeral=True)

        @bot.tree.command()
        async def reload_cogs(intr: Interaction):
            if not await bot.is_owner(intr.user):
                raise errors.CheckFailure()

            await intr.response.defer(thinking=True, ephemeral=True)
            await bot.reload_cogs()
            await intr.followup.send("Reloaded cogs!", ephemeral=True)

        @bot.tree.command()
        async def sql(intr: Interaction, query: str):
            if not await bot.is_owner(intr.user):
                raise errors.CheckFailure()
                
            await intr.response.defer(thinking=True, ephemeral=True)
            async with self.bot.db.conn.cursor() as cur:
                try:
                    result = await cur.execute(query)
                except sqlite3.OperationalError as err:
                    raise MiscellaneousError(f"SQL error!\n`{err}`")

                formatted_results = await self.bot.db.format_results(result)
                if len(formatted_results) > 1900:
                    buf = io.StringIO()
                    buf.write(formatted_results)
                    buf.seek(0)
                    return await intr.followup.send(file=discord.File(buf, filename="output.txt"), ephemeral=True)
                return await intr.followup.send(f"```\n{formatted_results}\n```", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(CommandsCog(bot))