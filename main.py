import streamlit as st
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
import re

def fetch_article_links(base_url, keyword):
    try:
        response = requests.get(base_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        links = []
        for a in soup.find_all('a', href=True):
            if keyword.lower() in a.get('href', '').lower() or keyword.lower() in a.text.lower():
                href = a['href']
                if not href.startswith("http"):
                    href = f"{base_url.rstrip('/')}/{href.lstrip('/')}"
                links.append(href)
        return links
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching URL: {e}")
        return []
    except Exception as e:
        st.error(f"Oops! Something went wrong while fetching the links: {e}")
        return []

def extract_article(link, newspaper):
    try:
        response = requests.get(link)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        article_date = "Date not found"
        if newspaper == "Gujarat Samachar":
            date_element = soup.find('span', class_='post-date')
            if date_element:
                article_date = date_element.get_text(strip=True)
        elif newspaper == "Mid Day":
            date_element = soup.find('h5')
            if date_element:
                article_date = date_element.get_text(strip=True)
        elif newspaper == "Divya Bhaskar":
            date_element = soup.find('span', class_='posted-on')
            if date_element:
                article_date = date_element.get_text(strip=True)
            if article_date == None:
                date_element = soup.find('time', class_='entry-date published')
                if date_element:
                    article_date = date_element['datetime']

        article_text = ""
        content = None
        if newspaper == "Mid Day":
            content = soup.find('div', class_='article-body')
        elif newspaper == "Divya Bhaskar":
            content = soup.find('div', class_='db-article-body')
        elif newspaper == "Gujarat Samachar":
            content = soup.find('div', class_='td-post-content')

        if content:
            paragraphs = content.find_all('p')
            seen_text = set()
            for p in paragraphs:
                text = p.get_text(strip=True)
                if text and text not in seen_text:
                    article_text += text + "\n"
                    seen_text.add(text)
        else:
            paragraphs = soup.find_all('p')
            seen_text = set()
            for p in paragraphs:
                text = p.get_text(strip=True)
                if text and text not in seen_text:
                    article_text += text + "\n"
                    seen_text.add(text)

        article_text = re.sub(r'http\S+', '', article_text)
        article_text = re.sub(r'www\S+', '', article_text)
        return article_date, article_text.strip() if article_text else "No article content found."

    except requests.exceptions.RequestException as e:
        return f"Error fetching article content: {e}", ""
    except Exception as e:
        return f"Error extracting article: {e}", ""

def main():
    st.set_page_config(page_title="Gujarati News Article Scraper", page_icon="📰")
    st.title("Gujarati News Article Finder")

    st.markdown("""
    **Welcome to the Gujarati News Article Finder!**
    This tool allows you to search for articles from popular Gujarati newspapers.
    Enter a keyword, and we'll find relevant articles for you!
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

    keyword = st.text_input("Enter a Keyword to Search (e.g., 'Cricket', 'Politics')")

    if st.button("Find Articles"):
        if keyword:
            with st.spinner("Detecting keyword language..."):
                try:
                    detected_language = GoogleTranslator(source='auto', target='en').translate(keyword)
                except Exception as e:
                    st.error(f"Error during language detection: {e}")
                    detected_language = keyword
                if detected_language == keyword:
                    st.info(f"Keyword detected in English: '{keyword}'")
                    translated_keyword = keyword
                else:
                    st.info(f"Keyword detected in Gujarati: '{keyword}'")
                    translated_keyword = keyword

            with st.spinner("Searching for articles..."):
                links = fetch_article_links(base_url, translated_keyword)

                if links:
                    st.success(f"Found {len(links)} articles for the keyword '{translated_keyword}':")
                    for i, link in enumerate(links, start=1):
                        st.write(f"**Article {i} (Link):** {link}")
                        with st.spinner(f"Extracting content from article {i}..."):
                            article_date, article_content = extract_article(link, newspaper)
                            st.write(f"**Published on:** {article_date}")

                            if article_content:
                                st.write(f"**Article Content (Without Links):**\n{article_content}")
                            else:
                                st.warning(f"Article {i} has no content.")
                else:
                    st.warning(f"No articles found for the keyword '{translated_keyword}'. Try using a different keyword.")
        else:
            st.error("Please enter a keyword to search for articles.")

if __name__ == "__main__":
    main()
