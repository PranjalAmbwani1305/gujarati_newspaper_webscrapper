"""
================================================================================
                    GUJARATI NEWS HUB - FULL APPLICATION
                     Web Scraper & Translation Tool
================================================================================
Author: News Hub Team
Purpose: Search, scrape, translate, and export articles from Gujarati newspapers
Dependencies: streamlit, requests, beautifulsoup4, deep-translator
================================================================================

FIXES APPLIED (v2):
  1. Translation (English / Hindi):
     - GoogleTranslator source now always passes "auto" as a plain string;
       never passes a newspaper-config lang code that may not be a valid
       deep-translator source identifier (e.g. "gu" caused silent failures).
     - Chunk joining now preserves paragraph breaks (\n\n).
     - Added per-chunk retry + explicit error surface in the UI.
     - translate_text now returns the ORIGINAL text on failure so the tab
       is never blank.

  2. Bookmarks not saving:
     - Removed the fragile button-key derived from url[:20] (collisions).
     - Bookmark state is now tracked in st.session_state["bookmarked_urls"]
       (a set), written BEFORE st.rerun() so the UI reflects immediately.
     - Added st.rerun() after toggling so the button label updates.
================================================================================
"""

import streamlit as st
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
import time
import random
import csv
import io
from datetime import datetime
import re
import json
import hashlib

# ═════════════════════════════════════════════════════════════════════════════
#                       CONSTANTS & CONFIGURATION
# ═════════════════════════════════════════════════════════════════════════════

NEWSPAPER_CONFIG = {
    "Gujarat Samachar": {
        "url": "https://www.gujaratsamachar.com/",
        "flag": "📰",
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
        "date_selectors": [
            ("span", {"class_": "date"}),
            ("time", {}),
        ],
        "content_selectors": [
            ("div", {"class_": "article-content"}),
            ("div", {"class_": "post-content"}),
        ],
    },
}

