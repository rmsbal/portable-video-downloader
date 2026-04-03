# 🚀 Smart Video Downloader

A cross-platform desktop application built with **PySide6 + yt-dlp** that allows you to download videos easily from multiple platforms (including Facebook and YouTube) using a clean and user-friendly interface.

---

## 🎯 Why This App is Useful

Downloading videos—especially from platforms like Facebook—can be frustrating:

- 🔐 Some videos require login (groups, reels, private content)
- ⚠️ Wrong videos (ads or previews) are sometimes downloaded
- 🧑‍💻 Command-line tools like `yt-dlp` are powerful but not beginner-friendly

👉 **This app solves these problems by:**
- Automatically using browser cookies (for correct video access)
- Providing a simple GUI (no terminal needed)
- Handling filenames, folders, and formats safely

---

## ✨ Features

- 🎥 Download videos from multiple platforms  
- 🔐 Automatic cookie handling (fixes Facebook reel/ad issues)  
- 📂 Custom save folder + subfolder support  
- 📝 Simple filename input (auto-cleaned & formatted)  
- 📊 Real-time download progress  
- ⛔ Stop download anytime  
- 🌐 Cross-platform (Linux + Windows)  
- 📦 Portable-ready (AppImage / EXE)  

---

## 🌐 Supported Platforms

This app uses **yt-dlp**, which supports many websites including:

- YouTube  
- Facebook (Reels, Videos, Groups)  
- Instagram  
- TikTok  
- Twitter (X)  
- and many more  

> ⚠️ Some platforms (like Facebook) require login — handled automatically using browser cookies.

---

## 🧠 How It Works

- **PySide6 (Qt)** → GUI  
- **yt-dlp** → video download engine  
- **Browser cookies** → access private/logged-in content  

👉 Example:  
When downloading a Facebook reel, the app uses your browser session to ensure the **correct video is downloaded (not ads).**

---

## 📌 Common Use Cases

- 📱 Save Facebook reels for offline viewing  
- 🎓 Download educational YouTube videos  
- 🗂️ Archive important content  
- 📡 Use a GUI instead of command-line tools  

---

## ⚙️ Installation (Development)

```bash
git clone https://github.com/yourusername/smart-video-downloader.git
cd smart-video-downloader

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
python app.py
