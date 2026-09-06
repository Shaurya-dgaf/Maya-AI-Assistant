# ❖ MAYA — Iron Man Inspired Desktop AI Assistant (Mark-VII)

> An Iron Man / J.A.R.V.I.S. inspired personal voice assistant featuring a real-time Stark-Tech sci-fi HUD interface, multimodal screen vision, real-time web search, and long-term memory.

---

## 🌟 Overview

**MAYA** is an intelligent desktop companion designed to manage tasks through voice commands and hotkeys. The project couples a high-performance Python backend with an interactive cyberpunk-styled HTML5/CSS HUD connected via WebSockets for zero-latency telemetry and state tracking.

---

## 🚀 Key Features

* **🎙️ Voice Interaction & Bilingual Support:**
  * Wake-word detection (`"Maya"`).
  * Natural speech response in both Hindi & English (via Edge-TTS & pyttsx3 fallback).
* **⚡ Dual LLM Pipeline:**
  * Primary: High-speed inference using **Groq** (`llama-3.3-70b-versatile`).
  * Fallback & Vision: **Google Gemini API** (`gemini-2.5-flash`).
* **👁️ Vision & Screen Solve:**
  * Dedicated global hotkey (`Ctrl + Shift + S`) or voice command (`"maya screen solve karo"`).
  * Captures active screen in-memory and passes it to Gemini Vision to solve questions or debug code step-by-step.
* **🖥️ Stark-Tech Futuristic HUD:**
  * Animated Arc Reactor core indicator with reactive color states (Idle, Listening, Thinking, Speaking).
  * Radar canvas sweep, dynamic telemetry bars, audio spectrum visualizer, and live subtitles.
* **🧠 Persistent Memory:**
  * Remembers user facts, habits, and preferences across sessions using a local `memory.json` store.
* **⚙️ OS & Web Automation:**
  * Application control (Chrome, Notepad, Spotify, Calculator).
  * System operations (Shutdown, Mute, Volume adjustments, Screenshot capture).
  * Live web search via DuckDuckGo (no extra API key needed).
  * YouTube playback automation via `pywhatkit`.

---

## 🛠️ Architecture & Tech Stack

* **Backend:** Python 3.10+
* **Frontend HUD:** HTML5, CSS3 Grid/Animations, Vanilla JavaScript, HTML5 Canvas
* **Real-time Bridge:** WebSockets (Port: `8765`)
* **AI & Vision:** Groq API, Google Generative AI (Gemini 2.5 Flash)
* **Audio & Speech:** `SpeechRecognition`, `edge-tts`, `pygame`, `pyttsx3`
* **Automation:** `pyautogui`, `keyboard`, `pynput`, `pywhatkit`

---

## 📂 Project Structure

```text
├── my_jarvis.py       # Core backend engine & agent logic
├── maya_ui.html       # Stark Tech HUD interface
├── .env.example       # Template for required API keys
├── requirements.txt   # Python dependency list
└── README.md          # Project documentation
