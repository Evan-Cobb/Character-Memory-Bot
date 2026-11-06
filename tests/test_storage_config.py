import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bot_core.config import Settings
from bot_core.storage import Repository


class StorageTests(unittest.TestCase):
    def test_persistent_edit_at_maximum_sorted_tree_capacity(self):
        workspace = self.repo.get("1:2")
        for index in range(100):
            workspace.create(f"Name {index:03}", "Kind")
        self.repo.mutate("1:2", lambda w: w.remember("Name 099", "Still editable"))
        restored = Repository(self.path)
        restored.load()
        self.assertIn("Still editable", restored.get("1:2").info("Name 099"))

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "characters.json"
        self.repo = Repository(self.path)

    def test_absent_file_and_unicode_roundtrip(self):
        self.repo.load()
        self.repo.mutate("1:2", lambda w: w.create("Zoë", "Curious", "kind"))
        self.repo.mutate("1:2", lambda w: w.remember("Zoë", "Enjoys café visits"))
        restored = Repository(self.path)
        restored.load()
        self.assertIn("café", restored.get("1:2").info("ZOË"))

    def test_isolation_between_users_servers_and_dms(self):
        first = Repository.scope(1, 2)
        self.repo.get(first).create("Ada", "Kind")
        for scope in (Repository.scope(1, 3), Repository.scope(2, 2), Repository.scope(None, 2)):
            self.assertEqual(self.repo.get(scope).names(), [])
        with self.assertRaises(ValueError):
            self.repo.get("invalid")

    def test_corrupt_file_is_not_overwritten(self):
        self.repo.mutate("1:2", lambda w: w.create("Ada", "Kind"))
        with patch.object(Path, "read_text", return_value="{broken"):
            with self.assertRaises(ValueError):
                self.repo.load()
        self.assertEqual(self.repo.get("1:2").names(), ["Ada"])

    def test_bad_schema_rejected(self):
        for payload in (
            [],
            {"version": 99},
            {"version": 1, "workspaces": []},
            {"version": 1, "workspaces": {"bad": []}},
        ):
            with (
                patch.object(Path, "exists", return_value=True),
                patch.object(
                    Path,
                    "read_text",
                    return_value=json.dumps(payload),
                ),
                self.assertRaises(ValueError),
            ):
                self.repo.load()

    def test_disk_failure_rolls_back_memory_and_preserves_file(self):
        self.repo.mutate("1:2", lambda w: w.create("Ada", "Kind"))
        before = self.path.read_bytes()
        with patch("bot_core.storage.os.replace", side_effect=OSError("disk failure")):
            with self.assertRaises(OSError):
                self.repo.mutate("1:2", lambda w: w.remember("Ada", "Unsaved"))
        self.assertNotIn("Unsaved", self.repo.get("1:2").info("Ada"))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])

    def test_failed_first_save_leaves_no_new_workspace(self):
        with patch.object(self.repo, "save", side_effect=OSError("disk failure")):
            with self.assertRaises(OSError):
                self.repo.mutate("1:2", lambda w: w.create("Ada", "Kind"))
        self.assertEqual(self.repo.get("1:2").names(), [])

    def test_undo_persists_and_failed_undo_can_be_retried(self):
        self.repo.mutate("1:2", lambda w: w.create("Ada", "Kind"))
        self.repo.mutate("1:2", lambda w: w.remember("Ada", "A fact"))
        with patch.object(self.repo, "save", side_effect=OSError("disk failure")):
            with self.assertRaises(OSError):
                self.repo.mutate("1:2", lambda w: w.undo())
        self.assertIn("A fact", self.repo.get("1:2").info("Ada"))
        self.repo.mutate("1:2", lambda w: w.undo())
        restored = Repository(self.path)
        restored.load()
        self.assertNotIn("A fact", restored.get("1:2").info("Ada"))


class ConfigTests(unittest.TestCase):
    def test_no_token_or_placeholder_fails_without_echoing_token(self):
        for token in ("", "YOUR_DISCORD_BOT_TOKEN"):
            with patch.dict(os.environ, {"DISCORD_TOKEN": token}, clear=True):
                with self.assertRaisesRegex(ValueError, "Set DISCORD_TOKEN"):
                    Settings.from_environment(Path("."))

    def test_optional_and_numeric_guild_and_relative_path(self):
        for guild in ("", "123"):
            with patch.dict(
                os.environ, {"DISCORD_TOKEN": "not-real", "DISCORD_GUILD_ID": guild}, clear=True
            ):
                settings = Settings.from_environment(Path("base"))
                self.assertEqual(settings.guild_id, int(guild) if guild else None)
                self.assertEqual(settings.data_path, Path("base/data/characters.json"))

    def test_invalid_guild_and_empty_path(self):
        for updates in (
            {"DISCORD_GUILD_ID": "abc"},
            {"DISCORD_GUILD_ID": "0"},
            {"DISCORD_GUILD_ID": "-1"},
            {"BOT_DATA_PATH": " "},
        ):
            with patch.dict(os.environ, {"DISCORD_TOKEN": "not-real"} | updates, clear=True):
                with self.assertRaises(ValueError):
                    Settings.from_environment(Path("."))
