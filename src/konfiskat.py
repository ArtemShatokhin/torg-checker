"""Check konfiskat-gov.ru automobiles for VIN or plate number."""

import random
import re
import logging
import time
import urllib.request
import urllib.error
from pathlib import Path

logger = logging.getLogger(__name__)

DEBUG_HTML_PATH = Path(__file__).resolve().parent.parent / "konfiskat_debug.html"

# Use percent-encoded path so HTTP request does not hit ASCII encoding issues
KONFISKAT_AUTOS_URL = "https://konfiskat-gov.ru/%D0%B0%D0%B2%D1%82%D0%BE%D0%BC%D0%BE%D0%B1%D0%B8%D0%BB%D0%B8"
KONFISKAT_BASE = "https://konfiskat-gov.ru"


def _normalize(s: str) -> str:
    return re.sub(r"\s+", "", s.upper())


def _extract_token(html: str) -> str | None:
    # Flexible: name then value, or value then name; single or double quotes
    m = re.search(r'name=["\']_token["\'][^>]*value=["\']([^"\']+)["\']', html)
    if m:
        return m.group(1)
    m = re.search(r'value=["\']([^"\']+)["\'][^>]*name=["\']_token["\']', html)
    if m:
        return m.group(1)
    return None


def _search_konfiskat(query: str, token: str) -> tuple[str, str]:
    data = urllib.parse.urlencode({
        "_token": token,
        "query": query,
        "page": "1",
        "category[]": "1",
    }).encode("utf-8")
    req = urllib.request.Request(
        KONFISKAT_AUTOS_URL,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/115.0",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace"), resp.geturl()


def _page_contains_listing(html: str, vin: str, plate: str) -> bool:
    norm_vin = _normalize(vin)
    norm_plate = _normalize(plate)
    text = re.sub(r"<[^>]+>", " ", html).upper()
    text_nospace = re.sub(r"\s+", "", text)
    if norm_vin and norm_vin in text_nospace:
        return True
    if norm_plate and norm_plate in text_nospace:
        return True
    return False


def _has_result_listings(html: str) -> bool:
    return "property-listing" in html and "listing-content" in html


