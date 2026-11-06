import unittest

from bot_core.characters import MAX_CHARACTERS, MAX_MEMORIES, MAX_QUEUE, MAX_UNDO, Workspace


class CharacterTests(unittest.TestCase):
    def test_unicode_tags_roundtrip_and_normalized_limits(self):
        valid = Workspace()
        valid.create("Zoë", "Kind", "ß" * 15)
        self.assertEqual(Workspace.from_data(valid.to_data()).to_data(), valid.to_data())
        with self.assertRaises(ValueError):
            Workspace().create("Bad tag", "Kind", "ß" * 16)
        combined = ",".join("ß" * 14 + f"{i:02}" for i in range(10))
        with self.assertRaises(ValueError):
            Workspace().create("Bad combined length", "Kind", combined)

    def setUp(self):
        self.workspace = Workspace()
        self.workspace.create("Ada", "Curious", "science, SCIENCE, kind")

    def test_normalized_lookup_and_tag_deduplication(self):
        info = self.workspace.info(" ADA ")
        self.assertIn("Ada", info)
        self.assertIn("Tags: kind, science", info)
        self.assertEqual(self.workspace.names(" SCIENCE "), ["Ada"])
        self.assertEqual(self.workspace.names("unknown"), [])

    def test_tree_alphabetical_browse(self):
        self.workspace.create("Zoe", "Bold")
        self.workspace.create("Bea", "Calm")
        self.assertEqual(self.workspace.names(), ["Ada", "Bea", "Zoe"])

    def test_duplicate_rejected_without_mutation(self):
        before = self.workspace.to_data()
        with self.assertRaises(ValueError):
            self.workspace.create("ada", "Different")
        self.assertEqual(self.workspace.to_data(), before)

    def test_invalid_character_fields(self):
        for args in (
            ("", "kind"),
            ("x" * 81, "kind"),
            ("Name", ""),
            ("Name", "p" * 301),
            ("Name", "kind", "t" * 31),
            ("Name", "kind", ",".join(str(i) for i in range(11))),
        ):
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.workspace.create(*args)
        self.assertEqual(self.workspace.names(), ["Ada"])

    def test_boundary_character_lengths(self):
        name = "n" * 80
        self.workspace.create(name, "p" * 300, "t" * 30)
        self.assertIn(name, self.workspace.names())

    def test_character_capacity(self):
        for index in range(MAX_CHARACTERS - 1):
            self.workspace.create(f"Name {index}", "Kind")
        with self.assertRaises(ValueError):
            self.workspace.create("Overflow", "Kind")

    def test_undo_is_lifo_across_characters(self):
        self.workspace.create("Bea", "Calm")
        self.workspace.remember("Ada", "First")
        self.workspace.remember("Bea", "Second")
        self.assertIn("Bea", self.workspace.undo())
        self.assertIn("Ada", self.workspace.undo())
        self.assertIn("None yet.", self.workspace.info("Ada"))
        with self.assertRaises(ValueError):
            self.workspace.undo()

    def test_memory_validation_and_capacity(self):
        for value in ("", " " * 2, "m" * 251):
            with self.assertRaises(ValueError):
                self.workspace.remember("Ada", value)
        for i in range(MAX_MEMORIES):
            self.workspace.remember("Ada", str(i))
        with self.assertRaises(ValueError):
            self.workspace.remember("Ada", "Overflow")

    def test_undo_history_is_bounded(self):
        self.workspace.create("Bea", "Calm")
        for i in range(MAX_MEMORIES):
            self.workspace.remember("Ada", str(i))
        self.workspace.remember("Bea", "Newest")
        for _ in range(MAX_UNDO):
            self.workspace.undo()
        with self.assertRaises(ValueError):
            self.workspace.undo()
        self.assertEqual(self.workspace.to_data()[0]["memories"], ["0"])

    def test_queued_memories_are_applied_fifo(self):
        self.workspace.enqueue("Ada", "First fact")
        self.workspace.enqueue("Ada", "Second fact")
        first = self.workspace.process_next()
        self.assertIn("First fact", first)
        self.assertIn("First fact", self.workspace.info("Ada"))
        self.assertNotIn("Second fact", self.workspace.info("Ada"))
        self.assertIn("Second fact", self.workspace.process_next())
        self.assertEqual(self.workspace.queue_size, 0)
        with self.assertRaises(ValueError):
            self.workspace.process_next()
        self.workspace.enqueue("Ada", "Reusable")
        self.assertIn("Reusable", self.workspace.process_next())

    def test_queue_validation_and_capacity(self):
        for name, prompt in (("Missing", "hello"), ("Ada", ""), ("Ada", "p" * 251)):
            with self.assertRaises(ValueError):
                self.workspace.enqueue(name, prompt)
        for i in range(MAX_QUEUE):
            self.workspace.enqueue("Ada", str(i))
        with self.assertRaises(ValueError):
            self.workspace.enqueue("Ada", "Overflow")

    def test_saved_roundtrip_excludes_session_state(self):
        self.workspace.remember("Ada", "Likes books")
        self.workspace.enqueue("Ada", "Hello")
        restored = Workspace.from_data(self.workspace.to_data())
        self.assertEqual(restored.to_data(), self.workspace.to_data())
        self.assertEqual(restored.queue_size, 0)
        with self.assertRaises(ValueError):
            restored.undo()

    def test_malformed_saved_records(self):
        valid = self.workspace.to_data()[0]
        for changes in (
            {"memories": "bad"},
            {"tags": [None]},
            {"name": 1},
            {"tags": ["bad,tag"]},
            {"memories": [None]},
            {"extra": "field"},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                Workspace.from_data([valid | changes])
        with self.assertRaises(ValueError):
            Workspace.from_data([valid, valid])

    def test_full_character_keeps_queued_memory_until_it_can_be_applied(self):
        for index in range(MAX_MEMORIES):
            self.workspace.remember("Ada", str(index))
        self.workspace.enqueue("Ada", "Pending fact")
        with self.assertRaises(ValueError):
            self.workspace.process_next()
        self.assertEqual(self.workspace.queue_size, 1)
        self.workspace.undo()
        self.workspace.process_next()
        self.assertEqual(self.workspace.queue_size, 0)
        self.assertIn("Pending fact", self.workspace.info("Ada"))

    def test_discard_unblocks_full_saved_character_without_losing_other_work(self):
        for index in range(MAX_MEMORIES):
            self.workspace.remember("Ada", str(index))
        workspace = Workspace.from_data(self.workspace.to_data())
        workspace.create("Bea", "Kind")
        workspace.enqueue("Ada", "Blocked fact")
        workspace.enqueue("Bea", "Keep this fact")
        with self.assertRaisesRegex(ValueError, "discard:true"):
            workspace.process_next()
        self.assertEqual(workspace.queue_size, 2)
        with self.assertRaises(ValueError):
            workspace.undo()
        self.assertIn("Blocked fact", workspace.discard_next())
        self.assertEqual(workspace.queue_size, 1)
        workspace.process_next()
        self.assertIn("Keep this fact", workspace.info("Bea"))
        self.assertEqual(workspace.queue_size, 0)
        with self.assertRaises(ValueError):
            workspace.discard_next()
