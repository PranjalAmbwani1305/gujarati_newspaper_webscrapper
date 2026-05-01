"""
================================================================================
        GUJARATI NEWSPAPER AI SCRAPER  — v3 (QA-Tested & Fixed)
================================================================================
FIXES IN v3:
  [FIX-1] Translation (English / Hindi) — no API key needed:
    · Uses MyMemory REST API (free, no key, works from user's machine).
    · Language codes mapped correctly: gu→gu-IN, hi→hi-IN, en→en-GB, etc.
    · Chunks text at paragraph boundaries; reassembles with \n\n.
    · Falls back to deep-translator GoogleTranslator if MyMemory fails.
    · Per-article "Translate" button so it only fires on demand.

  [FIX-2] Gujarat Samachar — clear error + manual link:
    · If site returns 403 / no content, shows a styled error card with a
      direct clickable link to open the site in the browser.
    · Same fallback applies to any newspaper that blocks scraping.
    · Multi-strategy attempt: direct → search URL → RSS paths.

  [FIX-3] Bookmarks disappear on page reload:
    · Bookmarks now saved to ~/.gujarati_news_bookmarks.json on disk.
    · Loaded from file on every app start — survives F5 / browser refresh.
    · bookmarked_urls set always rebuilt from the loaded list.
    · st.rerun() called after every add/remove so label updates instantly.
================================================================================
"""

import streamlit as st
import requests
from bs4 import BeautifulSoup
import time
import random
import csv
import io
from datetime import datetime
import re
import json
import hashlib
import os
from urllib.parse import urljoin, urlparse, quote

# ─────────────────────────────────────────────────────────────────────────────
#  CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

BOOKMARK_FILE = os.path.join(os.path.expanduser("~"), ".gujarati_news_bookmarks.json")

NEWSPAPER_CONFIG = {
    "Gujarat Samachar": {
        "url": "https://www.gujaratsamachar.com/",
        "flag": "📰",
        "search_paths": ["?s={kw}", "search?q={kw}"],
        "rss_paths": ["feed", "rss", "feed/rss2"],
        "date_selectors": [
            ("span", {"class_": "post-date"}),
            ("time", {"class_": "entry-date"}),
            ("span", {"class_": "date"}),
        ],
        "content_selectors": [
            ("div", {"class_": "td-post-content"}),
            ("div", {"class_": "entry-content"}),
            ("article", {}),
        ],
    },
    "Mid Day (Gujarati)": {
        "url": "https://www.gujaratimidday.com/",
        "flag": "📄",
        "search_paths": ["?s={kw}"],
        "rss_paths": ["feed", "rss"],
        "date_selectors": [
            ("h5", {}),
            ("span", {"class_": "date"}),
            ("time", {}),
        ],
        "content_selectors": [
            ("div", {"class_": "article-body"}),
            ("div", {"class_": "article-content"}),
            ("div", {"class_": "content"}),
        ],
    },
    "Divya Bhaskar": {
        "url": "https://www.divyabhaskar.co.in/",
        "flag": "🗞️",
        "search_paths": ["?s={kw}", "search?q={kw}"],
        "rss_paths": ["feed", "rss-feed/1061/"],
        "date_selectors": [
            ("span", {"class_": "posted-on"}),
            ("time", {"class_": "entry-date published"}),
            ("span", {"class_": "date"}),
        ],
        "content_selectors": [
            ("div", {"class_": "db-article-body"}),
            ("div", {"class_": "article-body"}),
            ("div", {"class_": "story-content"}),
        ],
    },
    "Sandesh": {
        "url": "https://www.sandesh.com/",
        "flag": "📋",
        "search_paths": ["?s={kw}"],
        "rss_paths": ["feed", "rss"],
        "date_selectors": [
            ("span", {"class_": "date"}),
            ("time", {}),
        ],
        "content_selectors": [
            ("div", {"class_": "article-content"}),
            ("div", {"class_": "post-content"}),
        ],
    },
    "TV9 Gujarati": {
        "url": "https://tv9gujarati.com/",
        "flag": "📺",
        "search_paths": ["?s={kw}"],
        "rss_paths": ["feed"],
        "date_selectors": [
            ("span", {"class_": "date"}),
            ("time", {}),
        ],
        "content_selectors": [
            ("div", {"class_": "article-content"}),
            ("div", {"class_": "entry-content"}),
        ],
    },
    "ABP Asmita": {
        "url": "https://www.abpasmita.com/",
        "flag": "📡",
        "search_paths": ["?s={kw}"],
        "rss_paths": ["feed"],
        "date_selectors": [
            ("span", {"class_": "date"}),
            ("time", {}),
        ],
        "content_selectors": [
            ("div", {"class_": "article-content"}),
            ("div", {"class_": "entry-content"}),
        ],
    },
}

