import sys
import os
import subprocess
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFileDialog, QTextEdit,
    QComboBox, QProgressBar
)
from PySide6.QtCore import QThread, Signal

# -------------------- Worker Thread --------------------
class DownloadWorker(QThread):
    log_signal = Signal(str)
    progress_signal = Signal(int)

    def __init__(self, cmd):
        super().__init__()
        self.cmd = cmd

    def run(self):
        try:
            process = subprocess.Popen(self.cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in process.stdout:
                line = line.strip()
                self.log_signal.emit(line)

                # Extract progress percentage
                if "%" in line and "download" in line.lower():
                    try:
                        percent = float(line.split('%')[0].split()[-1])
                        self.progress_signal.emit(int(percent))
                    except:
                        pass
        except Exception as e:
            self.log_signal.emit(f"❌ Error: {e}")

# -------------------- Main App --------------------
class DownloaderApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🔥 Smart Video Downloader (yt-dlp)")
        self.setGeometry(200, 200, 700, 420)

        layout = QVBoxLayout()

        # URL
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste video/reel URL here...")
        layout.addWidget(QLabel("Video URL:"))
        layout.addWidget(self.url_input)

        # Filename
        self.filename_input = QLineEdit("%(title)s.%(ext)s")
        self.filename_input.setPlaceholderText("Example: episode_3.%(ext)s or %(title)s.%(ext)s")
        layout.addWidget(QLabel("Filename:"))
        layout.addWidget(self.filename_input)

        # Optional subfolder name
        self.subfolder_input = QLineEdit()
        self.subfolder_input.setPlaceholderText("Optional subfolder inside Save to, e.g. Facebook/Reels")
        layout.addWidget(QLabel("Subfolder (optional):"))
        layout.addWidget(self.subfolder_input)

        # Browser cookies
        self.browser_select = QComboBox()
        self.browser_select.addItems(["auto", "chrome", "firefox", "edge", "none"])
        layout.addWidget(QLabel("Cookies (recommended for Facebook):"))
        layout.addWidget(self.browser_select)

        # Path
        path_layout = QHBoxLayout()
        self.path_input = QLineEdit(os.path.expanduser("~/Videos"))
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_folder)
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(browse_btn)
        layout.addWidget(QLabel("Save to:"))
        layout.addLayout(path_layout)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        # Buttons
        btn_layout = QHBoxLayout()
        self.download_btn = QPushButton("Download")
        self.download_btn.clicked.connect(self.download_video)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self.stop_download)
        btn_layout.addWidget(self.download_btn)
        btn_layout.addWidget(self.stop_btn)
        layout.addLayout(btn_layout)

        # Log
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)

        self.setLayout(layout)
        self.worker = None

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.path_input.setText(folder)

    def normalize_url(self, url):
        if "web.facebook.com" in url:
            return url.replace("web.facebook.com", "www.facebook.com")
        return url

    def get_yt_dlp_path(self):
        local_path = os.path.join(os.path.dirname(__file__), "yt-dlp")
        if os.path.exists(local_path):
            return local_path
        return "yt-dlp"

    def sanitize_subfolder(self, name):
        name = name.strip().replace('\\', '/').strip('/')
        invalid = '<>:"|?*'
        for ch in invalid:
            name = name.replace(ch, '_')
        return name

    def download_video(self):
        url = self.url_input.text().strip()
        path = self.path_input.text().strip()
        filename = self.filename_input.text().strip()
        subfolder = self.subfolder_input.text().strip()
        browser = self.browser_select.currentText()

        if not url:
            self.log.append("❌ Please enter a URL")
            return

        url = self.normalize_url(url)

        if not filename:
            filename = "%(title)s.%(ext)s"

        if subfolder:
            subfolder = self.sanitize_subfolder(subfolder)
            path = os.path.join(path, subfolder)

        os.makedirs(path, exist_ok=True)

        yt_dlp = self.get_yt_dlp_path()
        output_template = os.path.join(path, filename)

        cmd = [yt_dlp]

        # Smart cookie handling
        if browser == "auto":
            if "facebook.com" in url:
                cmd += ["--cookies-from-browser", "chrome"]
        elif browser != "none":
            cmd += ["--cookies-from-browser", browser]

        cmd += [
            "--force-overwrites",
            "--restrict-filenames",
            "-o", output_template,
            url
        ]

        self.log.append(f"▶ Running: {' '.join(cmd)}\n")
        self.progress.setValue(0)

        self.worker = DownloadWorker(cmd)
        self.worker.log_signal.connect(self.log.append)
        self.worker.progress_signal.connect(self.progress.setValue)
        self.worker.start()

    def stop_download(self):
        if self.worker:
            self.worker.terminate()
            self.log.append("⛔ Download stopped")

# -------------------- Run App --------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DownloaderApp()
    window.show()
    sys.exit(app.exec())
