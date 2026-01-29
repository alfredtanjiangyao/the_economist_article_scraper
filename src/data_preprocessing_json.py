import os
import json
import re
from typing import Any

def _extract_article_section(article_link: str) -> str:
    """
    Extract article section from the Economist article URL.

    Args:
        article_link (str): URL of the article.

    Returns:
        article_section (str)
    """

    pattern_path = re.compile(r"https?://[^/]+/(.+)")
    match = pattern_path.search(article_link)

    path = match.group(1)

    # Split the path into segments
    segments = path.split("/")

    # Remove all the date components
    cleaned = [
        s for s in segments
        if not re.fullmatch(r"\d{4}", s)   
        and not re.fullmatch(r"\d{2}", s)  
    ]

    article_section = cleaned[-2]

    return article_section

def preprocessing(file_path: str) -> None:
    """
    Load a JSON file containing article metadata, extract additional fields
    from the article URL, and save the updated JSON.

    The function:
    1. Adds 'article_section' extracted from the article URL.
    2. Adds 'article_date' extracted from the URL in YYYY-MM-DD format.
    3. Saves the updated JSON back to the same file.

    Args:
        file_path (str): Path to the JSON file.

    Raises:
        FileNotFoundError: If the JSON file does not exist.

    Returns:
        None
    """

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            articles= json.load(f)

        if not articles:
            raise ValueError("❌ JSON file is empty.")
        
        article = articles[0]
        article_link = article.get("article_link", "")

        # Extract article section from the URL
        article["article_section"] = _extract_article_section(article_link)

        # Extract article date (YYYY/MM/DD) and convert to YYYY-MM-DD format
        pattern_date = re.compile(r"/(\d{4}/\d{2}/\d{2})/")
        date_match = pattern_date.search(article_link)
        if date_match:
            ymd = date_match.group(1)
            article["article_date"] = ymd.replace("/", "-")
        else:
            article["article_date"] = None
        
        # Save JSON back
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(articles, f, ensure_ascii=False, indent=4)

        print(f"\n[SUCCESS] Successfully preprocessed: {file_path}")

    except FileNotFoundError:
        # Handle missing file gracefully
        raise FileNotFoundError(f"❌ CSV file not found: {file_path}")

    return None

