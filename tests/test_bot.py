import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import discord
from discord import app_commands
from discord.ext import commands

from bot import CharacterBot, error_message, offline_check, send_text
from bot_core.config import Settings
from bot_core.storage import PersistenceError


class BotTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.settings = Settings(
            "offline-not-a-token", 123, Path(self.directory.name) / "data.json"
        )
        self.bot = CharacterBot(self.settings)
        await self.bot.__aenter__()
        await self.bot.load_commands()

    async def asyncTearDown(self):
        await self.bot.close()
        self.directory.cleanup()

    def context(self, user=2, guild=1):
        return SimpleNamespace(
            author=SimpleNamespace(id=user),
            guild=SimpleNamespace(id=guild) if guild else None,
            interaction=None,
            send=AsyncMock(),
            defer=AsyncMock(),
        )

    async def invoke(self, name, ctx, *args):
        command = self.bot.get_command(name)
        await command.callback(command.cog, ctx, *args)

    async def test_all_commands_registered_without_network(self):
        expected = {
            "help",
            "create_character",
            "character_info",
            "characters",
            "remember",
            "undo",
            "enqueue",
            "next",
        }
        self.assertEqual({c.name for c in self.bot.tree.get_commands()}, expected)
        self.assertEqual({c.name for c in self.bot.commands}, expected)
        discard = self.bot.tree.get_command("next").get_parameter("discard")
        self.assertEqual(discard.type, discord.AppCommandOptionType.boolean)
        self.assertFalse(discard.required)
        self.assertIs(discard.default, False)
        self.assertTrue(self.bot.intents.message_content)
        self.assertEqual(
            self.bot.allowed_mentions.to_dict(), discord.AllowedMentions.none().to_dict()
        )

    async def test_character_workflow_uses_storage_and_queue(self):
        ctx = self.context()
        await self.invoke("create_character", ctx, "Ada", "Curious", "kind")
        await self.invoke("remember", ctx, "Ada", "Likes books")
        await self.invoke("enqueue", ctx, "Ada", "Likes puzzles")
        await self.invoke("next", ctx)
        self.assertIn("Likes puzzles", ctx.send.call_args.args[0])
        await self.invoke("undo", ctx)
        await self.invoke("character_info", ctx, "Ada")
        self.assertNotIn("Likes puzzles", ctx.send.call_args.args[0])
        self.assertIn("Likes books", ctx.send.call_args.args[0])
        self.assertTrue(self.settings.data_path.exists())

    async def test_handler_enforces_user_and_server_isolation(self):
        await self.invoke("create_character", self.context(), "Ada", "Curious")
        for ctx in (self.context(user=3), self.context(guild=2), self.context(guild=None)):
            with self.assertRaises(ValueError):
                await self.invoke("character_info", ctx, "Ada")

    async def test_long_responses_paginate_without_loss(self):
        ctx = self.context()
        value = "x" * 5000
        await send_text(ctx, value)
        self.assertEqual("".join(c.args[0] for c in ctx.send.call_args_list), value)
        self.assertTrue(all(len(c.args[0]) <= 1900 for c in ctx.send.call_args_list))
        self.assertTrue(all(not c.kwargs["ephemeral"] for c in ctx.send.call_args_list))

    async def test_interaction_responses_are_private(self):
        ctx = self.context()
        ctx.interaction = object()
        await send_text(ctx, "Private response")
        ctx.send.assert_awaited_once_with("Private response", ephemeral=True)

    async def test_prefix_error_is_actionable(self):
        ctx = self.context()
        await self.bot.on_command_error(
            ctx, commands.CommandInvokeError(ValueError("Invalid memory"))
        )
        ctx.send.assert_awaited_once_with("Invalid memory", ephemeral=False)
        self.assertIn("Unknown", error_message(commands.CommandNotFound("bad")))

    async def test_save_failure_is_reported_as_rolled_back(self):
        self.assertIn(
            "rolled back", error_message(commands.CommandInvokeError(PersistenceError("failure")))
        )

    async def test_sync_targets_test_guild_once_in_setup(self):
        with (
            patch.object(self.bot, "load_commands", new=AsyncMock()),
            patch.object(
                self.bot.tree,
                "sync",
                new=AsyncMock(return_value=[]),
            ) as sync,
        ):
            await self.bot.setup_hook()
            self.assertEqual(sync.await_count, 1)
            self.assertEqual(sync.call_args.kwargs["guild"].id, 123)

    async def test_hybrid_error_unwraps_all_real_library_layers(self):
        command = self.bot.tree.get_command("remember")
        wrapped = commands.HybridCommandError(
            app_commands.CommandInvokeError(command, ValueError("Invalid memory"))
        )
        self.assertEqual(error_message(wrapped), "Invalid memory")

    async def test_failed_reply_does_not_claim_committed_change_was_rolled_back(self):
        ctx = self.context()
        ctx.send.side_effect = OSError("reply transport failed")
        with self.assertRaises(OSError) as caught:
            await self.invoke("create_character", ctx, "Ada", "Curious")
        self.assertEqual(self.bot.repository.get("1:2").names(), ["Ada"])
        self.assertNotIn("rolled back", error_message(caught.exception))

    async def test_app_errors_use_initial_or_followup_response(self):
        command = self.bot.tree.get_command("remember")
        error = app_commands.CommandInvokeError(command, ValueError("Invalid memory"))
        for acknowledged in (False, True):
            interaction = SimpleNamespace(
                response=SimpleNamespace(
                    is_done=lambda: acknowledged,
                    send_message=AsyncMock(),
                ),
                followup=SimpleNamespace(send=AsyncMock()),
            )
            await self.bot.on_app_command_error(interaction, error)
            sender = (
                interaction.followup.send if acknowledged else interaction.response.send_message
            )
            sender.assert_awaited_once_with("Invalid memory", ephemeral=True)

    async def test_offline_check_exercises_data_structures_and_persistence(self):
        with patch("builtins.print") as output:
            await offline_check()
        messages = " ".join(str(call.args[0]) for call in output.call_args_list)
        self.assertIn("8 slash/prefix commands", messages)
        self.assertIn("save/reload", messages)

    async def test_failed_queue_save_preserves_pending_memory_for_retry(self):
        ctx = self.context()
        await self.invoke("create_character", ctx, "Ada", "Curious")
        await self.invoke("enqueue", ctx, "Ada", "Queued fact")
        with patch.object(self.bot.repository, "save", side_effect=OSError("disk failure")):
            with self.assertRaises(PersistenceError):
                await self.invoke("next", ctx)
        workspace = self.bot.repository.get("1:2")
        self.assertEqual(workspace.queue_size, 1)
        self.assertNotIn("Queued fact", workspace.info("Ada"))
        await self.invoke("next", ctx)
        self.assertEqual(self.bot.repository.get("1:2").queue_size, 0)
        self.assertIn("Queued fact", self.bot.repository.get("1:2").info("Ada"))

    async def test_global_sync_branch(self):
        settings = Settings("offline-only", None, self.settings.data_path)
        async with CharacterBot(settings) as bot:
            with patch.object(bot.tree, "sync", new=AsyncMock(return_value=[])) as sync:
                await bot.setup_hook()
                sync.assert_awaited_once_with()

    async def test_documented_prefix_commands_use_real_argument_parser(self):
        self.bot._connection.user = SimpleNamespace(id=999)
        examples = (
            '!create_character "Ada Lovelace" "Curious and thoughtful" "science,kind"',
            '!enqueue "Ada Lovelace" "First queued fact"',
            "!next",
            '!remember "Ada Lovelace" "Second direct fact"',
            "!undo",
            '!enqueue "Ada Lovelace" "Discard this fact"',
            "!next true",
            '!character_info "Ada Lovelace"',
        )
        with (
            patch.object(commands.Context, "send", new=AsyncMock()) as send,
            patch.object(commands.Context, "defer", new=AsyncMock()),
        ):
            for example in examples:
                message = SimpleNamespace(
                    content=example,
                    author=SimpleNamespace(id=2),
                    guild=SimpleNamespace(id=1),
                    channel=SimpleNamespace(id=10),
                    _state=self.bot._connection,
                    attachments=[],
                    id=123,
                )
                ctx = await self.bot.get_context(message)
                self.assertTrue(ctx.valid, example)
                await ctx.command.invoke(ctx)
            self.assertIn("First queued fact", send.call_args.args[0])
            self.assertNotIn("Second direct fact", send.call_args.args[0])
            self.assertNotIn("Discard this fact", send.call_args.args[0])
