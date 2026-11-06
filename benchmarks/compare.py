"""Run with: python -m benchmarks.compare --sizes 1000 5000 10000 --repeats 5."""

import argparse
import platform
import random
import statistics
from collections import deque
from time import perf_counter_ns

from bot_core.structures import LinkedQueue, NameTree


class ArrayQueue:
    """Deliberately inefficient baseline: each pop(0) shifts remaining elements."""

    def __init__(self):
        self.items = []

    def enqueue(self, value):
        self.items.append(value)

    def dequeue(self):
        return self.items.pop(0)


class DequeQueue:
    def __init__(self):
        self.items = deque()

    def enqueue(self, value):
        self.items.append(value)

    def dequeue(self):
        return self.items.popleft()


QUEUE_TYPES = (ArrayQueue, DequeQueue, LinkedQueue)


def queue_trial(queue_type, size):
    queue = queue_type()
    for value in range(size):
        queue.enqueue(value)
    checksum = 0
    for _ in range(size):
        checksum += queue.dequeue()
    return checksum


def queue_measurement(queue_type, size, repeats):
    expected = size * (size - 1) // 2
    assert queue_trial(queue_type, size) == expected  # warmup, outside timing
    samples = []
    for _ in range(repeats):
        started = perf_counter_ns()
        checksum = queue_trial(queue_type, size)
        samples.append((perf_counter_ns() - started) / 1_000_000)
        assert checksum == expected
    return statistics.median(samples)


def tree_measurement(size, shuffled, repeats):
    keys = [f"{index:08}" for index in range(size)]
    if shuffled:
        random.Random(212).shuffle(keys)
    samples = []
    height = 0
    for _ in range(repeats):
        tree = NameTree()
        started = perf_counter_ns()
        for key in keys:
            tree.insert(key)
        samples.append((perf_counter_ns() - started) / 1_000_000)
        assert list(tree) == sorted(keys)
        height = tree.height()
    return statistics.median(samples), height


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", type=int, nargs="+", default=[1000, 5000, 10000])
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    if args.repeats < 1 or any(size < 1 for size in args.sizes):
        parser.error("Sizes and repeats must be positive.")
    print(f"Python {platform.python_version()} | {platform.platform()} | median of {args.repeats}")
    print("\nFIFO workload: construct, enqueue n, dequeue n (milliseconds)")
    print("| n | Array pop(0) | collections.deque | Custom linked queue |")
    print("|---:|---:|---:|---:|")
    for size in args.sizes:
        results = [queue_measurement(kind, size, args.repeats) for kind in QUEUE_TYPES]
        print(f"| {size} | " + " | ".join(f"{value:.3f}" for value in results) + " |")
    print("\nUnbalanced BST construction (milliseconds); fixed-width keys, seeded shuffle")
    print("| n | Sorted input | Height | Shuffled input | Height |")
    print("|---:|---:|---:|---:|---:|")
    for size in (250, 500, 1000):
        ordered, ordered_height = tree_measurement(size, False, args.repeats)
        shuffled, shuffled_height = tree_measurement(size, True, args.repeats)
        print(f"| {size} | {ordered:.3f} | {ordered_height} | {shuffled:.3f} | {shuffled_height} |")
    print("\nTimings illustrate this environment; they do not prove asymptotic complexity.")


if __name__ == "__main__":
    main()
