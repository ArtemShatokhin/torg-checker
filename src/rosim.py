"""Check fiol.rosim.gov.ru marketplace (transport) for VIN."""

import logging
import time

logger = logging.getLogger(__name__)

ROSIM_URL = "https://fiol.rosim.gov.ru/mk/"


def _run_rosim_on_page(page, vin: str, result: dict) -> None:
    page.set_default_timeout(30000)
    page.goto(ROSIM_URL, wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle")
    time.sleep(2)

    transport_tab = page.locator('ul.filter-tabs__tabs li:has-text("Транспорт")').first
    if transport_tab.count():
        transport_tab.click()
        time.sleep(2)

    additional_btn = page.locator("button.filter-actions__btn-show:has-text('Дополнительные')").first
    if additional_btn.count():
        additional_btn.click()
        time.sleep(1)

    vin_input = page.locator("div.filters-vehicle-card div.field-filter").filter(
        has=page.locator("h4:has-text('Идентификационный')")
    ).locator("input.input").first
    vin_input.wait_for(state="visible", timeout=15000)
    vin_input.fill(vin)
    time.sleep(0.3)

    apply_btn = page.locator("button.filter-actions__btn-apply")
    apply_btn.click()
    time.sleep(2)

    body = page.locator(".table__body").first
    body_text = body.inner_text() if body.count() else ""
    no_objects_msg = "Объекты не найдены"
    if no_objects_msg in body_text:
        result["details"] = "No objects found for VIN on fiol.rosim.gov.ru"
    else:
        result["found"] = True
        result["details"] = "Found listing(s) for VIN on fiol.rosim.gov.ru"


def check_rosim(vin: str, page=None) -> dict:
    """
    Check Rosim marketplace transport tab for VIN. Returns dict with keys:
    - found: bool
    - url: str
    - details: str
    If `page` is provided (Playwright page), uses it and does not close the browser.
    """
    result = {"found": False, "url": ROSIM_URL, "details": ""}
    if not vin or not vin.strip():
        result["details"] = "VIN not set"
        return result

    vin = vin.strip()

    if page is not None:
        try:
            _run_rosim_on_page(page, vin, result)
        except Exception as e:
            logger.exception("Rosim check failed: %s", e)
            result["details"] = str(e)
        return result

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        result["details"] = "Playwright not installed (pip install playwright && playwright install chromium)"
        return result

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                _run_rosim_on_page(page, vin, result)
            finally:
                browser.close()
    except Exception as e:
        logger.exception("Rosim check failed: %s", e)
        result["details"] = str(e)

    return result
