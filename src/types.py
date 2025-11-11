import enum
from dataclasses import dataclass

import discord

@dataclass
class ReactionChannel:
    guild: discord.Guild
    destination_channel: discord.abc.GuildChannel
    emoji: str
    threshold: int
    is_whitelist: bool
    channel_list: list[discord.abc.GuildChannel]

class MiscellaneousError(discord.app_commands.AppCommandError):
    pass