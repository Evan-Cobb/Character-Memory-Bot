"""Queue and unbalanced search tree used by the CSE212 character bot."""


class _Link:
    def __init__(self, value):
        self.value = value
        self.next = None


class LinkedQueue:
    """FIFO queue: O(1) endpoint operations and O(n) storage.

    Empty means head and tail are both None and size is zero.
    """

    def __init__(self):
        self._head = None
        self._tail = None
        self._size = 0

    def __len__(self):
        return self._size

    def enqueue(self, value):
        node = _Link(value)
        if self._tail is None:
            self._head = node
        else:
            self._tail.next = node
        self._tail = node
        self._size += 1

    def peek(self):
        if self._head is None:
            raise IndexError("The queue is empty.")
        return self._head.value

    def dequeue(self):
        value = self.peek()
        self._head = self._head.next
        self._size -= 1
        if self._head is None:
            self._tail = None
        return value

    def __iter__(self):
        node = self._head
        while node is not None:
            yield node.value
            node = node.next


class _TreeNode:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None


class NameTree:
    """Unbalanced BST. Search/insert take O(h), worst-case O(n)."""

    def __init__(self):
        self._root = None
        self._size = 0

    def __len__(self):
        return self._size

    def insert(self, key):
        if self._root is None:
            self._root = _TreeNode(key)
            self._size = 1
            return True
        node = self._root
        while True:
            if key == node.key:
                return False
            if key < node.key:
                if node.left is None:
                    node.left = _TreeNode(key)
                    break
                node = node.left
            else:
                if node.right is None:
                    node.right = _TreeNode(key)
                    break
                node = node.right
        self._size += 1
        return True

    def __contains__(self, key):
        node = self._root
        while node is not None:
            if key == node.key:
                return True
            node = node.left if key < node.key else node.right
        return False

    def __iter__(self):
        """In-order traversal: O(n) time, O(h) extra stack space."""
        stack = []
        node = self._root
        while node is not None or stack:
            while node is not None:
                stack.append(node)
                node = node.left
            node = stack.pop()
            yield node.key
            node = node.right

    def height(self):
        if self._root is None:
            return 0
        pending = [(self._root, 1)]
        greatest = 0
        while pending:
            node, depth = pending.pop()
            greatest = max(greatest, depth)
            if node.left is not None:
                pending.append((node.left, depth + 1))
            if node.right is not None:
                pending.append((node.right, depth + 1))
        return greatest
