"""Worker side of the API ⇄ worker protocol."""

from __future__ import annotations

import json
import os
import sys
import threading
from collections.abc import Callable
from typing import Any, BinaryIO

from pipelab.gst import GLib
from pipelab.runtime.protocol import write_frame


class Channel:
    """Thread-safe event writer on a private copy of the original stdout.

    File descriptor 1 is redirected to stderr so that plugins calling
    ``g_print`` cannot corrupt the binary protocol; their output ends up in
    the log stream instead.
    """

    def __init__(self) -> None:
        protocol_fd = os.dup(sys.stdout.fileno())
        os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
        self._stream: BinaryIO = os.fdopen(protocol_fd, "wb", buffering=0)
        self._lock = threading.Lock()

    def send(self, event: dict[str, Any], payload: bytes = b"") -> None:
        with self._lock:
            try:
                write_frame(self._stream, event, payload)
            except (BrokenPipeError, ValueError):
                os._exit(0)  # the API went away: nothing left to report to


def start_command_reader(dispatch: Callable[[dict[str, Any]], None], on_eof: Callable[[], None]) -> None:
    """Read JSON commands from stdin and dispatch them on the GLib main loop."""

    def run() -> None:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                command = json.loads(line)
            except json.JSONDecodeError:
                continue
            GLib.idle_add(_once(dispatch, command))
        GLib.idle_add(_once(lambda _arg: on_eof(), None))

    threading.Thread(target=run, name="commands", daemon=True).start()


def _once(function: Callable[[Any], None], argument: Any) -> Callable[[], bool]:
    def call() -> bool:
        function(argument)
        return GLib.SOURCE_REMOVE

    return call
