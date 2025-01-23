import requests
from bs4 import BeautifulSoup
import re

def extract_article(link, newspaper):
    try:
        response = requests.get(link)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        article_date = "Date not found"  # Initialize outside the if/else
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
            if article_date == "Date not found": #Check if still default value
                date_element = soup.find('time', class_='entry-date published')
                if date_element:
                    datetime_str = date_element.get('datetime')
                    if datetime_str:
                        article_date = datetime_str.split('T')[0] #Extract Date part

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
