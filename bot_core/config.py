"""Configuration validation; never logs token values."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    token: str
    guild_id: int | None
    data_path: Path

    @classmethod
    def from_environment(cls, base: Path) -> "Settings":
        token = os.getenv("DISCORD_TOKEN", "").strip()
        if not token or token == "YOUR_DISCORD_BOT_TOKEN":
            raise ValueError("Set DISCORD_TOKEN in .env before starting the bot.")
        raw_guild = os.getenv("DISCORD_GUILD_ID", "").strip()
        if raw_guild and (
            not raw_guild.isascii() or not raw_guild.isdecimal() or int(raw_guild) <= 0
        ):
            raise ValueError("DISCORD_GUILD_ID must be a positive numeric server ID.")
        raw_path = os.getenv("BOT_DATA_PATH", "data/characters.json").strip()
        if not raw_path:
            raise ValueError("BOT_DATA_PATH must not be blank.")
        path = Path(raw_path)
        return cls(
            token,
            int(raw_guild) if raw_guild else None,
            path if path.is_absolute() else base / path,
        )
