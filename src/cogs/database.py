import discord
from discord.ext import commands
import asqlite
from asqlite import sqlite3 as sql

import pathlib

import config
from ..types import ReactionChannel, MiscellaneousError

class Database:
    def __init__(self, path: pathlib.Path):
        self.path = path

    async def connect(self):
        self.conn = await asqlite.connect(self.path)
        async with self.conn.cursor() as cur:
            await cur.execute("VACUUM;")
    
    async def close(self):
        if hasattr(self, "conn"):
            await self.conn.close()

    async def starboard_count_for_guild(self, guild: discord.Guild):
        """Returns the amount of starboards set up for the specified guild."""
        async with self.conn.cursor() as cur:
            res = await cur.execute(
                "SELECT COUNT(emoji) FROM ReactionChannels WHERE guild_id == ?",
                guild.id
            )
            count, *_ = await res.fetchone()
            return count

    async def format_results(self, result: asqlite.Cursor):
        """Formats the results of an SQL query to a string."""
        rows = await result.fetchall()
        headers = [column[0] for column in result.get_cursor().description]
        rows = [[*row,] for row in rows]
        max_column_lengths = []
        for i in range(len(headers)):
            max_len = len(headers[i])
            for row in rows:
                val = row[i] = str(row[i])
                max_len = max(max_len, len(val))
            max_column_lengths.append(max_len)
        s = ["|"]
        for length, header in zip(max_column_lengths, headers):
            s.append(f" {header: ^{length}} |")
        s.append("\n|")
        for length in max_column_lengths:
            s.append("-"*(length+2))
            s.append("|")
        for row in rows:
            s.append("\n|")
            for length, val in zip(max_column_lengths, row):
                if all(c in (*"0123456789+-.e",) for c in val):
                    s.append(f" {val: >{length}} |")
                else:
                    s.append(f" {val: <{length}} |")
        return "".join(s)

    async def validate_channel(self, channel: ReactionChannel):
        """Validates a reaction channel."""
        # Check whitelist isn't empty
        if not len(channel.channel_list) and channel.is_whitelist:
            raise MiscellaneousError("Channel whitelist must have at least one entry.")
        async with self.conn.cursor() as cur:
            # Check if the same emoji is set up in this guild 
            res = await cur.execute("""
                SELECT
                    emoji,
                    destination_channel_id
                FROM
                    ReactionChannels
                WHERE
                    emoji = ?
                    AND guild_id = ?;
            """, channel.emoji, channel.guild.id)
            row = await res.fetchone();
            if row is not None:
                emoji, dest_id = row
                raise MiscellaneousError(
                    f"The emoji {emoji} is already set up in this server for channel <#{dest_id}>."
                )
    
    async def add_reaction_channel(self, channel: ReactionChannel):
        """Registers a reaction channel in the bot."""
        if len(channel.channel_list) > 25:
            raise MiscellaneousError("Too many channels are in the specified list.")
        await self.validate_channel(channel)
        async with self.conn.cursor() as cur:
            await cur.execute("""
                INSERT INTO ReactionChannels
                    (guild_id, destination_channel_id, threshold, emoji)
                    VALUES (?, ?, ?, ?);
            """, channel.guild.id, channel.destination_channel.id, channel.threshold, channel.emoji)

            channel_list = [None for _ in range(25)]
            for i, ch in enumerate(channel.channel_list):
                channel_list[i] = ch.id

            await cur.execute("""
                INSERT INTO ChannelLists
                    (
                        guild_id, emoji, is_whitelist,
                        channel_list_1, channel_list_2, channel_list_3, channel_list_4, channel_list_5,
                        channel_list_6, channel_list_7, channel_list_8, channel_list_9, channel_list_10,
                        channel_list_11, channel_list_12, channel_list_13, channel_list_14, channel_list_15,
                        channel_list_16, channel_list_17, channel_list_18, channel_list_19, channel_list_20,
                        channel_list_21, channel_list_22, channel_list_23, channel_list_24, channel_list_25
                    )
                    VALUES (
                        ?, ?, ?, 
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?
                    );
            """, channel.guild.id, channel.emoji, channel.is_whitelist, *channel_list)
            
    async def remove_guild(self, guild: discord.Guild):
        async with self.conn.cursor() as cur:
            await cur.execute("DELETE FROM ReactionChannels WHERE guild_id = ?", guild.id);

    async def already_sent_message(self, guild_id: int, emoji: str, message_id: int):
        async with self.conn.cursor() as cur:
            res = await cur.execute(
                "SELECT 1 FROM SentMessages WHERE guild_id = ? AND emoji = ? AND source_message_id = ?",
                guild_id, emoji, message_id
            );
            row = await res.fetchone()
            return row is not None

    async def has_reaction_channel_for_emoji(self, guild_id: int, emoji: str):
        async with self.conn.cursor() as cur:
            res = await cur.execute(
                "SELECT 1 FROM ReactionChannels WHERE guild_id = ? AND emoji = ?",
                guild_id, emoji
            );
            row = await res.fetchone()
            return row is not None

    async def maybe_get_destination(
        self,
        message: discord.Message, channel: discord.abc.GuildChannel, guild: discord.Guild,
        emoji: str, count: int
    ):
        async with self.conn.cursor() as cur:
            res = await cur.execute("""
                SELECT ReactionChannels.destination_channel_id FROM ReactionChannels
                WHERE
                    ReactionChannels.guild_id = :guildid AND 
                    ReactionChannels.emoji = :emoj AND
                    threshold <= :count AND (
                        (SELECT COUNT(1) FROM ChannelLists WHERE :channelid IN (
                            channel_list_1, channel_list_2, channel_list_3, channel_list_4, channel_list_5,
                            channel_list_6, channel_list_7, channel_list_8, channel_list_9, channel_list_10,
                            channel_list_11, channel_list_12, channel_list_13, channel_list_14, channel_list_15,
                            channel_list_16, channel_list_17, channel_list_18, channel_list_19, channel_list_20,
                            channel_list_21, channel_list_22, channel_list_23, channel_list_24, channel_list_25
                        ) AND ChannelLists.guild_id = :guildid AND ChannelLists.emoji = :emoj) = (
                            SELECT is_whitelist FROM ChannelLists WHERE ChannelLists.guild_id = :guildid AND ChannelLists.emoji = :emoj
                        )
                    )
            """, {"guildid": guild.id, "emoj": emoji, "count": count, "channelid": channel.id});
            row = await res.fetchone()
            if row is not None:
                return guild.get_channel(*row)

    async def try_remove_emoji(
        self, guild: discord.Guild, emoji: str
    ):
        if not await self.has_reaction_channel_for_emoji(guild.id, emoji):
            raise MiscellaneousError(f"Emoji `{emoji}` isn't set up for any channels.")
        async with self.conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM ReactionChannels WHERE guild_id = ? AND emoji = ?",
                guild.id, emoji
            );

    async def set_emoji_threshold(
        self, guild: discord.Guild, emoji: str, threshold: int
    ):
        if not await self.has_reaction_channel_for_emoji(guild.id, emoji):
            raise MiscellaneousError(f"Emoji `{emoji}` isn't set up for any channels.")
        async with self.conn.cursor() as cur:
            await cur.execute(
                "UPDATE ReactionChannels SET threshold = ? WHERE guild_id = ? AND emoji = ?",
                threshold, guild.id, emoji
            );


    async def mark_as_sent(
        self, 
        message: discord.Message, guild: discord.Guild,
        emoji: str, sent: discord.Message
    ):
        async with self.conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO SentMessages (guild_id, emoji, source_message_id, destination_message_id) VALUES (?, ?, ?, ?)",
                guild.id, emoji, message.id, sent.id
            );

    async def get_emojis_in_guild(
        self, guild: discord.Guild
    ):
        async with self.conn.cursor() as cur:
            res = await cur.execute(
                "SELECT emoji FROM ReactionChannels WHERE guild_id = ?",
                guild.id
            );
            rows = await cur.fetchall();
            return [row[0] for row in rows]

async def setup(bot: commands.Bot):
    bot.db = Database(config.database_path)
    await bot.db.connect()