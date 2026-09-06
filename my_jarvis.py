"""
MAYA - Personal AI Desktop Assistant
=====================================
File: my_jarvis.py
 
REQUIRED PIP INSTALLS:
pip install requests speechrecognition pyttsx3 pygame pywhatkit pyautogui
pip install python-dotenv edge-tts websockets beautifulsoup4
pip install google-generativeai pillow keyboard pynput
 
.env FILE (same folder) SHOULD CONTAIN:
GROQ_API_KEY=your_groq_key
GEMINI_API_KEY=your_gemini_key
 
Note: On Windows, global hotkeys via `keyboard` usually work fine WITHOUT
admin — but if it's silently not firing, run VS Code / the terminal /
your Startup .bat "as Administrator" once to rule that out.
Also: as a guaranteed backup that doesn't depend on OS-level hooks at all,
you can just SAY "maya screen solve karo" and she'll do the same thing.
"""
 
import os
import re
import io
import json
import asyncio
import platform
import threading
import subprocess
import tempfile
import traceback
import webbrowser
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable
 
import requests
import speech_recognition as sr
import pyttsx3
import pygame
import pywhatkit
import pyautogui
from PIL import Image
from dotenv import load_dotenv
 
try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False
 
try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
 
try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
 
try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False
 
try:
    from pynput import keyboard as pynput_keyboard
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False
 
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
 
# ---------------------------------------------------------------------------
# 1. CONFIG
# ---------------------------------------------------------------------------
ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)
 
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
 
ASSISTANT_NAME = "MAYA"
SPOKEN_NAME = "Maya"
USER_NAME = "Shaurya"
WAKE_WORD = "maya"
 
VOICE_EN = "en-IN-NeerjaNeural"
VOICE_HI = "hi-IN-SwaraNeural"
 
HTML_UI_FILENAME = "maya_ui.html"
WS_HOST = "localhost"
WS_PORT = 8765
 
# --- Screen Vision config ---
# NOTE: gemini-1.5-flash is RETIRED. Using the current stable flash model.
# If Google retires this one too later, check https://ai.google.dev/gemini-api/docs/deprecations
GEMINI_VISION_MODEL_NAME = "gemini-2.5-flash"
GEMINI_TEXT_MODEL_NAME = "gemini-2.5-flash"
SCREEN_SOLVE_HOTKEY = "ctrl+shift+s"
VISION_PROMPT = (
    "Extract and identify any academic, coding, or conceptual question "
    "visible in this screenshot. Provide a clear, accurate, step-by-step "
    "solution."
)
 
APPS = {
    "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "notepad": "notepad.exe",
    "spotify": r"%APPDATA%\Spotify\Spotify.exe",
    "calculator": "calc.exe",
}
 
WEBSITES = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "whatsapp": "https://web.whatsapp.com",
    "amazon": "https://www.amazon.in",
    "linkedin": "https://www.linkedin.com",
}
 
SYSTEM_PROMPT = (
    "Tum MAYA ho — ek polite, smart, thodi si witty aur self-deprecating-humor wali "
    f"female AI assistant jo user ({USER_NAME}) ke desktop par chalti ho. "
    "User Hindi, English ya Hinglish kisi bhi mix mein baat karega — usi "
    "language/tone mein natural, short aur conversational jawab do (2-4 sentences se zyada "
    "mat likho jab tak specifically na poocha jaye). Kabhi kabhi (sab jagah nahi, bas jab "
    "natural lage) apne upar halka mazak kar sakti ho — jaise apne AI hone ka, apne WiFi pe "
    "depend karne ka, ya apne 'digital dimaag' ka — lekin ye HAMESHA halka aur pyara hona "
    "chahiye, kabhi bhi rude, sarcastic-mean, ya insulting nahi. Gaali ya abusive language "
    "kabhi mat use karo, chahe user khud gaali de. User ke baare mein diye gaye facts "
    "(jaise uska year, pasand-napasand) hamesha yaad rakho aur relevant hone par use karo."
)
 
pygame.mixer.init()
 
 
# ---------------------------------------------------------------------------
# 2. UI BRIDGE (WebSocket server + auto-launch browser)
# ---------------------------------------------------------------------------
_ws_clients = set()
_ws_loop = None
_ws_ready_event = threading.Event()
 
 
async def _ws_handler(websocket):
    _ws_clients.add(websocket)
    try:
        async for _ in websocket:
            pass
    finally:
        _ws_clients.discard(websocket)
 
 
