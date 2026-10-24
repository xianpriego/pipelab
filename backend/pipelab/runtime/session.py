"""API side of a running pipeline: one worker process per project."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import signal
import sys
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Any

import pipelab
from pipelab.graph.models import Graph
from pipelab.runtime.models import RuntimeStatus
from pipelab.runtime.protocol import encode_command, encode_ws_binary, read_frame

log = logging.getLogger(__name__)

Outgoing = tuple[str, str | bytes]  # ("text", json) or ("bytes", frame)
_REPLAYED_LOG_LINES = 200
_LOG_LINES_PER_SECOND = 300
_PACKAGE_ROOT = Path(pipelab.__file__).resolve().parent.parent  # the worker runs from the media dir


class RuntimeCommandError(RuntimeError):
    pass


def _exit_reason(code: int) -> str:
    if code < 0:
        with contextlib.suppress(ValueError):
            return f"the worker crashed ({signal.Signals(-code).name}); a plugin probably failed"
    return f"the worker exited with code {code}"


class RuntimeSession:
    def __init__(self, project_id: str, media_dir: Path) -> None:
        self.project_id = project_id
        self.media_dir = media_dir
        self.status = RuntimeStatus(project_id=project_id)
        self._process: asyncio.subprocess.Process | None = None
        self._tasks: list[asyncio.Task] = []
        self._subscribers: set[asyncio.Queue[Outgoing]] = set()
        self._history: deque[dict[str, Any]] = deque(maxlen=500)
        self._logs: deque[str] = deque(maxlen=2000)
        self._caps: dict[str, dict[str, Any]] = {}
        self._properties: dict[tuple, dict[str, Any]] = {}
        self._instances: dict[str, dict[str, Any]] = {}
        self._stats: dict[str, Any] | None = None
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._stopping = False

    @property
    def running(self) -> bool:
        return self._process is not None and self._process.returncode is None

    async def start(
        self,
        graph: Graph,
        gst_debug: str,
        preview: dict[str, Any] | None = None,
        components: dict[str, Any] | None = None,
    ) -> None:
        if self.running:
            await self.stop("kill")
        await asyncio.gather(*self._tasks, return_exceptions=True)  # let the previous run settle
        self._reset()
        python_path = os.pathsep.join(filter(None, [str(_PACKAGE_ROOT), os.environ.get("PYTHONPATH")]))
        env = {**os.environ, "GST_DEBUG": gst_debug, "GST_DEBUG_NO_COLOR": "1", "PYTHONPATH": python_path}
        self.media_dir.mkdir(parents=True, exist_ok=True)
        self._process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "pipelab.runtime.worker",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.media_dir,
            env=env,
        )
        self._update_status({"type": "state", "state": "starting"})
        self.status.started_at = time.time()
        await self._write(
            {"graph": graph.model_dump(), "components": components or {}, "preview": preview or {}}
        )
        process = self._process
        readers = [
            asyncio.create_task(self._read_events(process)),
            asyncio.create_task(self._read_logs(process)),
        ]
        self._tasks = [*readers, asyncio.create_task(self._watch_exit(process, readers))]

    def _reset(self) -> None:
        self._history.clear()
        self._logs.clear()
        self._caps.clear()
        self._properties.clear()
        self._instances.clear()
        self._stats = None
        self._stopping = False
        self.status = RuntimeStatus(project_id=self.project_id)

    async def _write(self, message: dict[str, Any]) -> None:
        if not self.running:
            raise RuntimeCommandError("the pipeline is not running")
        assert self._process is not None and self._process.stdin is not None
        self._process.stdin.write(encode_command(message))
        with contextlib.suppress(ConnectionResetError, BrokenPipeError):
            await self._process.stdin.drain()

    async def send(self, command: dict[str, Any]) -> None:
        await self._write(command)

    async def request(self, command: dict[str, Any], timeout: float = 5.0) -> dict[str, Any]:
        request_id = uuid.uuid4().hex
        future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        try:
            await self._write({**command, "request_id": request_id})
            return await asyncio.wait_for(future, timeout)
        except TimeoutError as error:
            raise RuntimeCommandError("the pipeline did not answer in time") from error
        finally:
            self._pending.pop(request_id, None)

    async def stop(self, mode: str = "eos", timeout: float = 9.0) -> None:
        process = self._process
        if process is None or process.returncode is not None:
            return
        self._stopping = True
        with contextlib.suppress(RuntimeCommandError):
            await self._write({"cmd": "stop", "mode": mode})
        try:
            await asyncio.wait_for(process.wait(), timeout if mode == "eos" else 2.0)
        except TimeoutError:
            process.kill()
            await process.wait()

    async def _read_events(self, process: asyncio.subprocess.Process) -> None:
        assert process.stdout is not None
        while (frame := await read_frame(process.stdout)) is not None:
            header, payload = frame
            if header.get("type") == "preview":
                self._broadcast(("bytes", encode_ws_binary(header, payload)))
                continue
            self._handle_event(header)

    def _handle_event(self, event: dict[str, Any]) -> None:
        request_id = event.get("request_id")
        if request_id in self._pending and not self._pending[request_id].done():
            self._pending[request_id].set_result(event.get("data", event))
        if event["type"] == "reply":
            return
        if event["type"] == "state":
            self._update_status(event)
            event = self._state_event()
        elif event["type"] == "caps":
            self._caps[event["edge_id"]] = event
        elif event["type"] == "stats":
            self._stats = event
        elif event["type"] == "instances":
            self._instances[event["slot"]] = event
        elif event["type"] == "property":
            self._properties[(event.get("node_id"), event.get("pad"), event.get("property"))] = event
        elif event["type"] != "probe":
            self._history.append(event)
        self._broadcast(("text", json.dumps(event)))

    def _update_status(self, event: dict[str, Any]) -> None:
        self.status.state = event["state"]
        if event.get("error"):
            self.status.error = event["error"]

    def _state_event(self) -> dict[str, Any]:
        return {"type": "state", **self.status.model_dump()}

    async def _read_logs(self, process: asyncio.subprocess.Process) -> None:
        """Forward GST_DEBUG output, at most ``_LOG_LINES_PER_SECOND`` lines per second."""
        assert process.stderr is not None
        window, sent, dropped = time.monotonic(), 0, 0
        async for raw in process.stderr:
            line = raw.decode(errors="replace").rstrip()
            if not line:
                continue
            now = time.monotonic()
            if now - window >= 1.0:
                self._report_dropped(dropped)
                window, sent, dropped = now, 0, 0
            if sent >= _LOG_LINES_PER_SECOND:
                dropped += 1
                continue
            sent += 1
            self._log_line(line)
        self._report_dropped(dropped)

    def _report_dropped(self, dropped: int) -> None:
        if dropped:
            self._log_line(f"… {dropped} log lines dropped (lower GST_DEBUG to see them all)")

    def _log_line(self, line: str) -> None:
        self._logs.append(line)
        self._broadcast(("text", json.dumps({"type": "log", "line": line})))

    async def _watch_exit(self, process: asyncio.subprocess.Process, readers: list[asyncio.Task]) -> None:
        code = await process.wait()
        await asyncio.gather(*readers, return_exceptions=True)
        if self._stopping or code == 0:
            self.status.state = "stopped"
        else:
            self.status.state = "error"
            self.status.error = self.status.error or _exit_reason(code)
        for future in self._pending.values():
            if not future.done():
                future.set_exception(RuntimeCommandError("the pipeline stopped"))
        self._broadcast(("text", json.dumps(self._state_event())))

    def subscribe(self) -> asyncio.Queue[Outgoing]:
        queue: asyncio.Queue[Outgoing] = asyncio.Queue(maxsize=512)
        for event in self.replay():
            queue.put_nowait(("text", json.dumps(event)))
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[Outgoing]) -> None:
        self._subscribers.discard(queue)

    def replay(self) -> list[dict[str, Any]]:
        """Events a new client needs to catch up with the current run."""
        logs = [{"type": "log", "line": line} for line in list(self._logs)[-_REPLAYED_LOG_LINES:]]
        stats = [self._stats] if self._stats else []
        properties = [{k: v for k, v in e.items() if k != "request_id"} for e in self._properties.values()]
        return [
            self._state_event(),
            *list(self._history)[-300:],
            *self._caps.values(),
            *properties,
            *self._instances.values(),
            *stats,
            *logs,
        ]

    def _broadcast(self, message: Outgoing) -> None:
        for queue in list(self._subscribers):
            if queue.full():
                if message[0] == "bytes":
                    continue  # previews are disposable; never block the pipeline for them
                with contextlib.suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
            queue.put_nowait(message)


class RuntimeManager:
    def __init__(self, media_dir: Path) -> None:
        self._media_dir = media_dir
        self._sessions: dict[str, RuntimeSession] = {}

    def session(self, project_id: str) -> RuntimeSession:
        if project_id not in self._sessions:
            self._sessions[project_id] = RuntimeSession(project_id, self._media_dir)
        return self._sessions[project_id]

    async def shutdown(self) -> None:
        await asyncio.gather(*(s.stop("kill") for s in self._sessions.values()), return_exceptions=True)
