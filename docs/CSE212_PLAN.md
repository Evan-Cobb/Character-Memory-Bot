# Why This Project Demonstrates CSE212 Learning

## Project explanation

I built this project as a Discord bot that lets each user create and delete characters, organize them with tags, add memories, undo recent changes, and process queued memory additions in order. The Discord commands are only the user interface. The main purpose of the project is the data management underneath the interface.

The project is organized so that the Discord code, application rules, data structures, and file storage have separate responsibilities. The command code in [`bot.py`](../bot.py) receives user input and displays results. The application behavior is in [`bot_core/characters.py`](../bot_core/characters.py), the custom structures are in [`bot_core/structures.py`](../bot_core/structures.py), and persistence is in [`bot_core/storage.py`](../bot_core/storage.py). This separation makes the algorithms easier to reason about and test without connecting to Discord.

## Data-structure choices

The character manager uses several structures because each one solves a different problem.

The dictionary maps a normalized character name to its character object. This makes direct lookup efficient and prevents two names that differ only in capitalization from becoming separate characters.

The set stores tags. A set is appropriate because a tag should only appear once, even if the user enters it more than once. Set membership also makes tag filtering straightforward.

The list stores memories in the order they were added. A list is a natural choice for chronological data because new memories are appended and the character displays its most recent memories.

The undo history uses a bounded deque as a stack. Undo must remove the most recent change first, so it follows last-in, first-out behavior. The bound prevents an unlimited amount of session history from accumulating.

Pending memory additions use the custom [`LinkedQueue`](../bot_core/structures.py). A queue follows first-in, first-out behavior: the oldest request is processed first. The queue keeps both a head and a tail pointer, so adding to the back and removing from the front are constant-time operations. I implemented this structure directly so the node links, empty-state rules, and endpoint behavior are visible rather than hidden behind a library abstraction.

Character names are also stored in the custom [`NameTree`](../bot_core/structures.py). Its in-order traversal produces names alphabetically. It is intentionally an unbalanced binary search tree, which makes the performance tradeoff clear: it can have efficient expected behavior when insertion order is reasonable, but sorted input can turn it into a chain.

## Systematic problem-solving

The project began with a broader bot concept, but I reduced it to one coherent feature instead of keeping unrelated games, color commands, time-zone behavior, or an unfinished AI response system. That made it possible to give every remaining feature a clear data model and a testable purpose.

I treated important behaviors as rules that the program must preserve. Character names are unique after normalization. Queue requests remain in order. Undo removes the latest undoable memory. A queued request is not removed until it has successfully been validated and applied. If saving fails, the in-memory change is restored so the user can retry it.

These decisions show systematic problem-solving because they identify the state that can change, define what must remain true, and handle failure cases instead of only implementing the successful path.

## Algorithmic performance

The project considers both average and worst-case behavior. Dictionary lookup and set membership are O(1) on average, although their worst cases can be O(n) and O(t). Appending to the memory list is O(1) amortized. Stack push and pop, linked-queue enqueue and dequeue, and discarding the oldest queue item are O(1).

The unbalanced BST is described in terms of its height, h. Search and insertion are O(h). With a reasonably shaped tree, the expected cost is O(log n), but the guaranteed worst case is O(n) when the tree becomes a chain. In-order traversal is O(n) because every name must be visited.

I also compared three FIFO implementations using the same workload: a list with `pop(0)`, `collections.deque`, and the custom linked queue. Removing from the front of a list shifts the remaining elements, so processing n items takes O(n²) total work. The deque and linked queue process n items in O(n) total work. The measurements supported the analysis, while the operation counts provide the actual Big O justification.

The benchmark implementation remains in [`benchmarks/compare.py`](../benchmarks/compare.py), but the important reasoning is summarized here so the project can be understood without a collection of reports.

## Code analysis and testing

The code is small enough to trace by hand. For example, if requests X and Y enter the queue, processing the queue adds X first. If the newly added memory is then undone, X is removed from the undo stack, while Y remains in the queue to be processed later. This demonstrates why the queue and stack need different ordering rules.

The tests check normal operations as well as boundaries and failures: empty structures, duplicate names, full capacities, case normalization, Unicode text, FIFO and LIFO behavior, workspace isolation, malformed saved data, failed saves, command parsing, and Discord error handling. The tests are not intended to replace understanding. They provide repeatable checks that the rules I designed continue to hold when the code changes.

## Communication and independent understanding

The project communicates its design through the code structure, command behavior, complexity comments, tests, and run instructions. A teacher can run the offline check, inspect the structures, and see the bot demonstrate creation, tag filtering, alphabetical browsing, queue processing, undo, isolation, and save/reload behavior.

The most important part of presenting this project is being able to explain the decisions personally. I should be able to trace a queue by hand, explain why the BST can degrade to O(n), justify why a deque would be preferable in production, describe the rollback behavior, and modify or debug one of the structures. Those explanations show that the project represents understanding of the underlying concepts rather than only a working interface.

## Conclusion

This project meets the character of a CSE212 project because it applies core data structures to a functioning problem, makes algorithmic tradeoffs explicit, analyzes average and worst-case performance, tests correctness and failure behavior, and separates the interface from the algorithms. It is not intended to force every possible course topic into one application. Instead, it demonstrates a focused set of structures deeply enough that their purpose, invariants, limitations, and Big O behavior can be explained and defended.
