import discord

activity = discord.CustomActivity(
    "Watching for emoji",
    emoji = discord.PartialEmoji.from_str("⭐")
)
description = "An open-source reaction tallying bot."
sync_on_startup = False
database_path = "bot.db"

MAX_STARBOARDS = 5