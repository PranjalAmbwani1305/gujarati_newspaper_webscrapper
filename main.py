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
            # Adjusted logic for Divya Bhaskar
            content = soup.find('div', class_='db-article-body')  # Update class as per Divya Bhaskar's structure
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
