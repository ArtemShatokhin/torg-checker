"""Send alerts when car listing is found."""

import urllib.parse
import urllib.request
import json
import logging

logger = logging.getLogger(__name__)


def send_telegram(bot_token: str, chat_id: str, text: str) -> bool:
    if not bot_token or not chat_id:
        logger.warning("Telegram not configured: set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
        return False
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    body = json.dumps({"chat_id": chat_id, "text": text, "disable_web_page_preview": True}).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 200:
                return True
            logger.error("Telegram API returned status %s", resp.status)
            return False
    except Exception as e:
        logger.exception("Failed to send Telegram message: %s", e)
        return False


def build_alert_message(sources: list[dict]) -> str:
    lines = [
        "⚠️ Обнаружен лот с вашим автомобилем на торгах.",
        "",
        "Проверьте срочно:",
    ]
    for s in sources:
        lines.append(f"• {s['name']}: {s['url']}")
    lines.append("")
    lines.append("VIN/госномер из настроек проверки.")
    return "\n".join(lines)
