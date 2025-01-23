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
            if keyword.lower() in a.get('href', '').lower() or keyword.lower() in a.text.lower():
                href = a['href']
                if not href.startswith("http"):
                    href = f"{base_url.rstrip('/')}/{href.lstrip('/')}"
                links.append(href)

        return links
    except Exception as e:
        st.error(f"Oops! Something went wrong while fetching the links: {e}")
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
            if content:
                article_text = "\n".join(p.get_text() for p in content.find_all('p'))
            else:
                paragraphs = soup.find_all('p')
                article_text = "\n".join(p.get_text() for p in paragraphs if p.get_text())
        elif newspaper == "Divya Bhaskar":
            # Specific logic for Divya Bhaskar articles
            content = soup.find('div', class_='db-article-body')  # Update if the class name changes
            if content:
                article_text = "\n".join(p.get_text() for p in content.find_all('p'))
            else:
                paragraphs = soup.find_all('p')
                article_text = "\n".join(p.get_text() for p in paragraphs if p.get_text())
        else:
            content = soup.find('div', class_='article-body')
            if content:
                article_text = "\n".join(p.get_text() for p in content.find_all('p'))
            else:
                paragraphs = soup.find_all('p')
                article_text = "\n".join(p.get_text() for p in paragraphs if p.get_text())

        return article_date, article_text if article_text else "No article content found."
    except Exception as e:
        return f"Error extracting article: {e}", ""

def main():
    st.set_page_config(page_title="Gujarati News Article Scraper", page_icon="📰")
    st.title("Gujarati News Article Finder")
    
    st.markdown("""
    **Welcome to the Gujarati News Article Finder!**  
    This tool allows you to search for articles from popular Gujarati newspapers like Gujarat Samachar, Mid Day, and Divya Bhaskar.  
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
                detected_language = GoogleTranslator(source='auto', target='en').translate(keyword)
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
                            st.write(f"**Article {i}:** [Link]({link})")
                            with st.spinner(f"Extracting content from article {i}..."):
                                article_date, article_content = extract_article(link, newspaper)
                                st.write(f"**Published on:** {article_date}")

                                if article_content:
                                    st.write(f"**Article Content (Original):**\n{article_content}")
                                else:
                                    st.warning(f"Article {i} has no content.")
                    else:
                        st.warning(f"No articles found for the keyword '{translated_keyword}'. Try using a different keyword.")
        else:
            st.error("Please enter a keyword to search for articles.")

if __name__ == "__main__":
    main()
