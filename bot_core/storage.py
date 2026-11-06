"""Validated, atomic JSON persistence for one local bot process."""

import copy
import json
import os
import re
import tempfile
from collections.abc import Callable
from pathlib import Path

from .characters import Workspace


class PersistenceError(OSError):
    """A persistent operation failed and its in-memory change was rolled back."""


class Repository:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._workspaces: dict[str, Workspace] = {}

    @staticmethod
    def scope(guild_id: int | None, user_id: int) -> str:
        return f"{guild_id or 0}:{user_id}"

    def get(self, scope: str) -> Workspace:
        if re.fullmatch(r"[0-9]+:[0-9]+", scope) is None:
            raise ValueError("Invalid workspace identifier.")
        if scope not in self._workspaces:
            self._workspaces[scope] = Workspace()
        return self._workspaces[scope]

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or payload.get("version") != 1:
                raise ValueError("Unsupported saved-data version.")
            rows = payload["workspaces"]
            if not isinstance(rows, dict):
                raise ValueError("Invalid workspaces.")
            loaded = {}
            for scope, characters in rows.items():
                if re.fullmatch(r"[0-9]+:[0-9]+", scope) is None:
                    raise ValueError("Invalid workspace identifier.")
                loaded[scope] = Workspace.from_data(characters)
        except (ValueError, KeyError, TypeError) as exc:
            raise ValueError(
                "Saved data is invalid; the existing file was not overwritten."
            ) from exc
        self._workspaces = loaded

    def save(self) -> None:
        payload = {
            "version": 1,
            "workspaces": {key: workspace.to_data() for key, workspace in self._workspaces.items()},
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=self.path.name + ".",
                suffix=".tmp",
                delete=False,
            ) as stream:
                temporary = stream.name
                json.dump(payload, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary is not None and os.path.exists(temporary):
                os.unlink(temporary)

    def mutate(self, scope: str, operation: Callable[[Workspace], str]) -> str:
        """Roll back in-memory edits if validation or disk persistence fails.

        Handlers call this synchronously, with no await between edit and save.
        This is single-process atomicity, not a distributed database transaction.
        """
        existed = scope in self._workspaces
        original = copy.deepcopy(self.get(scope))
        try:
            result = operation(self.get(scope))
            self.save()
            return result
        except Exception as exc:
            if existed:
                self._workspaces[scope] = original
            else:
                self._workspaces.pop(scope, None)
            if isinstance(exc, OSError):
                raise PersistenceError("Could not persist the change; it was rolled back.") from exc
            raise
