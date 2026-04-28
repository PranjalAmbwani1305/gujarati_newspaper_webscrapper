"""
================================================================================
                    GUJARATI NEWS HUB - FULL APPLICATION
                     Web Scraper & Translation Tool
================================================================================
Purpose: Search, scrape, translate, and export articles from Gujarati newspapers
Dependencies: streamlit, requests, beautifulsoup4
Translation: Uses free urllib-based Google Translate (no API key required)
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
import urllib.parse
import urllib.request
import html

# ═════════════════════════════════════════════════════════════════════════════
#                       CONSTANTS & CONFIGURATION
# ═════════════════════════════════════════════════════════════════════════════

NEWSPAPER_CONFIG = {
    "Gujarat Samachar": {
        "url": "https://www.gujaratsamachar.com/",
        "lang": "gu",
        "search_url": "https://www.gujaratsamachar.com/?s={keyword}",
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
        "lang": "gu",
        "search_url": "https://www.gujaratimidday.com/?s={keyword}",
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
        "lang": "gu",
        "search_url": "https://www.divyabhaskar.co.in/search/?q={keyword}",
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
        "lang": "gu",
        "search_url": "https://www.sandesh.com/?s={keyword}",
        "date_selectors": [
            ("span", {"class_": "date"}),
            ("time", {}),
        ],
        "content_selectors": [
            ("div", {"class_": "article-content"}),
            ("div", {"class_": "post-content"}),
        ],
    },
    "Akila Online": {
        "url": "https://www.akilanews.com/",
        "lang": "gu",
        "search_url": "https://www.akilanews.com/?s={keyword}",
        "date_selectors": [
            ("span", {"class_": "date"}),
            ("time", {}),
        ],
        "content_selectors": [
            ("div", {"class_": "entry-content"}),
            ("div", {"class_": "post-content"}),
            ("article", {}),
        ],
    },
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
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Mobile/15E148 Safari/604.1",
]

# ═════════════════════════════════════════════════════════════════════════════
#                    SESSION STATE INITIALIZATION
# ═════════════════════════════════════════════════════════════════════════════

def init_session():
    defaults = {
        "search_history": [],
        "bookmarks": [],
        "articles_cache": {},
        "total_searches": 0,
        "last_search_articles": [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

# ═════════════════════════════════════════════════════════════════════════════
#               FREE TRANSLATION (NO API KEY REQUIRED)
# ═════════════════════════════════════════════════════════════════════════════

def translate_free(text, dest="en", src="auto"):
    """
    Translate text using the free Google Translate web endpoint.
    No API key required. Works by calling the same endpoint browsers use.

    Args:
        text (str): Text to translate
        dest (str): Target language code (e.g. 'en', 'hi', 'gu')
        src (str): Source language code or 'auto'

    Returns:
        str: Translated text, or original text with error note on failure
    """
    if not text or not text.strip():
        return ""

    CHUNK = 4500
    paragraphs = text.split("\n")
    chunks, current = [], ""
    for para in paragraphs:
        if len(current) + len(para) + 1 <= CHUNK:
            current += para + "\n"
        else:
            if current.strip():
                chunks.append(current.strip())
            current = para + "\n"
    if current.strip():
        chunks.append(current.strip())

    translated_chunks = []
    for chunk in chunks:
        result = _translate_chunk(chunk, dest=dest, src=src)
        translated_chunks.append(result)
        time.sleep(0.3)

    return "\n\n".join(translated_chunks)


def _translate_chunk(text, dest="en", src="auto"):
    """Translate a single chunk via Google Translate web endpoint."""
    base = "https://translate.googleapis.com/translate_a/single"
    params = urllib.parse.urlencode({
        "client": "gtx",
        "sl": src,
        "tl": dest,
        "dt": "t",
        "q": text,
    })
    url = f"{base}?{params}"

    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://translate.google.com/",
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")

        # Response is a nested JSON list; extract translated text segments
        data = json.loads(raw)
        translated = ""
        if data and isinstance(data[0], list):
            for segment in data[0]:
                if segment and isinstance(segment, list) and segment[0]:
                    translated += html.unescape(str(segment[0]))
        return translated if translated.strip() else text

    except Exception as e:
        # Fallback: try requests library
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            data = resp.json()
            translated = ""
            if data and isinstance(data[0], list):
                for segment in data[0]:
                    if segment and isinstance(segment, list) and segment[0]:
                        translated += html.unescape(str(segment[0]))
            return translated if translated.strip() else text
        except Exception:
            return f"[Translation unavailable]\n\n{text}"


# ═════════════════════════════════════════════════════════════════════════════
#                       SCRAPING UTILITIES
# ═════════════════════════════════════════════════════════════════════════════

def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,gu;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
        "Referer": "https://www.google.com/",
    }


def safe_get(url, retries=3, delay=1.5):
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=get_headers(), timeout=15, allow_redirects=True)
            resp.raise_for_status()
            return resp
        except requests.exceptions.HTTPError as e:
            if hasattr(e, "response") and e.response is not None and e.response.status_code == 403:
                try:
                    s = requests.Session()
                    s.headers.update(get_headers())
                    r = s.get(url, timeout=15)
                    r.raise_for_status()
                    return r
                except Exception:
                    pass
            if attempt < retries - 1:
                time.sleep(delay * (attempt + 1) + random.uniform(0, 1))
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            if attempt < retries - 1:
                time.sleep(delay * (attempt + 1))
        except Exception:
            break
    return None


def normalize_url(href, base_url):
    if not href:
        return None
    href = href.strip()
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("http"):
        return href
    base = base_url.rstrip("/")
    return f"{base}/{href.lstrip('/')}"


def is_article_link(href, text, keyword):
    skip = ["#", "javascript:", "mailto:", "tel:", "/tag/", "/category/",
            "/page/", "?s=", "/feed", "/rss", "/sitemap", "/about",
            "/contact", "/privacy", "/terms", "/advertise", "/subscribe"]
    if any(p in href.lower() for p in skip):
        return False
    kw_lower = keyword.lower()
    return kw_lower in href.lower() or kw_lower in text.lower()


def fetch_article_links(newspaper_name, keyword, max_links=10):
    config = NEWSPAPER_CONFIG[newspaper_name]
    base_url = config["url"]
    search_url_tpl = config.get("search_url", "")

    seen, links = set(), []

    # 1. Try dedicated search URL first
    if search_url_tpl:
        search_url = search_url_tpl.replace("{keyword}", urllib.parse.quote(keyword))
        resp = safe_get(search_url)
        if resp:
            soup = BeautifulSoup(resp.content, "html.parser")
            for a in soup.find_all("a", href=True):
                href = normalize_url(a.get("href", ""), base_url)
                text = a.get_text(strip=True)
                if href and href not in seen and len(href) > len(base_url) + 5:
                    skip = ["#", "javascript:", "mailto:", "/tag/", "/category/",
                            "/page/", "/feed", "/rss", "/sitemap", "/about",
                            "/contact", "/privacy", "/terms", "/subscribe"]
                    if not any(p in href.lower() for p in skip):
                        seen.add(href)
                        links.append({"url": href, "title": text or href})
                        if len(links) >= max_links:
                            break

    # 2. Fallback: homepage scrape with keyword filter
    if len(links) < 3:
        resp = safe_get(base_url)
        if resp:
            soup = BeautifulSoup(resp.content, "html.parser")
            for a in soup.find_all("a", href=True):
                href = normalize_url(a.get("href", ""), base_url)
                text = a.get_text(strip=True)
                if href and href not in seen and is_article_link(href, text, keyword):
                    seen.add(href)
                    links.append({"url": href, "title": text or href})
                    if len(links) >= max_links:
                        break

    if not links:
        return [], "No articles found. The site may be blocking scrapers or keyword not found."

    return links[:max_links], None


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
            seen, parts = set(), []
            for p in paras:
                t = p.get_text(strip=True)
                if t and t not in seen and len(t) > 20:
                    seen.add(t)
                    parts.append(t)
            if parts:
                return "\n\n".join(parts)

    paras = soup.find_all("p")
    seen, parts = set(), []
    for p in paras:
        t = p.get_text(strip=True)
        if t and t not in seen and len(t) > 30:
            seen.add(t)
            parts.append(t)
    return "\n\n".join(parts) if parts else ""


def get_og_image(soup):
    og = soup.find("meta", property="og:image")
    return og.get("content", "") if og else ""


def get_og_title(soup):
    og = soup.find("meta", property="og:title")
    if og:
        return og.get("content", "")
    t = soup.find("title")
    return t.get_text(strip=True) if t else ""


def extract_article(url, newspaper_name):
    resp = safe_get(url)
    if not resp:
        return {
            "date": "N/A",
            "title": url,
            "content": "Could not fetch article. The site may be blocking automated requests.",
            "image": "",
            "read_time": 0,
            "word_count": 0,
        }

    soup = BeautifulSoup(resp.content, "html.parser")
    config = NEWSPAPER_CONFIG.get(newspaper_name, {})

    date_ = extract_article_date(soup, config.get("date_selectors", []))
    content = extract_article_content(soup, config.get("content_selectors", []))
    title = get_og_title(soup)
    image = get_og_image(soup)
    word_count = len(content.split()) if content else 0
    read_time = max(1, round(word_count / 200))

    return {
        "date": date_,
        "title": title,
        "content": content or "No content could be extracted from this article.",
        "image": image,
        "read_time": read_time,
        "word_count": word_count,
    }


# ═════════════════════════════════════════════════════════════════════════════
#                    EXPORT UTILITIES
# ═════════════════════════════════════════════════════════════════════════════

def articles_to_csv(articles):
    output = io.StringIO()
    fieldnames = ["newspaper", "title", "date", "url", "word_count", "read_time_mins", "content"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
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


# ═════════════════════════════════════════════════════════════════════════════
#                    UI HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def keyword_highlight(text, keyword):
    if not keyword or not text:
        return text
    pattern = re.compile(re.escape(keyword), re.IGNORECASE)
    return pattern.sub(
        lambda m: f"<mark style='background:#FFE066;padding:0 2px;border-radius:3px'>{m.group()}</mark>",
        text,
    )


def render_article_card(art, keyword, idx, newspaper_name, translate_to=None):
    title_display = art.get("title") or art.get("url", "")
    with st.expander(f"📄 Article {idx}: {title_display[:80]}", expanded=False):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.caption(
                f"📅 {art['date']}  •  ⏱ {art['read_time']} min read  •  📝 {art['word_count']} words"
            )
        with col2:
            st.markdown(f"[🔗 Open Article]({art['url']})")

        if art.get("image"):
            try:
                st.image(art["image"], use_column_width=True)
            except Exception:
                pass

        tab_orig, tab_trans = st.tabs(["🗒 Original", "🌐 Translated"])

        with tab_orig:
            highlighted = keyword_highlight(art["content"], keyword)
            st.markdown(highlighted, unsafe_allow_html=True)

        with tab_trans:
            if translate_to and translate_to != "-- Select Language --":
                lang_code = LANGUAGES.get(translate_to)
                if lang_code:
                    cache_key = f"{art['url']}_{lang_code}"
                    if cache_key not in st.session_state.articles_cache:
                        with st.spinner(f"Translating to {translate_to}…"):
                            src_lang = NEWSPAPER_CONFIG.get(newspaper_name, {}).get("lang", "auto")
                            translated = translate_free(art["content"], dest=lang_code, src=src_lang)
                            st.session_state.articles_cache[cache_key] = translated
                    translated_text = st.session_state.articles_cache.get(cache_key, "")
                    st.write(translated_text)
                    # Download translated text
                    st.download_button(
                        "⬇ Download translation",
                        data=translated_text.encode("utf-8"),
                        file_name=f"article_{idx}_{lang_code}.txt",
                        mime="text/plain",
                        key=f"dl_trans_{idx}_{lang_code}",
                    )
            else:
                st.info("Select a translation language from the sidebar.")

        bm_key = art["url"]
        is_bookmarked = bm_key in [b["url"] for b in st.session_state.bookmarks]
        if st.button(
            "✅ Bookmarked" if is_bookmarked else "🔖 Bookmark",
            key=f"bm_{idx}_{art['url'][:20]}",
        ):
            if bm_key not in [b["url"] for b in st.session_state.bookmarks]:
                st.session_state.bookmarks.append(art)
                st.success("Bookmarked!")
            else:
                st.info("Already bookmarked.")


# ═════════════════════════════════════════════════════════════════════════════
#                    STANDALONE TRANSLATION PAGE
# ═════════════════════════════════════════════════════════════════════════════

def render_translate_page():
    st.markdown("## 🌐 Paste & Translate")
    st.markdown("Paste any Gujarati (or any language) text below and translate it instantly — no API key needed.")

    col_src, col_dst = st.columns(2)
    with col_src:
        src_lang_name = st.selectbox("Source language", ["Auto Detect"] + list(LANGUAGES.keys()), index=0)
    with col_dst:
        dst_lang_name = st.selectbox("Translate to", list(LANGUAGES.keys()), index=0)  # default English

    input_text = st.text_area("Paste text here", height=250, placeholder="Paste Gujarati or any other language text…")

    if st.button("🌐 Translate Now", type="primary"):
        if not input_text.strip():
            st.warning("Please paste some text first.")
        else:
            src_code = "auto" if src_lang_name == "Auto Detect" else LANGUAGES[src_lang_name]
            dst_code = LANGUAGES[dst_lang_name]
            with st.spinner(f"Translating to {dst_lang_name}…"):
                result = translate_free(input_text, dest=dst_code, src=src_code)
            st.markdown(f"**Translation ({dst_lang_name}):**")
            st.text_area("Result", value=result, height=250)
            st.download_button(
                "⬇ Download Translation",
                data=result.encode("utf-8"),
                file_name=f"translation_{dst_code}.txt",
                mime="text/plain",
            )


# ═════════════════════════════════════════════════════════════════════════════
#                    MAIN APPLICATION
# ═════════════════════════════════════════════════════════════════════════════

def main():
    st.set_page_config(
        page_title="Gujarati News Hub",
        page_icon="📰",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    init_session()

    # ── Custom CSS ──────────────────────────
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Gujarati:wght@400;700&family=Playfair+Display:wght@700&family=Inter:wght@400;500;600&display=swap');

    .main { background: #F8F6F1; }
    h1, h2 { font-family: 'Playfair Display', serif !important; color: #1A0A00; }
    .stButton>button { border-radius: 8px; font-weight: 600; transition: all 0.2s; }
    .stButton>button:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
    .stat-card {
        background: white; border-radius: 12px; padding: 16px 20px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.07); text-align: center;
        border-left: 4px solid #FF6B35;
    }
    .stat-number { font-size: 2rem; font-weight: 800; color: #FF6B35; line-height: 1; }
    .stat-label  { font-size: 0.8rem; color: #666; margin-top: 4px; }
    mark { background: #FFE066; padding: 0 3px; border-radius: 3px; }
    .stExpander { border-radius: 12px !important; border: 1px solid #E8E4DC !important; }
    .translation-note {
        background: #E8F4E8; border-left: 4px solid #4CAF50;
        padding: 8px 12px; border-radius: 4px; font-size: 0.85rem; color: #2E7D32;
        margin-bottom: 12px;
    }
    </style>
    """, unsafe_allow_html=True)

    # ── Header ──────────────────────────────
    st.markdown("# 📰 Gujarati News Hub")
    st.markdown("*Search · Scrape · Translate · Export — all Gujarati newspapers in one place*")
    st.markdown(
        '<div class="translation-note">✅ <strong>Translation is free & API-key-free</strong> — uses Google Translate web endpoint directly (no account needed)</div>',
        unsafe_allow_html=True,
    )
    st.divider()

    # ── Sidebar ─────────────────────────────
    with st.sidebar:
        st.markdown("## 📰 Gujarati News Hub")
        page = st.radio("Navigation", ["🔍 Search News", "🌐 Paste & Translate", "🔖 Bookmarks", "📤 Export"], index=0)

        st.markdown("---")
        st.markdown("### ⚙️ Search Settings")
        selected_papers = st.multiselect(
            "Select Newspapers",
            list(NEWSPAPER_CONFIG.keys()),
            default=["Gujarat Samachar"],
            help="Search across multiple newspapers simultaneously",
        )
        max_articles = st.slider("Max articles per newspaper", 3, 15, 5)

        st.markdown("---")
        st.markdown("### 🌐 Translation")
        translate_to = st.selectbox(
            "Translate articles to",
            ["-- Select Language --"] + list(LANGUAGES.keys()),
            index=1,
        )

        st.markdown("---")
        st.markdown("### 📊 Session Stats")
        c1, c2 = st.columns(2)
        c1.metric("Searches", st.session_state.total_searches)
        c2.metric("Bookmarks", len(st.session_state.bookmarks))

        if st.session_state.search_history:
            st.markdown("### 🕐 Recent Searches")
            for h in reversed(st.session_state.search_history[-5:]):
                st.caption(f"• {h}")

    # ── Pages ─────────────────────────────────

    if page == "🌐 Paste & Translate":
        render_translate_page()
        return

    if page == "🔖 Bookmarks":
        st.markdown("## 🔖 Saved Articles")
        if not st.session_state.bookmarks:
            st.info("No bookmarks yet. Search for articles and click 'Bookmark' to save them here.")
        else:
            st.markdown(f"### {len(st.session_state.bookmarks)} saved article(s)")
            for idx, art in enumerate(st.session_state.bookmarks, 1):
                with st.expander(f"{idx}. {art.get('title', art.get('url', ''))[:80]}"):
                    st.caption(f"📅 {art.get('date', 'N/A')} | [🔗 Open Article]({art.get('url', '#')})")
                    st.write(art.get("content", "")[:600] + "…")
                    if st.button("🗑 Remove", key=f"del_bm_{idx}"):
                        st.session_state.bookmarks.pop(idx - 1)
                        st.rerun()
            if st.button("🗑 Clear All Bookmarks"):
                st.session_state.bookmarks = []
                st.rerun()
        return

    if page == "📤 Export":
        st.markdown("## 📤 Export Articles")
        articles = st.session_state.get("last_search_articles", [])
        if not articles:
            st.info("Run a search first. Scraped articles will appear here for export.")
        else:
            newspapers = set(a["newspaper"] for a in articles)
            st.markdown(f"**{len(articles)} articles** from **{len(newspapers)} newspaper(s)**")
            col_a, col_b = st.columns(2)
            with col_a:
                st.download_button(
                    "⬇ Download as CSV",
                    data=articles_to_csv(articles),
                    file_name=f"gujarati_news_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            with col_b:
                st.download_button(
                    "⬇ Download as JSON",
                    data=articles_to_json(articles),
                    file_name=f"gujarati_news_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                    mime="application/json",
                    use_container_width=True,
                )
            st.markdown("#### Preview")
            for a in articles:
                st.markdown(
                    f"**{a.get('newspaper')}** | {a.get('date')} | "
                    f"[{a.get('title', a.get('url', ''))[:60]}]({a.get('url', '#')})"
                )
        return

    # ── Search Page (default) ─────────────────
    st.markdown("## 🔍 Search News")

    col_kw, col_btn = st.columns([4, 1])
    with col_kw:
        keyword = st.text_input(
            "Search keyword",
            placeholder="e.g. cricket, elections, Modi, ક્રિકેટ ...",
            label_visibility="collapsed",
        )
    with col_btn:
        search_clicked = st.button("Search 🔍", type="primary", use_container_width=True)

    if search_clicked:
        if not keyword.strip():
            st.error("Please enter a keyword.")
        elif not selected_papers:
            st.error("Please select at least one newspaper from the sidebar.")
        else:
            if keyword not in st.session_state.search_history:
                st.session_state.search_history.append(keyword)
            st.session_state.total_searches += 1

            all_articles = []

            for paper in selected_papers:
                config = NEWSPAPER_CONFIG[paper]
                st.markdown(f"### 📰 {paper}")

                with st.spinner(f"Searching {paper}…"):
                    links, error = fetch_article_links(paper, keyword, max_links=max_articles)

                if error:
                    st.warning(f"⚠️ {paper}: {error}")
                    continue

                if not links:
                    st.info(f"No articles found for '{keyword}' in {paper}.")
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
                st.session_state["last_search_articles"] = all_articles
                st.toast(f"✅ {len(all_articles)} article(s) across {len(selected_papers)} newspaper(s)!")


if __name__ == "__main__":
    main()