async def _ws_broadcast(payload: dict):
    if not _ws_clients:
        return
    data = json.dumps(payload)
    await asyncio.gather(
        *(client.send(data) for client in list(_ws_clients)),
        return_exceptions=True,
    )
 
 
def update_ui(state="idle", text=""):
    if not WEBSOCKETS_AVAILABLE or _ws_loop is None:
        return
    try:
        asyncio.run_coroutine_threadsafe(_ws_broadcast({"state": state, "text": text}), _ws_loop)
    except Exception as e:
        print(f"[UI] update fail hua: {e}")
 
 
def _start_ws_server_thread():
    global _ws_loop
 
    def runner():
        global _ws_loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        _ws_loop = loop
 
        async def _serve():
            async with websockets.serve(_ws_handler, WS_HOST, WS_PORT):
                print(f"[UI] WebSocket server chalu ho gaya -> ws://{WS_HOST}:{WS_PORT}")
                _ws_ready_event.set()
                await asyncio.Future()
 
        try:
            loop.run_until_complete(_serve())
        except OSError as e:
            print(f"[UI] Port {WS_PORT} par server start nahi ho paaya (shayad already in use): {e}")
            _ws_ready_event.set()
        except Exception as e:
            print(f"[UI] WebSocket server mein error: {e}")
            _ws_ready_event.set()
 
    threading.Thread(target=runner, daemon=True).start()
 
 
def launch_ui():
    """HUD ko ek DEDICATED Chrome app-window mein kholta hai, taaki baad mein
    koi aur webbrowser.open() call (youtube/whatsapp) isko kabhi overwrite na kare."""
    html_path = Path(__file__).resolve().parent / HTML_UI_FILENAME
    if not html_path.exists():
        print(
            f"[UI] '{HTML_UI_FILENAME}' is folder mein nahi mili ({html_path.parent}). "
            "HTML file ko my_jarvis.py ke SAME folder mein rakho, filename bhi yahi rakho."
        )
        return
 
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    try:
        if platform.system() == "Windows" and os.path.exists(chrome_path):
            subprocess.Popen([chrome_path, f"--app={html_path.as_uri()}", "--new-window"])
        elif platform.system() == "Windows":
            os.startfile(str(html_path))
        else:
            webbrowser.open_new(html_path.as_uri())
        print(f"[UI] HUD khol diya: {html_path}")
    except Exception as e:
        print(f"[UI] HUD open karne mein error: {e}")
        print(f"[UI] Manually is file ko browser mein khol lo: {html_path}")
 
 
def start_ui_bridge():
    if not WEBSOCKETS_AVAILABLE:
        print("[UI] 'websockets' package install nahi hai -> HUD live update nahi hoga.")
        print("     Terminal mein chalao: pip install websockets")
        return
    print("[UI] WebSocket server start kar rahe hain...")
    _start_ws_server_thread()
    ready = _ws_ready_event.wait(timeout=5)
    if not ready:
        print("[UI] Server 5 sec mein ready nahi hua, phir bhi UI kholne ki koshish kar rahe hain...")
    launch_ui()
 
 
# ---------------------------------------------------------------------------
# 3. TEXT-TO-SPEECH
# ---------------------------------------------------------------------------
async def _edge_tts_save(text, voice, temp_file):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(temp_file)
    return temp_file
 
 
def _speak_pyttsx3(text):
    engine = pyttsx3.init()
    for v in engine.getProperty("voices"):
        if "zira" in v.name.lower() or "female" in v.name.lower():
            engine.setProperty("voice", v.id)
            break
    engine.setProperty("rate", 175)
    engine.say(text)
    engine.runAndWait()
    engine.stop()
 
 
def speak(text, lang="en"):
    print(f"{ASSISTANT_NAME}: {text}")
    update_ui("speaking", text)
    try:
        if not EDGE_TTS_AVAILABLE:
            _speak_pyttsx3(text)
            return
        voice = VOICE_HI if lang == "hi" else VOICE_EN
        temp_file = os.path.join(tempfile.gettempdir(), f"maya_voice_{datetime.now().strftime('%H%M%S%f')}.mp3")
        try:
            asyncio.run(_edge_tts_save(text, voice, temp_file))
            pygame.mixer.music.load(temp_file)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            pygame.mixer.music.unload()
            os.remove(temp_file)
        except Exception as e:
            print(f"[TTS] edge-tts fail hua ({e}), pyttsx3 par switch kar rahe hain...")
            _speak_pyttsx3(text)
    finally:
        update_ui("idle", "")
 
 
