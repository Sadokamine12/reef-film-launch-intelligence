from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urljoin
import csv
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

from data_contracts import canonical_booking_id
from project_config import load_config as load_project_config

BASE = "https://supernova.eso.org"
CONFIG_PATH = Path("config/project.json")
RESOLUTION_OUT = Path("data/eso_sales_snapshots.csv")
BASELINE_OUT = Path("data/eso_comparable_snapshots.csv")
DISCOVERY_OUT = Path("data/eso_discovered_programmes.csv")

# Public ESO programme pages. es1007 is confirmed to expose 2026 showings.
DEFAULT_DETAIL_SEEDS = [
    "https://supernova.eso.org/germany/programme/detail/es1007?lang=de",
    "https://supernova.eso.org/germany/programme/detail/es1185?lang=de",
    "https://supernova.eso.org/germany/programme/detail/es1246/?lang=de",
    "https://supernova.eso.org/germany/programme/detail/es1180-de/?lang=de",
]

# Verified public ESO booking pages. These are deliberately individual booking pages because
# they expose exact x/109 availability. Past pages are ignored for new snapshots, but their
# previously collected valid rows remain useful as historical training data.
DEFAULT_BOOKING_SEEDS = [
    "https://supernova.eso.org/germany/programme/booking/4r6dd/?lang=de",  # 23 Sep 2026
    "https://supernova.eso.org/programme/booking/v559n/?lang=en",         # 17 Oct 2026
    "https://supernova.eso.org/programme/booking/9bbdw/?lang=en",         # 18 Oct 2026
    "https://supernova.eso.org/germany/programme/booking/evv8n/?lang=en", # 7 Nov 2026
    "https://supernova.eso.org/programme/booking/j88ox/?lang=en",         # 21 Nov 2026
    "https://supernova.eso.org/programme/booking/dbbr8/?lang=en",         # 20 Dec 2026
]

COOKIE_TITLE_FRAGMENTS = (
    "was sind cookies",
    "what are cookies",
    "eso-cookie-richtlinie",
    "eso cookie policy",
    "unsere verwendung von cookies",
    "our use of cookies",
)

GENERIC_UI_TITLE_FRAGMENTS = (
    "weitere informationen",
    "more information",
    "informationen",
    "information",
    "details",
    "mehr erfahren",
    "learn more",
)

SEAT_PATTERNS = [
    re.compile(r"Available seats\s*:\s*(\d+)\s*/\s*(\d+)", re.I),
    re.compile(r"Verf(?:u|ü)gbare Sitze\s*:\s*(\d+)\s*/\s*(\d+)", re.I),
    re.compile(r"Sitzpl(?:a|ä)tze\s*:\s*(\d+)\s*/\s*(\d+)", re.I),
]

MONTHS = {
    "januar": 1, "january": 1,
    "februar": 2, "february": 2,
    "maerz": 3, "märz": 3, "march": 3,
    "april": 4,
    "mai": 5, "may": 5,
    "juni": 6, "june": 6,
    "juli": 7, "july": 7,
    "august": 8,
    "september": 9,
    "oktober": 10, "october": 10,
    "november": 11,
    "dezember": 12, "december": 12,
}

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/153 Safari/537.36",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
})

PROGRAMME_MARKERS = (
    "Verfügbare Sitzplätze",
    "Verfügbare Sitze",
    "Available seats",
    "Vorführungen",
    "Showings",
    "/programme/booking/",
)


def load_config() -> dict:
    cfg = load_project_config(CONFIG_PATH)
    tracking = cfg.get("tracking", {})
    return {
        "eso_booking_urls": tracking.get("resolution_booking_urls", []),
        "eso_baseline_max_pages": tracking.get("baseline_max_detail_pages", 30),
        "eso_baseline_max_booking_pages": tracking.get("baseline_max_booking_pages", 24),
    }


