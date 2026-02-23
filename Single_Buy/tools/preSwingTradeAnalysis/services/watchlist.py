"""
services/watchlist.py — Watchlist loading and file-change detection.

Single Responsibility: Only deals with reading the symbol list from disk
and notifying consumers when the file is updated.
"""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)


class WatchlistService:
    """
    Loads `watchlist.txt` and polls for modifications on a background thread.

    Usage
    -----
    svc = WatchlistService(path)
    symbols = svc.load()
    svc.watch(callback=my_fn, interval=3.0)   # fires my_fn(new_symbols) on change
    ...
    svc.stop()
    """

    def __init__(self, path: Path) -> None:
        self._path      = path
        self._symbols:  List[str] = []
        self._mtime:    float     = 0.0
        self._lock      = threading.Lock()
        self._watching  = False
        self._thread:   Optional[threading.Thread] = None

    # ── Public API ─────────────────────────────────────────────────────────────

    def load(self) -> List[str]:
        """Parse the watchlist file and return the deduplicated symbol list."""
        if not self._path.exists():
            logger.warning("Watchlist not found: %s", self._path)
            return []

        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                raw_lines = fh.readlines()
        except (OSError, PermissionError) as exc:
            logger.error("Cannot read watchlist %s: %s", self._path, exc)
            return self.get_symbols()  # return last known good list

        symbols: List[str] = []
        seen: set = set()
        for raw in raw_lines:
            sym = raw.strip().upper()
            # Skip blank lines, comments, and duplicates
            if sym and not sym.startswith("#") and not sym.startswith("//"):
                if sym not in seen:
                    symbols.append(sym)
                    seen.add(sym)

        with self._lock:
            self._symbols = symbols
            try:
                self._mtime = self._path.stat().st_mtime
            except OSError:
                pass

        logger.info("Loaded %d symbols from %s", len(symbols), self._path.name)
        return symbols

    def get_symbols(self) -> List[str]:
        with self._lock:
            return list(self._symbols)

    def get_path_display(self) -> str:
        return str(self._path)

    def current_mtime(self) -> float:
        try:
            return self._path.stat().st_mtime
        except FileNotFoundError:
            return 0.0

    def has_changed(self) -> bool:
        with self._lock:
            return self.current_mtime() != self._mtime

    def reload_if_changed(self) -> Optional[List[str]]:
        """Returns new symbol list only when the file was modified."""
        if self.has_changed():
            return self.load()
        return None

    def watch(self, callback: Callable[[List[str]], None], interval: float = 3.0) -> None:
        """Start a daemon thread that calls *callback* when the file changes."""
        if self._watching:
            return
        self._watching = True
        self._thread   = threading.Thread(
            target=self._poll_loop,
            args=(callback, interval),
            daemon=True,
            name="WatchlistWatcher",
        )
        self._thread.start()
        logger.info("Watchlist watcher started (interval=%.1fs)", interval)

    def stop(self) -> None:
        self._watching = False

    # ── Internal ───────────────────────────────────────────────────────────────

    def _poll_loop(self, callback: Callable, interval: float) -> None:
        while self._watching:
            try:
                new_symbols = self.reload_if_changed()
                if new_symbols is not None:
                    logger.info("Watchlist changed — %d symbols", len(new_symbols))
                    callback(new_symbols)
            except Exception as exc:
                logger.error("Watchlist watcher error: %s", exc)
            time.sleep(interval)
