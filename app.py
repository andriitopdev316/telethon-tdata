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
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

import converter as conv

ROOT = Path(__file__).resolve().parent

APP_STYLESHEET = """
QMainWindow, QWidget#central {
    background: #f4f7fb;
}
QLabel#title {
    color: #0f172a;
}
QLabel#subtitle {
    color: #64748b;
}
QLabel#sectionTitle {
    color: #334155;
    font-weight: 600;
}
QFrame#card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
}
QRadioButton {
    spacing: 8px;
    color: #1e293b;
    padding: 8px 12px;
}
QRadioButton::indicator {
    width: 16px;
    height: 16px;
}
QPushButton {
    background: #ffffff;
    color: #1e293b;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 8px 14px;
    font-weight: 500;
}
QPushButton:hover:!disabled {
    background: #f8fafc;
    border-color: #94a3b8;
}
QPushButton:pressed:!disabled {
    background: #e2e8f0;
}
QPushButton:disabled {
    color: #94a3b8;
    background: #f1f5f9;
    border-color: #e2e8f0;
}
QPushButton#primary {
    background: #2AABEE;
    color: white;
    border: none;
    border-radius: 10px;
    padding: 12px 18px;
    font-weight: 700;
    font-size: 14px;
}
QPushButton#primary:hover:!disabled {
    background: #229ED9;
}
QPushButton#primary:disabled {
    background: #9bbfd0;
    color: #eef8fd;
}
QListWidget, QTextEdit {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 6px;
    color: #0f172a;
    selection-background-color: #2AABEE;
    selection-color: white;
}
QProgressBar {
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    background: #e2e8f0;
    text-align: center;
    color: #0f172a;
    height: 18px;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                stop:0 #2AABEE, stop:1 #1a8fd1);
    border-radius: 7px;
}
QLabel#status {
    color: #475569;
}
"""


class Worker(QThread):
    log = pyqtSignal(str)
    progress = pyqtSignal(int, int, str)  # current, total, item
    finished_ok = pyqtSignal(int, int)  # ok_count, fail_count

    def __init__(self, mode: str, items: list):
        super().__init__()
        self.mode = mode
        self.items = items

    def _log(self, message: str) -> None:
        self.log.emit(message)

    def _progress(self, current: int, total: int, item: str) -> None:
        self.progress.emit(current, total, item)

    def run(self) -> None:
        try:
            if self.mode == "session_to_tdata":
                ok, failed = conv.run_async(
                    conv.convert_sessions(
                        self.items, log=self._log, progress=self._progress
                    )
                )
            else:
                ok, failed = conv.run_async(
                    conv.convert_tdatas(
                        self.items, log=self._log, progress=self._progress
                    )
                )
            self.finished_ok.emit(len(ok), len(failed))
        except Exception as exc:  # noqa: BLE001
            self.log.emit(f"FATAL: {exc}")
            self.log.emit(traceback.format_exc())
            self.finished_ok.emit(0, max(1, len(self.items)))


