#!.venv/bin/python

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import discord
from discord.ext import commands

import config
import auth

class Bot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def shutdown(self):
        sys.exit(0)

    async def unload_cogs(self):
        await asyncio.gather(*(
            self.unload_extension(f"src.cogs.{cog.stem}", package="bot")
            for cog in Path("src/cogs").glob("*.py")
        ))

    async def reload_cogs(self):
        await asyncio.gather(*(
            self.reload_extension(f"src.cogs.{cog.stem}", package="bot")
            for cog in Path("src/cogs").glob("*.py")
        ))
    
    async def load_cogs(self):
        await asyncio.gather(*(
            self.load_extension(f"src.cogs.{cog.stem}", package="bot")
            for cog in Path("src/cogs").glob("*.py")
        ))

    async def on_ready(self):
        await self.load_cogs()

        if config.sync_on_startup:
            await self.tree.sync()

        print("Ready!")

    async def on_guild_remove(self, guild: discord.Guild):
        print("Removing stale entries...")
        await self.db.remove_guild(guild)
    
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if hasattr(self, "raw_reaction_add"):
            await self.raw_reaction_add(self, payload)

def main():
    discord.utils.setup_logging()

    bot = Bot(
        [],
        activity=config.activity,
        description=config.description,
        allowed_mentions=discord.AllowedMentions(everyone=False, roles=False),
        intents=discord.Intents(guilds=True, reactions=True),
        member_cache_flags=discord.MemberCacheFlags.none(),
        max_messages=None,
        chunk_guilds_at_startup=False,
    )

    try: 
        bot.run(auth.DISCORD_TOKEN, log_handler=None)
    finally:
        asyncio.run(bot.close())

if __name__ == "__main__":
    main()
