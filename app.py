import sys
import os
import shutil
import subprocess
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFileDialog, QTextEdit,
    QComboBox, QProgressBar, QMessageBox
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
                self.log_signal.emit(line)

                if "Resuming download" in line:
                    self.log_signal.emit("🔄 Resuming previous download...")

                if "%" in line and "download" in line.lower():
                    try:
                        percent = float(line.split('%')[0].split()[-1])
                        self.progress_signal.emit(int(percent))
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


class DownloaderApp(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.setWindowTitle(f"🔥 {APP_NAME}")
        self.setGeometry(200, 200, 760, 500)
        self.build_ui()
        self.run_startup_checks()

    def build_ui(self):
        layout = QVBoxLayout()

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste video or reel URL here...")
        layout.addWidget(QLabel("Video URL:"))
        layout.addWidget(self.url_input)

        self.filename_input = QLineEdit("")
        self.filename_input.setPlaceholderText("Optional basic filename, e.g. episode 3")
        layout.addWidget(QLabel("Filename:"))
        layout.addWidget(self.filename_input)

        self.subfolder_input = QLineEdit()
        self.subfolder_input.setPlaceholderText("Optional subfolder inside Save to, e.g. Facebook/Reels")
        layout.addWidget(QLabel("Subfolder (optional):"))
        layout.addWidget(self.subfolder_input)

        self.browser_select = QComboBox()
        self.browser_select.addItems(["auto", "chrome", "firefox", "edge", "none"])
        layout.addWidget(QLabel("Cookies (recommended for Facebook):"))
        layout.addWidget(self.browser_select)

        path_layout = QHBoxLayout()
        self.path_input = QLineEdit(self.default_download_path())
        browse_btn = QPushButton("Browse Folder")
        browse_btn.clicked.connect(self.browse_folder)
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(browse_btn)
        layout.addWidget(QLabel("Save to:"))
        layout.addLayout(path_layout)

        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        btn_layout = QHBoxLayout()
        self.download_btn = QPushButton("Download")
        self.download_btn.clicked.connect(self.download_video)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self.stop_download)
        self.show_cmd_btn = QPushButton("Show Command")
        self.show_cmd_btn.clicked.connect(self.show_command_preview)
        btn_layout.addWidget(self.download_btn)
        btn_layout.addWidget(self.stop_btn)
        btn_layout.addWidget(self.show_cmd_btn)
        layout.addLayout(btn_layout)

        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)

        self.setLayout(layout)

    def default_download_path(self):
        if IS_WINDOWS:
            return os.path.join(os.path.expanduser("~"), "Downloads")
        return os.path.join(os.path.expanduser("~"), "Videos")

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.path_input.setText(folder)

    def normalize_url(self, url):
        if "web.facebook.com" in url:
            return url.replace("web.facebook.com", "www.facebook.com")
        return url

    def sanitize_subfolder(self, name):
        name = name.strip().replace("\\", "/").strip("/")
        invalid = '<>:"|?*'
        for ch in invalid:
            name = name.replace(ch, "_")
        return name

    def sanitize_filename_base(self, name):
        name = name.strip()
        invalid = '<>:"/\\|?*'
        for ch in invalid:
            name = name.replace(ch, "_")
        name = "_".join(name.split())
        name = name.strip("._")
        return name

    def get_yt_dlp_path(self):
        local_candidates = [
            os.path.join(APP_DIR, "yt-dlp.exe"),
            os.path.join(APP_DIR, "yt-dlp"),
            os.path.join(APP_DIR, "bin", "yt-dlp.exe"),
            os.path.join(APP_DIR, "bin", "yt-dlp"),
        ]
        for candidate in local_candidates:
            if os.path.exists(candidate):
                return candidate
        return shutil.which("yt-dlp")

    def packaging_hint(self):
        if IS_WINDOWS:
            return (
                "Windows portable build:\n"
                "1. Put yt-dlp.exe beside app.exe or in a bin folder.\n"
                "2. Build on Windows with:\n"
                "   pyinstaller --noconfirm --windowed --onefile app.py\n"
            )
        if IS_LINUX:
            return (
                "Linux portable build:\n"
                "1. Put yt-dlp beside the app or in a bin folder.\n"
                "2. Build a folder app first:\n"
                "   pyinstaller --noconfirm --windowed app.py\n"
                "3. Package that build as an AppImage on Linux.\n"
                "4. AppImage is the best portable format here; it reduces dependency issues.\n"
            )
        return "Package this app on the same OS you want to distribute it on."

    def linux_runtime_hint(self):
        return (
            "If the app fails to start on some Linux systems, missing Qt/X11 runtime libraries may be the cause.\n"
            "For Debian/Ubuntu systems, these usually fix it:\n"
            "sudo apt install libxcb-cursor0 libxkbcommon-x11-0\n"
            "For distribution, prefer AppImage instead of trying to auto-install system packages."
        )

    def run_startup_checks(self):
        yt_dlp = self.get_yt_dlp_path()
        if yt_dlp:
            self.log.append(f"✅ yt-dlp found: {yt_dlp}")
        else:
            self.log.append("⚠️ yt-dlp not found beside the app or in PATH.")
            self.log.append("Place yt-dlp next to this app for a portable build.")

        if IS_LINUX:
            self.log.append("ℹ️ Linux detected. Best portable packaging target: AppImage.")
        elif IS_WINDOWS:
            self.log.append("ℹ️ Windows detected. Best portable packaging target: standalone .exe.")

    def build_command(self):
        url = self.url_input.text().strip()
        path = self.path_input.text().strip()
        filename = self.filename_input.text().strip()
        subfolder = self.subfolder_input.text().strip()
        browser = self.browser_select.currentText()

        if not url:
            return None, None, None

        url = self.normalize_url(url)

        if subfolder:
            subfolder = self.sanitize_subfolder(subfolder)
            path = os.path.join(path, subfolder)

        os.makedirs(path, exist_ok=True)

        yt_dlp = self.get_yt_dlp_path()
        if not yt_dlp:
            return None, None, "yt-dlp not found. Put yt-dlp beside the app or install it in PATH."

        if filename:
            filename = self.sanitize_filename_base(filename)
            if not filename:
                filename = "download"
            filename = f"{filename}.%(ext)s"
        else:
            filename = "%(title)s.%(ext)s"

        output_template = os.path.join(path, filename)
        cmd = [yt_dlp]

        if browser == "auto":
            if "facebook.com" in url:
                cmd += ["--cookies-from-browser", "chrome"]
        elif browser != "none":
            cmd += ["--cookies-from-browser", browser]

        cmd += [
            "--continue",
            "--restrict-filenames",
            "--concurrent-fragments", "5",
            "--buffer-size", "16K",
            "--no-cache-dir",
            "-f", "bv*+ba/b",
            "-o", output_template,
            url,
        ]
        return cmd, path, None

    def show_command_preview(self):
        cmd, _, error = self.build_command()
        if error:
            QMessageBox.warning(self, APP_NAME, error)
            return
        QMessageBox.information(self, APP_NAME, "Command preview:\n\n" + " ".join(cmd))

    def download_video(self):
        cmd, _, error = self.build_command()
        if error:
            QMessageBox.warning(self, APP_NAME, error)
            return

        self.log.append(f"▶ Running: {' '.join(cmd)}\n")
        self.progress.setValue(0)
        self.status_label.setText("Downloading...")
        self.download_btn.setEnabled(False)

        self.worker = DownloadWorker(cmd)
        self.worker.log_signal.connect(self.log.append)
        self.worker.progress_signal.connect(self.progress.setValue)
        self.worker.finished_signal.connect(self.download_finished)
        self.worker.start()

    def download_finished(self, code):
        self.download_btn.setEnabled(True)
        if code == 0:
            self.progress.setValue(100)
            self.status_label.setText("Download completed")
            self.log.append("✅ Download completed")
        else:
            self.status_label.setText("Download failed or stopped")
            self.log.append("⚠️ Download failed or stopped")

    def stop_download(self):
        if self.worker:
            self.worker.stop()
            self.log.append("⛔ Download stopping...")
            self.status_label.setText("Stopping...")


def show_packaging_message():
    message = (
        f"{APP_NAME} startup notes\n\n"
        "For the most portable setup:\n"
        "• Put yt-dlp next to the app executable.\n"
        "• Build Windows on Windows.\n"
        "• Build Linux on Linux and package as AppImage.\n\n"
        "This app intentionally does not auto-install system packages on the user's machine."
    )
    QMessageBox.information(None, APP_NAME, message)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    show_packaging_message()
    window = DownloaderApp()
    window.show()
    sys.exit(app.exec())