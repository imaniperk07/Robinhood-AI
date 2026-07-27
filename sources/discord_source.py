import os
from datetime import timezone
from typing import Awaitable, Callable

import discord
from dotenv import load_dotenv

from sources.base_source import BaseSource, SourceItem

load_dotenv()


class DiscordSource(BaseSource):
    """Listens to a Discord server via a real bot (added by the server's admin through
    Discord's Developer Portal) and normalizes every message into a SourceItem. Contains
    no ticker-detection or analysis logic of its own — that's Athena's job downstream."""

    name = "discord"

    def __init__(self):
        self.bot_token = os.environ.get("DISCORD_BOT_TOKEN")
        channel_ids = os.environ.get("DISCORD_LISTEN_CHANNEL_IDS", "")
        self.channel_ids = {int(c) for c in channel_ids.split(",") if c.strip()}

    async def run(self, on_item: Callable[[SourceItem], Awaitable[None]]) -> None:
        if not self.bot_token:
            raise SystemExit("DISCORD_BOT_TOKEN not set in .env — see setup instructions.")

        intents = discord.Intents.default()
        intents.message_content = True  # privileged intent — must be enabled in the Dev Portal
        client = discord.Client(intents=intents)

        @client.event
        async def on_ready():
            print(f"[discord] Logged in as {client.user}. Watching channels: {self.channel_ids or 'ALL'}")

        @client.event
        async def on_message(message: discord.Message):
            if message.author.bot:
                return
            if self.channel_ids and message.channel.id not in self.channel_ids:
                return

            item = SourceItem(
                source=self.name,
                author=str(message.author),
                content=message.content,
                url=message.jump_url,
                timestamp=message.created_at.astimezone(timezone.utc).isoformat(),
                metadata={"channel_id": str(message.channel.id), "message_id": str(message.id)},
            )
            await on_item(item)

        await client.start(self.bot_token)
