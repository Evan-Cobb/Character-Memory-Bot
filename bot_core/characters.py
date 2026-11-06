"""Owner-scoped character state and algorithms, with no network dependency."""

from collections import deque
from dataclasses import dataclass, field

from .structures import LinkedQueue, NameTree
from .validation import text

MAX_CHARACTERS = 100
MAX_MEMORIES = 100
MAX_QUEUE = 50
MAX_UNDO = 100


@dataclass
class Character:
    name: str
    personality: str
    tags: set[str] = field(default_factory=set)
    memories: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Request:
    character_key: str
    fact: str


class Workspace:
    """One user's data within one guild (DMs use guild ID zero).

    Maps provide lookup, sets ensure unique tags, a bounded stack undoes memories,
    a linked queue holds pending memory additions, and the BST indexes names in order.
    """

    def __init__(self) -> None:
        self._characters: dict[str, Character] = {}
        self._names = NameTree()
        self._undo: deque[tuple[str, str]] = deque(maxlen=MAX_UNDO)
        self._requests = LinkedQueue()

    def create(self, name: str, personality: str, tags: str = "") -> str:
        name = text(name, "Name", 80)
        personality = text(personality, "Personality", 300)
        key = name.casefold()
        if key in self._characters:
            raise ValueError("You already have a character with that name.")
        if len(self._characters) >= MAX_CHARACTERS:
            raise ValueError(f"At most {MAX_CHARACTERS} characters per workspace.")
        if not isinstance(tags, str) or len(tags) > 300:
            raise ValueError("Tags must be at most 300 characters of comma-separated text.")
        normalized = {text(tag.casefold(), "Tag", 30) for tag in tags.split(",") if tag.strip()}
        if len(normalized) > 10:
            raise ValueError("Use at most 10 unique tags.")
        if len(",".join(normalized)) > 300:
            raise ValueError("Normalized tags must total at most 300 characters including commas.")
        self._characters[key] = Character(name, personality, normalized)
        self._names.insert(key)
        return f"Created {name}."

    def _find(self, name: str) -> tuple[str, Character]:
        key = text(name, "Name", 80).casefold()
        if key not in self._characters:
            raise ValueError("Character not found in your workspace.")
        return key, self._characters[key]

    def info(self, name: str) -> str:
        _, character = self._find(name)
        facts = "\n".join(f"- {fact}" for fact in character.memories[-5:]) or "None yet."
        return (
            f"{character.name}\nPersonality: {character.personality}\n"
            f"Tags: {', '.join(sorted(character.tags)) or 'none'}\n"
            f"Latest memories ({len(character.memories)} total):\n{facts}"
        )

    def names(self, tag: str = "") -> list[str]:
        required = text(tag.casefold(), "Tag", 30) if tag.strip() else ""
        return [
            self._characters[key].name
            for key in self._names
            if not required or required in self._characters[key].tags
        ]

    def remember(self, name: str, fact: str) -> str:
        key, character = self._find(name)
        fact = text(fact, "Memory", 250)
        if len(character.memories) >= MAX_MEMORIES:
            raise ValueError(f"At most {MAX_MEMORIES} memories per character.")
        character.memories.append(fact)
        self._undo.append((key, fact))
        return f"{character.name} remembered: {fact}"

    def undo(self) -> str:
        if not self._undo:
            raise ValueError("No memory changes to undo in this session.")
        key, fact = self._undo.pop()
        character = self._characters[key]
        assert character.memories[-1] == fact
        character.memories.pop()
        return f"Undid the last memory added to {character.name}."

    def enqueue(self, name: str, fact: str) -> str:
        key, character = self._find(name)
        fact = text(fact, "Memory", 250)
        if len(self._requests) >= MAX_QUEUE:
            raise ValueError(f"At most {MAX_QUEUE} memory additions can be queued.")
        self._requests.enqueue(Request(key, fact))
        return f"Queued memory for {character.name} at position {len(self._requests)}. Use /next."

    def process_next(self) -> str:
        if not self._requests:
            raise ValueError("Your memory queue is empty. Add a memory with /enqueue.")
        request = self._requests.peek()
        character = self._characters[request.character_key]
        if len(character.memories) >= MAX_MEMORIES:
            raise ValueError(
                f"{character.name} has {MAX_MEMORIES} memories. Use /next discard:true "
                "(or !next true) to discard this queued addition, or /undo to free a recent memory."
            )
        # Validate/add before dequeuing: a full character must not lose queued work.
        result = self.remember(character.name, request.fact)
        self._requests.dequeue()
        return result

    def discard_next(self) -> str:
        if not self._requests:
            raise ValueError("Your memory queue is empty.")
        request = self._requests.dequeue()
        character = self._characters[request.character_key]
        return f"Discarded the oldest queued memory for {character.name}: {request.fact}"

    @property
    def queue_size(self) -> int:
        return len(self._requests)

    def to_data(self) -> list[dict]:
        """Persist character data only; requests and undo state are session-local."""
        return [
            {
                "name": c.name,
                "personality": c.personality,
                "tags": sorted(c.tags),
                "memories": list(c.memories),
            }
            for c in self._characters.values()
        ]

    @classmethod
    def from_data(cls, rows: list[dict]) -> "Workspace":
        if not isinstance(rows, list) or len(rows) > MAX_CHARACTERS:
            raise ValueError("Invalid saved character list.")
        workspace = cls()
        for row in rows:
            if not isinstance(row, dict) or set(row) != {"name", "personality", "tags", "memories"}:
                raise ValueError("Invalid saved character fields.")
            tags, memories = row["tags"], row["memories"]
            if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
                raise ValueError("Invalid saved tags.")
            if not isinstance(memories, list) or len(memories) > MAX_MEMORIES:
                raise ValueError("Invalid saved memories.")
            if len(tags) > 10 or any("," in t or not t.strip() for t in tags):
                raise ValueError("Invalid saved tags.")
            workspace.create(row["name"], row["personality"], ",".join(tags))
            _, character = workspace._find(row["name"])
            character.memories = [text(fact, "Memory", 250) for fact in memories]
        return workspace