def append_rows(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists() and path.stat().st_size > 0
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        if not exists:
            w.writeheader()
        w.writerows(rows)


def find_browser() -> str | None:
    candidates = []
    local = os.environ.get("LOCALAPPDATA", "")
    pf = os.environ.get("PROGRAMFILES", "")
    pfx86 = os.environ.get("PROGRAMFILES(X86)", "")
    if local:
        candidates += [
            os.path.join(local, "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(local, "Microsoft", "Edge", "Application", "msedge.exe"),
        ]
    if pf:
        candidates += [
            os.path.join(pf, "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(pf, "Microsoft", "Edge", "Application", "msedge.exe"),
        ]
    if pfx86:
        candidates += [
            os.path.join(pfx86, "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(pfx86, "Microsoft", "Edge", "Application", "msedge.exe"),
        ]
    for name in ("chrome", "chrome.exe", "msedge", "msedge.exe"):
        p = shutil.which(name)
        if p:
            candidates.append(p)
    for p in candidates:
        if p and os.path.exists(p):
            return p
    return None


def browser_dump_dom(url: str, timeout: int = 35) -> str:
    browser = find_browser()
    if not browser:
        raise RuntimeError("Chrome/Edge not found for rendered-page fallback")
    with tempfile.TemporaryDirectory(prefix="reef_eso_browser_") as profile:
        cmd = [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            "--disable-background-networking",
            "--disable-component-update",
            "--disable-sync",
            "--hide-scrollbars",
            "--window-size=1400,1200",
            f"--user-data-dir={profile}",
            "--virtual-time-budget=5000",
            "--dump-dom",
            url,
        ]
        kwargs = {}
        if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW"):
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            **kwargs,
        )
        html = proc.stdout or ""
        if "<html" not in html.lower():
            raise RuntimeError(f"Browser returned no DOM (exit={proc.returncode})")
        return html


def requests_get(url: str, timeout: int = 25) -> str:
    r = SESSION.get(url, timeout=timeout)
    r.raise_for_status()
    return r.text


def _normalised_text(html: str) -> str:
    return BeautifulSoup(html, "html.parser").get_text(" ", strip=True)


def _looks_like_cookie_title(value: str) -> bool:
    low = (value or "").strip().lower()
    # ESO privacy pages use several changing headings. Any page title/heading containing
    # "cookie" is not a programme title and must never enter the training data.
    return "cookie" in low or any(fragment in low for fragment in COOKIE_TITLE_FRAGMENTS)


def _looks_like_generic_ui_title(value: str) -> bool:
    low = re.sub(r"\s+", " ", (value or "").strip().lower())
    if not low:
        return True
    return any(low == fragment or low.startswith(fragment + " ") for fragment in GENERIC_UI_TITLE_FRAGMENTS)


def _has_exact_booking_signature(html: str) -> bool:
    text = _normalised_text(html)
    seat_ok = any(pat.search(text) for pat in SEAT_PATTERNS)
    date_ok = bool(re.search(r"(?:Datum|Date)\s*:\s*\d{1,2}", text, re.I))
    start_ok = bool(re.search(r"(?:Beginn|Start(?: time)?)\s*:\s*\d{1,2}:\d{2}", text, re.I))
    price_ok = bool(re.search(r"(?:Ticket-Preis|Ticket price)\s*:", text, re.I))
    return seat_ok and date_ok and start_ok and price_ok


def _has_detail_signature(html: str) -> bool:
    text = _normalised_text(html)
    seat_ok = bool(re.search(
        r"(?:Available seats|Verf(?:u|ü)gbare Sitzpl(?:a|ä)tze|Verf(?:u|ü)gbare Sitze)\s*:\s*\d+(?:\s*/\s*109)?",
        text,
        re.I,
    ))
    date_ok = bool(re.search(
        r"(?:Mo|Di|Mi|Do|Fr|Sa|So|Mon|Tue|Wed|Thu|Fri|Sat|Sun)\.?\s+\d{1,2}[\.\s]",
        text,
        re.I,
    ))
    return seat_ok and date_ok


def is_cookie_privacy_only(html: str) -> bool:
    """True only when we have the ESO privacy layer without actual programme data."""
    soup = BeautifulSoup(html, "html.parser")
    candidates = []
    for tag in ("h1", "h2", "title"):
        node = soup.find(tag)
        if node:
            candidates.append(node.get_text(" ", strip=True))
    cookie_title = any(_looks_like_cookie_title(x) for x in candidates)
    text = _normalised_text(html).lower()
    cookie_body = (
        "cookie-richtlinie" in text
        or "cookie policy" in text
        or "nur unbedingt erforderliche cookies" in text
        or "only accept necessary cookies" in text
    )
    # A real programme page can contain the cookie banner too. Programme evidence wins.
    real_programme = _has_exact_booking_signature(html) or _has_detail_signature(html)
    return (cookie_title or cookie_body) and not real_programme


def validate_programme_html(url: str, html: str) -> tuple[bool, str]:
    if not html or "<html" not in html.lower():
        return False, "no HTML document"
    if is_cookie_privacy_only(html):
        return False, "cookie/privacy page only"
    if "/programme/booking/" in url:
        return (_has_exact_booking_signature(html), "valid booking page" if _has_exact_booking_signature(html) else "missing booking signature")
    if "/programme/detail/" in url or "/programme/calendar/" in url:
        return (_has_detail_signature(html), "valid programme detail" if _has_detail_signature(html) else "missing detail signature")
    return (_has_exact_booking_signature(html) or _has_detail_signature(html), "programme markers")


def has_programme_content(html: str) -> bool:
    # Kept for backwards compatibility with V8.2 callers, but made strict.
    return not is_cookie_privacy_only(html) and (_has_exact_booking_signature(html) or _has_detail_signature(html))


def selenium_dump_dom(url: str, timeout: int = 40) -> str:
    """Render ESO with Selenium and click the consent button if present.

    Selenium Manager uses the installed Chrome/Edge browser and normally downloads only the
    matching driver on first use. No administrator rights are required.
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
    except Exception as e:
        raise RuntimeError(f"selenium is not installed ({e})")

    browser = find_browser()
    if not browser:
        raise RuntimeError("Chrome/Edge not found")

    options = webdriver.ChromeOptions()
    options.binary_location = browser
    for arg in (
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-extensions",
        "--window-size=1440,1600",
        "--lang=de-DE",
    ):
        options.add_argument(arg)

    driver = None
    try:
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(timeout)
        driver.get(url)
        time.sleep(1.0)

        consent_texts = [
            "Nur unbedingt erforderliche Cookies akzeptieren",
            "Alle akzeptieren",
            "Only accept necessary cookies",
            "Accept all",
        ]
        clicked = False
        for label in consent_texts:
            try:
                button = WebDriverWait(driver, 2).until(
                    EC.element_to_be_clickable((By.XPATH, f"//button[contains(normalize-space(.), {json.dumps(label)})]"))
                )
                driver.execute_script("arguments[0].click();", button)
                clicked = True
                time.sleep(1.0)
                break
            except Exception:
                continue

        # Some ESO variants show privacy content as the first rendered state. Once consent is
        # saved, explicitly navigate back to the requested programme URL.
        html = driver.page_source or ""
        if clicked or is_cookie_privacy_only(html):
            driver.get(url)
            time.sleep(1.5)
            html = driver.page_source or ""
        return html
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass


def fetch_programme_html(url: str) -> tuple[str, str]:
    """Fetch only validated programme HTML; never accept the cookie/privacy page as data."""
    errors = []
    try:
        html = requests_get(url)
        ok, reason = validate_programme_html(url, html)
        if ok:
            return html, "requests"
        errors.append(f"requests: {reason}")
    except Exception as e:
        errors.append(f"requests failed: {e}")

    try:
        html = selenium_dump_dom(url)
        ok, reason = validate_programme_html(url, html)
        if ok:
            return html, "selenium"
        errors.append(f"selenium: {reason}")
    except Exception as e:
        errors.append(f"selenium failed: {e}")

    # Last resort for machines where Selenium cannot start. This method cannot click consent,
    # so validation remains strict and it will not create false rows.
    try:
        html = browser_dump_dom(url)
        ok, reason = validate_programme_html(url, html)
        if ok:
            return html, "browser-dump"
        errors.append(f"browser-dump: {reason}")
    except Exception as e:
        errors.append(f"browser-dump failed: {e}")

    raise RuntimeError("; ".join(errors))

def parse_available_seats(html: str):
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    for pat in SEAT_PATTERNS:
        m = pat.search(text)
        if m:
            return int(m.group(1)), int(m.group(2))
    return None, None


def parse_money(text: str):
    m = re.search(r"(?:Ticket-Preis|Ticket price)\s*:\s*([0-9]+(?:[\.,][0-9]+)?)", text, re.I)
    if not m:
        return ""
    try:
        return float(m.group(1).replace(",", "."))
    except Exception:
        return ""


def parse_duration_min(text: str):
    m = re.search(r"(?:Dauer|Duration)\s*:\s*(\d{1,2}):(\d{2}):(\d{2})", text, re.I)
    if not m:
        return ""
    return int(m.group(1)) * 60 + int(m.group(2)) + (1 if int(m.group(3)) >= 30 else 0)


def parse_min_age(text: str):
    m = re.search(r"(?:Minimum recommended age|Empfohlenes Mindestalter|Mindestalter)\s*:\s*(\d+)", text, re.I)
    return int(m.group(1)) if m else ""


def page_title(soup: BeautifulSoup) -> str:
    # On booking pages H1 can be "Buchung"; H2 is usually the programme name.
    generic = {"buchung", "booking", "programme", "program", "eso supernova"}
    for tag in ("h2", "h1", "title"):
        for node in soup.find_all(tag):
            value = node.get_text(" ", strip=True)
            if not value:
                continue
            low = value.lower()
            if low in generic or _looks_like_cookie_title(value) or _looks_like_generic_ui_title(value):
                continue
            return value
    return "Unknown programme"

def parse_booking_page(url: str, html: str, retrieval_mode: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)
    available, capacity = parse_available_seats(html)
    if available is None or capacity is None or capacity < 50:
        return None

    title = page_title(soup)
    if title == "Unknown programme" or _looks_like_cookie_title(title):
        return None
    date_m = re.search(r"(?:Datum|Date)\s*:\s*(\d{1,2})\.?\s*([A-Za-zÄÖÜäöü]+)\s*(\d{4})", text, re.I)
    if not date_m:
        date_m = re.search(r"(?:Datum|Date)\s*:\s*(\d{1,2})\.(\d{1,2})\.(\d{4})", text, re.I)
    time_m = re.search(r"(?:Beginn|Start(?: time)?)\s*:\s*(\d{1,2}):(\d{2})", text, re.I)

    show_dt = None
    if date_m and time_m:
        try:
            if date_m.group(2).isdigit():
                month = int(date_m.group(2))
            else:
                month = MONTHS.get(date_m.group(2).lower())
            if month:
                show_dt = datetime(int(date_m.group(3)), month, int(date_m.group(1)), int(time_m.group(1)), int(time_m.group(2)))
        except Exception:
            show_dt = None

    if show_dt is None:
        return None

    now = datetime.now(timezone.utc)
    show_iso = show_dt.strftime("%Y-%m-%d %H:%M")
    return {
        "collected_at_utc": now.isoformat(),
        "programme_title": title,
        "show_datetime_local": show_iso,
        "weekday": show_dt.strftime("%A") if show_dt else "",
        "start_hour": (show_dt.hour + show_dt.minute / 60) if show_dt else "",
        "month": show_dt.month if show_dt else "",
        "minimum_age": parse_min_age(text),
        "ticket_price_eur": parse_money(text),
        "duration_min": parse_duration_min(text),
        "available_seats": available,
        "capacity": capacity or 109,
        "tickets_sold_so_far": (capacity or 109) - available,
        "days_to_event": (show_dt.date() - now.date()).days if show_dt else "",
        "programme_url": url,
        "source_type": "booking_page",
        "retrieval_mode": retrieval_mode,
        "status": "ok",
    }


def extract_booking_links(base_url: str, html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    out = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if "/programme/booking/" not in href:
            continue
        u = urljoin(base_url, href)
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def parse_detail_page(url: str, html: str, retrieval_mode: str) -> tuple[dict, list[dict]]:
    soup = BeautifulSoup(html, "html.parser")
    title = page_title(soup)
    if (
        title == "Unknown programme"
        or _looks_like_cookie_title(title)
        or _looks_like_generic_ui_title(title)
        or is_cookie_privacy_only(html)
    ):
        raise RuntimeError("non-programme/detail UI page rejected before detail parsing")
    text = soup.get_text("\n", strip=True)
    ticket_price = parse_money(text)
    duration_min = parse_duration_min(text)
    min_age = parse_min_age(text)

    lines = [re.sub(r"\s+", " ", x).strip() for x in text.splitlines() if x.strip()]
    current_available = None
    rows = []

    seat_line = re.compile(r"^(?:Available seats|Verf(?:u|ü)gbare Sitzpl(?:a|ä)tze|Verf(?:u|ü)gbare Sitze)\s*:\s*(\d+)(?:\s*/\s*(\d+))?$", re.I)
    date_de = re.compile(r"(?:Mo|Di|Mi|Do|Fr|Sa|So|Mon|Tue|Wed|Thu|Fri|Sat|Sun)\.?\s+(\d{1,2})\.(\d{1,2})\.(\d{4}),\s*(\d{1,2}):(\d{2})", re.I)
    date_en = re.compile(r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\.?\s+(\d{1,2})\s+([A-Za-z]+)\s+(\d{4}),\s*(\d{1,2}):(\d{2})", re.I)

    for line in lines:
        sm = seat_line.match(line)
        if sm:
            current_available = int(sm.group(1))
            continue
        dm = date_de.search(line)
        if dm and current_available is not None:
            day, month, year, hh, minute = map(int, dm.groups())
            rows.append((datetime(year, month, day, hh, minute), current_available))
            current_available = None
            continue
        em = date_en.search(line)
        if em and current_available is not None:
            month = MONTHS.get(em.group(2).lower())
            if month:
                rows.append((datetime(int(em.group(3)), month, int(em.group(1)), int(em.group(4)), int(em.group(5))), current_available))
                current_available = None

    # Flexible window fallback for rendered pages where HTML inserts extra text between seat count and date.
    if not rows:
        compact = "\n".join(lines)
        pat = re.compile(
            r"(?:Available seats|Verf(?:u|ü)gbare Sitzpl(?:a|ä)tze|Verf(?:u|ü)gbare Sitze)\s*:\s*(\d+)(?:\s*/\s*(\d+))?.{0,240}?"
            r"(?:Mo|Di|Mi|Do|Fr|Sa|So|Mon|Tue|Wed|Thu|Fri|Sat|Sun)\.?\s+(\d{1,2})\.(\d{1,2})\.(\d{4}),\s*(\d{1,2}):(\d{2})",
            re.I | re.S,
        )
        for m in pat.finditer(compact):
            available = int(m.group(1))
            day, month, year, hh, minute = map(int, m.groups()[2:])
            rows.append((datetime(year, month, day, hh, minute), available))

    meta = {
        "programme_title": title,
        "programme_url": url,
        "ticket_price_eur": ticket_price,
        "duration_min": duration_min,
        "minimum_age": min_age,
        "retrieval_mode": retrieval_mode,
    }
    now = datetime.now(timezone.utc)
    snapshots = []
    for show_dt, available in rows:
        capacity = 109
        snapshots.append({
            "collected_at_utc": now.isoformat(),
            "programme_title": title,
            "show_datetime_local": show_dt.strftime("%Y-%m-%d %H:%M"),
            "weekday": show_dt.strftime("%A"),
            "start_hour": show_dt.hour + show_dt.minute / 60,
            "month": show_dt.month,
            "minimum_age": min_age,
            "ticket_price_eur": ticket_price,
            "duration_min": duration_min,
            "available_seats": available,
            "capacity": capacity,
            "tickets_sold_so_far": capacity - available,
            "days_to_event": (show_dt.date() - now.date()).days,
            "programme_url": url,
            "source_type": "detail_page",
            "retrieval_mode": retrieval_mode,
            "status": "ok",
        })
    return meta, snapshots


def discover_detail_urls() -> list[str]:
    urls: list[str] = []
    for sm in (f"{BASE}/sitemap.xml", f"{BASE}/germany/sitemap.xml"):
        try:
            xml = requests_get(sm)
            root = ET.fromstring(xml)
            for elem in root.iter():
                if elem.tag.lower().endswith("loc") and elem.text and "/programme/detail/" in elem.text:
                    urls.append(elem.text.strip())
            if urls:
                break
        except Exception:
            continue

    cfg = load_config()
    urls.extend([u for u in (cfg.get("eso_baseline_detail_urls", []) or []) if isinstance(u, str) and u])
    urls.extend(DEFAULT_DETAIL_SEEDS)

    unique, seen = [], set()
    for u in urls:
        canonical = re.sub(r"\?.*$", "", u).rstrip("/")
        if canonical not in seen:
            seen.add(canonical)
            unique.append(u)
    return unique


def snapshot_resolution_urls(cfg: dict) -> list[dict]:
    rows = []
    for item in cfg.get("eso_booking_urls", []) or []:
        if isinstance(item, str):
            url, configured_date = item, ""
        else:
            url, configured_date = item.get("url", ""), item.get("show_date", "")
        if not url:
            continue
        try:
            html, mode = fetch_programme_html(url)
            row = parse_booking_page(url, html, mode)
            if row:
                rows.append({
                    "collected_at_utc": row["collected_at_utc"],
                    "show_date": (configured_date or row.get("show_datetime_local", ""))[:10],
                    "url": url,
                    "available_seats": row["available_seats"],
                    "capacity": row["capacity"],
                    "tickets_sold": row["tickets_sold_so_far"],
                    "status": f"ok:{mode}",
                })
            else:
                rows.append({
                    "collected_at_utc": datetime.now(timezone.utc).isoformat(),
                    "show_date": configured_date,
                    "url": url,
                    "available_seats": "", "capacity": "", "tickets_sold": "",
                    "status": f"seat_count_not_found:{mode}",
                })
        except Exception as e:
            print(f"WARNING Resolution booking {canonical_booking_id(url) or url}: {e}")
            rows.append({
                "collected_at_utc": datetime.now(timezone.utc).isoformat(),
                "show_date": configured_date,
                "url": url,
                "available_seats": "", "capacity": "", "tickets_sold": "",
                "status": f"error: {e}",
            })
    upsert_resolution_snapshots(rows)
    return rows


def upsert_resolution_snapshots(rows: list[dict]) -> None:
    """Preserve each show/day and replace a changed seat count on the same day."""
    fields = ["collected_at_utc", "show_date", "url", "available_seats", "capacity", "tickets_sold", "status"]
    old = []
    if RESOLUTION_OUT.exists():
        with RESOLUTION_OUT.open("r", newline="", encoding="utf-8") as handle:
            old = list(csv.DictReader(handle))
    chosen = {}
    for row in [*old, *rows]:
        if not str(row.get("status", "")).startswith("ok"):
            continue
        booking = canonical_booking_id(str(row.get("url", "")))
        day = str(row.get("collected_at_utc", ""))[:10]
        if not booking or not day:
            continue
        key = (booking, day)
        if key not in chosen or str(row["collected_at_utc"]) >= str(chosen[key]["collected_at_utc"]):
            chosen[key] = row
    RESOLUTION_OUT.parent.mkdir(parents=True, exist_ok=True)
    with RESOLUTION_OUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(sorted(chosen.values(), key=lambda r: (r["show_date"], r["collected_at_utc"])))


def clean_invalid_baseline_rows() -> tuple[int, int]:
    """Remove privacy false positives and same-show/same-day duplicates.

    Repeated snapshots on different days are intentionally kept because they form the
    longitudinal sales curve. When a detail-page and booking-page snapshot describe the
    same show on the same collection date, the booking page wins because its x/109 count
    is the most direct observation.
    """
    if not BASELINE_OUT.exists() or BASELINE_OUT.stat().st_size == 0:
        return 0, 0
    try:
        with BASELINE_OUT.open("r", newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    except Exception:
        return 0, 0

    valid_rows = []
    removed = 0
    for row in rows:
        title = str(row.get("programme_title", "")).strip()
        dt = str(row.get("show_datetime_local", "")).strip()
        try:
            available = int(float(str(row.get("available_seats", ""))))
            capacity = int(float(str(row.get("capacity", "109"))))
        except Exception:
            available, capacity = -1, -1
        valid = (
            title
            and not _looks_like_cookie_title(title)
            and not _looks_like_generic_ui_title(title)
            and str(row.get("source_type", "")).strip() == "booking_page"
            and dt
            and 0 <= available <= capacity
            and capacity == 109
        )
        if valid:
            valid_rows.append(row)
        else:
            removed += 1

    # One observation per show per calendar day. Prefer exact booking pages over detail pages.
    chosen = {}
    for row in valid_rows:
        collected = str(row.get("collected_at_utc", ""))
        day = collected[:10] if len(collected) >= 10 else collected
        key = (
            _canonical_url(str(row.get("programme_url", ""))) or str(row.get("programme_title", "")).strip().lower(),
            str(row.get("show_datetime_local", "")).strip(),
            day,
        )
        rank = 2 if row.get("source_type") == "booking_page" else 1
        prev = chosen.get(key)
        if prev is None:
            chosen[key] = (rank, collected, row)
        else:
            prev_rank, prev_collected, _ = prev
            if rank > prev_rank or (rank == prev_rank and collected >= prev_collected):
                chosen[key] = (rank, collected, row)

    kept = [x[2] for x in chosen.values()]
    deduped = len(valid_rows) - len(kept)
    removed += deduped
    kept.sort(key=lambda r: (str(r.get("show_datetime_local", "")), str(r.get("collected_at_utc", ""))))

    fields = list(rows[0].keys()) if rows else []
    if fields and removed:
        backup_dir = BASELINE_OUT.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(BASELINE_OUT, backup_dir / f"eso_preclean_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.csv")
        with BASELINE_OUT.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(kept)
    return removed, len(kept)


def _canonical_url(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    booking_id = canonical_booking_id(value)
    if booking_id:
        return f"booking:{booking_id}"
    return re.sub(r"\?.*$", "", value).rstrip("/").lower()


def _observation_day(value: str) -> str:
    value = (value or "").strip()
    return value[:10] if len(value) >= 10 else value


def load_existing_daily_snapshots() -> dict[tuple[str, str, str], dict]:
    """Return existing booking snapshots keyed by booking URL/show/day.

    We intentionally keep one observation per show per calendar day. If the seat count
    changes later on the same day, V8.6 replaces that day's observation with the newest
    count instead of appending another row. This prevents repeated manual runs from
    inflating the training dataset while preserving genuine day-to-day sales velocity.
    """
    if not BASELINE_OUT.exists() or BASELINE_OUT.stat().st_size == 0:
        return {}
    out = {}
    try:
        with BASELINE_OUT.open("r", newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if str(row.get("source_type", "")).strip() != "booking_page":
                    continue
                url_key = _canonical_url(str(row.get("programme_url", "")))
                show_key = str(row.get("show_datetime_local", "")).strip()
                day_key = _observation_day(str(row.get("collected_at_utc", "")))
                if not show_key or not day_key:
                    continue
                key = (url_key or str(row.get("programme_title", "")).strip().lower(), show_key, day_key)
                prev = out.get(key)
                if prev is None or str(row.get("collected_at_utc", "")) >= str(prev.get("collected_at_utc", "")):
                    out[key] = row
    except Exception:
        return {}
    return out


def upsert_daily_snapshots(rows: list[dict]) -> tuple[int, int, int]:
    """Merge today's observations into the CSV without same-day inflation.

    Returns (new_rows, changed_rows, unchanged_rows).
    """
    if not rows:
        return 0, 0, 0

    existing = load_existing_daily_snapshots()
    new_count = changed_count = unchanged_count = 0
    changed_keys: set[tuple[str, str, str]] = set()
    appendable: list[dict] = []

    for row in rows:
        url_key = _canonical_url(str(row.get("programme_url", "")))
        show_key = str(row.get("show_datetime_local", "")).strip()
        day_key = _observation_day(str(row.get("collected_at_utc", "")))
        key = (url_key or str(row.get("programme_title", "")).strip().lower(), show_key, day_key)
        prev = existing.get(key)
        if prev is None:
            appendable.append(row)
            existing[key] = row
            new_count += 1
            continue

        old_available = str(prev.get("available_seats", "")).strip()
        new_available = str(row.get("available_seats", "")).strip()
        if old_available == new_available:
            unchanged_count += 1
            continue

        # Same show/day but a real seat-count change. Replace today's older observation
        # with the newest one so the ML dataset still has one point per show/day.
        existing[key] = row
        changed_keys.add(key)
        changed_count += 1

    if changed_keys:
        # Rewrite the compact daily snapshot table using the latest observation per key.
        rows_out = list(existing.values())
        rows_out.sort(key=lambda r: (str(r.get("show_datetime_local", "")), str(r.get("collected_at_utc", ""))))
        fields = [
            "collected_at_utc", "programme_title", "show_datetime_local", "weekday", "start_hour", "month",
            "minimum_age", "ticket_price_eur", "duration_min", "available_seats", "capacity",
            "tickets_sold_so_far", "days_to_event", "programme_url", "source_type", "retrieval_mode", "status",
        ]
        BASELINE_OUT.parent.mkdir(parents=True, exist_ok=True)
        with BASELINE_OUT.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows_out)
    elif appendable:
        append_rows(
            BASELINE_OUT,
            appendable,
            [
                "collected_at_utc", "programme_title", "show_datetime_local", "weekday", "start_hour", "month",
                "minimum_age", "ticket_price_eur", "duration_min", "available_seats", "capacity",
                "tickets_sold_so_far", "days_to_event", "programme_url", "source_type", "retrieval_mode", "status",
            ],
        )

    return new_count, changed_count, unchanged_count


def collect_comparable_eso_programmes(max_pages: int = 30, max_booking_pages: int = 24) -> tuple[list[dict], list[dict]]:
    detail_urls = discover_detail_urls()[:max_pages]
    cfg = load_config()
    configured_booking = [u for u in (cfg.get("eso_baseline_booking_urls", []) or []) if isinstance(u, str) and u]
    booking_urls = list(configured_booking) + list(DEFAULT_BOOKING_SEEDS)

    all_snapshots: list[dict] = []
    catalogue: list[dict] = []

    for i, url in enumerate(detail_urls, 1):
        try:
            html, mode = fetch_programme_html(url)
            links = extract_booking_links(url, html)
            booking_urls.extend(links)

            # Detail pages are discovery-only in V8.5. They are too easy for ESO's privacy/UI
            # layer to contaminate, so they NEVER create ticket/seat training observations.
            soup = BeautifulSoup(html, "html.parser")
            discovered_title = page_title(soup)
            if _looks_like_cookie_title(discovered_title) or _looks_like_generic_ui_title(discovered_title):
                discovered_title = ""

            catalogue.append({
                "collected_at_utc": datetime.now(timezone.utc).isoformat(),
                "programme_title": discovered_title,
                "programme_url": url,
                "ticket_price_eur": "",
                "duration_min": "",
                "minimum_age": "",
                "retrieval_mode": mode,
                "showings_found": len(links),
                "status": "discovery_only" if links else "no_booking_links_found",
            })
            print(
                f"Comparable detail {i}/{len(detail_urls)} [{mode}]: "
                f"booking links discovered={len(links)} (detail seat rows ignored)"
            )
        except Exception as e:
            catalogue.append({
                "collected_at_utc": datetime.now(timezone.utc).isoformat(),
                "programme_title": "",
                "programme_url": url,
                "ticket_price_eur": "",
                "duration_min": "",
                "minimum_age": "",
                "retrieval_mode": "failed",
                "showings_found": 0,
                "status": f"error: {e}",
            })
            print(f"WARNING detail {i}/{len(detail_urls)}: {e}")
        time.sleep(0.1)

    # Follow booking URLs because they expose exact x/109 availability and are useful even
    # when the programme detail page is hidden behind ESO's privacy overlay.
    unique_booking, seen = [], set()
    for u in booking_urls:
        if not u:
            continue
        canonical = _canonical_url(u)
        if canonical not in seen:
            seen.add(canonical)
            unique_booking.append(u)

    for i, url in enumerate(unique_booking[:max_booking_pages], 1):
        try:
            html, mode = fetch_programme_html(url)
            row = parse_booking_page(url, html, mode)
            if row:
                # Do not create fresh snapshots for performances that have already passed.
                try:
                    row_dt = datetime.strptime(row.get("show_datetime_local", ""), "%Y-%m-%d %H:%M")
                except Exception:
                    row_dt = None
                if row_dt is not None and row_dt < datetime.now():
                    print(f"Comparable booking {i}/{min(len(unique_booking), max_booking_pages)} [{mode}]: past show skipped ({row['programme_title']})")
                    continue
                # Avoid duplicate exact show/title records already obtained from a detail page.
                key = (str(row.get("programme_title", "")).strip().lower(), row.get("show_datetime_local", ""))
                existing = {
                    (str(x.get("programme_title", "")).strip().lower(), x.get("show_datetime_local", ""))
                    for x in all_snapshots
                }
                if key not in existing:
                    all_snapshots.append(row)
                print(f"Comparable booking {i}/{min(len(unique_booking), max_booking_pages)} [{mode}]: {row['programme_title']} -> {row['available_seats']}/{row['capacity']} available")
        except Exception as e:
            print(f"WARNING booking {i}/{min(len(unique_booking), max_booking_pages)}: {e}")
        time.sleep(0.1)

    resolution_candidates = find_resolution_candidates(all_snapshots)
    comparable_snapshots = [r for r in all_snapshots if r not in resolution_candidates]
    new_rows, changed_rows, unchanged_rows = upsert_daily_snapshots(comparable_snapshots)
    if all_snapshots:
        print(
            f"Daily snapshot quality: {new_rows} new, {changed_rows} changed seat-count, "
            f"{unchanged_rows} unchanged duplicate(s) skipped."
        )
    append_rows(
        DISCOVERY_OUT,
        catalogue,
        [
            "collected_at_utc", "programme_title", "programme_url", "ticket_price_eur", "duration_min",
            "minimum_age", "retrieval_mode", "showings_found", "status",
        ],
    )
    # Only rows that created or updated today's persisted observation are training changes.
    # Return all validated observations for diagnostics; main() reports persistence quality separately.
    return catalogue, all_snapshots


def find_resolution_candidates(snapshots: list[dict]) -> list[dict]:
    out = []
    show_dates = set(load_project_config()["screenings"]["dates"])
    for r in snapshots:
        title = str(r.get("programme_title", "")).lower()
        dt = str(r.get("show_datetime_local", ""))
        if "resolution" in title and dt[:10] in show_dates:
            out.append(r)
    return out


def main():
    removed, kept = clean_invalid_baseline_rows()
    if removed:
        print(f"Cleaned baseline to booking-only rows: removed {removed}, kept {kept} valid row(s).")

    cfg = load_config()
    resolution_rows = snapshot_resolution_urls(cfg)

    if resolution_rows:
        print(f"Resolution booking tracker: {len(resolution_rows)} configured page(s) checked.")
    else:
        print("Resolution booking pages are not configured/public yet. Starting pre-launch baseline collection instead.")

    browser = find_browser()
    if browser:
        print(f"Rendered-page fallback available: {browser}")
    else:
        print("WARNING: Chrome/Edge was not found. ESO cookie/privacy pages may block programme parsing.")

    catalogue, snapshots = collect_comparable_eso_programmes(
        max_pages=int(cfg.get("eso_baseline_max_pages", 30) or 30),
        max_booking_pages=int(cfg.get("eso_baseline_max_booking_pages", 24) or 24),
    )
    ok_programmes = sum(1 for r in catalogue if r.get("status") == "ok")
    booking_rows = sum(1 for r in snapshots if r.get("source_type") == "booking_page")
    detail_rows = sum(1 for r in snapshots if r.get("source_type") == "detail_page")
    print(
        f"ESO comparable baseline: {booking_rows} validated booking snapshot row(s) checked this run; "
        f"detail pages are discovery-only in V8.6. "
        f"Persistence summary is shown above (unchanged same-day snapshots are skipped)."
    )
    print(f"Saved: {BASELINE_OUT}")
    print(f"Diagnostics: {DISCOVERY_OUT}")

    candidates = find_resolution_candidates(snapshots)
    if candidates:
        upsert_resolution_snapshots([{
            "collected_at_utc": r["collected_at_utc"], "show_date": r["show_datetime_local"][:10],
            "url": r["programme_url"], "available_seats": r["available_seats"],
            "capacity": r["capacity"], "tickets_sold": r["tickets_sold_so_far"], "status": "ok:discovered",
        } for r in candidates])
        print("Potential Resolution / February 2027 programme rows detected:")
        for r in candidates[:12]:
            print(f"  {r['programme_title']} | {r['show_datetime_local']} | {r['available_seats']}/{r['capacity']} available")
    else:
        print("No public February 2027 Resolution show rows detected yet. Baseline collection can continue before tickets open.")

    if not snapshots:
        print("\nDIAGNOSTIC: ESO returned no validated comparable seat rows. V8.3 deliberately rejects cookie/privacy pages instead of creating fake training data. If Selenium is not installed, run: .\\.venv\\Scripts\\python.exe -m pip install selenium")


if __name__ == "__main__":
    main()
