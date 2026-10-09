"""Optional fishing task with local/clone controls and explicit backend disclosure."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from src.fishing.bridge import BACKEND, ROOT
from src.fishing.runner import DEFAULTS
from src.ui.shell import actions, clone_flow, data
from src.ui.shell.config_form import ConfigForm
from src.ui.shell.page import Page
from src.ui.shell.widgets import Button, Card, Text, hbox, vbox
from src.utils import clone_desktop


class FishingPage(Page):
    interval = 1000

    def __init__(self):
        super().__init__("shellFishing", "自动钓鱼", "先进入已解锁的钓场，再开始")
        intro = Card()
        column = vbox(intro, (22, 18, 22, 18), 12)
        column.addWidget(
            Text(
                "钓鱼模块基于 MadestSamurai / MadSamurai 的 BD2 Fishing（MIT）。"
                "它会向游戏进程注入组件、读取钓鱼状态并调用游戏内部接口，可能带来账号处罚风险。"
                "普通日常任务仍使用图像识别。",
                "muted",
                wrap=True,
            )
        )
        column.addWidget(
            Text(
                "关闭游戏内自动钓鱼。默认运行 30 分钟，自动出售关闭；"
                "锁定及资料不明的鱼始终保留。桌面分身启动后，请在分身游戏里手动进入钓场。",
                "sub",
                wrap=True,
            )
        )
        row = hbox(None, (0, 0, 0, 0), 8)
        self.start_button = Button("开始钓鱼", "primary", "play", on_click=self._start)
        self.clone_button = Button(
            "在桌面分身钓鱼", "secondary", "monitor", on_click=self._start_clone
        )
        self.pause_button = Button("暂停 / 继续", "secondary", "pause", on_click=self._pause)
        self.stop_button = Button("停止", "danger", "square", on_click=self._stop)
        for button in (self.start_button, self.clone_button, self.pause_button, self.stop_button):
            row.addWidget(button)
        row.addStretch(1)
        column.addLayout(row)
        self.backend_text = Text("", "muted", wrap=True)
        column.addWidget(self.backend_text)
        self.build_button = Button(
            "构建钓鱼后端", "secondary", "hammer", on_click=self._build_backend
        )
        column.addWidget(self.build_button)
        column.addWidget(Button("打开钓鱼诊断目录", "ghost", "folder", on_click=self._open_logs))
        self.body.addWidget(intro)
        state_card = Card()
        state_layout = vbox(state_card, (22, 16, 22, 16), 8)
        state_layout.addWidget(Text("本次状态", "h2"))
        self.status = Text("尚未开始", "sub", wrap=True)
        state_layout.addWidget(self.status)
        self.body.addWidget(state_card)
        self.form_card = Card()
        self.form_layout = vbox(self.form_card, (22, 16, 22, 16), 8)
        self.form_layout.addWidget(Text("钓鱼设置", "h2"))
        self.form = None
        self.body.addWidget(self.form_card)
        self.body.addStretch(1)
        self.refresh()

    def _task(self):
        return data.task_by_name("自动钓鱼")

    def _running(self):
        task = data.current_task()
        if task is None:
            task = clone_flow.remote_task()
        return task if task is not None and str(task.name) == "自动钓鱼" else None

    def _start(self):
        from src.ui.shell import autorun

        autorun.cancel()
        actions.start(self._task(), self.window())

    def _start_clone(self):
        clone_flow.ask_and_start(self.window(), self._task())

    def _pause(self):
        task = self._running()
        if getattr(task, "remote", False):
            clone_desktop.send_control("resume" if task.paused else "pause")
        else:
            actions.toggle_pause(task)

    def _stop(self):
        task = self._running()
        if getattr(task, "remote", False):
            clone_desktop.send_control("stop")
        else:
            actions.stop(task)

    def _build_backend(self):
        try:
            subprocess.Popen(
                [
                    "powershell.exe",
                    "-NoExit",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(ROOT / "scripts/build_fishing.ps1"),
                ],
                cwd=str(ROOT),
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        except OSError as exc:
            self.backend_text.set_text(f"无法启动构建：{exc}")

    def _open_logs(self):
        session = clone_desktop._session_of(os.getpid())
        path = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "YES-BD2/Fishing"
        # Show both session folders from the outside, the current one inside.
        if clone_desktop.in_clone():
            path /= f"session-{session}"
        path.mkdir(parents=True, exist_ok=True)
        actions.open_folder(str(path))

    def refresh(self):
        task = self._task()
        running = self._running()
        if self.form is None and task is not None:
            # These time limits are user controls, not the recognition tuning
            # rows hidden by the shared form's keyword filter.
            self.form = ConfigForm(task, keys=list(DEFAULTS))
            self.form_layout.addWidget(self.form)
        if self.form:
            self.form.setEnabled(running is None)
            self.form.sync()
        ready = BACKEND.is_file()
        self.backend_text.set_text(
            "钓鱼后端已就绪 · " + clone_flow.background_status()
            if ready
            else "钓鱼后端未构建。源码版需安装 .NET SDK 8 或更新版本，再点击构建。"
        )
        busy = data.busy() or clone_flow.busy_in_clone()
        self.start_button.setEnabled(ready and task is not None and not busy)
        self.clone_button.setVisible(not clone_desktop.in_clone())
        self.clone_button.setEnabled(
            ready and task is not None and not busy and clone_flow.available()
        )
        self.pause_button.setEnabled(running is not None)
        self.stop_button.setEnabled(running is not None)
        self.build_button.setVisible(not ready and (ROOT / "scripts/build_fishing.ps1").is_file())
        self.build_button.setEnabled(not busy)
        if running is not None and getattr(running, "remote", False):
            info = running.status.get("fishing", {})
        else:
            info = getattr(task, "fishing_status", {}) or {}
        self.status.set_text(
            "\n".join(f"{key}：{value}" for key, value in info.items()) or "尚未开始"
        )
