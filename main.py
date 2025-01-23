import streamlit as st
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator

def fetch_article_links(base_url, keyword):
    try:
        response = requests.get(base_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        return [a['href'] if a['href'].startswith('http') else f"{base_url.rstrip('/')}/{a['href'].lstrip('/')}"
                for a in soup.find_all('a', href=True) if keyword.lower() in (a.get('href', '').lower() or a.text.lower())]
    except Exception as e:
        st.error(f"Error fetching links: {e}")
        return []

def extract_article(link, newspaper):
    try:
        response = requests.get(link)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        date = soup.find('h5')
        article_date = date.get_text(strip=True) if date else "Date not found"
        content = soup.find('div', class_='article_content' if newspaper == 'Sandesh' else 'article-body')
        article_text = "\n".join(p.get_text() for p in content.find_all('p')) if content else "\n".join(p.get_text() for p in soup.find_all('p'))
        return article_date, article_text if article_text else "No content found."
    except Exception as e:
        return f"Error extracting article: {e}", ""

def main():
    st.set_page_config(page_title="Gujarati News Scraper", page_icon="📰")
    st.title("Gujarati News Article Finder")

    newspaper = st.sidebar.selectbox("Select Newspaper", ("Gujarat Samachar", "Sandesh", "Divya Bhaskar"))
    newspaper_urls = {"Gujarat Samachar": "https://www.gujaratsamachar.com/", "Sandesh": "https://www.sandesh.com/", "Divya Bhaskar": "https://www.divyabhaskar.co.in/"}
    base_url = newspaper_urls.get(newspaper)
    
    keyword = st.text_input("Enter Keyword")
    if st.button("Find Articles") and keyword:
        with st.spinner("Detecting keyword language..."):
            detected_language = GoogleTranslator(source='auto', target='en').translate(keyword)
            keyword = detected_language if detected_language != keyword else keyword
            with st.spinner("Searching for articles..."):
                links = fetch_article_links(base_url, keyword)
                if links:
                    st.success(f"Found {len(links)} articles with '{keyword}':")
                    for i, link in enumerate(links, 1):
                        st.write(f"**Article {i}:** [Link]({link})")
                        with st.spinner("Extracting content..."):
                            date, content = extract_article(link, newspaper)
                            st.write(f"**Published on:** {date}")
                            st.write(f"**Content:**\n{content}")
                else:
                    st.warning(f"No articles found with '{keyword}'.")
    else:
        st.error("Please enter a keyword.")

if __name__ == "__main__":
    main()
