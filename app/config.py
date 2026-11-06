"""PromptForge configuration."""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.environ.get("PROMPTFORGE_DB", os.path.join(BASE_DIR, "promptforge.db"))
HOST = os.environ.get("PROMPTFORGE_HOST", "0.0.0.0")
PORT = int(os.environ.get("PROMPTFORGE_PORT", "8000"))
DEBUG = os.environ.get("PROMPTFORGE_DEBUG", "1") == "1"
APP_NAME = "PromptForge"
APP_VERSION = "1.2.0"
