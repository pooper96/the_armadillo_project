# services/persistence.py
"""
Robust JSON persistence for the game state.

- Uses Kivy's App to place the save file under the app's user_data_dir.
- Falls back to a local ./.userdata/save.json path when no app is running.
- Writes are atomic: data is written to a temporary file in the same directory
  and then os.replace() swaps it into place.
"""

from __future__ import annotations

import json
import os
from tempfile import NamedTemporaryFile
from typing import Any, Dict

from kivy.app import App  # Only Kivy import allowed here
from services.state import GameState


class Persistence:
    """JSON-backed persistence layer for GameState with atomic writes."""

    def __init__(self) -> None:
        """Initialize and cache the computed save path."""
        self._cached_path: str | None = None
        # Precompute so tests that inspect path don't trigger directory creation.
        self._cached_path = self._compute_path()

    def _compute_path(self) -> str:
        """Compute the save file path based on running Kivy app or local fallback."""
        app = App.get_running_app()
        if app is not None and getattr(app, "user_data_dir", None):
            base = app.user_data_dir
        else:
            base = os.path.join(".", ".userdata")
        return os.path.join(base, "save.json")

    def _save_path(self) -> str:
        """
        Return the save file path and ensure its parent directory exists.

        Returns:
            str: Absolute or relative path to save.json.
        """
        path = self._cached_path or self._compute_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self._cached_path = path
        return path

    def save(self, state: GameState) -> bool:
        """
        Serialize and atomically persist the provided GameState.

        Writes UTF-8 JSON with indent=2 to a temp file in the save directory,
        then replaces the final file in a single operation.

        Returns:
            bool: True on success, False if any error occurs.
        """
        try:
            path = self._save_path()
            directory = os.path.dirname(path)
            payload: Dict[str, Any] = state.to_dict()

            with NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=directory,
                prefix=".save-",
                suffix=".tmp",
                delete=False,
            ) as tmp:
                json.dump(payload, tmp, indent=2, ensure_ascii=False)
                tmp.flush()
                os.fsync(tmp.fileno())
                temp_name = tmp.name

            os.replace(temp_name, path)
            return True
        except Exception:
            # Best-effort cleanup of the temp file if it still exists.
            try:
                if "temp_name" in locals() and os.path.exists(temp_name):
                    os.remove(temp_name)
            except Exception:
                pass
            return False

    def load(self, state: GameState) -> bool:
        """
        Load JSON from disk into the provided GameState instance.

        If the save file is missing or any error occurs during read/parse,
        the state is left unchanged and False is returned.

        Returns:
            bool: True on successful load, False otherwise.
        """
        try:
            path = self._save_path()
            if not os.path.exists(path):
                return False
            with open(path, "r", encoding="utf-8") as f:
                data: Dict[str, Any] = json.load(f)
            state.from_dict(data)
            return True
        except Exception:
            return False
