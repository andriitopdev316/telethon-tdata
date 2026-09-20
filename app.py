"""User-friendly GUI for session ↔ tdata conversion."""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import converter as conv

ROOT = Path(__file__).resolve().parent


class Worker(QThread):
    log = pyqtSignal(str)
    finished_ok = pyqtSignal(int, int)  # ok_count, fail_count

    def __init__(self, mode: str, items: list):
        super().__init__()
        self.mode = mode
        self.items = items

    def _log(self, message: str) -> None:
        self.log.emit(message)

    def run(self) -> None:
        try:
            if self.mode == "session_to_tdata":
                ok, failed = conv.run_async(
                    conv.convert_sessions(self.items, log=self._log)
                )
            else:
                ok, failed = conv.run_async(
                    conv.convert_tdatas(self.items, log=self._log)
                )
            self.finished_ok.emit(len(ok), len(failed))
        except Exception as exc:  # noqa: BLE001
            self.log.emit(f"FATAL: {exc}")
            self.log.emit(traceback.format_exc())
            self.finished_ok.emit(0, max(1, len(self.items)))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Session / tdata Converter")
        self.resize(720, 560)
        self.worker: Worker | None = None

        conv.ensure_dirs()

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        title = QLabel("Session / tdata Converter")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        layout.addWidget(title)

        hint = QLabel(
            "Pick a direction, add files or folders, then click Convert.\n"
            "Use only with accounts you own. Internet is required."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #444;")
        layout.addWidget(hint)

        mode_row = QHBoxLayout()
        self.mode_group = QButtonGroup(self)
        self.radio_s2t = QRadioButton("Session -> tdata")
        self.radio_t2s = QRadioButton("tdata -> Session")
        self.radio_s2t.setChecked(True)
        self.mode_group.addButton(self.radio_s2t)
        self.mode_group.addButton(self.radio_t2s)
        mode_row.addWidget(self.radio_s2t)
        mode_row.addWidget(self.radio_t2s)
        mode_row.addStretch(1)
        layout.addLayout(mode_row)

        self.radio_s2t.toggled.connect(self._refresh_mode_ui)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("Add...")
        self.btn_add_existing = QPushButton("Use folder contents")
        self.btn_clear = QPushButton("Clear list")
        self.btn_open_sessions = QPushButton("Open sessions")
        self.btn_open_tdatas = QPushButton("Open tdatas")
        for b in (
            self.btn_add,
            self.btn_add_existing,
            self.btn_clear,
            self.btn_open_sessions,
            self.btn_open_tdatas,
        ):
            btn_row.addWidget(b)
        layout.addLayout(btn_row)

        self.list_label = QLabel("Queue")
        layout.addWidget(self.list_label)
        self.queue = QListWidget()
        self.queue.setMinimumHeight(120)
        layout.addWidget(self.queue)

        self.btn_convert = QPushButton("Convert")
        self.btn_convert.setMinimumHeight(40)
        self.btn_convert.setStyleSheet(
            "QPushButton { background: #2AABEE; color: white; font-weight: 600;"
            " border: none; border-radius: 6px; padding: 8px 16px; }"
            "QPushButton:disabled { background: #9bbfd0; }"
            "QPushButton:hover:!disabled { background: #229ED9; }"
        )
        layout.addWidget(self.btn_convert)

        layout.addWidget(QLabel("Log"))
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(QFont("Consolas", 10))
        layout.addWidget(self.log, stretch=1)

        self.status = QLabel("Ready")
        self.status.setStyleSheet("color: #333;")
        layout.addWidget(self.status)

        self.btn_add.clicked.connect(self.add_items)
        self.btn_add_existing.clicked.connect(self.add_existing)
        self.btn_clear.clicked.connect(self.queue.clear)
        self.btn_open_sessions.clicked.connect(lambda: self._open_dir(conv.SESSIONS_DIR))
        self.btn_open_tdatas.clicked.connect(lambda: self._open_dir(conv.TDATAS_DIR))
        self.btn_convert.clicked.connect(self.start_convert)

        self._paths: list[str] = []  # display names / keys in queue
        self._refresh_mode_ui()

    def mode(self) -> str:
        return "session_to_tdata" if self.radio_s2t.isChecked() else "tdata_to_session"

    def _refresh_mode_ui(self) -> None:
        if self.mode() == "session_to_tdata":
            self.btn_add.setText("Add .session files...")
            self.btn_add_existing.setText("Load from sessions/")
            self.list_label.setText("Queue (session names)")
        else:
            self.btn_add.setText("Add tdata folders...")
            self.btn_add_existing.setText("Load from tdatas/")
            self.list_label.setText("Queue (tdata folders)")
        self.queue.clear()
        self._paths.clear()

    def _append_log(self, message: str) -> None:
        self.log.append(message)
        self.log.ensureCursorVisible()

    def _open_dir(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        os.startfile(str(path))  # noqa: S606 - Windows explorer open

    def _add_queue_item(self, key: str) -> None:
        if key in self._paths:
            return
        self._paths.append(key)
        self.queue.addItem(key)

    def add_items(self) -> None:
        try:
            if self.mode() == "session_to_tdata":
                files, _ = QFileDialog.getOpenFileNames(
                    self,
                    "Select Telethon session files",
                    str(ROOT),
                    "Session files (*.session);;All files (*.*)",
                )
                for f in files:
                    name = conv.import_session_file(Path(f))
                    self._add_queue_item(name)
                    self._append_log(f"Added session: {name}")
            else:
                folder = QFileDialog.getExistingDirectory(
                    self,
                    "Select a tdata folder (or a folder that contains tdata)",
                    str(ROOT),
                )
                if folder:
                    name = conv.import_tdata_folder(Path(folder))
                    self._add_queue_item(name)
                    self._append_log(f"Added tdata: {name}")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Add failed", str(exc))

    def add_existing(self) -> None:
        if self.mode() == "session_to_tdata":
            names = conv.discover_session_names()
            if not names:
                QMessageBox.information(
                    self,
                    "Nothing found",
                    f"No sessions found in:\n{conv.SESSIONS_DIR}",
                )
                return
            for name in names:
                self._add_queue_item(name)
            self._append_log(f"Loaded {len(names)} session(s) from sessions/")
        else:
            folders = conv.discover_tdata_folders()
            if not folders:
                QMessageBox.information(
                    self,
                    "Nothing found",
                    f"No tdata folders found in:\n{conv.TDATAS_DIR}",
                )
                return
            for folder in folders:
                self._add_queue_item(folder.name)
            self._append_log(f"Loaded {len(folders)} tdata folder(s) from tdatas/")

    def set_busy(self, busy: bool) -> None:
        for w in (
            self.btn_add,
            self.btn_add_existing,
            self.btn_clear,
            self.btn_convert,
            self.radio_s2t,
            self.radio_t2s,
        ):
            w.setEnabled(not busy)
        self.status.setText("Converting..." if busy else "Ready")

    def start_convert(self) -> None:
        if self.worker and self.worker.isRunning():
            return
        items = list(self._paths)
        if not items:
            QMessageBox.information(
                self,
                "Queue is empty",
                "Add files/folders first, or click Load from sessions/tdatas.",
            )
            return

        self.set_busy(True)
        self._append_log("—")
        self._append_log(
            "Starting session -> tdata..."
            if self.mode() == "session_to_tdata"
            else "Starting tdata -> session..."
        )
        self.worker = Worker(self.mode(), items)
        self.worker.log.connect(self._append_log)
        self.worker.finished_ok.connect(self.on_finished)
        self.worker.start()

    def on_finished(self, ok_count: int, fail_count: int) -> None:
        self.set_busy(False)
        out = conv.TDATAS_DIR if self.mode() == "session_to_tdata" else conv.SESSIONS_DIR
        msg = f"Done. Success: {ok_count}, failed: {fail_count}. Output: {out}"
        self.status.setText(msg)
        self._append_log(msg)
        if ok_count:
            reply = QMessageBox.question(
                self,
                "Conversion finished",
                f"{msg}\n\nOpen the output folder?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if reply == QMessageBox.Yes:
                self._open_dir(out)


def main() -> None:
    # Ensure relative paths and working directory match project root
    os.chdir(ROOT)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
