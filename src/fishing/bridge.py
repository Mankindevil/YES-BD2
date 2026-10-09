"""Bounded JSON-lines transport to our own child process, never a shell command."""

from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "tools/fishing/backend/YesBd2.FishingBridge.exe"


class BridgeError(RuntimeError):
    pass


class FishingBridge:
    def __init__(self, check=lambda: None, progress=lambda _text: None):
        if not BACKEND.is_file():
            raise BridgeError("钓鱼后端未构建，请先运行 scripts/build_fishing.ps1，然后重开工具。")
        self.check = check
        self.progress = progress
        self.messages = queue.Queue(maxsize=256)
        self.serial = 0
        self.last_pulse = 0.0
        self.closed = False
        self.proc = subprocess.Popen(
            [str(BACKEND), "--parent", str(os.getpid())],
            cwd=str(ROOT),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            bufsize=1,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        threading.Thread(target=self._read, daemon=True, name="FishingBridgeOutput").start()

    def _read(self):
        try:
            for line in self.proc.stdout:
                value = json.loads(line)
                self.messages.put(value, timeout=2)
        except (ValueError, OSError, queue.Full):
            # The caller has a bounded timeout and the backend a parent watchdog.
            pass

    def send(self, value):
        if self.proc.poll() is not None:
            raise BridgeError("钓鱼后端已退出，请查看诊断后重新开始。")
        try:
            self.proc.stdin.write(json.dumps(value, ensure_ascii=False) + "\n")
            self.proc.stdin.flush()
        except (OSError, ValueError) as exc:
            raise BridgeError("钓鱼后端连接已中断。") from exc

    def pulse(self):
        if time.monotonic() - self.last_pulse >= 0.5:
            self.send({"op": "heartbeat"})
            self.last_pulse = time.monotonic()

    def request(self, op, *, timeout=8.0, **values):
        self.check()
        self.serial += 1
        request_id = self.serial
        self.send({"id": request_id, "op": op, **values})
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            self.check()
            self.pulse()
            if self.proc.poll() is not None:
                raise BridgeError("钓鱼后端意外退出。")
            try:
                message = self.messages.get(timeout=0.1)
            except queue.Empty:
                continue
            if message.get("type") == "progress":
                self.progress(message.get("message", ""))
            if message.get("id") != request_id:
                continue
            if not message.get("ok"):
                raise BridgeError(message.get("error") or "钓鱼后端请求失败。")
            return message.get("result")
        raise BridgeError(f"钓鱼后端 {op} 超时，已终止本次任务。")

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.check = lambda: None
        try:
            self.request("shutdown", timeout=3)
        except (BridgeError, OSError):
            pass
        finally:
            try:
                self.proc.stdin.close()
                self.proc.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                self.proc.kill()
                self.proc.wait(timeout=2)
            self.proc.stdout.close()
