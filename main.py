import streamlit as st
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator

def fetch_article_links(base_url, keyword):
    try:
        # Fetch the page content
        response = requests.get(base_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        links = []
        # Look for all <a> tags with href attribute
        for a in soup.find_all('a', href=True):
            # Check if keyword is in href or anchor text (case insensitive)
            if keyword.lower() in a.get('href', '').lower() or keyword.lower() in a.text.lower():
                href = a['href']
                # Ensure full URL if it's a relative path
                if not href.startswith("http"):
                    href = f"{base_url.rstrip('/')}/{href.lstrip('/')}"
                links.append(href)

        return links
    except Exception as e:
        st.error(f"An error occurred while fetching links: {e}")
        return []

def extract_article(link, newspaper):
    try:
        # Fetch the article page content
        response = requests.get(link)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract the date of publication
        date = soup.find('h5')
        article_date = date.get_text(strip=True) if date else "Date not found"

        # Extract article content based on newspaper type
        article_text = ""
        if newspaper == "Sandesh":
            # For Sandesh, we need to adjust the extraction logic
            content = soup.find('div', class_='article_content')  # Adjust this class as per actual structure
            if content:
                article_text = "\n".join(p.get_text() for p in content.find_all('p'))
            else:
                # If we can't find the content in expected tag, fall back to all <p> tags
                paragraphs = soup.find_all('p')
                article_text = "\n".join(p.get_text() for p in paragraphs if p.get_text())
        else:
            # For other newspapers, use a more general approach
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

    # Sidebar for newspaper selection
    newspaper = st.sidebar.selectbox(
        "Select a Newspaper",
        ("Gujarat Samachar", "Sandesh", "Divya Bhaskar")
    )

    # Mapping the newspaper names to their base URLs
    newspaper_urls = {
        "Gujarat Samachar": "https://www.gujaratsamachar.com/",
        "Sandesh": "https://www.sandesh.com/",
        "Divya Bhaskar": "https://www.divyabhaskar.co.in/"
    }

    # Get the base URL based on selected newspaper
    base_url = newspaper_urls.get(newspaper)

    keyword = st.text_input("Keyword to Search")

    if st.button("Find and Extract Articles"):
        if keyword:
            with st.spinner("Detecting keyword language..."):
                detected_language = GoogleTranslator(source='auto', target='en').translate(keyword)
                if detected_language == keyword:
                    st.info(f"Detected keyword in English. Using it directly: '{keyword}'")
                    translated_keyword = keyword
                else:
                    st.info(f"Detected keyword in Gujarati. Using it directly: '{keyword}'")
                    translated_keyword = keyword

                with st.spinner("Searching for articles..."):
                    links = fetch_article_links(base_url, translated_keyword)

                    if links:
                        st.success(f"Found {len(links)} articles with the keyword '{translated_keyword}':")
                        for i, link in enumerate(links, start=1):
                            st.write(f"**Article {i}:** [Link]({link})")
                            with st.spinner("Extracting article content..."):
                                article_date, article_content = extract_article(link, newspaper)
                                st.write(f"**Published on:** {article_date}")

                                if article_content:
                                    st.write(f"**Article Content (Original):**\n{article_content}")
                                else:
                                    st.warning(f"Article {i} has no content.")
                    else:
                        st.warning(f"No articles found with the keyword '{translated_keyword}'.")
        else:
            st.error("Please enter a keyword.")

if __name__ == "__main__":
    main()
