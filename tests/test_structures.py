import random
import unittest
from collections import deque

from bot_core.structures import LinkedQueue, NameTree


class QueueTests(unittest.TestCase):
    def test_empty_queue(self):
        queue = LinkedQueue()
        self.assertEqual(len(queue), 0)
        self.assertEqual(list(queue), [])
        for method in (queue.peek, queue.dequeue):
            with self.assertRaises(IndexError):
                method()

    def test_fifo_and_reuse_after_last_item(self):
        queue = LinkedQueue()
        for i in range(10):
            queue.enqueue(i)
        self.assertEqual(queue.peek(), 0)
        self.assertEqual([queue.dequeue() for _ in range(10)], list(range(10)))
        queue.enqueue("new")
        self.assertEqual(queue.dequeue(), "new")
        self.assertEqual(len(queue), 0)

    def test_randomized_against_standard_deque(self):
        rng = random.Random(212)
        queue, reference = LinkedQueue(), deque()
        for _ in range(2000):
            if not reference or rng.random() < 0.6:
                value = rng.randrange(100)
                queue.enqueue(value)
                reference.append(value)
            else:
                self.assertEqual(queue.dequeue(), reference.popleft())
            self.assertEqual(len(queue), len(reference))
            self.assertEqual(list(queue), list(reference))

    def test_remove_if_preserves_remaining_fifo_items(self):
        queue = LinkedQueue()
        for value in ("keep", "remove", "keep", "remove"):
            queue.enqueue(value)
        self.assertEqual(queue.remove_if(lambda value: value == "remove"), 2)
        self.assertEqual(list(queue), ["keep", "keep"])
        self.assertEqual(queue.dequeue(), "keep")
        self.assertEqual(queue.dequeue(), "keep")


class TreeTests(unittest.TestCase):
    def test_empty(self):
        tree = NameTree()
        self.assertEqual(list(tree), [])
        self.assertEqual(tree.height(), 0)
        self.assertNotIn("missing", tree)

    def test_order_duplicates_and_search(self):
        tree = NameTree()
        for name in ("m", "c", "z", "a", "e"):
            self.assertTrue(tree.insert(name))
        self.assertFalse(tree.insert("c"))
        self.assertEqual(len(tree), 5)
        self.assertEqual(list(tree), ["a", "c", "e", "m", "z"])
        self.assertIn("e", tree)
        self.assertNotIn("d", tree)
        self.assertEqual(tree.height(), 3)

    def test_degenerate_tree_beyond_recursion_limit(self):
        tree = NameTree()
        expected = [f"{i:05}" for i in range(1100)]
        for key in expected:
            tree.insert(key)
        self.assertEqual(list(tree), expected)
        self.assertEqual(tree.height(), len(expected))

    def test_randomized_against_sorted_set(self):
        rng = random.Random(212)
        names = [str(rng.randrange(1000)) for _ in range(500)]
        tree = NameTree()
        for name in names:
            tree.insert(name)
        self.assertEqual(list(tree), sorted(set(names)))
        self.assertEqual(len(tree), len(set(names)))

    def test_delete_leaf_one_child_two_children_and_missing(self):
        tree = NameTree()
        for name in ("m", "c", "z", "a", "e", "d", "f"):
            tree.insert(name)
        self.assertTrue(tree.delete("a"))
        self.assertTrue(tree.delete("e"))
        self.assertTrue(tree.delete("m"))
        self.assertFalse(tree.delete("missing"))
        self.assertEqual(list(tree), ["c", "d", "f", "z"])
        self.assertEqual(len(tree), 4)
