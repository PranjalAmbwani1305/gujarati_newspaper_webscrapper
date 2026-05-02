"""
GUJARATI NEWSPAPER AI SCRAPER
Requirements: pip install streamlit requests beautifulsoup4 deep-translator lxml
Run: streamlit run gujarati_news_hub.py
"""

import os
import re
import io
import csv
import json
import time
import random
import hashlib
from datetime import datetime
from urllib.parse import urljoin, urlparse, quote

import streamlit as st
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

BOOKMARK_FILE = os.path.join(os.path.expanduser("~"), ".gujarati_scraper_bookmarks.json")

NEWSPAPERS = {
    "Gujarat Samachar": {
        "url":  "https://www.gujaratsamachar.com/",
        "flag": "📰",
        "search": "?s={kw}",
        "rss":  ["feed", "rss"],
        "date_sel": [
            ("span", "post-date"), ("time", "entry-date"), ("span", "date"),
        ],
        "body_sel": [
            ("div", "td-post-content"), ("div", "entry-content"), ("article", None),
        ],
    },
    "Divya Bhaskar": {
        "url":  "https://www.divyabhaskar.co.in/",
        "flag": "🗞️",
        "search": "?s={kw}",
        "rss":  ["feed", "rss-feed/1061/"],
        "date_sel": [
            ("span", "posted-on"), ("time", "entry-date published"), ("span", "date"),
        ],
        "body_sel": [
            ("div", "db-article-body"), ("div", "article-body"), ("div", "story-content"),
        ],
    },
    "Sandesh": {
        "url":  "https://www.sandesh.com/",
        "flag": "📋",
        "search": "?s={kw}",
        "rss":  ["feed", "rss"],
        "date_sel": [("span", "date"), ("time", None)],
        "body_sel": [("div", "article-content"), ("div", "post-content")],
    },
    "Mid Day (Gujarati)": {
        "url":  "https://www.gujaratimidday.com/",
        "flag": "📄",
        "search": "?s={kw}",
        "rss":  ["feed"],
        "date_sel": [("h5", None), ("span", "date"), ("time", None)],
        "body_sel": [("div", "article-body"), ("div", "article-content"), ("div", "content")],
    },
    "TV9 Gujarati": {
        "url":  "https://tv9gujarati.com/",
        "flag": "📺",
        "search": "?s={kw}",
        "rss":  ["feed"],
        "date_sel": [("span", "date"), ("time", None)],
        "body_sel": [("div", "article-content"), ("div", "entry-content")],
    },
    "ABP Asmita": {
        "url":  "https://www.abpasmita.com/",
        "flag": "📡",
        "search": "?s={kw}",
        "rss":  ["feed"],
        "date_sel": [("span", "date"), ("time", None)],
        "body_sel": [("div", "article-content"), ("div", "entry-content")],
    },
}

