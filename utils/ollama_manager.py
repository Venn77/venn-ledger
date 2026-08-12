import os, sys, subprocess, atexit, json, urllib.request, urllib.error
from typing import Optional


_ollama_process: Optional[subprocess.Popen] = None


def is_ollama_running() -> bool:
    """Pings the default Ollama local port to see if the engine is already active."""
    try:
        urllib.request.urlopen("http://127.0.0.1:11434/", timeout=0.5)
        return True
    except (urllib.error.URLError, OSError):
        return False

def start_ollama_daemon():
    """
    Silently starts the Ollama daemon in the background if it isn't already running.
    Handles Steam Deck specifics (custom path, AMD iGPU flags) and detaches the process.
    """
    global _ollama_process
    if _ollama_process is not None or is_ollama_running():
        return

    env = os.environ.copy()
    env["OLLAMA_IGPU_ENABLE"] = "1"

    try:
        if sys.platform == "win32":
            _ollama_process = subprocess.Popen(
                ["ollama", "serve"],
                env=env,
                creationflags=subprocess.CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        else:
            deck_binary = os.path.expanduser("~/.local/bin/ollama")
            cmd = [deck_binary, "serve"] if os.path.exists(deck_binary) else ["ollama", "serve"]

            _ollama_process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
    except (FileNotFoundError, OSError):
        pass

def stop_ollama_daemon():
    """Unloads the AI model from VRAM and terminates the background daemon if we started it."""
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:11434/api/generate",
            data=json.dumps({"model": "mistral:7b", "keep_alive": 0}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5.0) as response:
            _ = response.read()
    except (urllib.error.URLError, OSError):
        pass

    global _ollama_process
    if _ollama_process is not None:
        try:
            if sys.platform == "win32":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(_ollama_process.pid)],
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            else:
                _ollama_process.terminate()
        except OSError:
            pass
        _ollama_process = None


atexit.register(stop_ollama_daemon)