# Supported languages for translation
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
    """Initialize session state variables on app startup."""
    defaults = {
        "search_history": [],
        "bookmarks": [],           # list of article dicts
        "bookmarked_urls": set(),  # FIX: fast O(1) lookup; keeps state across reruns
        "articles_cache": {},
        "total_searches": 0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

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
            if e.response.status_code == 403:
                try:
                    session = requests.Session()
                    session.headers.update(get_headers())
                    resp = session.get(url, timeout=15)
                    resp.raise_for_status()
                    return resp
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
    skip_patterns = [
        "#", "javascript:", "mailto:", "tel:", "/tag/", "/category/",
        "/page/", "?s=", "/feed", "/rss", "/sitemap", "/about",
        "/contact", "/privacy", "/terms", "/advertise",
    ]
    if any(p in href.lower() for p in skip_patterns):
        return False
    kw_lower = keyword.lower()
    return kw_lower in href.lower() or kw_lower in text.lower()

def fetch_article_links(base_url, keyword, max_links=10):
    resp = safe_get(base_url)
    if not resp:
        return [], "Could not reach the newspaper website. It may be blocking scrapers."

    soup = BeautifulSoup(resp.content, "html.parser")
    seen, links = set(), []

    search_urls = [
        f"{base_url}?s={keyword}",
        f"{base_url}search?q={keyword}",
        f"{base_url}search/{keyword}",
        f"{base_url}tag/{keyword.lower().replace(' ', '-')}",
    ]

    for a in soup.find_all("a", href=True):
        href = normalize_url(a.get("href", ""), base_url)
        text = a.get_text(strip=True)
        if href and href not in seen and is_article_link(href, text, keyword):
            seen.add(href)
            links.append({"url": href, "title": text or href})
            if len(links) >= max_links:
                break

    if len(links) < 3:
        for search_url in search_urls:
            try:
                search_resp = safe_get(search_url)
                if search_resp and search_resp.status_code == 200:
                    search_soup = BeautifulSoup(search_resp.content, "html.parser")
                    for a in search_soup.find_all("a", href=True):
                        href = normalize_url(a.get("href", ""), base_url)
                        text = a.get_text(strip=True)
                        if href and href not in seen and is_article_link(href, text, keyword):
                            seen.add(href)
                            links.append({"url": href, "title": text or href})
                            if len(links) >= max_links:
                                break
                if len(links) >= max_links:
                    break
            except Exception:
                continue

    return links, None

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
    meta_date = soup.find("meta", {"property": "article:published_time"})
    if meta_date:
        return meta_date.get("content", "").split("T")[0]
    return "Date not found"

def extract_article_content(soup, selectors):
    for tag, attrs in selectors:
        content = soup.find(tag, **attrs) if attrs else soup.find(tag)
        if content:
            paras = content.find_all("p") or content.find_all(["p", "div", "span"])
            seen, parts = set(), []
            for p in paras:
                text = p.get_text(strip=True)
                if text and text not in seen and len(text) > 20:
                    seen.add(text)
                    parts.append(text)
            if parts:
                return "\n\n".join(parts)

    paras = soup.find_all("p")
    seen, parts = set(), []
    for p in paras:
        text = p.get_text(strip=True)
        if text and text not in seen and len(text) > 30:
            seen.add(text)
            parts.append(text)
    return "\n\n".join(parts) if parts else ""

def get_og_image(soup):
    og = soup.find("meta", property="og:image")
    return og.get("content", "") if og else ""

def get_og_title(soup):
    og = soup.find("meta", property="og:title")
    if og:
        return og.get("content", "")
    title = soup.find("title")
    return title.get_text(strip=True) if title else ""

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
#                    TRANSLATION UTILITIES  (FIX v2)
# ═════════════════════════════════════════════════════════════════════════════

def translate_text(text, target_lang_code, chunk_size=4500):
    """
    Translate text to target_lang_code in safe chunks.

    FIX: source is always "auto" — passing a newspaper-specific lang code
    (e.g. "gu") as the source to deep-translator can cause silent failures
    or exceptions because deep-translator maps language codes differently
    from what Google Translate expects internally.  Using "auto" lets Google
    detect the source reliably and works for both Gujarati → English and
    Gujarati → Hindi.

    FIX: paragraph separator is preserved by splitting on "\n\n" and
    re-joining with "\n\n" so the translated output keeps its structure.

    FIX: returns original text on any error so the tab is never blank.
    """
    if not text or not text.strip():
        return ""

    # Split on blank lines (paragraph boundaries) first; fall back to lines.
    paragraphs = text.split("\n\n")
    chunks, current = [], ""

    for para in paragraphs:
        if len(current) + len(para) + 2 < chunk_size:
            current = current + para + "\n\n" if current else para + "\n\n"
        else:
            if current:
                chunks.append(current.strip())
            current = para + "\n\n"
    if current.strip():
        chunks.append(current.strip())

    translated_parts = []
    for chunk in chunks:
        if not chunk.strip():
            continue
        success = False
        # Retry up to 3 times per chunk
        for attempt in range(3):
            try:
                result = GoogleTranslator(
                    source="auto",          # FIX: always auto-detect source
                    target=target_lang_code,
                ).translate(chunk)
                translated_parts.append(result if result else chunk)
                success = True
                time.sleep(0.3)
                break
            except Exception as exc:
                if attempt == 2:
                    # On final failure keep original chunk so output isn't blank
                    translated_parts.append(f"[Translation error: {exc}]\n{chunk}")
                else:
                    time.sleep(1.0 * (attempt + 1))

    return "\n\n".join(translated_parts) if translated_parts else text

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

def stable_key(url):
    """Generate a short stable key from a URL using MD5 (avoids length / special-char issues)."""
    return hashlib.md5(url.encode()).hexdigest()[:12]

def render_article_card(art, keyword, idx, newspaper_name, translate_to=None):
    """
    Render an article in an expandable card.

    FIX (bookmarks): bookmark state is stored in st.session_state["bookmarked_urls"]
    (a set of URLs).  The button writes to session_state THEN calls st.rerun() so
    the label always reflects the current state.  Button keys use stable_key(url)
    instead of url[:20] to avoid collisions between articles with similar URLs.
    """
    url = art["url"]
    s_key = stable_key(url)

    with st.expander(f"Article {idx}: {(art['title'] or url)[:80]}", expanded=False):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.caption(f"Date: {art['date']} | Read time: {art['read_time']} min | Words: {art['word_count']}")
        with col2:
            st.markdown(f"[Open Article]({url})")

        if art.get("image"):
            try:
                st.image(art["image"], use_container_width=True)
            except Exception:
                pass

        tab_orig, tab_trans = st.tabs(["Original", "Translated"])

        with tab_orig:
            highlighted = keyword_highlight(art["content"], keyword)
            st.markdown(highlighted, unsafe_allow_html=True)

        with tab_trans:
            if translate_to and translate_to != "-- Select Language --":
                lang_code = LANGUAGES.get(translate_to)
                if lang_code:
                    cache_key = f"{url}_{lang_code}"
                    if cache_key not in st.session_state.articles_cache:
                        with st.spinner(f"Translating to {translate_to}…"):
                            # FIX: source is always "auto" inside translate_text now
                            translated = translate_text(art["content"], lang_code)
                            st.session_state.articles_cache[cache_key] = translated
                    cached = st.session_state.articles_cache.get(cache_key, "")
                    if cached:
                        st.write(cached)
                    else:
                        st.warning("Translation returned empty. Please try again.")
            else:
                st.info("Select a translation language from the sidebar.")

        # ── Bookmark button (FIX) ──────────────────────────────────────────
        is_bookmarked = url in st.session_state.bookmarked_urls
        btn_label = "✅ Bookmarked" if is_bookmarked else "🔖 Bookmark"

        if st.button(btn_label, key=f"bm_{s_key}_{idx}"):
            if url not in st.session_state.bookmarked_urls:
                # Add bookmark
                st.session_state.bookmarked_urls.add(url)
                art_copy = dict(art)          # store a snapshot
                st.session_state.bookmarks.append(art_copy)
                st.success("Bookmarked! ✅")
            else:
                # Remove bookmark
                st.session_state.bookmarked_urls.discard(url)
                st.session_state.bookmarks = [
                    b for b in st.session_state.bookmarks if b.get("url") != url
                ]
                st.info("Bookmark removed.")
            st.rerun()   # FIX: force UI refresh so button label updates immediately

# ═════════════════════════════════════════════════════════════════════════════
#                    MAIN APPLICATION
# ═════════════════════════════════════════════════════════════════════════════

def main():
    st.set_page_config(
        page_title="Gujarati Newspaper AI Scraper",
        page_icon="📰",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    init_session()

    # ── Custom CSS ───────────────────────────────────────────────────────────
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Gujarati:wght@400;700&family=Playfair+Display:wght@700&family=Inter:wght@400;500;600&display=swap');

    .main { background: #F8F6F1; }
    h1 { font-family: 'Playfair Display', serif !important; color: #1A0A00; letter-spacing: -0.5px; }
    .stButton>button {
        border-radius: 8px; font-weight: 600; transition: all 0.2s;
    }
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
    </style>
    """, unsafe_allow_html=True)

    # ── Header ───────────────────────────────────────────────────────────────
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
            help="Search across multiple newspapers simultaneously",
        )

        max_articles = st.slider("Max articles per newspaper", 3, 15, 5)

        st.markdown("---")
        st.markdown("### 🌐 Translation")
        translate_to = st.selectbox(
            "Translate articles to",
            ["-- Select Language --"] + list(LANGUAGES.keys()),
            index=1,   # Default: English
        )

        st.markdown("---")
        st.markdown("### 🔍 Filters")
        keyword_in_url = st.checkbox("Keyword must appear in URL", value=False)

        st.markdown("---")
        st.markdown("### 📊 Session Stats")
        c1, c2 = st.columns(2)
        c1.metric("Searches", st.session_state.total_searches)
        c2.metric("Bookmarks", len(st.session_state.bookmarks))

        if st.session_state.search_history:
            st.markdown("---")
            st.markdown("### 🕒 Recent Searches")
            for h in reversed(st.session_state.search_history[-5:]):
                st.caption(f"- {h}")

    # ── Search bar ───────────────────────────────────────────────────────────
    col_kw, col_btn = st.columns([4, 1])
    with col_kw:
        keyword = st.text_input(
            "Search keyword",
            placeholder="e.g. cricket, elections, Modi, ક્રિકેટ …",
            label_visibility="collapsed",
        )
    with col_btn:
        search_clicked = st.button("🔎 Search", type="primary", use_container_width=True)

    # ── Tabs ─────────────────────────────────────────────────────────────────
    tab_results, tab_bookmarks, tab_export = st.tabs(["📑 Results", "🔖 Bookmarks", "📤 Export"])

    # ── Results tab ──────────────────────────────────────────────────────────
    with tab_results:
        if search_clicked:
            if not keyword.strip():
                st.error("Please enter a keyword.")
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
                    base_url = config["url"]

                    with st.spinner(f"Searching {paper}…"):
                        links, error = fetch_article_links(base_url, keyword, max_links=max_articles)

                    if error:
                        st.warning(f"{paper}: {error}")
                        continue
                    if not links:
                        st.info(f"No articles found for '{keyword}' in {paper}. Try a different keyword.")
                        continue

                    # Optional: filter links where keyword appears in URL
                    if keyword_in_url:
                        links = [l for l in links if keyword.lower() in l["url"].lower()]

                    st.success(f"Found {len(links)} article(s)")

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
                    st.toast(f"Found {len(all_articles)} article(s) across {len(selected_papers)} newspaper(s)!")

    # ── Bookmarks tab ────────────────────────────────────────────────────────
    with tab_bookmarks:
        if not st.session_state.bookmarks:
            st.info("No bookmarks yet. Click '🔖 Bookmark' on any article to save it here.")
        else:
            st.markdown(f"### {len(st.session_state.bookmarks)} Saved Article(s)")
            for idx, art in enumerate(st.session_state.bookmarks):
                with st.expander(f"{idx + 1}. {art.get('title', art.get('url', ''))[:80]}"):
                    st.caption(f"📅 {art.get('date', 'N/A')} | [Open Article]({art.get('url', '#')})")
                    st.write(art.get("content", "")[:500] + "…")
                    if st.button("🗑️ Remove", key=f"del_bm_{stable_key(art.get('url',''))}_{idx}"):
                        url_to_remove = art.get("url", "")
                        st.session_state.bookmarked_urls.discard(url_to_remove)
                        st.session_state.bookmarks = [
                            b for b in st.session_state.bookmarks if b.get("url") != url_to_remove
                        ]
                        st.rerun()

            if st.button("🗑️ Clear All Bookmarks"):
                st.session_state.bookmarks = []
                st.session_state.bookmarked_urls = set()
                st.rerun()

    # ── Export tab ───────────────────────────────────────────────────────────
    with tab_export:
        articles = st.session_state.get("last_search_articles", [])
        if not articles:
            st.info("Run a search first. Scraped articles will appear here for export.")
        else:
            st.markdown(f"### Export {len(articles)} Article(s)")
            newspapers_count = len(set(a["newspaper"] for a in articles))
            st.markdown(f"Last search returned **{len(articles)}** articles from **{newspapers_count}** newspaper(s).")

            col_a, col_b = st.columns(2)
            with col_a:
                st.download_button(
                    label="⬇️ Download as CSV",
                    data=articles_to_csv(articles),
                    file_name=f"gujarati_news_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            with col_b:
                st.download_button(
                    label="⬇️ Download as JSON",
                    data=articles_to_json(articles),
                    file_name=f"gujarati_news_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                    mime="application/json",
                    use_container_width=True,
                )

            st.markdown("#### Preview")
            for a in articles:
                st.markdown(
                    f"**{a.get('newspaper')}** | {a.get('date')} | "
                    f"[{a.get('title', a.get('url', ''))}]({a.get('url', '#')})"
                )

if __name__ == "__main__":
    main()