# Only English and Hindi as requested
TRANSLATE_OPTIONS = {
    "English": "en",
    "Hindi":   "hi",
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

SKIP_HREF = [
    "#", "javascript:", "mailto:", "tel:", "/tag/", "/category/",
    "/page/", "/feed", "/rss", "/sitemap", "/about", "/contact",
    "/privacy", "/terms", "/advertise", "/author/", "/wp-admin",
]

# ─────────────────────────────────────────────────────────────────────────────
# BOOKMARK — disk persistence so reloads don't lose data
# ─────────────────────────────────────────────────────────────────────────────

def bm_load():
    try:
        if os.path.exists(BOOKMARK_FILE):
            with open(BOOKMARK_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        pass
    return []

def bm_save(bookmarks):
    try:
        with open(BOOKMARK_FILE, "w", encoding="utf-8") as f:
            json.dump(bookmarks, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.warning(f"Bookmark save failed: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────────────────────

def init_session():
    # Only runs once per browser session (not on every rerun)
    if "app_ready" not in st.session_state:
        saved = bm_load()
        st.session_state.bookmarks     = saved                          # list of dicts
        st.session_state.bm_urls       = [b["url"] for b in saved]     # list, not set — serializable
        st.session_state.trans_cache   = {}                             # {url+lang: translated_text}
        st.session_state.search_hist   = []
        st.session_state.total_search  = 0
        st.session_state.results       = []                             # last search results
        st.session_state.app_ready     = True

# ─────────────────────────────────────────────────────────────────────────────
# TRANSLATION — deep_translator GoogleTranslator (works on local machine)
# ─────────────────────────────────────────────────────────────────────────────

def translate_text(text, target_code):
    """
    Translate Gujarati text → English or Hindi.
    Uses GoogleTranslator(source='auto') so it works for any source language.
    Splits into 4500-char chunks to stay within API limits.
    """
    if not text or not text.strip():
        return ""

    # Split on paragraph boundaries
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks, cur = [], ""
    for p in paras:
        if len(cur) + len(p) + 2 <= 4500:
            cur = (cur + "\n\n" + p).strip() if cur else p
        else:
            if cur:
                chunks.append(cur)
            cur = p
    if cur:
        chunks.append(cur)

    results = []
    for chunk in chunks:
        for attempt in range(3):
            try:
                translated = GoogleTranslator(source="auto", target=target_code).translate(chunk)
                results.append(translated or chunk)
                time.sleep(0.3)
                break
            except Exception as e:
                if attempt == 2:
                    results.append(chunk)   # keep original on failure
                else:
                    time.sleep(1.5 * (attempt + 1))

    return "\n\n".join(results)

# ─────────────────────────────────────────────────────────────────────────────
# HTTP UTILS
# ─────────────────────────────────────────────────────────────────────────────

def make_headers(url=""):
    parsed = urlparse(url)
    return {
        "User-Agent":      random.choice(USER_AGENTS),
        "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "gu-IN,gu;q=0.9,en-IN;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection":      "keep-alive",
        "Referer":         f"{parsed.scheme}://{parsed.netloc}/" if parsed.netloc else "https://www.google.com/",
        "Cache-Control":   "max-age=0",
    }

def fetch(url, retries=3):
    """GET with retries. Returns Response or None."""
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=make_headers(url), timeout=15, allow_redirects=True)
            if r.status_code == 200 and len(r.content) > 100:
                return r
            if r.status_code in (403, 429, 503):
                time.sleep(2 * (attempt + 1))
        except Exception:
            if attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
    return None

def abs_url(href, base):
    if not href:
        return None
    href = href.strip()
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("http"):
        return href
    return urljoin(base, href)

def uid(text):
    return hashlib.md5(text.encode()).hexdigest()[:10]

# ─────────────────────────────────────────────────────────────────────────────
# SCRAPING
# ─────────────────────────────────────────────────────────────────────────────

def good_link(href, keyword):
    """True if href looks like an article URL containing the keyword."""
    hl = href.lower()
    if any(s in hl for s in SKIP_HREF):
        return False
    if "?" in href and "s=" in href:
        return False
    return keyword.lower() in hl

def links_from_html(html, base_url, keyword, limit, seen):
    soup = BeautifulSoup(html, "html.parser")
    found = []
    for a in soup.find_all("a", href=True):
        href = abs_url(a["href"], base_url)
        if not href or href in seen:
            continue
        text = a.get_text(strip=True)
        if good_link(href, keyword) or keyword.lower() in text.lower():
            # Skip obvious non-article URLs
            if any(s in href.lower() for s in SKIP_HREF):
                continue
            seen.add(href)
            found.append({"url": href, "title": text or href})
            if len(found) >= limit:
                break
    return found

def links_from_rss(rss_url, keyword, limit, seen):
    r = fetch(rss_url)
    if not r:
        return []
    try:
        soup = BeautifulSoup(r.content, "xml")
        items = soup.find_all("item") or soup.find_all("entry")
        found = []
        kw = keyword.lower()
        for item in items:
            t_el = item.find("title")
            l_el = item.find("link")
            title = t_el.get_text(strip=True) if t_el else ""
            href  = l_el.get_text(strip=True) if l_el else (l_el.get("href", "") if l_el else "")
            if href and href not in seen and (kw in title.lower() or kw in href.lower()):
                seen.add(href)
                found.append({"url": href, "title": title or href})
                if len(found) >= limit:
                    break
        return found
    except Exception:
        return []

def get_article_links(paper_name, keyword, max_links):
    """
    Three-strategy link fetcher:
      1. Direct homepage  →  2. Search URL  →  3. RSS feed
    Returns (links, error_msg, is_blocked)
    """
    cfg      = NEWSPAPERS[paper_name]
    base     = cfg["url"]
    seen     = set()
    links    = []

    # Strategy 1 — homepage
    r = fetch(base)
    if not r:
        return [], None, True   # blocked

    links += links_from_html(r.content, base, keyword, max_links, seen)

    # Strategy 2 — search URL
    if len(links) < 3:
        search_url = base.rstrip("/") + "/" + cfg["search"].format(kw=quote(keyword))
        r2 = fetch(search_url)
        if r2:
            links += links_from_html(r2.content, base, keyword, max_links - len(links), seen)

    # Strategy 3 — RSS
    if len(links) < 3:
        for rss_path in cfg["rss"]:
            rss_url = base.rstrip("/") + "/" + rss_path
            links += links_from_rss(rss_url, keyword, max_links - len(links), seen)
            if len(links) >= max_links:
                break

    if not links:
        return [], f"No articles found for **'{keyword}'**. Try another keyword.", False

    return links[:max_links], None, False

# ─────────────────────────────────────────────────────────────────────────────
# ARTICLE EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────

def get_date(soup, selectors):
    for tag, cls in selectors:
        el = soup.find(tag, class_=cls) if cls else soup.find(tag)
        if el:
            txt = el.get_text(strip=True)
            if txt:
                return txt
            dt = el.get("datetime", "")
            if dt:
                return dt.split("T")[0]
    meta = soup.find("meta", {"property": "article:published_time"})
    if meta:
        return meta.get("content", "").split("T")[0]
    return "N/A"

def get_body(soup, selectors):
    for tag, cls in selectors:
        el = soup.find(tag, class_=cls) if cls else soup.find(tag)
        if el:
            paras, seen_t = [], set()
            for p in el.find_all("p"):
                t = p.get_text(strip=True)
                if t and t not in seen_t and len(t) > 20:
                    seen_t.add(t)
                    paras.append(t)
            if paras:
                return "\n\n".join(paras)
    # fallback — all <p> on page
    paras, seen_t = [], set()
    for p in soup.find_all("p"):
        t = p.get_text(strip=True)
        if t and t not in seen_t and len(t) > 30:
            seen_t.add(t)
            paras.append(t)
    return "\n\n".join(paras)

def scrape_article(url, paper_name):
    r = fetch(url)
    if not r:
        return {
            "date": "N/A", "title": url,
            "content": "⚠️ Could not fetch — site may be blocking requests.",
            "image": "", "words": 0, "mins": 0,
        }
    soup = BeautifulSoup(r.content, "html.parser")
    cfg  = NEWSPAPERS.get(paper_name, {})

    date    = get_date(soup, cfg.get("date_sel", []))
    content = get_body(soup, cfg.get("body_sel", []))

    og_t = soup.find("meta", property="og:title")
    title = (og_t["content"] if og_t and og_t.get("content") else
             soup.title.get_text(strip=True) if soup.title else url)

    og_i  = soup.find("meta", property="og:image")
    image = og_i["content"] if og_i and og_i.get("content") else ""

    words = len(content.split()) if content else 0
    return {
        "date":    date,
        "title":   title,
        "content": content or "No content extracted.",
        "image":   image,
        "words":   words,
        "mins":    max(1, round(words / 200)),
    }

# ─────────────────────────────────────────────────────────────────────────────
# EXPORT
# ─────────────────────────────────────────────────────────────────────────────

def to_csv(articles):
    buf = io.StringIO()
    w   = csv.DictWriter(buf, fieldnames=["newspaper", "title", "date", "url", "words", "mins", "content"])
    w.writeheader()
    for a in articles:
        w.writerow({
            "newspaper": a.get("newspaper", ""),
            "title":     a.get("title", ""),
            "date":      a.get("date", ""),
            "url":       a.get("url", ""),
            "words":     a.get("words", 0),
            "mins":      a.get("mins", 0),
            "content":   a.get("content", "").replace("\n", " | "),
        })
    return buf.getvalue().encode("utf-8")

def to_json(articles):
    return json.dumps(articles, ensure_ascii=False, indent=2).encode("utf-8")

# ─────────────────────────────────────────────────────────────────────────────
# UI HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def highlight(text, keyword):
    if not keyword or not text:
        return text
    pat = re.compile(re.escape(keyword), re.IGNORECASE)
    return pat.sub(
        lambda m: f"<mark style='background:#FFE066;padding:0 2px;border-radius:3px'>{m.group()}</mark>",
        text,
    )

def render_article(art, keyword, idx, translate_lang):
    url   = art["url"]
    key   = uid(url)
    title = (art["title"] or url)[:80]

    with st.expander(f"Article {idx}: {title}", expanded=False):

        c1, c2 = st.columns([3, 1])
        c1.caption(f"📅 {art['date']}  ·  ⏱ {art['mins']} min  ·  📝 {art['words']} words")
        c2.markdown(f"[🔗 Open]({url})")

        if art.get("image"):
            try:
                st.image(art["image"], use_container_width=True)
            except Exception:
                pass

        tab_orig, tab_tr = st.tabs(["📄 Original (Gujarati)", f"🌐 {translate_lang}"])

        with tab_orig:
            st.markdown(highlight(art["content"], keyword), unsafe_allow_html=True)

        with tab_tr:
            lang_code = TRANSLATE_OPTIONS[translate_lang]
            cache_key = f"{url}_{lang_code}"

            if cache_key in st.session_state.trans_cache:
                # Already translated — show instantly
                st.write(st.session_state.trans_cache[cache_key])
            else:
                if st.button(f"Translate to {translate_lang}", key=f"tr_{key}_{idx}"):
                    with st.spinner(f"Translating to {translate_lang}…"):
                        result = translate_text(art["content"], lang_code)
                        st.session_state.trans_cache[cache_key] = result
                    st.rerun()

        # ── Bookmark button ───────────────────────────────────────────────────
        already = url in st.session_state.bm_urls
        label   = "✅ Bookmarked" if already else "🔖 Bookmark"

        if st.button(label, key=f"bm_{key}_{idx}"):
            if not already:
                st.session_state.bm_urls.append(url)
                st.session_state.bookmarks.append(dict(art))
                bm_save(st.session_state.bookmarks)
                st.success("Saved! ✅")
            else:
                st.session_state.bm_urls = [u for u in st.session_state.bm_urls if u != url]
                st.session_state.bookmarks = [b for b in st.session_state.bookmarks if b.get("url") != url]
                bm_save(st.session_state.bookmarks)
                st.info("Removed.")
            st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
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
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=Inter:wght@400;500;600&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    h1 { font-family: 'Playfair Display', serif !important; color: #1A0A00; }
    .stButton > button {
        border-radius: 8px; font-weight: 600;
        transition: transform 0.15s, box-shadow 0.15s;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 14px rgba(0,0,0,0.15);
    }
    mark { background: #FFE066; padding: 0 2px; border-radius: 3px; }
    </style>
    """, unsafe_allow_html=True)

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown("# 📰 Gujarati Newspaper AI Scraper")
    st.caption("Search · Scrape · Translate (English / Hindi) · Bookmark · Export")
    st.divider()

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("## ⚙️ Settings")

        selected_papers = st.multiselect(
            "Newspapers",
            options=list(NEWSPAPERS.keys()),
            default=["Gujarat Samachar"],
        )

        max_articles = st.slider("Max articles per paper", 3, 15, 5)

        st.divider()
        st.markdown("## 🌐 Translation")
        # Only English and Hindi
        translate_lang = st.radio(
            "Translate scraped articles to:",
            options=list(TRANSLATE_OPTIONS.keys()),
            index=0,
            horizontal=True,
        )

        st.divider()
        st.markdown("## 📊 Stats")
        col1, col2 = st.columns(2)
        col1.metric("Searches",  st.session_state.total_search)
        col2.metric("Bookmarks", len(st.session_state.bookmarks))

        if st.session_state.search_hist:
            st.divider()
            st.markdown("## 🕒 Recent")
            for h in reversed(st.session_state.search_hist[-5:]):
                st.caption(f"• {h}")

    # ── Search bar ────────────────────────────────────────────────────────────
    kw_col, btn_col = st.columns([5, 1])
    with kw_col:
        keyword = st.text_input(
            "keyword",
            placeholder="e.g.  cricket   elections   Modi   ક્રિકેટ",
            label_visibility="collapsed",
        )
    with btn_col:
        search_clicked = st.button("🔎 Search", type="primary", use_container_width=True)

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tab_res, tab_bm, tab_exp = st.tabs(["📑 Results", "🔖 Bookmarks", "📤 Export"])

    # ── RESULTS ───────────────────────────────────────────────────────────────
    with tab_res:
        if search_clicked:
            if not keyword.strip():
                st.error("Enter a keyword first.")
                st.stop()
            if not selected_papers:
                st.error("Select at least one newspaper.")
                st.stop()

            if keyword not in st.session_state.search_hist:
                st.session_state.search_hist.append(keyword)
            st.session_state.total_search += 1
            all_articles = []

            for paper in selected_papers:
                cfg = NEWSPAPERS[paper]
                st.markdown(f"### {cfg['flag']} {paper}")

                with st.spinner(f"Searching {paper}…"):
                    links, err, blocked = get_article_links(paper, keyword, max_articles)

                # ── Blocked (403) ──────────────────────────────────────────
                if blocked:
                    st.error(
                        f"🚫 **{paper}** is blocking automated requests (HTTP 403).\n\n"
                        f"Open it manually → **[{cfg['url']}]({cfg['url']})**"
                    )
                    st.divider()
                    continue

                # ── No results ─────────────────────────────────────────────
                if err:
                    st.warning(err)
                    st.divider()
                    continue

                st.success(f"Found {len(links)} article(s)")

                for idx, link in enumerate(links, 1):
                    with st.spinner(f"Loading {idx}/{len(links)}…"):
                        art = scrape_article(link["url"], paper)
                        art["url"]       = link["url"]
                        art["newspaper"] = paper
                        all_articles.append(art)

                    render_article(art, keyword, idx, translate_lang)

                st.divider()

            if all_articles:
                st.session_state.results = all_articles
                st.toast(f"✅ {len(all_articles)} articles from {len(selected_papers)} paper(s)")

    # ── BOOKMARKS ─────────────────────────────────────────────────────────────
    with tab_bm:
        bms = st.session_state.bookmarks
        if not bms:
            st.info("No bookmarks yet. Click **🔖 Bookmark** inside any article.\n\n"
                    "Bookmarks persist on disk — safe after page reload.")
        else:
            st.markdown(f"### {len(bms)} Saved Article(s)")
            st.caption(f"Stored at: `{BOOKMARK_FILE}`")
            for i, art in enumerate(bms):
                art_url = art.get("url", "")
                with st.expander(f"{i+1}. {art.get('title', art_url)[:75]}"):
                    st.caption(f"📅 {art.get('date','N/A')}  ·  📰 {art.get('newspaper','N/A')}")
                    st.markdown(f"[🔗 Open article]({art_url})")
                    preview = art.get("content", "")
                    st.write(preview[:500] + ("…" if len(preview) > 500 else ""))

                    if st.button("🗑️ Remove", key=f"rmbm_{uid(art_url)}_{i}"):
                        st.session_state.bm_urls = [u for u in st.session_state.bm_urls if u != art_url]
                        st.session_state.bookmarks = [b for b in bms if b.get("url") != art_url]
                        bm_save(st.session_state.bookmarks)
                        st.rerun()

            st.markdown("---")
            if st.button("🗑️ Clear all bookmarks"):
                st.session_state.bookmarks = []
                st.session_state.bm_urls   = []
                bm_save([])
                st.rerun()

    # ── EXPORT ────────────────────────────────────────────────────────────────
    with tab_exp:
        arts = st.session_state.results
        if not arts:
            st.info("Run a search first.")
        else:
            st.markdown(f"### Export {len(arts)} Article(s)")
            c1, c2 = st.columns(2)
            with c1:
                st.download_button(
                    "⬇️ CSV",
                    data=to_csv(arts),
                    file_name=f"gujarati_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            with c2:
                st.download_button(
                    "⬇️ JSON",
                    data=to_json(arts),
                    file_name=f"gujarati_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                    mime="application/json",
                    use_container_width=True,
                )
            st.divider()
            for a in arts:
                st.markdown(f"**{a.get('newspaper')}** · {a.get('date')} · [{(a.get('title') or a.get('url',''))[:65]}]({a.get('url','#')})")


if __name__ == "__main__":
    main()