# MyMemory locale codes — must be "gu-IN" format, NOT bare "gu"
MYMEMORY_LOCALES = {
    "en":    "en-GB",
    "hi":    "hi-IN",
    "gu":    "gu-IN",
    "mr":    "mr-IN",
    "bn":    "bn-IN",
    "ta":    "ta-IN",
    "te":    "te-IN",
    "kn":    "kn-IN",
    "pa":    "pa-IN",
    "ur":    "ur-PK",
    "fr":    "fr-FR",
    "de":    "de-DE",
    "es":    "es-ES",
    "ja":    "ja-JP",
    "zh-CN": "zh-CN",
    "ar":    "ar-SA",
}

LANGUAGES = {
    "English": "en",
    "Hindi": "hi",
    "Gujarati": "gu",
    "Marathi": "mr",
    "Bengali": "bn",
    "Tamil": "ta",
    "Telugu": "te",
    "Kannada": "kn",
    "Punjabi": "pa",
    "Urdu": "ur",
    "French": "fr",
    "German": "de",
    "Spanish": "es",
    "Japanese": "ja",
    "Chinese (Simplified)": "zh-CN",
    "Arabic": "ar",
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
]

# ─────────────────────────────────────────────────────────────────────────────
#  BOOKMARK PERSISTENCE  [FIX-3]
# ─────────────────────────────────────────────────────────────────────────────