def _card() -> QFrame:
    frame = QFrame()
    frame.setObjectName("card")
    return frame


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Session ↔ tdata Converter")
        self.resize(780, 640)
        self.setMinimumSize(640, 520)
        self.worker: Worker | None = None

        conv.ensure_dirs()

        root = QWidget()
        root.setObjectName("central")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(14)

        header = QVBoxLayout()
        header.setSpacing(4)
        title = QLabel("Session ↔ tdata Converter")
        title.setObjectName("title")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        subtitle = QLabel(
            "Convert Telethon sessions and Telegram Desktop tdata folders. "
            "Use only with accounts you own — internet required."
        )
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        header.addWidget(title)
        header.addWidget(subtitle)
        layout.addLayout(header)

        # Mode card
        mode_card = _card()
        mode_layout = QVBoxLayout(mode_card)
        mode_layout.setContentsMargins(16, 14, 16, 14)
        mode_layout.setSpacing(8)
        mode_title = QLabel("Conversion direction")
        mode_title.setObjectName("sectionTitle")
        mode_layout.addWidget(mode_title)

        mode_row = QHBoxLayout()
        self.mode_group = QButtonGroup(self)
        self.radio_s2t = QRadioButton("Session → tdata")
        self.radio_t2s = QRadioButton("tdata → Session")
        self.radio_s2t.setChecked(True)
        self.mode_group.addButton(self.radio_s2t)
        self.mode_group.addButton(self.radio_t2s)
        mode_row.addWidget(self.radio_s2t)
        mode_row.addWidget(self.radio_t2s)
        mode_row.addStretch(1)
        mode_layout.addLayout(mode_row)
        layout.addWidget(mode_card)

        self.radio_s2t.toggled.connect(self._refresh_mode_ui)

        # Queue card
        queue_card = _card()
        queue_layout = QVBoxLayout(queue_card)
        queue_layout.setContentsMargins(16, 14, 16, 14)
        queue_layout.setSpacing(10)

        queue_header = QHBoxLayout()
        self.list_label = QLabel("Queue")
        self.list_label.setObjectName("sectionTitle")
        queue_header.addWidget(self.list_label)
        queue_header.addStretch(1)
        queue_layout.addLayout(queue_header)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.btn_add = QPushButton("Add...")
        self.btn_add_existing = QPushButton("Use folder contents")
        self.btn_clear = QPushButton("Clear list")
        for b in (self.btn_add, self.btn_add_existing, self.btn_clear):
            btn_row.addWidget(b)
        btn_row.addStretch(1)
        queue_layout.addLayout(btn_row)

        self.queue = QListWidget()
        self.queue.setMinimumHeight(130)
        self.queue.setAlternatingRowColors(True)
        queue_layout.addWidget(self.queue)
        layout.addWidget(queue_card)

        # Convert + progress
        self.btn_convert = QPushButton("Convert")
        self.btn_convert.setObjectName("primary")
        self.btn_convert.setMinimumHeight(44)
        self.btn_convert.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self.btn_convert)

        progress_row = QVBoxLayout()
        progress_row.setSpacing(6)
        progress_header = QHBoxLayout()
        self.progress_label = QLabel("Idle")
        self.progress_label.setObjectName("status")
        self.progress_pct = QLabel("0%")
        self.progress_pct.setObjectName("status")
        self.progress_pct.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        progress_header.addWidget(self.progress_label)
        progress_header.addStretch(1)
        progress_header.addWidget(self.progress_pct)
        progress_row.addLayout(progress_header)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(16)
        progress_row.addWidget(self.progress)
        layout.addLayout(progress_row)

        # Log card
        log_card = _card()
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(16, 14, 16, 14)
        log_layout.setSpacing(8)
        log_title = QLabel("Activity log")
        log_title.setObjectName("sectionTitle")
        log_layout.addWidget(log_title)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(QFont("Consolas", 10))
        self.log.setMinimumHeight(140)
        self.log.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        log_layout.addWidget(self.log)
        layout.addWidget(log_card, stretch=1)

        self.status = QLabel("Ready")
        self.status.setObjectName("status")
        layout.addWidget(self.status)

        self.btn_add.clicked.connect(self.add_items)
        self.btn_add_existing.clicked.connect(self.add_existing)
        self.btn_clear.clicked.connect(self._clear_queue)
        self.btn_convert.clicked.connect(self.start_convert)

        self._paths: list[str] = []
        self._refresh_mode_ui()

    def mode(self) -> str:
        return "session_to_tdata" if self.radio_s2t.isChecked() else "tdata_to_session"

    def _clear_queue(self) -> None:
        self.queue.clear()
        self._paths.clear()

    def _refresh_mode_ui(self) -> None:
        if self.mode() == "session_to_tdata":
            self.btn_add.setText("Add .session files…")
            self.btn_add_existing.setText("Load from sessions/")
            self.list_label.setText("Queue — session names")
        else:
            self.btn_add.setText("Add tdata folders…")
            self.btn_add_existing.setText("Load from tdatas/")
            self.list_label.setText("Queue — tdata folders")
        self._clear_queue()

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

    def _reset_progress(self) -> None:
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress_pct.setText("0%")
        self.progress_label.setText("Idle")

    def _on_progress(self, current: int, total: int, item: str) -> None:
        if total <= 0:
            self._reset_progress()
            return
        pct = int(round(100 * current / total))
        self.progress.setValue(pct)
        self.progress_pct.setText(f"{pct}%")
        if current >= total:
            self.progress_label.setText(f"Finishing… ({total}/{total})")
        elif item:
            self.progress_label.setText(
                f"Converting {current + 1} of {total}: {item}"
            )
        else:
            self.progress_label.setText(f"Progress {current}/{total}")
        self.status.setText(self.progress_label.text())

    def add_items(self) -> None:
        try:
            if self.mode() == "session_to_tdata":
                conv.SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
                files, _ = QFileDialog.getOpenFileNames(
                    self,
                    "Select Telethon session files",
                    str(conv.SESSIONS_DIR),
                    "Session files (*.session);;All files (*.*)",
                )
                for f in files:
                    name = conv.import_session_file(Path(f))
                    self._add_queue_item(name)
                    self._append_log(f"Added session: {name}")
            else:
                conv.TDATAS_DIR.mkdir(parents=True, exist_ok=True)
                folder = QFileDialog.getExistingDirectory(
                    self,
                    "Select a tdata folder (or a folder that contains tdata)",
                    str(conv.TDATAS_DIR),
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
        if busy:
            self.status.setText("Converting…")
            self.progress_label.setText("Starting…")
            self.progress.setValue(0)
            self.progress_pct.setText("0%")
        else:
            self.status.setText("Ready")

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
            "Starting session → tdata..."
            if self.mode() == "session_to_tdata"
            else "Starting tdata → session..."
        )
        self.worker = Worker(self.mode(), items)
        self.worker.log.connect(self._append_log)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_ok.connect(self.on_finished)
        self.worker.start()

    def on_finished(self, ok_count: int, fail_count: int) -> None:
        self.set_busy(False)
        total = ok_count + fail_count
        if total:
            self.progress.setValue(100)
            self.progress_pct.setText("100%")
        self.progress_label.setText(
            f"Done — {ok_count} succeeded, {fail_count} failed"
        )
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
    os.chdir(ROOT)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
