"""Unified discord.py application. Importing this module never connects to Discord."""

import argparse
import asyncio
import logging
from pathlib import Path
from tempfile import TemporaryDirectory

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from bot_core.config import Settings
from bot_core.storage import PersistenceError, Repository

BASE = Path(__file__).resolve().parent
LOG = logging.getLogger(__name__)
HELP = (
    "Commands (also available with !):\n"
    "/create_character name personality tags - create; tags are comma-separated\n"
    "/delete_character name - permanently delete one of your characters\n"
    "/character_info name - personality, tags, and latest memories\n"
    "/characters tag - alphabetical names, optionally filtered by tag\n"
    "/remember name fact - add a memory\n/undo - undo your latest memory addition\n"
    "/enqueue name fact - queue a memory addition\n/next - save the oldest queued memory\n"
    "/next discard:true (or !next true) - discard the oldest queued addition\n"
    "Each user has separate data in each server. Slash character replies are private; "
    "prefix-command replies are visible in the channel. For ! commands, quote multiword arguments."
)


async def send_text(ctx: commands.Context, message: str) -> None:
    """Stay below Discord's message limit, including long lists of names."""
    # Ephemeral messages only apply to interactions (slash commands). Prefix
    # commands use ordinary channel messages, so do not pass the flag there.
    private = ctx.interaction is not None
    for offset in range(0, len(message), 1900):
        await ctx.send(message[offset : offset + 1900], ephemeral=private)


class CharacterCommands(commands.Cog):
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def scope(self, ctx: commands.Context) -> str:
        return self.repository.scope(ctx.guild.id if ctx.guild else None, ctx.author.id)

    @commands.hybrid_command(name="help", description="Show commands and data behavior.")
    async def help_command(self, ctx: commands.Context) -> None:
        await send_text(ctx, HELP)

    @commands.hybrid_command(name="create_character", description="Create your own character.")
    async def create_character(
        self,
        ctx: commands.Context,
        name: str,
        personality: str,
        tags: str = "",
    ) -> None:
        await ctx.defer(ephemeral=True)
        result = self.repository.mutate(
            self.scope(ctx), lambda w: w.create(name, personality, tags)
        )
        await send_text(ctx, result)

    @commands.hybrid_command(name="delete_character", description="Delete one of your characters.")
    async def delete_character(self, ctx: commands.Context, name: str) -> None:
        await ctx.defer(ephemeral=True)
        result = self.repository.mutate(self.scope(ctx), lambda w: w.delete(name))
        await send_text(ctx, result)

    @commands.hybrid_command(name="character_info", description="Show one of your characters.")
    async def character_info(self, ctx: commands.Context, name: str) -> None:
        await send_text(ctx, self.repository.get(self.scope(ctx)).info(name))

    @commands.hybrid_command(
        name="characters", description="Browse your characters alphabetically."
    )
    async def characters(self, ctx: commands.Context, tag: str = "") -> None:
        names = self.repository.get(self.scope(ctx)).names(tag)
        await send_text(ctx, "\n".join(names) if names else "No matching characters.")

    @commands.hybrid_command(name="remember", description="Add a memory to your character.")
    async def remember(self, ctx: commands.Context, name: str, fact: str) -> None:
        await ctx.defer(ephemeral=True)
        result = self.repository.mutate(self.scope(ctx), lambda w: w.remember(name, fact))
        await send_text(ctx, result)

    @commands.hybrid_command(
        name="undo", description="Undo your last memory addition this session."
    )
    async def undo(self, ctx: commands.Context) -> None:
        await ctx.defer(ephemeral=True)
        result = self.repository.mutate(self.scope(ctx), lambda w: w.undo())
        await send_text(ctx, result)

    @commands.hybrid_command(name="enqueue", description="Queue a memory addition for later.")
    async def enqueue(self, ctx: commands.Context, name: str, fact: str) -> None:
        await send_text(ctx, self.repository.get(self.scope(ctx)).enqueue(name, fact))

    @commands.hybrid_command(name="next", description="Save the oldest queued memory.")
    async def next_command(self, ctx: commands.Context, discard: bool = False) -> None:
        if discard:
            await send_text(ctx, self.repository.get(self.scope(ctx)).discard_next())
            return
        await ctx.defer(ephemeral=True)
        result = self.repository.mutate(self.scope(ctx), lambda w: w.process_next())
        await send_text(ctx, result)