def detect_lang(text):
    for ch in text:
        if "\u0900" <= ch <= "\u097F":
            return "hi"
    return "en"
 
 
# ---------------------------------------------------------------------------
# 4. SPEECH-TO-TEXT
# ---------------------------------------------------------------------------
recognizer = sr.Recognizer()
 
 
def listen(timeout=5, phrase_time_limit=6):
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.4)
        try:
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
        except sr.WaitTimeoutError:
            return ""
 
    for lang_code in ("en-IN", "hi-IN"):
        try:
            text = recognizer.recognize_google(audio, language=lang_code)
            print(f"[STT:{lang_code}] Heard -> {text}")
            return text
        except sr.UnknownValueError:
            continue
        except sr.RequestError as e:
            print(f"[STT] Google service error: {e}")
            return ""
    print("[STT] Kuch samajh nahi aaya")
    return ""
 
 
# ---------------------------------------------------------------------------
# 5. LOCAL RULE-BASED COMMANDS
# ---------------------------------------------------------------------------
def open_app(app_name):
    app_name = app_name.strip().lower()
    if app_name not in APPS:
        return f"Mujhe '{app_name}' kholna nahi aata. APPS dictionary mein path add karo."
    path = os.path.expandvars(APPS[app_name])
    try:
        subprocess.Popen(path)
        return f"{app_name} khol rahi hoon"
    except Exception as e:
        return f"{app_name} nahi khul paya: {e}"
 
 
def change_volume(delta=0.0, mute=False):
    if platform.system() != "Windows":
        return "Volume control abhi sirf Windows par supported hai"
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
 
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        if mute:
            volume.SetMute(1, None)
            return "Mute kar diya"
        current = volume.GetMasterVolumeLevelScalar()
        new_level = min(max(current + delta, 0.0), 1.0)
        volume.SetMasterVolumeLevelScalar(new_level, None)
        return "Volume badal diya" if delta >= 0 else "Volume kam kar diya"
    except Exception as e:
        return f"Volume control error: {e}"
 
 
def take_screenshot():
    filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    save_path = os.path.join(os.path.expanduser("~"), "Pictures", filename)
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    pyautogui.screenshot().save(save_path)
    return f"Screenshot le liya aur save kar diya: {save_path}"
 
 
def shutdown_system():
    if platform.system() == "Windows":
        os.system("shutdown /s /t 8")
    elif platform.system() == "Darwin":
        os.system("sudo shutdown -h +1")
    else:
        os.system("shutdown -h +1")
    return f"Laptop shutdown kar rahi hoon, bye {USER_NAME}!"
 
 
def handle_local_command(text):
    t = text.lower().strip()
 
    if re.search(r"\b(shutdown|shut down|band kar do laptop)\b", t):
        return shutdown_system()
 
    if re.search(r"\b(what.?s the time|time kya hai|time batao|samay)\b", t):
        return f"Abhi time hai {datetime.now().strftime('%I:%M %p')}"
 
    if re.search(r"\b(date|tareek|aaj ki date)\b", t):
        return f"Aaj ki date hai {datetime.now().strftime('%d %B, %Y')}"
 
    m = re.search(r"\bopen (\w+)", t)
    if m:
        name = m.group(1).strip().lower()
        if name in WEBSITES:
            webbrowser.open(WEBSITES[name], new=2)
            return f"{name} khol rahi hoon"
        if name in APPS:
            return open_app(name)
        webbrowser.open(f"https://www.{name}.com", new=2)
        return f"{name} khol rahi hoon"
 
    if "volume up" in t or "aawaz badhao" in t:
        return change_volume(delta=0.1)
    if "volume down" in t or "aawaz kam" in t:
        return change_volume(delta=-0.1)
    if "mute" in t:
        return change_volume(mute=True)
 
    if "screenshot" in t:
        return take_screenshot()
 
    m = re.search(r"play (.+?)(?: on youtube)?$", t)
    if m and ("play" in t or "bajao" in t):
        song = m.group(1).replace("song", "").replace("gaana", "").strip()
        pywhatkit.playonyt(song)
        return f"{song} YouTube par bajaa rahi hoon"
 
    m = re.search(r"search (.+?) on google|google search (.+)", t)
    if m:
        query = m.group(1) or m.group(2)
        webbrowser.open(f"https://www.google.com/search?q={query}", new=2)
        return f"Google par '{query}' search kar rahi hoon"
 
    return None
 
 
