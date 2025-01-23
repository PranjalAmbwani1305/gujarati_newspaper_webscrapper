import streamlit as st
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator


def fetch_article_links(base_url, keyword):
    try:
        response = requests.get(base_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        links = []
        for a in soup.find_all('a', href=True):
            if keyword.lower() in a.text.lower() or keyword.lower() in a['href'].lower():
                href = a['href']
                if not href.startswith("http"):
                    href = f"{base_url.rstrip('/')}/{href.lstrip('/')}"
                links.append(href)

        return links
    except Exception as e:
        st.error(f"Error fetching links: {e}")
        return []


def extract_article(link, newspaper):
    try:
        response = requests.get(link, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        date = soup.find('h5')
        article_date = date.get_text(strip=True) if date else "Date not available"

        if newspaper == "Mid Day":
            content = soup.find('div', class_='article-body')
        elif newspaper == "Divya Bhaskar":
            content = soup.find('div', class_='db-article-body')
        else:
            content = soup.find('div', class_='article-body')

        if content:
            article_text = "\n".join(p.get_text(strip=True) for p in content.find_all('p'))
        else:
            article_text = "No article content available."

        return article_date, article_text
    except Exception as e:
        return f"Error extracting article: {e}", ""


def main():
    st.set_page_config(page_title="News Article Finder", page_icon="📰")
    st.title("📰 Professional News Article Finder")

    st.markdown("""
    **Welcome!**  
    This tool helps you find and extract Gujarati news articles from popular newspapers.  
    Simply select a newspaper, enter a keyword, and let us do the rest!  
    """)

    newspaper = st.sidebar.selectbox(
        "Choose a Newspaper",
        ("Gujarat Samachar", "Mid Day", "Divya Bhaskar")
    )

    newspaper_urls = {
        "Gujarat Samachar": "https://www.gujaratsamachar.com/",
        "Mid Day": "https://www.gujaratimidday.com/",
        "Divya Bhaskar": "https://www.divyabhaskar.co.in/"
    }

    base_url = newspaper_urls.get(newspaper)
    keyword = st.text_input("Enter a Keyword to Search (e.g., 'Modi', 'Election')")

    if st.button("Search Articles"):
        if keyword:
            st.info(f"Searching articles in **{newspaper}** with the keyword: **{keyword}**")
            with st.spinner("Searching for articles..."):
                links = fetch_article_links(base_url, keyword)
                if links:
                    st.success(f"Found {len(links)} article(s) matching the keyword '{keyword}':")
                    for i, link in enumerate(links, start=1):
                        st.write(f"**Article {i}:** [Read here]({link})")
                        with st.spinner(f"Extracting content from Article {i}..."):
                            article_date, article_content = extract_article(link, newspaper)
                            with st.expander(f"Article {i} Content (Published: {article_date})", expanded=False):
                                st.write(article_content)
                else:
                    st.warning(f"No articles found with the keyword '{keyword}'. Try another keyword.")
        else:
            st.error("Please enter a keyword to search.")


if __name__ == "__main__":
    main()
