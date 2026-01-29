import os
import sys

# Add project root to sys.path
base_dir = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)

sys.path.append(base_dir)

from utils.load_config import load_config

from src.generate_json import generate_json
from src.data_preprocessing_json import preprocessing as preprocessing
from src.scrape_article_html import main as scrape_article_html
from src.scrape_article_text_image import main as scrape_article_text_image
from src.reorder_json import reorder_field

import time

if __name__ == "__main__":
    
    CONFIG_PATH = os.path.join(base_dir, "config.yaml")
    config = load_config(CONFIG_PATH)
    USER_AGENTS = config["USER_AGENTS"]
    DEFAULT_HEADERS_GOOGLE = config["DEFAULT_HEADERS_GOOGLE"]
    DEFAULT_HEADERS_THE_ECONOMIST = config["DEFAULT_HEADERS_THE_ECONOMIST"]

    article_link = "https://www.economist.com/finance-and-economics/2026/01/28/just-how-debased-is-the-dollar"
    article_title = "Just how debased is the dollar?"

    article_title = article_title.replace("’", "'")

    start = time.time()

    folder_path = os.path.join(base_dir, "data", article_title)
    os.makedirs(folder_path, exist_ok=True)

    file_path = os.path.join(folder_path, f"{article_title}.json")
    
    generate_json(file_path, article_link, article_title)

    preprocessing(file_path)

    article_html_section = scrape_article_html(
                                USER_AGENTS,
                                DEFAULT_HEADERS_GOOGLE,
                                base_dir,
                                article_link,
                                article_title,
                                file_path
                            )

    scrape_article_text_image(USER_AGENTS, 
                              DEFAULT_HEADERS_THE_ECONOMIST, 
                              base_dir, 
                              article_html_section, 
                              folder_path,
                              file_path)
    
    reorder_field(file_path)

    # Total elapsed time
    elapsed_time = int(time.time() - start)

    hours = elapsed_time // 3600
    minutes = (elapsed_time % 3600) // 60
    seconds = elapsed_time % 60

    print(f"\n✅ Successfully scraped: {article_link}")
    print(f"⏱️ Time taken: {hours}h {minutes}m {seconds}s")