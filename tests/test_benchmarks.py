import random
import unittest
from collections import deque

from benchmarks.compare import QUEUE_TYPES, queue_trial


class QueueContractTests(unittest.TestCase):
    def test_same_fifo_contract_for_all_three_implementations(self):
        for kind in QUEUE_TYPES:
            with self.subTest(kind=kind):
                queue, reference = kind(), deque()
                rng = random.Random(212)
                for _ in range(500):
                    if not reference or rng.random() < 0.55:
                        value = rng.randrange(1000)
                        queue.enqueue(value)
                        reference.append(value)
                    else:
                        self.assertEqual(queue.dequeue(), reference.popleft())
                while reference:
                    self.assertEqual(queue.dequeue(), reference.popleft())
                with self.assertRaises(IndexError):
                    queue.dequeue()
                queue.enqueue("reused")
                self.assertEqual(queue.dequeue(), "reused")

    def test_benchmark_workloads_have_equal_results(self):
        for kind in QUEUE_TYPES:
            for size in (0, 1, 100):
                with self.subTest(kind=kind, size=size):
                    self.assertEqual(queue_trial(kind, size), size * (size - 1) // 2)
