"""
desktop_app.py
==============
Wraps the CV Extractor Streamlit app in a native Chrome App window.
This is more reliable on Windows than pywebview as it uses your installed browser.
"""

import subprocess
import sys
import time
import os
import logging
from pathlib import Path

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_FILE = Path(__file__).parent / "desktop_app.log"
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    filemode="w"
)
logger = logging.getLogger("DesktopApp")

APP_DIR  = Path(__file__).parent
PORT     = 8501
URL      = f"http://localhost:{PORT}"
TITLE    = "CV Extractor"

CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
]

def _find_chrome():
    for p in CHROME_PATHS:
        if os.path.exists(p):
            return p
    return None

def _start_streamlit() -> subprocess.Popen:
    """Launch Streamlit server as a background subprocess."""
    python = sys.executable
    logger.info(f"Using Python: {python}")
    cmd = [
        python, "-m", "streamlit", "run", str(APP_DIR / "app.py"),
        "--server.port",           str(PORT),
        "--server.headless",       "true",
        "--server.address",        "localhost",
        "--browser.gatherUsageStats", "false",
        "--theme.base",            "dark",
    ]
    logger.info(f"Running Streamlit: {' '.join(cmd)}")
    return subprocess.Popen(
        cmd,
        cwd=str(APP_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )

def _wait_for_server(timeout: int = 45) -> bool:
    """Poll localhost until Streamlit responds."""
    logger.info(f"Waiting for server at {URL} ...")
    try:
        import urllib.request
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                urllib.request.urlopen(URL, timeout=1)
                logger.info("Server is UP!")
                return True
            except Exception:
                time.sleep(1)
    except Exception as e:
        logger.error(f"Error while waiting: {e}")
    return False

def main():
    logger.info("Starting CV Extractor server …")
    proc = _start_streamlit()

    logger.info("Waiting for server to be ready …")
    if not _wait_for_server(timeout=60):
        logger.error("Streamlit server did not start in time.")
        proc.terminate()
        sys.exit(1)

    chrome_path = _find_chrome()
    if not chrome_path:
        logger.error("Chrome not found. Falling back to default browser.")
        import webbrowser
        webbrowser.open(URL)
        sys.exit(0)

    logger.info(f"Launching Chrome App Mode: {chrome_path}")
    
    # Launch Chrome in --app mode (no tabs, standalone window)
    app_cmd = [
        chrome_path,
        f"--app={URL}",
        "--window-size=1440,900",
        "--user-data-dir=" + str(APP_DIR / ".chrome_profile"), # Isolated profile
    ]
    
    try:
        # Launch Chrome window (non-blocking)
        chrome_proc = subprocess.Popen(app_cmd)
        logger.info("Chrome launched.")
        
        # Wait for the Chrome process to finish (the user closes the window)
        chrome_proc.wait()
        logger.info("Chrome window closed.")
        
    except Exception as e:
        logger.error(f"Failed to launch Chrome: {e}")
    finally:
        logger.info("Cleaning up processes.")
        proc.terminate()

if __name__ == "__main__":
    main()
