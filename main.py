"""
================================================================================
                    GUJARATI NEWS HUB - FULL APPLICATION
                     Web Scraper & Translation Tool
================================================================================
Author: News Hub Team
Purpose: Search, scrape, translate, and export articles from Gujarati newspapers
Dependencies: streamlit, requests, beautifulsoup4, deep-translator
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
from datetime import datetime, date
import re
import json
import hashlib

# ═════════════════════════════════════════════════════════════════════════════
#                       CONSTANTS & CONFIGURATION
# ═════════════════════════════════════════════════════════════════════════════

NEWSPAPER_CONFIG = {
    "Gujarat Samachar": {
        "url": "https://www.gujaratsamachar.com/",
        "lang": "gu",
        "flag": "IN",
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
        "flag": "NEWS",
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
        "flag": "TIMES",
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
        "flag": "PAPER",
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

# Rotating user agents to avoid blocking
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
        "search_history": [],      # List of previous searches
        "bookmarks": [],           # Saved articles
        "articles_cache": {},      # Cache for translated articles
        "total_searches": 0,       # Total number of searches performed
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

# ═════════════════════════════════════════════════════════════════════════════
#                       SCRAPING UTILITIES
# ═════════════════════════════════════════════════════════════════════════════

def get_headers():
    """Generate HTTP headers with random user agent."""
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
    """
    Fetch a URL with retries, random delays, and rotating user agents.
    
    Args:
        url (str): URL to fetch
        retries (int): Number of retry attempts
        delay (float): Initial delay between retries in seconds
    
    Returns:
        requests.Response or None: Response object if successful, None otherwise
    """
    for attempt in range(retries):
        try:
            resp = requests.get(
                url,
                headers=get_headers(),
                timeout=15,
                allow_redirects=True,
            )
            resp.raise_for_status()
            return resp
        except requests.exceptions.HTTPError as e:
            # Special handling for 403 Forbidden
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
        except requests.exceptions.ConnectionError:
            if attempt < retries - 1:
                time.sleep(delay * (attempt + 1))
        except requests.exceptions.Timeout:
            if attempt < retries - 1:
                time.sleep(delay)
        except Exception:
            break
    return None

def normalize_url(href, base_url):
    """
    Convert relative URLs to absolute URLs.
    
    Args:
        href (str): URL (relative or absolute)
        base_url (str): Base URL for relative path resolution
    
    Returns:
        str or None: Normalized absolute URL or None if invalid
    """
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
    """
    Heuristic: determine if a link is likely an article link.
    
    Args:
        href (str): URL to check
        text (str): Link text
        keyword (str): Search keyword to match
    
    Returns:
        bool: True if likely an article link, False otherwise
    """
    skip_patterns = ["#", "javascript:", "mailto:", "tel:", "/tag/", "/category/",
                     "/page/", "?s=", "/feed", "/rss", "/sitemap", "/about",
                     "/contact", "/privacy", "/terms", "/advertise"]
    if any(p in href.lower() for p in skip_patterns):
        return False
    kw_lower = keyword.lower()
    href_lower = href.lower()
    text_lower = text.lower()
    return kw_lower in href_lower or kw_lower in text_lower

def fetch_article_links(base_url, keyword, max_links=10):
    """
    Scrape homepage and linked pages for matching article URLs.
    
    Args:
        base_url (str): Newspaper website base URL
        keyword (str): Search keyword to find articles
        max_links (int): Maximum number of article links to return
    
    Returns:
        tuple: (list of article links, error message or None)
    """
    resp = safe_get(base_url)
    if not resp:
        return [], "Could not reach the newspaper website. It may be blocking scrapers."

    soup = BeautifulSoup(resp.content, "html.parser")
    seen = set()
    links = []

    # Try search URL patterns common in news sites
    search_urls = [
        f"{base_url}?s={keyword}",
        f"{base_url}search?q={keyword}",
        f"{base_url}search/{keyword}",
        f"{base_url}tag/{keyword.lower().replace(' ', '-')}",
    ]

    # First pass: homepage links
    for a in soup.find_all("a", href=True):
        href = normalize_url(a.get("href", ""), base_url)
        text = a.get_text(strip=True)
        if href and href not in seen and is_article_link(href, text, keyword):
            seen.add(href)
            links.append({"url": href, "title": text or href})
            if len(links) >= max_links:
                break

    # Second pass: try search endpoints if not enough links found
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
    """
    Try multiple selectors to find a publication date.
    
    Args:
        soup (BeautifulSoup): Parsed HTML of article
        selectors (list): List of (tag, attributes) tuples to try
    
    Returns:
        str: Publication date or "Date not found"
    """
    for tag, attrs in selectors:
        el = soup.find(tag, **attrs) if attrs else soup.find(tag)
        if el:
            text = el.get_text(strip=True)
            if text:
                return text
            dt = el.get("datetime", "")
            if dt:
                return dt.split("T")[0]
    # Fallback: look for <time> or meta tags
    time_el = soup.find("time")
    if time_el:
        return time_el.get("datetime", time_el.get_text(strip=True))
    meta_date = soup.find("meta", {"property": "article:published_time"})
    if meta_date:
        return meta_date.get("content", "").split("T")[0]
    return "Date not found"

def extract_article_content(soup, selectors):
    """
    Try multiple selectors to extract article body text.
    
    Args:
        soup (BeautifulSoup): Parsed HTML of article
        selectors (list): List of (tag, attributes) tuples to try
    
    Returns:
        str: Article body text or empty string
    """
    for tag, attrs in selectors:
        content = soup.find(tag, **attrs) if attrs else soup.find(tag)
        if content:
            paras = content.find_all("p")
            if not paras:
                paras = content.find_all(["p", "div", "span"])
            seen, parts = set(), []
            for p in paras:
                text = p.get_text(strip=True)
                if text and text not in seen and len(text) > 20:
                    seen.add(text)
                    parts.append(text)
            if parts:
                return "\n\n".join(parts)

    # Generic fallback: grab all <p> on the page
    paras = soup.find_all("p")
    seen, parts = set(), []
    for p in paras:
        text = p.get_text(strip=True)
        if text and text not in seen and len(text) > 30:
            seen.add(text)
            parts.append(text)
    return "\n\n".join(parts) if parts else ""

def get_og_image(soup):
    """Extract Open Graph image meta tag."""
    og = soup.find("meta", property="og:image")
    if og:
        return og.get("content", "")
    return ""

def get_og_title(soup):
    """Extract article title from meta tags or title element."""
    og = soup.find("meta", property="og:title")
    if og:
        return og.get("content", "")
    title = soup.find("title")
    return title.get_text(strip=True) if title else ""

def extract_article(url, newspaper_name):
    """
    Extract article details from a URL.
    
    Args:
        url (str): Article URL
        newspaper_name (str): Name of newspaper source
    
    Returns:
        dict: Dictionary with article metadata and content
    """
    resp = safe_get(url)
    if not resp:
        return {
            "date": "N/A",
            "title": url,
            "content": "Could not fetch article. The site may be blocking automated requests.",
            "image": "",
            "read_time": 0,
        }

    soup = BeautifulSoup(resp.content, "html.parser")
    config = NEWSPAPER_CONFIG.get(newspaper_name, {})

    date_ = extract_article_date(soup, config.get("date_selectors", []))
    content = extract_article_content(soup, config.get("content_selectors", []))
    title = get_og_title(soup)
    image = get_og_image(soup)
    word_count = len(content.split()) if content else 0
    read_time = max(1, round(word_count / 200))  # ~200 wpm average

    return {
        "date": date_,
        "title": title,
        "content": content or "No content could be extracted from this article.",
        "image": image,
        "read_time": read_time,
        "word_count": word_count,
    }

# ═════════════════════════════════════════════════════════════════════════════
#                    TRANSLATION UTILITIES
# ═════════════════════════════════════════════════════════════════════════════

def translate_text(text, target_lang_code, source="auto"):
    from deep_translator import GoogleTranslator
    import time

    if not text.strip():
        return ""

    chunks = [text[i:i+2000] for i in range(0, len(text), 2000)]
    result = []

    for chunk in chunks:
        for attempt in range(3):  # retry 3 times
            try:
                translated = GoogleTranslator(source=source, target=target_lang_code).translate(chunk)
                result.append(translated)
                break
            except Exception:
                time.sleep(1.5)  # backoff
        else:
            result.append(chunk)  # fallback

        time.sleep(0.5)  # avoid rate limit

    return " ".join(result)

def detect_language(text):
    """
    Detect language of text using translation heuristic.
    
    Args:
        text (str): Text to detect language for
    
    Returns:
        str: Language code (gu, en, or auto)
    """
    try:
        sample = text[:500]
        detected = GoogleTranslator(source="auto", target="en").translate(sample)
        # Heuristic: if translation differs substantially, source was non-English
        return "gu" if detected != sample else "en"
    except Exception:
        return "auto"

# ═════════════════════════════════════════════════════════════════════════════
#                    EXPORT UTILITIES
# ═════════════════════════════════════════════════════════════════════════════

def articles_to_csv(articles):
    """
    Convert articles list to CSV format.
    
    Args:
        articles (list): List of article dictionaries
    
    Returns:
        bytes: CSV data encoded as UTF-8
    """
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
    """
    Convert articles list to JSON format.
    
    Args:
        articles (list): List of article dictionaries
    
    Returns:
        bytes: JSON data encoded as UTF-8
    """
    return json.dumps(articles, ensure_ascii=False, indent=2).encode("utf-8")

# ═════════════════════════════════════════════════════════════════════════════
#                    UI HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def keyword_highlight(text, keyword):
    """
    Wrap keyword occurrences in <mark> HTML tags for highlighting.
    
    Args:
        text (str): Text to highlight
        keyword (str): Keyword to highlight
    
    Returns:
        str: HTML-formatted text with highlighted keywords
    """
    if not keyword or not text:
        return text
    pattern = re.compile(re.escape(keyword), re.IGNORECASE)
    return pattern.sub(lambda m: f"<mark style='background:#FFE066;padding:0 2px;border-radius:3px'>{m.group()}</mark>", text)

def reading_progress_bar(word_count):
    """Display reading time and word count."""
    mins = max(1, round(word_count / 200))
    st.caption(f"Read time: {mins} min | Words: {word_count}")


def render_article_card(art, keyword, idx, newspaper_name, translate_to=None):

    with st.expander(f"Article {idx}: {art['title'][:80] or art['url'][:80]}", expanded=False):

        col1, col2 = st.columns([3, 1])
        with col1:
            st.caption(f"Date: {art['date']} | Read time: {art['read_time']} min | Words: {art['word_count']}")
        with col2:
            st.markdown(f"[Open Article]({art['url']})")

        if art.get("image"):
            try:
                st.image(art["image"], use_column_width=True)
            except:
                pass

        tab_orig, tab_trans = st.tabs(["Original", "Translated"])

        with tab_orig:
            highlighted = keyword_highlight(art["content"], keyword)
            st.markdown(highlighted, unsafe_allow_html=True)

        with tab_trans:
            if translate_to and translate_to != "-- Select Language --":
                lang_code = LANGUAGES.get(translate_to)
                if lang_code:
                    cache_key = f"{art['url']}_{lang_code}"
                    if cache_key not in st.session_state.articles_cache:
                        with st.spinner(f"Translating to {translate_to}..."):
                            src = NEWSPAPER_CONFIG.get(newspaper_name, {}).get("lang", "auto")
                            translated = translate_text(art["content"], lang_code, source=src)
                            st.session_state.articles_cache[cache_key] = translated
                    st.write(st.session_state.articles_cache.get(cache_key, ""))
            else:
                st.info("Select a translation language from the sidebar.")

        # ===== BOOKMARK SECTION =====

        if "bookmarks" not in st.session_state:
            st.session_state.bookmarks = []

        bm_key = art["url"]

        is_bookmarked = any(b["url"] == bm_key for b in st.session_state.bookmarks)

        import hashlib
        unique_key = hashlib.md5(bm_key.encode()).hexdigest()

        if is_bookmarked:
            if st.button("Remove Bookmark", key=f"rm_{unique_key}"):
                st.session_state.bookmarks = [
                    b for b in st.session_state.bookmarks if b["url"] != bm_key
                ]
                st.rerun()
        else:
            if st.button("Bookmark", key=f"bm_{unique_key}"):
                st.session_state.bookmarks.append(art)
                st.rerun()

# ═════════════════════════════════════════════════════════════════════════════
#                    MAIN APPLICATION
# ═════════════════════════════════════════════════════════════════════════════

def main():
    """Main Streamlit application."""
    st.set_page_config(
        page_title="Gujarati News Hub",
        page_icon="NEWS",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    init_session()

    # ── Custom CSS ──────────────────────────
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
    .stat-label { font-size: 0.8rem; color: #666; margin-top: 4px; }
    mark { background: #FFE066; padding: 0 3px; border-radius: 3px; }
    .news-badge {
        display: inline-block; background: #FF6B35; color: white;
        padding: 2px 10px; border-radius: 20px; font-size: 0.75rem; font-weight: 600;
    }
    .stExpander { border-radius: 12px !important; border: 1px solid #E8E4DC !important; }
    </style>
    """, unsafe_allow_html=True)

    # ── Header ──────────────────────────────
    st.markdown("# Gujarati News Hub")
    st.markdown("*Search, Scrape, Translate, Export -- all Gujarati newspapers in one place*")
    st.divider()

    # ── Sidebar ─────────────────────────────
    with st.sidebar:
        st.markdown("### Search Settings")

        selected_papers = st.multiselect(
            "Select Newspapers",
            list(NEWSPAPER_CONFIG.keys()),
            default=["Gujarat Samachar"],
            help="Search across multiple newspapers simultaneously",
        )

        max_articles = st.slider("Max articles per newspaper", 3, 15, 5)

        st.markdown("---")
        st.markdown("### Translation")
        translate_to = st.selectbox(
            "Translate articles to",
            ["-- Select Language --"] + list(LANGUAGES.keys()),
            index=1,  # Default: English
        )

        st.markdown("---")
        st.markdown("### Filters")
        keyword_in_url = st.checkbox("Keyword must appear in URL", value=False)
        show_images = st.checkbox("Show article images", value=True)

        st.markdown("---")
        st.markdown("### Session Stats")
        c1, c2 = st.columns(2)
        c1.metric("Searches", st.session_state.total_searches)
        c2.metric("Bookmarks", len(st.session_state.bookmarks))

        st.markdown("---")
        if st.session_state.search_history:
            st.markdown("### Recent Searches")
            for h in reversed(st.session_state.search_history[-5:]):
                st.caption(f"- {h}")

    # ── Main Content ─────────────────────────
    col_kw, col_btn = st.columns([4, 1])
    with col_kw:
        keyword = st.text_input(
            "Enter search keyword (English or Gujarati)",
            placeholder="e.g. cricket, elections, Modi...",
            label_visibility="collapsed",
        )
    with col_btn:
        search_clicked = st.button("Search", type="primary", use_container_width=True)

    # ── Tabs ─────────────────────────────────
    tab_results, tab_bookmarks, tab_export = st.tabs(["Results", "Bookmarks", "Export"])

    with tab_results:
        if search_clicked:
            if not keyword.strip():
                st.error("Please enter a keyword.")
            elif not selected_papers:
                st.error("Please select at least one newspaper.")
            else:
                # Add to history
                if keyword not in st.session_state.search_history:
                    st.session_state.search_history.append(keyword)
                st.session_state.total_searches += 1

                all_articles = []  # collect for export

                for paper in selected_papers:
                    config = NEWSPAPER_CONFIG[paper]
                    st.markdown(f"### {config['flag']} {paper}")
                    base_url = config["url"]

                    with st.spinner(f"Searching {paper}..."):
                        links, error = fetch_article_links(base_url, keyword, max_links=max_articles)

                    if error:
                        st.warning(f"{paper}: {error}")
                        continue

                    if not links:
                        st.info(f"No articles found for '{keyword}' in {paper}. Try a different keyword or check spelling.")
                        continue

                    st.success(f"Found {len(links)} article(s)")

                    for idx, link_info in enumerate(links, 1):
                        url = link_info["url"]
                        with st.spinner(f"Loading article {idx}/{len(links)}..."):
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

                # Cache articles for export
                if all_articles:
                    st.session_state["last_search_articles"] = all_articles
                    st.toast(f"Found {len(all_articles)} article(s) across {len(selected_papers)} newspaper(s)!")

    with tab_bookmarks:
        if not st.session_state.bookmarks:
            st.info("No bookmarks yet. Click 'Bookmark' on any article to save it here.")
        else:
            st.markdown(f"### {len(st.session_state.bookmarks)} Saved Article(s)")
            for idx, art in enumerate(st.session_state.bookmarks, 1):
                with st.expander(f"{idx}. {art.get('title', art.get('url', ''))[:80]}"):
                    st.caption(f"Date: {art.get('date', 'N/A')} | [Open Article]({art.get('url', '#')})")
                    st.write(art.get("content", "")[:500] + "...")
                    if st.button("Remove", key=f"del_bm_{idx}"):
                        st.session_state.bookmarks.pop(idx - 1)
                        st.rerun()

            if st.button("Clear All Bookmarks"):
                st.session_state.bookmarks = []
                st.rerun()

    with tab_export:
        articles = st.session_state.get("last_search_articles", [])
        if not articles:
            st.info("Run a search first. Scraped articles will appear here for export.")
        else:
            st.markdown(f"### Export {len(articles)} Article(s)")
            st.markdown(f"Last search returned **{len(articles)}** articles from **{len(set(a['newspaper'] for a in articles))}** newspaper(s).")

            col_a, col_b = st.columns(2)
            with col_a:
                csv_data = articles_to_csv(articles)
                st.download_button(
                    label="Download as CSV",
                    data=csv_data,
                    file_name=f"gujarati_news_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            with col_b:
                json_data = articles_to_json(articles)
                st.download_button(
                    label="Download as JSON",
                    data=json_data,
                    file_name=f"gujarati_news_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                    mime="application/json",
                    use_container_width=True,
                )

            st.markdown("#### Preview")
            for a in articles:
                st.markdown(f"**{a.get('newspaper')}** | {a.get('date')} | [{a.get('title', a.get('url', ''))}]({a.get('url', '#')})")

if __name__ == "__main__":
    main()