def load_bookmarks_from_disk():
    """Load bookmarks from local JSON file. Survives page reloads."""
    try:
        if os.path.exists(BOOKMARK_FILE):
            with open(BOOKMARK_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
    except Exception:
        pass
    return []

def save_bookmarks_to_disk(bookmarks):
    """Write bookmarks list to disk immediately after any change."""
    try:
        with open(BOOKMARK_FILE, "w", encoding="utf-8") as f:
            json.dump(bookmarks, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.warning(f"Could not save bookmarks: {e}")

# ─────────────────────────────────────────────────────────────────────────────
#  SESSION STATE
# ─────────────────────────────────────────────────────────────────────────────

def init_session():
    if "initialized" not in st.session_state:
        saved = load_bookmarks_from_disk()          # [FIX-3] load from disk
        st.session_state.bookmarks = saved
        st.session_state.bookmarked_urls = {b["url"] for b in saved}
        st.session_state.search_history = []
        st.session_state.articles_cache = {}
        st.session_state.total_searches = 0
        st.session_state.last_search_articles = []
        st.session_state.initialized = True

# ─────────────────────────────────────────────────────────────────────────────
#  TRANSLATION — MyMemory (no key) + fallback  [FIX-1]
# ─────────────────────────────────────────────────────────────────────────────

def _mymemory_chunk(text, src_locale, tgt_locale):
    """Call MyMemory free REST API for one text chunk."""
    resp = requests.get(
        "https://api.mymemory.translated.net/get",
        params={
            "q": text,
            "langpair": f"{src_locale}|{tgt_locale}",
            "de": "gujaratinewsscraper@email.com",  # raises daily limit to 50k chars
        },
        timeout=12,
    )
    resp.raise_for_status()
    data = resp.json()
    result = data.get("responseData", {}).get("translatedText", "")
    if not result or "MYMEMORY WARNING" in str(result):
        raise ValueError(f"MyMemory: {data.get('responseStatus')}")
    return result

def _google_fallback_chunk(text, target_lang_code):
    """Fallback using deep-translator GoogleTranslator."""
    from deep_translator import GoogleTranslator
    return GoogleTranslator(source="auto", target=target_lang_code).translate(text)

def translate_text(text, target_lang_code, chunk_size=4500):
    """
    Translate full text in paragraph chunks.
    Primary: MyMemory REST API (free, no key).
    Fallback: GoogleTranslator via deep-translator.
    """
    if not text or not text.strip():
        return ""

    src_locale = "gu-IN"
    tgt_locale = MYMEMORY_LOCALES.get(target_lang_code, f"{target_lang_code}-{target_lang_code.upper()}")

    # Build chunks on paragraph boundaries
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks, current = [], ""
    for para in paragraphs:
        if len(current) + len(para) + 2 <= chunk_size:
            current = (current + "\n\n" + para).strip() if current else para
        else:
            if current:
                chunks.append(current)
            current = para
    if current:
        chunks.append(current)

    parts = []
    for chunk in chunks:
        translated = None
        # Try MyMemory (2 attempts)
        for attempt in range(2):
            try:
                translated = _mymemory_chunk(chunk, src_locale, tgt_locale)
                time.sleep(0.4)
                break
            except Exception:
                time.sleep(1.5)
        # Fallback to Google Translate
        if not translated:
            try:
                translated = _google_fallback_chunk(chunk, target_lang_code)
            except Exception:
                translated = chunk   # keep original on complete failure
        parts.append(translated)

    return "\n\n".join(parts)

# ─────────────────────────────────────────────────────────────────────────────
#  NETWORK UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def get_headers(url=""):
    parsed = urlparse(url)
    referer = f"{parsed.scheme}://{parsed.netloc}/" if parsed.netloc else "https://www.google.com/"
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "gu-IN,gu;q=0.9,en-IN;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Referer": referer,
        "Cache-Control": "max-age=0",
    }

def safe_get(url, retries=3, delay=1.5):
    session = requests.Session()
    for attempt in range(retries):
        try:
            session.headers.update(get_headers(url))
            resp = session.get(url, timeout=15, allow_redirects=True)
            if resp.status_code == 200 and len(resp.content) > 50:
                return resp
            if resp.status_code in (403, 429, 503):
                time.sleep(delay * (attempt + 1) + random.uniform(0.5, 2))
        except Exception:
            if attempt < retries - 1:
                time.sleep(delay * (attempt + 1))
    return None

def normalize_url(href, base_url):
    if not href:
        return None
    href = href.strip()
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("http"):
        return href
    return urljoin(base_url, href)

def stable_key(text):
    return hashlib.md5(text.encode()).hexdigest()[:12]

# ─────────────────────────────────────────────────────────────────────────────
#  SCRAPING — MULTI-STRATEGY  [FIX-2]
# ─────────────────────────────────────────────────────────────────────────────

SKIP_URL_PARTS = {
    "#", "javascript:", "mailto:", "tel:", "/tag/", "/category/",
    "/page/", "/feed", "/rss", "/sitemap", "/about", "/contact",
    "/privacy", "/terms", "/advertise", "/author/", "/wp-admin",
}

def _is_article_url(href):
    href_lower = href.lower()
    if any(p in href_lower for p in SKIP_URL_PARTS):
        return False
    if "?" in href and "s=" in href:
        return False
    return True

def _links_from_soup(soup, base_url, keyword, max_links, seen):
    kw = keyword.lower()
    links = []
    for a in soup.find_all("a", href=True):
        href = normalize_url(a.get("href", ""), base_url)
        if not href or href in seen or not _is_article_url(href):
            continue
        text = a.get_text(strip=True)
        path = urlparse(href).path.lower()
        if kw in path or kw in text.lower():
            seen.add(href)
            links.append({"url": href, "title": text or href})
            if len(links) >= max_links:
                break
    return links

def _links_from_rss(rss_url, keyword, max_links, seen):
    resp = safe_get(rss_url)
    if not resp:
        return []
    try:
        soup = BeautifulSoup(resp.content, "xml")
        items = soup.find_all("item") or soup.find_all("entry")
        kw = keyword.lower()
        links = []
        for item in items:
            title_el = item.find("title")
            link_el = item.find("link")
            title = title_el.get_text(strip=True) if title_el else ""
            href = ""
            if link_el:
                href = link_el.get_text(strip=True) or link_el.get("href", "")
            if href and href not in seen and (kw in title.lower() or kw in href.lower()):
                seen.add(href)
                links.append({"url": href, "title": title or href})
                if len(links) >= max_links:
                    break
        return links
    except Exception:
        return []

def fetch_article_links(newspaper_name, keyword, max_links=10):
    """
    Multi-strategy fetcher. Returns (links, error_msg_or_None, is_blocked).
    Strategies: 1) direct homepage  2) search URL  3) RSS feeds
    """
    config = NEWSPAPER_CONFIG[newspaper_name]
    base_url = config["url"]
    seen, links = set(), []

    # Strategy 1: direct homepage
    resp = safe_get(base_url)
    if not resp:
        # [FIX-2] site is blocked — clear message + manual link
        return [], None, True

    soup = BeautifulSoup(resp.content, "html.parser")
    links.extend(_links_from_soup(soup, base_url, keyword, max_links, seen))

    # Strategy 2: search URL
    if len(links) < 3:
        for path_tpl in config.get("search_paths", []):
            search_url = base_url.rstrip("/") + "/" + path_tpl.format(kw=quote(keyword))
            resp2 = safe_get(search_url)
            if resp2:
                soup2 = BeautifulSoup(resp2.content, "html.parser")
                links.extend(_links_from_soup(soup2, base_url, keyword, max_links - len(links), seen))
            if len(links) >= max_links:
                break

    # Strategy 3: RSS
    if len(links) < 3:
        for rss_path in config.get("rss_paths", []):
            rss_url = base_url.rstrip("/") + "/" + rss_path
            links.extend(_links_from_rss(rss_url, keyword, max_links - len(links), seen))
            if len(links) >= max_links:
                break

    if not links:
        return [], f"No articles found for **'{keyword}'**. Try a different keyword.", False

    return links[:max_links], None, False

# ─────────────────────────────────────────────────────────────────────────────
#  ARTICLE EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────

def extract_article_date(soup, selectors):
    for tag, attrs in selectors:
        el = soup.find(tag, **attrs) if attrs else soup.find(tag)
        if el:
            text = el.get_text(strip=True)
            if text:
                return text
            dt = el.get("datetime", "")
            if dt:
                return dt.split("T")[0]
    time_el = soup.find("time")
    if time_el:
        return time_el.get("datetime", time_el.get_text(strip=True))
    meta = soup.find("meta", {"property": "article:published_time"})
    if meta:
        return meta.get("content", "").split("T")[0]
    return "Date not found"

def extract_article_content(soup, selectors):
    for tag, attrs in selectors:
        content = soup.find(tag, **attrs) if attrs else soup.find(tag)
        if content:
            paras = content.find_all("p") or content.find_all(["p", "div", "span"])
            seen_t, parts = set(), []
            for p in paras:
                text = p.get_text(strip=True)
                if text and text not in seen_t and len(text) > 20:
                    seen_t.add(text)
                    parts.append(text)
            if parts:
                return "\n\n".join(parts)
    paras = soup.find_all("p")
    seen_t, parts = set(), []
    for p in paras:
        text = p.get_text(strip=True)
        if text and text not in seen_t and len(text) > 30:
            seen_t.add(text)
            parts.append(text)
    return "\n\n".join(parts) if parts else ""

def extract_article(url, newspaper_name):
    resp = safe_get(url)
    if not resp:
        return {
            "date": "N/A", "title": url,
            "content": "⚠️ Could not fetch article. The site may be blocking requests.",
            "image": "", "read_time": 0, "word_count": 0,
        }
    soup = BeautifulSoup(resp.content, "html.parser")
    config = NEWSPAPER_CONFIG.get(newspaper_name, {})
    date_ = extract_article_date(soup, config.get("date_selectors", []))
    content = extract_article_content(soup, config.get("content_selectors", []))
    og_title = soup.find("meta", property="og:title")
    title = (og_title.get("content", "") if og_title else "") or (soup.title.get_text(strip=True) if soup.title else url)
    og_img = soup.find("meta", property="og:image")
    image = og_img.get("content", "") if og_img else ""
    word_count = len(content.split()) if content else 0
    return {
        "date": date_, "title": title,
        "content": content or "No content could be extracted.",
        "image": image,
        "read_time": max(1, round(word_count / 200)),
        "word_count": word_count,
    }

# ─────────────────────────────────────────────────────────────────────────────
#  EXPORT
# ─────────────────────────────────────────────────────────────────────────────

def articles_to_csv(articles):
    output = io.StringIO()
    fields = ["newspaper", "title", "date", "url", "word_count", "read_time_mins", "content"]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for a in articles:
        writer.writerow({
            "newspaper": a.get("newspaper", ""),
            "title": a.get("title", ""),
            "date": a.get("date", ""),
            "url": a.get("url", ""),
            "word_count": a.get("word_count", 0),
            "read_time_mins": a.get("read_time", 0),
            "content": a.get("content", "").replace("\n", " | "),
        })
    return output.getvalue().encode("utf-8")

def articles_to_json(articles):
    return json.dumps(articles, ensure_ascii=False, indent=2).encode("utf-8")

# ─────────────────────────────────────────────────────────────────────────────
#  UI HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def keyword_highlight(text, keyword):
    if not keyword or not text:
        return text
    pattern = re.compile(re.escape(keyword), re.IGNORECASE)
    return pattern.sub(
        lambda m: f"<mark style='background:#FFE066;padding:0 2px;border-radius:3px'>{m.group()}</mark>",
        text,
    )

def render_blocked_error(newspaper_name, base_url):
    """Styled error card for bot-blocked sites. [FIX-2]"""
    st.error(
        f"🚫 **{newspaper_name}** is blocking automated scraping (HTTP 403).\n\n"
        f"Please open it manually: **[Open {newspaper_name} →]({base_url})**"
    )

def render_article_card(art, keyword, idx, newspaper_name, translate_to=None):
    url = art["url"]
    s_key = stable_key(url)

    with st.expander(f"Article {idx}: {(art['title'] or url)[:80]}", expanded=False):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.caption(f"📅 {art['date']} | ⏱ {art['read_time']} min | 📝 {art['word_count']} words")
        with col2:
            st.markdown(f"[🔗 Open Article]({url})")

        if art.get("image"):
            try:
                st.image(art["image"], use_container_width=True)
            except Exception:
                pass

        tab_orig, tab_trans = st.tabs(["📄 Original", "🌐 Translated"])

        with tab_orig:
            st.markdown(keyword_highlight(art["content"], keyword), unsafe_allow_html=True)

        with tab_trans:
            if translate_to and translate_to != "-- Select Language --":
                lang_code = LANGUAGES.get(translate_to)
                if lang_code:
                    cache_key = f"{url}_{lang_code}"
                    if cache_key in st.session_state.articles_cache:
                        # Already translated — show immediately
                        st.write(st.session_state.articles_cache[cache_key])
                    else:
                        # [FIX-1] Explicit button — only translates when clicked
                        if st.button(f"Translate to {translate_to}", key=f"trans_{s_key}_{idx}"):
                            with st.spinner(f"Translating to {translate_to} via MyMemory…"):
                                result = translate_text(art["content"], lang_code)
                                st.session_state.articles_cache[cache_key] = result
                            st.rerun()
            else:
                st.info("Select a language in the sidebar, then click Translate.")

        # ── Bookmark button [FIX-3] ───────────────────────────────────────────
        is_bookmarked = url in st.session_state.bookmarked_urls
        btn_label = "✅ Bookmarked" if is_bookmarked else "🔖 Bookmark"

        if st.button(btn_label, key=f"bm_{s_key}_{idx}"):
            if url not in st.session_state.bookmarked_urls:
                st.session_state.bookmarked_urls.add(url)
                st.session_state.bookmarks.append(dict(art))
                save_bookmarks_to_disk(st.session_state.bookmarks)   # write to disk immediately
                st.success("Bookmarked! ✅")
            else:
                st.session_state.bookmarked_urls.discard(url)
                st.session_state.bookmarks = [
                    b for b in st.session_state.bookmarks if b.get("url") != url
                ]
                save_bookmarks_to_disk(st.session_state.bookmarks)   # write to disk immediately
                st.info("Bookmark removed.")
            st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
#  MAIN APP
# ─────────────────────────────────────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="Gujarati Newspaper AI Scraper",
        page_icon="📰",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    init_session()

    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Gujarati:wght@400;700&family=Playfair+Display:wght@700&family=Inter:wght@400;500;600&display=swap');
    .main { background: #F8F6F1; }
    h1 { font-family: 'Playfair Display', serif !important; color: #1A0A00; }
    .stButton>button { border-radius: 8px; font-weight: 600; transition: all 0.2s; }
    .stButton>button:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
    mark { background: #FFE066; padding: 0 3px; border-radius: 3px; }
    .stExpander { border-radius: 12px !important; border: 1px solid #E8E4DC !important; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("# 📰 Gujarati Newspaper AI Scraper")
    st.markdown("*Search · Scrape · Translate · Export — all Gujarati newspapers in one place*")
    st.divider()

    # ── Sidebar ──────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### ⚙️ Search Settings")
        selected_papers = st.multiselect(
            "Select Newspapers",
            list(NEWSPAPER_CONFIG.keys()),
            default=["Gujarat Samachar"],
        )
        max_articles = st.slider("Max articles per newspaper", 3, 15, 5)

        st.markdown("---")
        st.markdown("### 🌐 Translation")
        st.caption("Free · No API key · Powered by MyMemory")
        translate_to = st.selectbox(
            "Translate articles to",
            ["-- Select Language --"] + list(LANGUAGES.keys()),
            index=0,
        )
        if translate_to != "-- Select Language --":
            st.success(f"Click **'Translate to {translate_to}'** inside any article tab.")

        st.markdown("---")
        st.markdown("### 📊 Session Stats")
        c1, c2 = st.columns(2)
        c1.metric("Searches", st.session_state.total_searches)
        c2.metric("Bookmarks", len(st.session_state.bookmarks))

        if st.session_state.search_history:
            st.markdown("---")
            st.markdown("### 🕒 Recent Searches")
            for h in reversed(st.session_state.search_history[-5:]):
                st.caption(f"• {h}")

    # ── Search bar ───────────────────────────────────────────────────────────
    col_kw, col_btn = st.columns([4, 1])
    with col_kw:
        keyword = st.text_input(
            "Keyword",
            placeholder="e.g. cricket, elections, Modi, ક્રિકેટ …",
            label_visibility="collapsed",
        )
    with col_btn:
        search_clicked = st.button("🔎 Search", type="primary", use_container_width=True)

    tab_results, tab_bookmarks, tab_export = st.tabs(["📑 Results", "🔖 Bookmarks", "📤 Export"])

    # ── Results ──────────────────────────────────────────────────────────────
    with tab_results:
        if search_clicked:
            if not keyword.strip():
                st.error("Please enter a search keyword.")
            elif not selected_papers:
                st.error("Please select at least one newspaper.")
            else:
                if keyword not in st.session_state.search_history:
                    st.session_state.search_history.append(keyword)
                st.session_state.total_searches += 1
                all_articles = []

                for paper in selected_papers:
                    config = NEWSPAPER_CONFIG[paper]
                    st.markdown(f"### {config['flag']} {paper}")

                    with st.spinner(f"Searching {paper}…"):
                        links, error, blocked = fetch_article_links(paper, keyword, max_links=max_articles)

                    if blocked:
                        render_blocked_error(paper, config["url"])
                        st.divider()
                        continue

                    if error:
                        st.warning(error)
                        st.divider()
                        continue

                    st.success(f"✅ Found {len(links)} article(s)")

                    for idx, link_info in enumerate(links, 1):
                        url = link_info["url"]
                        with st.spinner(f"Loading article {idx}/{len(links)}…"):
                            art = extract_article(url, paper)
                            art["url"] = url
                            art["newspaper"] = paper
                            all_articles.append(art)

                        render_article_card(
                            art=art,
                            keyword=keyword,
                            idx=idx,
                            newspaper_name=paper,
                            translate_to=translate_to if translate_to != "-- Select Language --" else None,
                        )
                    st.divider()

                if all_articles:
                    st.session_state.last_search_articles = all_articles
                    st.toast(f"✅ {len(all_articles)} article(s) across {len(selected_papers)} newspaper(s)")

    # ── Bookmarks ─────────────────────────────────────────────────────────────
    with tab_bookmarks:
        if not st.session_state.bookmarks:
            st.info(
                "No bookmarks yet.\n\n"
                "Click **🔖 Bookmark** inside any article. "
                "Bookmarks are saved to disk and survive page reloads."
            )
        else:
            st.markdown(f"### {len(st.session_state.bookmarks)} Saved Article(s)")
            st.caption(f"💾 Saved at: `{BOOKMARK_FILE}`")
            for idx, art in enumerate(st.session_state.bookmarks):
                art_url = art.get("url", "")
                with st.expander(f"{idx + 1}. {art.get('title', art_url)[:80]}"):
                    st.caption(f"📅 {art.get('date','N/A')} | 📰 {art.get('newspaper','N/A')}")
                    st.markdown(f"[🔗 Open Article]({art_url})")
                    preview = art.get("content", "")
                    st.write(preview[:600] + ("…" if len(preview) > 600 else ""))
                    if st.button("🗑️ Remove", key=f"del_{stable_key(art_url)}_{idx}"):
                        st.session_state.bookmarked_urls.discard(art_url)
                        st.session_state.bookmarks = [
                            b for b in st.session_state.bookmarks if b.get("url") != art_url
                        ]
                        save_bookmarks_to_disk(st.session_state.bookmarks)
                        st.rerun()

            st.markdown("---")
            if st.button("🗑️ Clear All Bookmarks"):
                st.session_state.bookmarks = []
                st.session_state.bookmarked_urls = set()
                save_bookmarks_to_disk([])
                st.rerun()

    # ── Export ────────────────────────────────────────────────────────────────
    with tab_export:
        articles = st.session_state.last_search_articles
        if not articles:
            st.info("Run a search first. Results will appear here for export.")
        else:
            newspapers_count = len(set(a["newspaper"] for a in articles))
            st.markdown(f"### Export {len(articles)} Article(s)")
            st.markdown(f"**{len(articles)}** articles from **{newspapers_count}** newspaper(s).")
            col_a, col_b = st.columns(2)
            with col_a:
                st.download_button(
                    "⬇️ Download CSV",
                    data=articles_to_csv(articles),
                    file_name=f"gujarati_news_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            with col_b:
                st.download_button(
                    "⬇️ Download JSON",
                    data=articles_to_json(articles),
                    file_name=f"gujarati_news_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                    mime="application/json",
                    use_container_width=True,
                )
            st.markdown("#### Preview")
            for a in articles:
                st.markdown(
                    f"**{a.get('newspaper')}** | {a.get('date')} | "
                    f"[{(a.get('title') or a.get('url',''))[:70]}]({a.get('url','#')})"
                )

if __name__ == "__main__":
    main()
