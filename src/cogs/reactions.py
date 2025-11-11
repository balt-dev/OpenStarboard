import traceback

import discord
from discord.ext import commands
from discord import app_commands, Interaction
from discord.app_commands import Choice

from datetime import datetime, UTC

async def on_raw_reaction_add(bot: commands.Bot, payload: discord.RawReactionActionEvent):
    try:
        if await bot.db.already_sent_message(payload.guild_id, payload.emoji.name, payload.message_id):
            return
        if not await bot.db.has_reaction_channel_for_emoji(payload.guild_id, payload.emoji.name):
            return
        guild = bot.get_guild(payload.guild_id)
        if guild is None: return
        channel = guild.get_channel(payload.channel_id)
        if channel is None: return
        if not hasattr(channel, "fetch_message"): return
        message = await channel.fetch_message(payload.message_id)
        if message is None: return
        reactions = message.reactions
        for reaction in reactions:
            emoji = getattr(reaction.emoji, "name", reaction.emoji)
            if emoji is not None and emoji == payload.emoji.name:
                dest = await bot.db.maybe_get_destination(message, channel, guild, payload.emoji.name, reaction.count)
                if dest is not None:
                    await message.forward(dest)
                    await dest.send(f"-# Sent to this board at <t:{int(datetime.now(UTC).timestamp())}:F>")
                    await bot.db.mark_as_sent(message, guild, payload.emoji.name)
    except Exception as err:
        traceback.print_exception(err)


async def setup(bot: commands.Bot):
    bot.raw_reaction_add = on_raw_reaction_add