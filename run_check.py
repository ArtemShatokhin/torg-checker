#!/usr/bin/env python3
"""
Check Rosim and Konfiskat sites for car listing by VIN and plate number.
Exits 0 if no listing found, 1 if at least one listing found (and alert sent).
Config via env: CAR_VIN or VIN, CAR_PLATE or PLATE_NUMBER, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID.
"""

import logging
import sys

from src.config import load_config
from src.rosim import check_rosim
from src.konfiskat import check_konfiskat, check_konfiskat_with_page
from src.alerts import send_telegram, build_alert_message

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def run():
    config = load_config()
    vin = config["vin"]
    plate = config["plate"]
    if not vin and not plate:
        logger.error("Set VIN and/or PLATE_NUMBER (or CAR_VIN/CAR_PLATE) in environment")
        sys.exit(2)

    logger.info("Checking for VIN=%s, Plate=%s", vin or "(none)", plate or "(none)")

    sources_with_listings = []
    headless = config.get("headless", True)

    try:
        from playwright.sync_api import sync_playwright
        use_browser = True
    except ImportError:
        use_browser = False

    if use_browser:
        with sync_playwright() as p:
            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-infobars",
                "--window-size=1280,800",
            ]
            if not headless:
                logger.info("Running with visible browser (HEADLESS=0); Konfiskat may allow it.")
            try:
                browser = p.chromium.launch(channel="chrome", headless=headless, args=launch_args)
            except Exception:
                browser = p.chromium.launch(headless=headless, args=launch_args)
            try:
                context = browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    ),
                    locale="ru-RU",
                    timezone_id="Europe/Moscow",
                    java_script_enabled=True,
                )
                context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined,
                        configurable: true,
                        enumerable: true,
                    });
                    window.chrome = { runtime: {} };
                """)
                page = context.new_page()
                page.set_extra_http_headers({"Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8"})
                konfiskat_result = check_konfiskat_with_page(page, vin, plate)
                logger.info("Konfiskat: %s", konfiskat_result["details"])
                if konfiskat_result["found"]:
                    sources_with_listings.append({
                        "name": "Конфискат (konfiskat-gov.ru)",
                        "url": konfiskat_result["url"],
                    })
                if vin:
                    rosim_result = check_rosim(vin, page=page)
                    logger.info("Rosim: %s", rosim_result["details"])
                    if rosim_result["found"]:
                        sources_with_listings.append({
                            "name": "Росимущество (fiol.rosim.gov.ru)",
                            "url": rosim_result["url"],
                        })
            finally:
                browser.close()
    else:
        if vin:
            rosim_result = check_rosim(vin)
            logger.info("Rosim: %s", rosim_result["details"])
            if rosim_result["found"]:
                sources_with_listings.append({
                    "name": "Росимущество (fiol.rosim.gov.ru)",
                    "url": rosim_result["url"],
                })
        konfiskat_result = check_konfiskat(vin, plate)
        logger.info("Konfiskat: %s", konfiskat_result["details"])
        if konfiskat_result["found"]:
            sources_with_listings.append({
                "name": "Конфискат (konfiskat-gov.ru)",
                "url": konfiskat_result["url"],
            })

    if not sources_with_listings:
        logger.info("No listings found. Your car is not listed.")
        sys.exit(0)

    logger.warning("Listing(s) found on: %s", [s["name"] for s in sources_with_listings])
    message = build_alert_message(sources_with_listings)
    if config["telegram_bot_token"] and config["telegram_chat_id"]:
        sent = send_telegram(config["telegram_bot_token"], config["telegram_chat_id"], message)
        if sent:
            logger.info("Telegram alert sent.")
        else:
            logger.warning("Failed to send Telegram alert.")
    else:
        logger.warning("Telegram not configured. Message:\n%s", message)

    sys.exit(1)


if __name__ == "__main__":
    run()
