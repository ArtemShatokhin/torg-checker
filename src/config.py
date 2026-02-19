"""Load config from environment and optional .env file."""

import os
from pathlib import Path

# Load .env from repo root (directory containing run_check.py when run as script)
def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    root = Path(__file__).resolve().parent.parent
    load_dotenv(root / ".env")


def load_config() -> dict:
    _load_dotenv()
    vin = os.environ.get("CAR_VIN", "").strip()
    plate = os.environ.get("CAR_PLATE", "").strip()
    if not vin and not plate:
        vin = os.environ.get("VIN", "5TDDK3DC4BS021726").strip()
        plate = os.environ.get("PLATE_NUMBER", "Н777ХК190").strip()
    headless_val = os.environ.get("HEADLESS", "1").strip().lower()
    headless = headless_val not in ("0", "false", "no", "off")

    return {
        "vin": vin,
        "plate": plate,
        "telegram_bot_token": os.environ.get("TELEGRAM_BOT_TOKEN", "").strip(),
        "telegram_chat_id": os.environ.get("TELEGRAM_CHAT_ID", "").strip(),
        "headless": headless,
    }
