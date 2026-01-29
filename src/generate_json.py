import json
import os

def generate_json(file_path: str, article_link: str, article_title: str) -> None:
    """
    Generate a JSON file containing article metadata.

    Args:
        file_path (str): Path to the JSON file.
        article_link (str): URL of the article.
        article_title (str): Title of the article.

    Returns:
        None
    """

    data = [
        {
            "article_title": article_title,
            "article_link": article_link
        }
    ]

    # Ensure directory exists
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    # Write JSON file
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    print(f"[SUCCESS] JSON file generated at {file_path}")