def error_message(error: Exception) -> str:
    original = error
    while isinstance(
        original,
        (
            commands.CommandInvokeError,
            commands.HybridCommandError,
            app_commands.CommandInvokeError,
        ),
    ):
        original = original.original
    if isinstance(original, (ValueError, commands.UserInputError)):
        return str(original)
    if isinstance(original, commands.CommandNotFound):
        return "Unknown command. Use /help or !help."
    if isinstance(original, PersistenceError):
        return "Could not save your change. It was rolled back; please contact the bot owner."
    if isinstance(original, OSError):
        return "Could not complete the reply. A change may already be saved; check /character_info before retrying."
    LOG.error("Command failed (%s)", type(original).__name__)
    return "The command failed. Please contact the bot owner."


class CharacterBot(commands.Bot):
    def __init__(self, settings: Settings) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
            allowed_mentions=discord.AllowedMentions.none(),
            case_insensitive=True,
        )
        self.settings = settings
        self.repository = Repository(settings.data_path)
        self.repository.load()
        self.tree.on_error = self.on_app_command_error

    async def load_commands(self) -> None:
        await self.add_cog(CharacterCommands(self.repository))

    async def setup_hook(self) -> None:
        await self.load_commands()
        if self.settings.guild_id:
            guild = discord.Object(id=self.settings.guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
        else:
            synced = await self.tree.sync()
        LOG.info("Registered %d slash commands", len(synced))

    async def on_ready(self) -> None:
        LOG.info("Connected as %s", self.user)

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        await send_text(ctx, error_message(error))

    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        message = error_message(error)
        if interaction.response.is_done():
            await interaction.followup.send(message[:1900], ephemeral=True)
        else:
            await interaction.response.send_message(message[:1900], ephemeral=True)


async def offline_check() -> None:
    # Temporary storage means this check never changes the user's saved characters.
    with TemporaryDirectory(prefix="cse212-bot-check-") as directory:
        path = Path(directory) / "characters.json"
        settings = Settings("offline-check-only", None, path)
        async with CharacterBot(settings) as bot:
            await bot.load_commands()
            names = sorted(command.name for command in bot.tree.get_commands())
            print(
                f"PASS: {len(names)} slash/prefix commands registered locally: {', '.join(names)}"
            )
            repo = bot.repository
            scope = repo.scope(1, 2)
            repo.mutate(scope, lambda w: w.create("Bea", "Kind", "science"))
            repo.mutate(scope, lambda w: w.create("Ada", "Curious", "SCIENCE,science"))
            workspace = repo.get(scope)
            assert workspace.names("science") == ["Ada", "Bea"]
            workspace.enqueue("Ada", "First memory")
            workspace.enqueue("Ada", "Second memory")
            repo.mutate(scope, lambda w: w.process_next())
            assert "First memory" in repo.get(scope).info("Ada")
            assert "Second memory" not in repo.get(scope).info("Ada")
            repo.mutate(scope, lambda w: w.undo())
            assert "First memory" not in repo.get(scope).info("Ada")
            repo.mutate(scope, lambda w: w.process_next())
            restored = Repository(path)
            restored.load()
            assert "Second memory" in restored.get(scope).info("Ada")
            assert restored.get("1:3").names() == []
            print("PASS: create, tag filtering, BST order, FIFO, undo, isolation, save/reload.")
            print("No Discord connection, command sync, or changes to your data were attempted.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Check imports and registration offline."
    )
    args = parser.parse_args()
    load_dotenv(BASE / ".env", override=False)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        if args.check:
            asyncio.run(offline_check())
            return
        settings = Settings.from_environment(BASE)
        bot = CharacterBot(settings)
        bot.run(settings.token)
    except (ValueError, OSError) as exc:
        raise SystemExit(f"Startup failed: {exc}") from exc
    except discord.LoginFailure as exc:
        raise SystemExit("Discord rejected DISCORD_TOKEN. Check the bot's .env file.") from exc
    except discord.PrivilegedIntentsRequired as exc:
        raise SystemExit("Enable Message Content Intent in the Discord Developer Portal.") from exc
    except (discord.Forbidden, discord.NotFound) as exc:
        raise SystemExit(
            "Check DISCORD_GUILD_ID and invite the bot to that server with bot and applications.commands scopes."
        ) from exc


if __name__ == "__main__":
    main()