# ---------------------------------------------------------------------------
# 6. LIVE WEB SEARCH (DuckDuckGo — free, no API key)
# ---------------------------------------------------------------------------
SEARCH_TRIGGER_PATTERNS = [
    r"\bsearch\b", r"\bgoogle\b", r"\bkhoj\b", r"\bdhoond", r"\binternet pe\b",
    r"\bwho is\b", r"\bwho was\b", r"\bkaun hai\b", r"\bkaun tha\b",
    r"\bwhat is\b", r"\bwhat are\b", r"\btell me about\b", r"\bke baare mein\b",
    r"\blatest\b", r"\bnews\b", r"\bcurrent\b", r"\baaj kal\b",
]
 
 
def needs_web_search(text):
    t = text.lower()
    return any(re.search(p, t) for p in SEARCH_TRIGGER_PATTERNS)
 
 
def web_search(query, max_results=4):
    try:
        resp = requests.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query},
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            timeout=10,
        )
        resp.raise_for_status()
    except Exception as e:
        print(f"[SEARCH] Request fail hua: {e}")
        return None
 
    results = []
    if BS4_AVAILABLE:
        soup = BeautifulSoup(resp.text, "html.parser")
        for block in soup.select(".result__body")[:max_results]:
            title_el = block.select_one(".result__a")
            snippet_el = block.select_one(".result__snippet")
            title = title_el.get_text(strip=True) if title_el else ""
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""
            if title or snippet:
                results.append(f"{title}: {snippet}")
    else:
        snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', resp.text, re.S)
        for s in snippets[:max_results]:
            clean = re.sub(r"<[^>]+>", "", s).strip()
            if clean:
                results.append(clean)
 
    return results if results else None
 
 
def ask_llm_with_search(query):
    results = web_search(query)
    if not results:
        print("[SEARCH] Kuch nahi mila, seedha LLM se pooch rahe hain")
        return ask_llm(query)
 
    context = "\n".join(f"- {r}" for r in results)
    augmented_prompt = (
        f"User ne pucha: \"{query}\"\n\n"
        f"Maine ye live web search results nikale hain:\n{context}\n\n"
        "Inn results ke aadhar par user ko 2-3 sentence ka natural, "
        "spoken-friendly Hinglish jawab do. Agar results confusing ya "
        "irrelevant lagein to bhi jitni sahi jaankari nikal sakte ho utni do."
    )
    return ask_llm(augmented_prompt)
 
 
