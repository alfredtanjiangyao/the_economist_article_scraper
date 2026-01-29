import json
from typing import Any

def reorder_field(file_path: str) -> None:
    """
    Reorder fields in the article JSON file based on a preferred key order.

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
        
        article = articles[0]

        ORDER = [
            "article_title",
            "article_subtitle",
            "article_link",
            "article_section",
            "article_date",
            "formattted_article_date",
            "cover_page_exists",
            "cover_page_more_than_2",
            "cover_page_metadata_dict",
            "images_metadata_dict",
            "paragraph_image_counts_dict",
            "structured_text_blocks_dict",
            "exact_start_marker",
            "exact_end_marker",
            "manual_review_signals",
            "requires_manual_review"
        ]

        # Rebuild dict in preferred order
        reordered_article = {
            key: article.get(key)
            for key in ORDER
            if key in article
        }

        # Save JSON back
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump([reordered_article], f, ensure_ascii=False, indent=4)

        print(f"\n[SUCCESS] Fields reordered successfully: {file_path}")

    except FileNotFoundError:
        # Handle missing file gracefully
        raise FileNotFoundError(f"❌ CSV file not found: {file_path}")

    return None