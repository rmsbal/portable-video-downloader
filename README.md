# 🚀 Smart Video Downloader

A cross-platform desktop application built with **PySide6 + yt-dlp** that allows you to download videos (especially Facebook reels) easily with a clean GUI.

---

## ✨ Features

- 🎥 Download videos from Facebook and other supported platforms  
- 🔐 Automatic cookie handling (fixes Facebook reel/ad issues)  
- 📂 Custom save folder support  
- 📝 Simple filename input (auto-formatted safely)  
- 📊 Real-time download progress  
- ⛔ Stop download anytime  
- 🌐 Cross-platform (Linux + Windows)  
- 📦 Portable-ready (AppImage / EXE)  

---

## 🧠 How It Works

The app uses:

- Python + PySide6 → GUI  
- yt-dlp → video extraction & download  
- Browser cookies → to access protected videos  

---

## ⚙️ Installation (Development)

```bash
git clone https://github.com/yourusername/smart-video-downloader.git
cd smart-video-downloader

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
python app.py
