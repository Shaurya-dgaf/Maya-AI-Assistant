# ❖ MAYA — Iron Man Inspired Desktop AI Assistant (Mark-VII)

> An Iron Man / J.A.R.V.I.S. inspired personal voice assistant featuring automated system boot, a real-time Stark-Tech sci-fi HUD, multimodal screen vision, real-time web search, and persistent memory.

---

## 🌟 Overview

**MAYA** is an intelligent desktop companion designed for hands-free workflow automation, system control, and academic/coding problem-solving. Built to operate like an authentic digital assistant, Maya seamlessly initializes on system boot, coupling a high-performance Python backend with an interactive cyberpunk-styled HTML5/CSS HUD connected via local WebSockets.

---

## 🚀 Key Features

* **⚡ Auto-Boot & Dedicated HUD Launch:**
  * Configured for automated startup on system boot, initializing all voice engines and services in the background.
  * Auto-launches a standalone, dedicated Chrome app window (`--app`) to prevent standard browser tabs from interrupting the HUD.
* **🎙️ Voice Interaction & Bilingual Support:**
  * Background wake-word listening (`"Maya"`).
  * Natural speech output in Hindi & English (via Edge-TTS neural voices with local pyttsx3 fallback).
* **⚡ Dual LLM Pipeline:**
  * Primary: Ultra-fast text inference using **Groq** (`llama-3.3-70b-versatile`).
  * Secondary & Vision: **Google Gemini API** (`gemini-2.5-flash`).
* **👁️ Vision & Screen Solve:**
  * Dedicated global hotkey (`Ctrl + Shift + S`) or natural voice trigger (`"maya screen solve karo"`).
  * In-memory full-screen capture sent directly to Gemini Vision for instant, step-by-step problem-solving.
* **🖥️ Stark-Tech Futuristic HUD:**
  * Animated Arc Reactor core indicator with reactive color states (Idle, Listening, Thinking, Speaking).
  * Real-time radar sweep canvas, live telemetry meters, audio spectrum visualizer, and live transcription subtitles.
* **🧠 Persistent Memory:**
  * Automatically extracts and saves user details, preferences, and session context to local storage (`memory.json`).
* **⚙️ OS & Web Automation:**
  * Voice-controlled application launching (Chrome, Notepad, Spotify, Calculator).
  * Native OS tasks (Shutdown, Volume control, Mute, Full-screen screenshot capture).
  * Headless web search via DuckDuckGo and instant YouTube music playback via `pywhatkit`.

---

## 🛠️ Architecture & Tech Stack

* **Backend Engine:** Python 3.10+
* **Frontend HUD:** HTML5, CSS3 Grid/Animations, Vanilla JavaScript, HTML5 Canvas
* **Real-time Bridge:** WebSockets (`ws://localhost:8765`)
* **AI & Vision Models:** Groq Cloud API, Google Generative AI (Gemini 2.5 Flash)
* **Speech & Audio:** `SpeechRecognition`, `edge-tts`, `pygame`, `pyttsx3`
* **Desktop Automation:** `pyautogui`, `keyboard`, `pynput`, `pywhatkit`

---

## 📂 Project Structure

```text
├── my_jarvis.py       # Core backend engine, automation & hotkey listeners
├── maya_ui.html       # Dedicated Stark-Tech HUD interface
├── .env.example       # Template for API keys
├── requirements.txt   # Python dependency list
└── README.md          # Project documentation