def check_konfiskat(vin: str, plate: str) -> dict:
    """
    Check konfiskat-gov.ru automobiles. Returns dict with keys:
    - found: bool
    - url: str
    - details: str
    """
    result = {"found": False, "url": KONFISKAT_AUTOS_URL, "details": ""}
    try:
        req = urllib.request.Request(
            KONFISKAT_AUTOS_URL,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/115.0",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as e:
        logger.exception("Failed to load konfiskat page: %s", e)
        result["details"] = f"Error loading page: {e}"
        return result

    token = _extract_token(html)
    if not token:
        if "verification" in html.lower() or "killbot" in html.lower() or len(html) < 5000:
            result["details"] = "Could not extract CSRF token (site may be showing bot verification)"
        else:
            result["details"] = "Could not extract CSRF token"
        return result

    queries = []
    if vin:
        queries.append(vin)
    if plate and plate != vin:
        queries.append(plate)

    for q in queries:
        try:
            search_html, final_url = _search_konfiskat(q, token)
            if _has_result_listings(search_html) and _page_contains_listing(search_html, vin, plate):
                result["found"] = True
                result["url"] = final_url or KONFISKAT_AUTOS_URL
                result["details"] = f"Match for query '{q}' on konfiskat-gov.ru"
                return result
        except urllib.error.URLError as e:
            logger.warning("Konfiskat search failed for '%s': %s", q, e)
            result["details"] = str(e)

    result["details"] = "No matching listings"
    return result


def _save_debug_html(page, result: dict) -> None:
    try:
        html = page.content()
        url = page.url
        DEBUG_HTML_PATH.write_text(
            f"<!-- URL: {url} -->\n{html}",
            encoding="utf-8",
            errors="replace",
        )
        result["details"] = f"Form/input not found. Page saved to {DEBUG_HTML_PATH.name} — open it to see what the site returned (block page vs real page)."
    except Exception as e:
        result["details"] = f"Form/input not found. Could not save page: {e}"


# Temporary id we inject to find the real KillBot thumb (cursor:pointer). Avoids relying on
# exact track dimensions, which may be randomized.
_KILLBOT_THUMB_ID = "kb-real-thumb"


def _try_solve_killbot_slider(page, *, timeout_ms: int = 15000) -> bool:
    """
    Try to pass the KillBot "swipe right" slider. The real thumb is the one with
    cursor:pointer (decoys use cursor:unset). We find it by computed style and track
    size range, not fixed pixels. Thumb position is driven only by clientX, so we drag
    horizontally in screen space. Returns True if the overlay disappeared (form visible).
    """
    try:
        # Find the real thumb by behavior: only the real one has cursor:pointer. Track
        # is any horizontal bar (width 200–400px, height ~40–60) so we don't depend on
        # exact dimensions that KillBot might randomize.
        found = page.evaluate(
            f"""
            () => {{
                const id = "{_KILLBOT_THUMB_ID}";
                const existing = document.getElementById(id);
                if (existing) existing.removeAttribute("id");
                for (const div of document.querySelectorAll("div")) {{
                    const style = getComputedStyle(div);
                    if (style.cursor !== "pointer") continue;
                    const parent = div.parentElement;
                    if (!parent) continue;
                    const pr = parent.getBoundingClientRect();
                    if (pr.width < 200 || pr.width > 400 || pr.height < 40 || pr.height > 60) continue;
                    if (div.getBoundingClientRect().width > 80) continue;
                    div.id = id;
                    return true;
                }}
                return false;
            }}
            """
        )
        if not found:
            return False

        thumb = page.locator(f"#{_KILLBOT_THUMB_ID}")
        thumb.wait_for(state="visible", timeout=5000)
        container = thumb.locator("xpath=..")

        box_thumb = thumb.bounding_box()
        box_container = container.bounding_box()
        if not box_thumb or not box_container:
            return False

        start_x = box_thumb["x"] + box_thumb["width"] / 2
        start_y = box_thumb["y"] + box_thumb["height"] / 2
        drag_distance = box_container["width"] - box_thumb["width"]
        end_x = start_x + drag_distance

        page.mouse.move(start_x, start_y)
        time.sleep(0.05 + random.uniform(0, 0.05))
        page.mouse.down()
        time.sleep(0.05 + random.uniform(0, 0.05))

        steps = 12 + random.randint(0, 5)
        for i in range(1, steps + 1):
            x = start_x + (end_x - start_x) * i / steps + random.uniform(-2, 2)
            page.mouse.move(x, start_y)
            time.sleep(0.02 + random.uniform(0, 0.03))
        page.mouse.up()

        # Wait for overlay to disappear or form to appear
        page.wait_for_selector("form#js-search-form", state="visible", timeout=timeout_ms)
        return True
    except Exception as e:
        logger.warning("KillBot slider solve failed: %s", e)
        return False


def check_konfiskat_with_page(page, vin: str, plate: str) -> dict:
    """
    Check konfiskat-gov.ru using a Playwright page.
    On failure, saves the page HTML to konfiskat_debug.html so we can see what we got.
    """
    result = {"found": False, "url": KONFISKAT_AUTOS_URL, "details": ""}
    queries = []
    if vin:
        queries.append(vin)
    if plate and plate != vin:
        queries.append(plate)
    if not queries:
        result["details"] = "No VIN or plate to search"
        return result

    try:
        page.goto(KONFISKAT_AUTOS_URL, wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        title = page.title()
        html_snippet = page.content()[:8000] if page.content() else ""
        if (
            "Проверка пользователя" in title
            or "user verification" in title.lower()
            or "kill-bot.ru" in html_snippet
            or "KillBot" in html_snippet
        ):
            if _try_solve_killbot_slider(page):
                time.sleep(0.5)
            else:
                logger.warning("Could not pass KillBot captcha; skipping Konfiskat check.")
                result["details"] = "Konfiskat is protected by KillBot (captcha). Cannot check from this environment. The hourly GitHub Action may still reach the site from its network."
                return result

        last_error = None
        for attempt in range(2):
            try:
                form = page.locator("form#js-search-form").first
                form.wait_for(state="attached", timeout=15000)
                page.evaluate("if (typeof openFilterSearch === 'function') openFilterSearch();")
                time.sleep(0.5)

                query_input = page.locator("input[name='query']").first
                query_input.wait_for(state="visible", timeout=10000)

                for q in queries:
                    query_input.fill("")
                    query_input.fill(q)
                    time.sleep(0.2)
                    page.locator("form#js-search-form").locator("button[type='submit']").first.click()
                    page.wait_for_load_state("networkidle")
                    time.sleep(1)

                    content = page.content()
                    if _has_result_listings(content) and _page_contains_listing(content, vin or "", plate or ""):
                        result["found"] = True
                        result["url"] = page.url
                        result["details"] = f"Match for query '{q}' on konfiskat-gov.ru"
                        return result
                    if q != queries[-1]:
                        page.goto(KONFISKAT_AUTOS_URL, wait_until="domcontentloaded")
                        page.wait_for_load_state("networkidle")
                        time.sleep(2)
                        page.evaluate("if (typeof openFilterSearch === 'function') openFilterSearch();")
                        time.sleep(0.5)
                        query_input = page.locator("input[name='query']").first
                        query_input.wait_for(state="visible", timeout=10000)

                result["details"] = "No matching listings"
                break
            except Exception as e:
                last_error = e
                if attempt == 0 and _try_solve_killbot_slider(page):
                    logger.info("Form not found; passed KillBot on retry, continuing.")
                    time.sleep(0.5)
                else:
                    _save_debug_html(page, result)
                    logger.debug("Konfiskat failed: %s", last_error)
                    break

    except Exception as e:
        _save_debug_html(page, result)
        logger.debug("Konfiskat failed: %s", e)
    return result
