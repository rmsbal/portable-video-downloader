import sys
import os
import shutil
import subprocess
import json
import re
from collections import deque
from datetime import datetime

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFileDialog, QTextEdit,
    QComboBox, QProgressBar, QListWidget, QInputDialog,
    QMessageBox, QCheckBox
)
from PySide6.QtCore import QThread, Signal

APP_NAME = "Smart Video Downloader"
APP_DIR = os.path.dirname(os.path.abspath(__file__))
IS_WINDOWS = sys.platform.startswith("win")
IS_LINUX = sys.platform.startswith("linux")


class DownloadWorker(QThread):
    log_signal = Signal(str)
    progress_signal = Signal(int)
    finished_signal = Signal(int)

    def __init__(self, cmd):
        super().__init__()
        self.cmd = cmd
        self.process = None

    def run(self):
        try:
            self.process = subprocess.Popen(
                self.cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )

            for line in self.process.stdout:
                line = line.strip()
                if not line:
                    continue

                self.log_signal.emit(line)

                if "Resuming download" in line:
                    self.log_signal.emit("🔄 Resuming previous download...")

                if "%" in line and "download" in line.lower():
                    match = re.search(r"(\d+(?:\.\d+)?)%", line)
                    if match:
                        try:
                            self.progress_signal.emit(int(float(match.group(1))))
                        except Exception:
                            pass

            code = self.process.wait()
            self.finished_signal.emit(code)

        except Exception as e:
            self.log_signal.emit(f"❌ Error: {e}")
            self.finished_signal.emit(1)

    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()


class FormatWorker(QThread):
    log_signal = Signal(str)
    formats_signal = Signal(list)
    finished_signal = Signal()

    def __init__(self, cmd):
        super().__init__()
        self.cmd = cmd

    def run(self):
        resolutions = set()
        audio_found = False

        try:
            process = subprocess.Popen(
                self.cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )

            for line in process.stdout:
                raw = line.rstrip()
                if not raw:
                    continue

                self.log_signal.emit(raw)

                lower = raw.lower()

                if "audio only" in lower:
                    audio_found = True

                # detect 1920x1080
                m = re.search(r"(\d{3,5})x(\d{3,5})", raw)
                if m:
                    try:
                        h = int(m.group(2))
                        if h >= 100:
                            resolutions.add(h)
                    except Exception:
                        pass

                # detect 1080p / 720p
                for match in re.findall(r"\b(\d{3,5})p\b", lower):
                    try:
                        h = int(match)
                        if h >= 100:
                            resolutions.add(h)
                    except Exception:
                        pass

            process.wait()

            ordered = sorted(resolutions, reverse=True)
            result = [f"{h}p" for h in ordered]

            if audio_found:
                result.append("Audio only")

            self.formats_signal.emit(result)
            self.finished_signal.emit()

        except Exception as e:
            self.log_signal.emit(f"❌ Error reading formats: {e}")
            self.formats_signal.emit([])
            self.finished_signal.emit()


