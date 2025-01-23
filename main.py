import streamlit as st
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator

def fetch_article_links(base_url, keyword):
    try:
        response = requests.get(base_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        links = []
        for a in soup.find_all('a', href=True):
            # Match keyword in anchor text or href, case insensitive
            if keyword.lower() in a.text.lower() or keyword.lower() in a['href'].lower():
                href = a['href']
                if not href.startswith("http"):
                    href = f"{base_url.rstrip('/')}/{href.lstrip('/')}"
                links.append(href)

        return links
    except Exception as e:
        st.error(f"Error while fetching links: {e}")
        return []

def extract_article(link, newspaper):
    try:
        response = requests.get(link)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        date = soup.find('h5')
        article_date = date.get_text(strip=True) if date else "Date not found"

        article_text = ""
        if newspaper == "Mid Day":
            content = soup.find('div', class_='article-body')
        elif newspaper == "Divya Bhaskar":
            content = soup.find('div', class_='db-article-body')
        else:
            content = soup.find('div', class_='article-body')

        if content:
            article_text = "\n".join(p.get_text(strip=True) for p in content.find_all('p'))
        else:
            article_text = "No article content found."

        return article_date, article_text
    except Exception as e:
        return f"Error extracting article: {e}", ""

def main():
    st.set_page_config(page_title="Universal News Scraper", page_icon="📰")
    st.title("News Article Finder")
    
    st.markdown("""
    **Welcome to the Universal News Scraper!**  
    Enter any keyword, and we'll find relevant articles from popular Gujarati newspapers.  
    """)

    newspaper = st.sidebar.selectbox(
        "Select a Newspaper",
        ("Gujarat Samachar", "Mid Day", "Divya Bhaskar")
    )

    newspaper_urls = {
        "Gujarat Samachar": "https://www.gujaratsamachar.com/",
        "Mid Day": "https://www.gujaratimidday.com/",
        "Divya Bhaskar": "https://www.divyabhaskar.co.in/"
    }

    base_url = newspaper_urls.get(newspaper)
    keyword = st.text_input("Enter a Keyword to Search (e.g., 'Modi', 'Election', 'Cricket')")

    if st.button("Search Articles"):
        if keyword:
            with st.spinner("Searching for articles..."):
                links = fetch_article_links(base_url, keyword)
                if links:
                    st.success(f"Found {len(links)} articles with the keyword '{keyword}':")
                    for i, link in enumerate(links, start=1):
                        st.write(f"**Article {i}:** [Link]({link})")
                        with st.spinner(f"Extracting content from article {i}..."):
                            article_date, article_content = extract_article(link, newspaper)
                            st.write(f"**Published on:** {article_date}")
                            st.write(f"**Content:**\n{article_content}")
                else:
                    st.warning(f"No articles found with the keyword '{keyword}'. Try another.")
        else:
            st.error("Please enter a keyword to search.")

if __name__ == "__main__":
    main()