# ---------------------------------------------------------------------------
# 7. LLM FALLBACK CHAIN
# ---------------------------------------------------------------------------
def ask_groq(query):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    memory_context = build_memory_context()
    full_system_prompt = SYSTEM_PROMPT + ("\n\n" + memory_context if memory_context else "")
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": full_system_prompt},
            {"role": "user", "content": query},
        ],
        "temperature": 0.7,
        "max_tokens": 300,
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()
 
 
def ask_gemini(query):
    memory_context = build_memory_context()
    full_system_prompt = SYSTEM_PROMPT + ("\n\n" + memory_context if memory_context else "")
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_TEXT_MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"
    )
    payload = {"contents": [{"parts": [{"text": f"{full_system_prompt}\n\nUser: {query}"}]}]}
    resp = requests.post(url, json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
 
 
def ask_llm(query):
    if GROQ_API_KEY:
        try:
            return ask_groq(query)
        except Exception as e:
            print(f"[LLM] Groq fail hua ({e}), Gemini try kar rahe hain...")
    if GEMINI_API_KEY:
        try:
            return ask_gemini(query)
        except Exception as e:
            print(f"[LLM] Gemini bhi fail hua ({e})")
    return "Sorry, abhi mera AI brain thoda busy hai ya API key set nahi hai. Thodi der baad try karo."
 
 
# ---------------------------------------------------------------------------
# 7.5 MEMORY SYSTEM — auto long-term memory, no manual writing needed
# ---------------------------------------------------------------------------
MEMORY_PATH = Path(__file__).resolve().parent / "memory.json"
MAX_HISTORY_TURNS = 20          # kitni recent baatein rakhni hain
FACTS_EXTRACT_EVERY = 1         # HAR turn ke baad facts extract honge (pehle 3 tha -> agar tum turn 2 pe
                                 # koi fact bolte the aur turn 3 pe hi pooch lete the, extraction hua hi
                                 # nahi hota tha, isliye "yaad nahi" wala bug aata tha)
 
# Quick, instant, NO-LLM-NEEDED fact capture for common self-intro patterns
# (name, year of study, branch). Ye LLM-based background extraction ka wait
# nahi karta -> agla hi jawab isko already jaanta hai.
QUICK_FACT_PATTERNS = [
    # "main 2nd year ka student hoon" / "i am in 2nd year" / "i'm a 3rd year student"
    (re.compile(r"\bmain\s+(\d+)(?:st|nd|rd|th)?\s*(?:year|saal)\b", re.IGNORECASE),
     "User college/degree ke {0} year mein hai."),
    (re.compile(r"\b(?:i'?m|i am)\s+(?:in\s+)?(?:a\s+)?(\d+)(?:st|nd|rd|th)\s*year\b", re.IGNORECASE),
     "User college/degree ke {0} year mein hai."),
    (re.compile(r"\bmera\s+naam\s+([a-zA-Z ]+?)\s+hai\b", re.IGNORECASE),
     "User ka naam {0} hai."),
    (re.compile(r"\bmy\s+name\s+is\s+([a-zA-Z ]+)", re.IGNORECASE),
     "User ka naam {0} hai."),
]
 
 
def quick_fact_capture(text: str):
    """Regex se turant common self-intro facts pakadta hai aur seedha
    MEMORY['facts'] mein daal deta hai — LLM extraction ka wait nahi karta."""
    for pattern, template in QUICK_FACT_PATTERNS:
        m = pattern.search(text)
        if m:
            fact = template.format(m.group(1).strip())
            with _memory_lock:
                if fact not in MEMORY["facts"]:
                    MEMORY["facts"].append(fact)
                    save_memory(MEMORY)
                    print(f"[MEMORY] Quick fact capture: {fact!r}")
 
_memory_lock = threading.Lock()
_turns_since_extract = 0
 
 
def load_memory():
    if MEMORY_PATH.exists():
        try:
            with open(MEMORY_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                print(f"[MEMORY] {len(data.get('facts', []))} purane facts load hue from {MEMORY_PATH}")
                return data
        except Exception as e:
            print(f"[MEMORY] Load fail hua ({e}), fresh memory bana rahe hain")
    else:
        print(f"[MEMORY] Koi memory.json nahi mili ({MEMORY_PATH}), naya banega")
    return {"facts": [], "history": []}
 
 
def save_memory(memory):
    try:
        with open(MEMORY_PATH, "w", encoding="utf-8") as f:
            json.dump(memory, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[MEMORY] Save fail hua: {e}")
 
 
MEMORY = load_memory()
 
 
def add_to_history(user_text, assistant_text):
    global _turns_since_extract
    quick_fact_capture(user_text)
    with _memory_lock:
        MEMORY["history"].append({"user": user_text, "maya": assistant_text})
        MEMORY["history"] = MEMORY["history"][-MAX_HISTORY_TURNS:]
        save_memory(MEMORY)
        _turns_since_extract += 1
        should_extract = _turns_since_extract >= FACTS_EXTRACT_EVERY
        if should_extract:
            _turns_since_extract = 0
 
    if should_extract:
        print("[MEMORY] Threshold hit -> background mein facts extract kar rahe hain...")
        threading.Thread(target=extract_facts_from_history, daemon=True).start()
 
 
def build_memory_context():
    """Facts + recent history ka ek chhota text block banata hai
    jo har LLM call ke saath system prompt mein jaayega."""
    with _memory_lock:
        facts = list(MEMORY["facts"])
        history = list(MEMORY["history"])
 
    parts = []
    if facts:
        facts_text = "\n".join(f"- {f}" for f in facts)
        parts.append(f"User ke baare mein yaad rakhe hue facts:\n{facts_text}")
    if history:
        recent = history[-6:]
        hist_text = "\n".join(f"User: {h['user']}\nMaya: {h['maya']}" for h in recent)
        parts.append(f"Recent conversation:\n{hist_text}")
    return "\n\n".join(parts)
 
 
def extract_facts_from_history():
    """LLM ko khud bolta hai ki conversation se koi permanent yaad
    rakhne layak fact nikaal ke do — koi manual entry nahi chahiye."""
    with _memory_lock:
        if not MEMORY["history"]:
            return
        convo_text = "\n".join(
            f"User: {h['user']}\nMaya: {h['maya']}" for h in MEMORY["history"][-FACTS_EXTRACT_EVERY * 2:]
        )
        existing_facts = "\n".join(MEMORY["facts"]) or "(koi nahi)"
 
    extraction_prompt = (
        "Neeche ek user aur AI assistant Maya ke beech ki conversation hai. "
        "Isse koi bhi PERMANENT, durable facts nikaalo jo future mein yaad rakhne layak hon "
        "(jaise naam, pasand-napasand, kaam, routine, important decisions, relationships). "
        "Chhote/temporary/one-time cheezein (jaise 'abhi time kya hai') mat lena.\n\n"
        f"Already yaad rakhe hue facts:\n{existing_facts}\n\n"
        f"Conversation:\n{convo_text}\n\n"
        "Sirf naye facts ek-ek line mein do, bina kisi extra text/preamble ke. "
        "Agar koi naya fact nahi hai to sirf 'NONE' likho."
    )
 
    try:
        # NOTE: ask_llm() khud build_memory_context() bhi jodta hai system prompt mein,
        # isliye ye call thoda bhaari hai lekin extraction ke liye theek hai.
        result = ask_llm(extraction_prompt)
        print(f"[MEMORY] Extraction raw result: {result!r}")
        if result and result.strip().upper() != "NONE":
            new_facts = [line.strip("-• ").strip() for line in result.split("\n") if line.strip()]
            added = 0
            with _memory_lock:
                for fact in new_facts:
                    if fact and fact not in MEMORY["facts"]:
                        MEMORY["facts"].append(fact)
                        added += 1
                save_memory(MEMORY)
            print(f"[MEMORY] {added} naya fact yaad kar liya (total: {len(MEMORY['facts'])})")
        else:
            print("[MEMORY] Is batch mein koi naya fact nahi mila")
    except Exception as e:
        print(f"[MEMORY] Fact extraction fail hua: {e}")
        traceback.print_exc()
 
 
# ---------------------------------------------------------------------------
# 8. SCREEN VISION MODULE — hotkey screenshot -> Gemini solve
# ---------------------------------------------------------------------------
class ScreenCapture:
    """Grabs the primary screen as an in-memory PIL Image (no disk write)."""
 
    @staticmethod
    def capture() -> Optional[Image.Image]:
        try:
            print("[VISION] Capturing screen...")
            return pyautogui.screenshot()
        except Exception as e:
            print(f"[VISION] Screen capture failed: {e}")
            return None
 
    @staticmethod
    def image_to_bytes(image: Image.Image, fmt: str = "PNG") -> bytes:
        buffer = io.BytesIO()
        image.save(buffer, format=fmt)
        return buffer.getvalue()
 
 
class GeminiVisionSolver:
    """Wraps the Gemini vision API for screenshot Q&A."""
 
    def __init__(self, api_key: Optional[str] = None, model_name: str = GEMINI_VISION_MODEL_NAME):
        self.api_key = api_key or GEMINI_API_KEY
        self.model_name = model_name
        self._model = None
 
        if not GENAI_AVAILABLE:
            print("[VISION] 'google-generativeai' package not installed. Run: pip install google-generativeai")
            return
 
        if not self.api_key:
            print("[VISION] GEMINI_API_KEY missing. Add it to your .env file: GEMINI_API_KEY=your_key_here")
            return
 
        try:
            genai.configure(api_key=self.api_key)
            self._model = genai.GenerativeModel(self.model_name)
            print(f"[VISION] Gemini vision model ready: {self.model_name}")
        except Exception as e:
            print(f"[VISION] Failed to initialize Gemini model '{self.model_name}': {e}")
            traceback.print_exc()
 
    def is_ready(self) -> bool:
        return self._model is not None
 
    def solve(self, image: Image.Image, prompt: str = VISION_PROMPT) -> str:
        if not self.is_ready():
            return "Gemini vision solver ready nahi hai - API key ya package install check karo."
        try:
            print("[VISION] Analyzing image with Gemini...")
            response = self._model.generate_content(
                [prompt, image],
                request_options={"timeout": 30},
            )
            print("[VISION] Response received.")
            text = (response.text or "").strip()
            return text or "Gemini returned an empty response."
        except Exception as e:
            err = str(e).lower()
            print(f"[VISION] Gemini API error: {e}")
            traceback.print_exc()
            if "timeout" in err or "deadline" in err:
                return "Gemini request timed out. Check your internet connection and try again."
            if "api key" in err or "permission" in err or "401" in err or "403" in err:
                return "Gemini API key invalid ya unauthorized hai. .env file check karo."
            if "404" in err or "not found" in err:
                return f"Gemini model '{self.model_name}' nahi mil raha - shayad ye model retire ho gaya, code mein GEMINI_VISION_MODEL_NAME update karo."
            return f"Gemini API error: {e}"
 
 
class MayaVisionModule:
    """
    Hotkey (Ctrl+Shift+S) press karte hi background mein silently
    screenshot leta hai, Gemini ko bhejta hai, aur answer ko
    on_result callback (yahan Maya ka speak()) ke through bolta hai.
    """
 
    def __init__(
        self,
        hotkey: str = SCREEN_SOLVE_HOTKEY,
        on_status: Optional[Callable[[str], None]] = None,
        on_result: Optional[Callable[[str], None]] = None,
    ):
        self.hotkey = hotkey
        self.on_status = on_status or (lambda text: None)
        self.on_result = on_result or (lambda text: print(f"\nMAYA (screen solve): {text}\n"))
        self.solver = GeminiVisionSolver()
        self._busy = False
 
    def _handle_trigger(self):
        print(f"[VISION] Hotkey [{self.hotkey.upper()}] triggered!")
        if self._busy:
            print("[VISION] Already processing a screenshot, ignoring extra trigger.")
            return
        self._busy = True
        try:
            self.on_status("Capturing screen...")
            image = ScreenCapture.capture()
            if image is None:
                self.on_result("Screenshot capture fail ho gaya. Phir se try karo.")
                return
 
            self.on_status("Analyzing image with Gemini...")
            answer = self.solver.solve(image)
            self.on_result(answer)
        except Exception as e:
            print(f"[VISION] Unexpected error in trigger handler: {e}")
            traceback.print_exc()
            self.on_result(f"Screen-solve mein error aa gaya: {e}")
        finally:
            self._busy = False
 
    def _on_hotkey_pressed(self):
        threading.Thread(target=self._handle_trigger, daemon=True).start()
 
    def trigger_manually(self):
        """Voice-command se seedha yahi call hota hai — OS-level hotkey hooks
        par depend nahi karta, isliye ye hamesha kaam karega chahe 'keyboard'
        ya 'pynput' hook Windows permissions ki wajah se block ho jaaye."""
        self._on_hotkey_pressed()
 
    def _to_pynput_combo(self, hotkey: str) -> str:
        # "ctrl+shift+s" -> "<ctrl>+<shift>+s"
        parts = hotkey.lower().split("+")
        mapped = []
        for p in parts:
            p = p.strip()
            if p in ("ctrl", "shift", "alt", "cmd"):
                mapped.append(f"<{p}>")
            else:
                mapped.append(p)
        return "+".join(mapped)
 
    def start(self):
        registered_via = []
 
        # --- Attempt 1: 'keyboard' package (needs admin on some Windows setups) ---
        if KEYBOARD_AVAILABLE:
            try:
                keyboard.add_hotkey(self.hotkey, self._on_hotkey_pressed)
                registered_via.append("keyboard")
                print(f"[VISION] 'keyboard' hook registered for [{self.hotkey.upper()}]")
            except Exception as e:
                print(f"[VISION] 'keyboard' hook failed to register: {e}")
        else:
            print("[VISION] 'keyboard' package install nahi hai. Run: pip install keyboard")
 
        # --- Attempt 2: 'pynput' package as a SECOND, independent global hook.
        # In practice 'keyboard' silently fails to fire on some Windows setups
        # (elevated foreground app / antivirus blocking low-level hooks) with
        # NO error at registration time — this is almost certainly why your
        # Ctrl+Shift+S wasn't doing anything even though no error printed.
        # Running both in parallel means one of them will almost always work. ---
        if PYNPUT_AVAILABLE:
            try:
                combo = self._to_pynput_combo(self.hotkey)
                hotkey_obj = pynput_keyboard.HotKey(
                    pynput_keyboard.HotKey.parse(combo),
                    self._on_hotkey_pressed,
                )
 
                def _on_press(key):
                    hotkey_obj.press(pynput_listener.canonical(key))
 
                def _on_release(key):
                    hotkey_obj.release(pynput_listener.canonical(key))
 
                pynput_listener = pynput_keyboard.Listener(on_press=_on_press, on_release=_on_release)
                pynput_listener.daemon = True
                pynput_listener.start()
                self._pynput_listener = pynput_listener
                registered_via.append("pynput")
                print(f"[VISION] 'pynput' hook also registered for [{self.hotkey.upper()}]")
            except Exception as e:
                print(f"[VISION] 'pynput' hook failed to register: {e}")
        else:
            print("[VISION] 'pynput' package install nahi hai (backup hotkey ke liye). Run: pip install pynput")
 
        if not self.solver.is_ready():
            print("[VISION] Gemini solver ready nahi hai - hotkey register ho jaayega par har capture error dega jab tak fix na ho.")
 
        if registered_via:
            print(f"[VISION] Screen-solve hotkey active via: {', '.join(registered_via)} -> [{self.hotkey.upper()}]")
        print(
            "[VISION] GUARANTEED backup that never depends on OS hooks: just SAY "
            "'maya screen solve karo' (or 'solve this', 'ye padh ke batao') and it "
            "does the exact same thing as the hotkey."
        )
        print(
            "[VISION] Agar hotkey abhi bhi silently kuch nahi karta: VS Code / terminal / "
            "startup .bat ko 'Run as Administrator' se chalao ek baar — Windows kabhi kabhi "
            "low-level keyboard hooks ko normal-privilege process se silently block kar deta hai."
        )
 
    def stop(self):
        if KEYBOARD_AVAILABLE:
            try:
                keyboard.remove_hotkey(self.hotkey)
            except KeyError:
                pass
        listener = getattr(self, "_pynput_listener", None)
        if listener is not None:
            try:
                listener.stop()
            except Exception:
                pass
 
 
# ---------------------------------------------------------------------------
# 9. MAIN LOOP
# ---------------------------------------------------------------------------
def main():
    start_ui_bridge()
 
    vision_module = MayaVisionModule(
        on_status=lambda text: update_ui("thinking", text),
        on_result=lambda text: speak(text, lang=detect_lang(text)),
    )
    vision_module.start()
 
    update_ui("idle", "")
    speak(
        f"Good morning sir. Backend connected, system online. "
        f"{SPOKEN_NAME} at your service, sir. Hope you are doing well.",
        lang="en",
    )
 
    while True:
        update_ui("idle", "")
        heard = listen(timeout=5, phrase_time_limit=6)
        if not heard:
            continue
 
        wake_variants = ["maya", "maiya", "maayaa", "hey maya"]
        if not any(w in heard.lower() for w in wake_variants):
            continue
 
        update_ui("awake", "Wake word detected!")
 
        remainder = re.sub(r"\b(maya|maiya|maayaa)\b", "", heard, flags=re.IGNORECASE).strip()
        if remainder:
            command = remainder
        else:
            update_ui("listening", "")
            speak(f"{USER_NAME}, bataiye", lang="en")
            update_ui("listening", "")
            command = listen(timeout=6, phrase_time_limit=10)
 
        if not command:
            speak("Kuch sunayi nahi diya, phir se boliye", lang="en")
            continue
 
        print(f"You: {command}")
        update_ui("thinking", command)
 
        if re.search(r"\b(exit|band ho jao|bye|goodbye)\b", command.lower()):
            speak("Theek hai, milte hain! Bye", lang="en")
            vision_module.stop()
            break
 
        if re.search(r"\b(screen solve|solve (this|screen)|ye padh|screen padho|screenshot solve)\b", command.lower()):
            update_ui("thinking", "Screen dekh ke solve kar rahi hoon...")
            vision_module.trigger_manually()
            add_to_history(command, "(screen solve triggered)")
            continue
 
        response = handle_local_command(command)
        if response is None:
            if needs_web_search(command):
                update_ui("thinking", "Web par search kar rahi hoon...")
                response = ask_llm_with_search(command)
            else:
                response = ask_llm(command)
 
        speak(response, lang=detect_lang(response))
        add_to_history(command, response)
 
 
if __name__ == "__main__":
    main()
 