class DownloaderApp(QWidget):
    def __init__(self):
        super().__init__()

        self.worker = None
        self.format_worker = None
        self.queue = deque()
        self.current_job = None
        self.is_paused = False
        self.paused_job = None
        self.stop_requested = False
        self.sleep_inhibitor = None

        self.queue_file = os.path.join(APP_DIR, "queue.json")
        self.history_file = os.path.join(APP_DIR, "history.json")

        self.setWindowTitle(f"🔥 {APP_NAME}")
        self.setGeometry(200, 150, 620, 860)

        self.build_ui()
        self.run_startup_checks()
        self.load_queue()

    def build_ui(self):
        layout = QVBoxLayout()

        layout.addWidget(QLabel("Video URL:"))
        url_row = QHBoxLayout()

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste video URL...")

        self.check_res_btn = QPushButton("Check Resolutions")
        self.check_res_btn.clicked.connect(self.check_resolutions)

        url_row.addWidget(self.url_input)
        url_row.addWidget(self.check_res_btn)
        layout.addLayout(url_row)

        self.filename_input = QLineEdit()
        self.filename_input.setPlaceholderText("Optional filename (e.g. episode 1)")
        layout.addWidget(QLabel("Filename:"))
        layout.addWidget(self.filename_input)

        self.subfolder_input = QLineEdit()
        self.subfolder_input.setPlaceholderText("Optional subfolder")
        layout.addWidget(QLabel("Subfolder:"))
        layout.addWidget(self.subfolder_input)

        self.resolution_select = QComboBox()
        self.resolution_select.addItems(["Best available"])
        layout.addWidget(QLabel("Resolution:"))
        layout.addWidget(self.resolution_select)

        self.browser_select = QComboBox()
        self.browser_select.addItems(["auto", "chrome", "firefox", "edge", "none"])
        layout.addWidget(QLabel("Cookies:"))
        layout.addWidget(self.browser_select)

        self.retry_select = QComboBox()
        self.retry_select.addItems(["0", "1", "2", "3", "5"])
        self.retry_select.setCurrentText("2")
        layout.addWidget(QLabel("Auto Retry Count:"))
        layout.addWidget(self.retry_select)

        self.prevent_sleep_checkbox = QCheckBox("Prevent system sleep while downloading")
        self.prevent_sleep_checkbox.setChecked(True)
        layout.addWidget(self.prevent_sleep_checkbox)

        path_layout = QHBoxLayout()
        self.path_input = QLineEdit(self.default_download_path())
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_folder)
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(browse_btn)

        layout.addWidget(QLabel("Save to:"))
        layout.addLayout(path_layout)

        queue_btn_layout = QHBoxLayout()

        self.add_btn = QPushButton("Add to Queue")
        self.add_btn.clicked.connect(self.add_to_queue)

        self.remove_btn = QPushButton("Remove Selected")
        self.remove_btn.clicked.connect(self.remove_selected)

        self.clear_btn = QPushButton("Clear Queue")
        self.clear_btn.clicked.connect(self.clear_queue)

        self.export_btn = QPushButton("Export Queue")
        self.export_btn.clicked.connect(self.export_queue)

        self.import_btn = QPushButton("Import Queue")
        self.import_btn.clicked.connect(self.import_queue)

        queue_btn_layout.addWidget(self.add_btn)
        queue_btn_layout.addWidget(self.remove_btn)
        queue_btn_layout.addWidget(self.clear_btn)
        queue_btn_layout.addWidget(self.export_btn)
        queue_btn_layout.addWidget(self.import_btn)
        layout.addLayout(queue_btn_layout)

        self.queue_list = QListWidget()
        self.queue_list.itemDoubleClicked.connect(self.edit_item)
        layout.addWidget(QLabel("Queue:"))
        layout.addWidget(self.queue_list)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        action_layout = QHBoxLayout()

        self.start_btn = QPushButton("Start Queue / Resume")
        self.start_btn.clicked.connect(self.start_queue)

        self.pause_btn = QPushButton("Pause Current")
        self.pause_btn.clicked.connect(self.pause_download)

        self.stop_btn = QPushButton("Stop Current")
        self.stop_btn.clicked.connect(self.stop_download)

        self.history_btn = QPushButton("Show History")
        self.history_btn.clicked.connect(self.show_history)

        action_layout.addWidget(self.start_btn)
        action_layout.addWidget(self.pause_btn)
        action_layout.addWidget(self.stop_btn)
        action_layout.addWidget(self.history_btn)
        layout.addLayout(action_layout)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)

        self.setLayout(layout)

    def run_startup_checks(self):
        yt = self.get_yt_dlp()
        if yt:
            self.log.append(f"✅ yt-dlp found: {yt}")
        else:
            self.log.append("⚠️ yt-dlp not found in PATH or app folder.")

        if IS_LINUX:
            self.log.append("ℹ️ Linux detected.")
            self.log.append("ℹ️ Sleep prevention supported via systemd-inhibit if available.")
        elif IS_WINDOWS:
            self.log.append("ℹ️ Windows detected.")
            self.log.append("ℹ️ Sleep prevention is not implemented in this version on Windows.")

    def default_download_path(self):
        if IS_WINDOWS:
            return os.path.join(os.path.expanduser("~"), "Downloads")
        return os.path.join(os.path.expanduser("~"), "Videos")

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self)
        if folder:
            self.path_input.setText(folder)

    def sanitize(self, text):
        invalid = '<>:"/\\|?*'
        for ch in invalid:
            text = text.replace(ch, "_")
        return "_".join(text.split()).strip("._")

    def get_yt_dlp(self):
        local_candidates = [
            os.path.join(APP_DIR, "yt-dlp"),
            os.path.join(APP_DIR, "yt-dlp.exe"),
            os.path.join(APP_DIR, "bin", "yt-dlp"),
            os.path.join(APP_DIR, "bin", "yt-dlp.exe"),
        ]
        for candidate in local_candidates:
            if os.path.exists(candidate):
                return candidate

        found = shutil.which("yt-dlp")
        if found:
            return found
        return None

    def build_browser_args(self, url):
        browser = self.browser_select.currentText()
        args = []

        if browser == "auto":
            if "facebook.com" in url or "fb.watch" in url:
                args += ["--cookies-from-browser", "chrome"]
        elif browser != "none":
            args += ["--cookies-from-browser", browser]

        return args

    def build_format_check_command(self, url):
        yt = self.get_yt_dlp()
        if not yt:
            self.log.append("❌ yt-dlp not found")
            return None

        cmd = [yt]
        cmd += self.build_browser_args(url)
        cmd += ["-F", url]
        return cmd

    def make_format_selector(self, resolution_text):
        resolution_text = (resolution_text or "").strip()

        if resolution_text == "Audio only":
            return "bestaudio/best"

        if resolution_text == "Best available" or not resolution_text:
            return "bv*+ba/b"

        match = re.match(r"(\d{3,5})p$", resolution_text)
        if match:
            h = int(match.group(1))
            return f"bestvideo[height<={h}]+bestaudio/best[height<={h}]"

        return "bv*+ba/b"

    def build_command(self, job):
        yt = self.get_yt_dlp()
        if not yt:
            self.log.append("❌ yt-dlp not found")
            return None

        path = self.path_input.text().strip()
        subfolder = job.get("subfolder", "").strip()
        if subfolder:
            path = os.path.join(path, self.sanitize(subfolder))

        os.makedirs(path, exist_ok=True)

        filename = job.get("filename", "").strip()
        if filename:
            name = self.sanitize(filename)
            if not name:
                name = "download"
            name += ".%(ext)s"
        else:
            name = "%(title)s.%(ext)s"

        output = os.path.join(path, name)
        url = job["url"]
        resolution = job.get("resolution", "Best available")

        cmd = [yt]
        cmd += self.build_browser_args(url)

        format_selector = self.make_format_selector(resolution)

        cmd += [
            "--continue",
            "--concurrent-fragments", "5",
            "--buffer-size", "16K",
            "-f", format_selector,
        ]

        if resolution == "Audio only":
            cmd += ["-x", "--audio-format", "mp3"]

        cmd += [
            "-o", output,
            url,
        ]

        return cmd

    def check_resolutions(self):
        url = self.url_input.text().strip()
        if not url:
            self.log.append("⚠️ Please enter a URL first")
            return

        if self.format_worker and self.format_worker.isRunning():
            self.log.append("⚠️ Resolution check already running")
            return

        cmd = self.build_format_check_command(url)
        if not cmd:
            return

        self.check_res_btn.setEnabled(False)
        self.resolution_select.clear()
        self.resolution_select.addItem("Checking...")

        self.log.append("🔍 Checking available resolutions...")

        self.format_worker = FormatWorker(cmd)
        self.format_worker.log_signal.connect(self.log.append)
        self.format_worker.formats_signal.connect(self.show_resolutions)
        self.format_worker.finished_signal.connect(self.finish_resolution_check)
        self.format_worker.start()

    def show_resolutions(self, resolutions):
        self.resolution_select.clear()

        if not resolutions:
            self.resolution_select.addItem("Best available")
            QMessageBox.information(
                self,
                APP_NAME,
                "No specific resolutions detected.\nUsing Best available."
            )
            return

        self.resolution_select.addItem("Best available")
        for item in resolutions:
            if item != "Best available":
                self.resolution_select.addItem(item)

        self.log.append("✅ Available resolutions: " + ", ".join(
            [self.resolution_select.itemText(i) for i in range(self.resolution_select.count())]
        ))

    def finish_resolution_check(self):
        self.check_res_btn.setEnabled(True)

    def add_to_queue(self):
        url = self.url_input.text().strip()
        if not url:
            self.log.append("⚠️ Please enter a URL")
            return

        selected_resolution = self.resolution_select.currentText().strip()
        if not selected_resolution:
            selected_resolution = "Best available"

        job = {
            "url": url,
            "filename": self.filename_input.text().strip(),
            "subfolder": self.subfolder_input.text().strip(),
            "resolution": selected_resolution,
            "retries_left": int(self.retry_select.currentText()),
            "status": "queued",
        }

        self.queue.append(job)
        self.save_queue()
        self.refresh_queue()

        display_name = job["filename"] if job["filename"] else "[auto]"
        self.log.append(
            f"📥 Added to queue: {display_name} | {selected_resolution} | {url}"
        )

        self.url_input.clear()
        self.filename_input.clear()
        self.subfolder_input.clear()
        self.resolution_select.clear()
        self.resolution_select.addItem("Best available")

    def refresh_queue(self):
        self.queue_list.clear()
        for i, job in enumerate(self.queue, 1):
            name = job.get("filename") or "[auto]"
            folder = job.get("subfolder") or "[root]"
            resolution = job.get("resolution") or "Best available"
            retries = job.get("retries_left", 0)
            status = job.get("status", "queued")
            self.queue_list.addItem(
                f"{i}. {name} | {folder} | {resolution} | retries:{retries} | {status} | {job['url']}"
            )

    def remove_selected(self):
        row = self.queue_list.currentRow()
        if row >= 0:
            q = list(self.queue)
            removed = q.pop(row)
            self.queue = deque(q)
            self.save_queue()
            self.refresh_queue()
            self.log.append(f"🗑️ Removed: {removed['url']}")
        else:
            self.log.append("⚠️ No queue item selected")

    def clear_queue(self):
        if self.worker and self.worker.isRunning():
            self.log.append("⚠️ Cannot clear queue while download is running")
            return

        self.queue.clear()
        self.current_job = None
        self.paused_job = None
        self.save_queue()
        self.refresh_queue()
        self.log.append("🗑️ Queue cleared")

    def edit_item(self, item):
        row = self.queue_list.row(item)
        if row < 0:
            return

        q = list(self.queue)
        job = q[row]

        new_name, ok = QInputDialog.getText(
            self, APP_NAME, "Edit filename:", text=job.get("filename", "")
        )
        if not ok:
            return

        new_folder, ok = QInputDialog.getText(
            self, APP_NAME, "Edit subfolder:", text=job.get("subfolder", "")
        )
        if not ok:
            return

        resolution_options = ["Best available", "2160p", "1440p", "1080p", "720p", "480p", "360p", "Audio only"]
        current_res = job.get("resolution", "Best available")
        current_index = resolution_options.index(current_res) if current_res in resolution_options else 0

        new_res, ok = QInputDialog.getItem(
            self, APP_NAME, "Edit resolution:", resolution_options, current_index, False
        )
        if not ok:
            return

        job["filename"] = new_name.strip()
        job["subfolder"] = new_folder.strip()
        job["resolution"] = new_res.strip() if new_res.strip() else "Best available"

        q[row] = job
        self.queue = deque(q)
        self.save_queue()
        self.refresh_queue()
        self.log.append(f"✏️ Updated queue item: {job['url']}")

    def start_queue(self):
        if self.worker and self.worker.isRunning():
            self.log.append("⚠️ A download is already running")
            return

        if self.prevent_sleep_checkbox.isChecked():
            self.start_sleep_inhibitor()

        if self.is_paused and self.paused_job:
            self.log.append("▶️ Resuming paused download...")
            self.current_job = self.paused_job
            self.paused_job = None
            self.is_paused = False
            self.stop_requested = False
            self.start_worker_for_current_job()
            return

        self.process_next()

    def start_worker_for_current_job(self):
        if not self.current_job:
            return

        self.current_job["status"] = "downloading"
        self.save_queue()

        cmd = self.build_command(self.current_job)
        if not cmd:
            self.current_job = None
            self.process_next()
            return

        self.progress.setValue(0)
        self.log.append(
            f"▶ Starting: {self.current_job['url']} | {self.current_job.get('resolution', 'Best available')}"
        )

        self.worker = DownloadWorker(cmd)
        self.worker.log_signal.connect(self.log.append)
        self.worker.progress_signal.connect(self.progress.setValue)
        self.worker.finished_signal.connect(self.finished)
        self.worker.start()

    def process_next(self):
        if not self.queue:
            self.current_job = None
            self.progress.setValue(0)
            self.save_queue()
            self.stop_sleep_inhibitor()
            self.log.append("✅ All done")
            return

        self.current_job = self.queue.popleft()
        self.current_job["status"] = "downloading"
        self.save_queue()
        self.refresh_queue()
        self.stop_requested = False
        self.start_worker_for_current_job()

    def finished(self, code):
        if self.is_paused:
            if self.current_job:
                self.current_job["status"] = "paused"
                self.paused_job = self.current_job
                self.current_job = None
            self.save_queue()
            self.refresh_queue()
            self.log.append("⏸️ Download paused")
            self.progress.setValue(0)
            self.stop_sleep_inhibitor()
            return

        if self.stop_requested:
            if self.current_job:
                self.current_job["status"] = "stopped"
                self.add_history(self.current_job, "stopped")
                self.log.append(f"⛔ Stopped: {self.current_job['url']}")
            self.current_job = None
            self.stop_requested = False
            self.progress.setValue(0)
            self.save_queue()
            self.refresh_queue()
            self.stop_sleep_inhibitor()
            return

        if code == 0:
            if self.current_job:
                self.current_job["status"] = "completed"
                self.add_history(self.current_job, "completed")
            self.log.append("✅ Done")
            self.current_job = None
            self.save_queue()
            self.refresh_queue()
            self.process_next()
            return

        if self.current_job:
            retries_left = self.current_job.get("retries_left", 0)
            if retries_left > 0:
                self.current_job["retries_left"] = retries_left - 1
                self.current_job["status"] = "retrying"
                self.log.append(
                    f"🔁 Failed, retrying... remaining retries: {self.current_job['retries_left']}"
                )
                retry_job = self.current_job
                self.current_job = None
                self.queue.appendleft(retry_job)
                self.save_queue()
                self.refresh_queue()
                self.process_next()
                return

            self.current_job["status"] = "failed"
            self.add_history(self.current_job, "failed")
            self.log.append("⚠️ Failed")

        self.current_job = None
        self.save_queue()
        self.refresh_queue()
        self.process_next()

    def pause_download(self):
        if self.worker and self.worker.isRunning() and self.current_job:
            self.is_paused = True
            self.stop_requested = False
            self.worker.stop()
            self.log.append("⏸️ Pausing current download...")
        else:
            self.log.append("⚠️ No active download to pause")

    def stop_download(self):
        if self.worker and self.worker.isRunning():
            self.is_paused = False
            self.paused_job = None
            self.stop_requested = True
            self.worker.stop()
            self.log.append("⛔ Stopping current download...")
        else:
            self.log.append("⚠️ No active download to stop")

    def save_queue(self):
        try:
            data = list(self.queue)

            if self.paused_job:
                paused_copy = dict(self.paused_job)
                paused_copy["status"] = "paused"
                data.insert(0, paused_copy)
            elif self.current_job and not self.stop_requested and not self.is_paused:
                current_copy = dict(self.current_job)
                if current_copy.get("status") != "completed":
                    data.insert(0, current_copy)

            with open(self.queue_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.log.append(f"⚠️ Failed to save queue: {e}")

    def load_queue(self):
        if not os.path.exists(self.queue_file):
            return

        try:
            with open(self.queue_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            cleaned = []
            for job in data:
                status = job.get("status", "queued")
                if status == "completed":
                    continue
                if status == "downloading":
                    job["status"] = "queued"
                job.setdefault("resolution", "Best available")
                cleaned.append(job)

            self.queue = deque(cleaned)
            self.refresh_queue()

            if cleaned:
                self.log.append("🔄 Restored previous queue")
        except Exception as e:
            self.log.append(f"⚠️ Failed to load queue: {e}")

    def add_history(self, job, result):
        try:
            history = []
            if os.path.exists(self.history_file):
                with open(self.history_file, "r", encoding="utf-8") as f:
                    history = json.load(f)

            history.append({
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "url": job.get("url", ""),
                "filename": job.get("filename", ""),
                "subfolder": job.get("subfolder", ""),
                "resolution": job.get("resolution", "Best available"),
                "result": result,
            })

            history = history[-200:]

            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.log.append(f"⚠️ Failed to save history: {e}")

    def show_history(self):
        try:
            if not os.path.exists(self.history_file):
                QMessageBox.information(self, APP_NAME, "No history yet.")
                return

            with open(self.history_file, "r", encoding="utf-8") as f:
                history = json.load(f)

            if not history:
                QMessageBox.information(self, APP_NAME, "No history yet.")
                return

            lines = []
            for item in reversed(history[-30:]):
                name = item.get("filename") or "[auto]"
                res = item.get("resolution", "Best available")
                lines.append(
                    f"{item['time']} | {item['result']} | {name} | {res} | {item['url']}"
                )

            QMessageBox.information(self, APP_NAME, "\n".join(lines))
        except Exception as e:
            self.log.append(f"⚠️ Failed to load history: {e}")

    def export_queue(self):
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Queue",
                os.path.join(APP_DIR, "exported_queue.json"),
                "JSON Files (*.json)"
            )
            if not file_path:
                return

            data = list(self.queue)
            if self.paused_job:
                paused_copy = dict(self.paused_job)
                paused_copy["status"] = "paused"
                data.insert(0, paused_copy)

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            self.log.append(f"📤 Queue exported: {file_path}")
        except Exception as e:
            self.log.append(f"⚠️ Failed to export queue: {e}")

    def import_queue(self):
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Import Queue",
                APP_DIR,
                "JSON Files (*.json)"
            )
            if not file_path:
                return

            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            added = 0
            for job in data:
                if "url" not in job:
                    continue
                job.setdefault("filename", "")
                job.setdefault("subfolder", "")
                job.setdefault("resolution", "Best available")
                job.setdefault("retries_left", int(self.retry_select.currentText()))
                job.setdefault("status", "queued")
                if job["status"] == "completed":
                    continue
                self.queue.append(job)
                added += 1

            self.save_queue()
            self.refresh_queue()
            self.log.append(f"📥 Imported {added} queue item(s)")
        except Exception as e:
            self.log.append(f"⚠️ Failed to import queue: {e}")

    def start_sleep_inhibitor(self):
        if not self.prevent_sleep_checkbox.isChecked():
            return

        if not IS_LINUX:
            return

        if self.sleep_inhibitor and self.sleep_inhibitor.poll() is None:
            return

        systemd_inhibit = shutil.which("systemd-inhibit")
        if not systemd_inhibit:
            self.log.append("⚠️ systemd-inhibit not found; sleep prevention unavailable.")
            return

        try:
            self.sleep_inhibitor = subprocess.Popen(
                [
                    systemd_inhibit,
                    "--why=Downloading videos",
                    "--what=sleep",
                    "--mode=block",
                    "bash", "-c", "while true; do sleep 3600; done"
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self.log.append("🌙 Sleep prevention enabled while downloading.")
        except Exception as e:
            self.sleep_inhibitor = None
            self.log.append(f"⚠️ Failed to enable sleep prevention: {e}")

    def stop_sleep_inhibitor(self):
        if self.sleep_inhibitor and self.sleep_inhibitor.poll() is None:
            try:
                self.sleep_inhibitor.terminate()
                self.sleep_inhibitor.wait(timeout=3)
                self.log.append("🌙 Sleep prevention disabled.")
            except Exception:
                try:
                    self.sleep_inhibitor.kill()
                except Exception:
                    pass
            finally:
                self.sleep_inhibitor = None

    def closeEvent(self, event):
        self.save_queue()
        self.stop_sleep_inhibitor()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = DownloaderApp()
    w.show()
    sys.exit(app.exec())