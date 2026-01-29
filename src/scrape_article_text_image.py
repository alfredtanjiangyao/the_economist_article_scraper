import os
import time
import random
import requests
from bs4 import BeautifulSoup
from typing import List, Optional, Tuple
from datetime import datetime
import re
import csv
import json
from PIL import Image
from io import BytesIO

def log_user_agent(user_agent: str, status: str, base_dir: str, csv_filename: str = "user_agents_log.csv") -> None:
    """
    Append a User-Agent and its request status to a CSV file in the specified directory.

    Args:
        user_agent (str): The User-Agent string to log.
        status (str): The request status (e.g., "SUCCESS" or "FAIL").
        base_dir (str): Base directory where the 'src' folder is located.
        csv_filename (str): Name of the CSV file. Defaults to "user_agents_log.csv".

    Returns:
        None
    """
    # Full path to the CSV file
    csv_file = os.path.join(base_dir, "logs", csv_filename)

    # Generate timestamp (e.g., 2025-11-17 14:32:10)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Append the User-Agent and status
    with open(csv_file, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, user_agent, status])

def _convert_human_readable_date_to_iso(date_str: str | None) -> str | None:
    """
    Convert a human-readable date (e.g. 'Jan 26th 2022')
    into ISO format 'YYYY-MM-DD'.

    Args:
        date_str (str): Human-readable date string

    Returns:
        Optional[str]: ISO formatted date, or None if parsing fails
    """
    if not date_str:
        return None
    
    # Remove ordinal suffixes: st, nd, rd, th
    cleaned_date = re.sub(r"(st|nd|rd|th)", "", date_str)

    parsed_date = datetime.strptime(cleaned_date, "%b %d %Y")
    
    return parsed_date.strftime("%Y-%m-%d")

def _extract_article_date_from_html(article_html_section: str) -> Optional[str]:
    """
    Extract the article date string from a <time> HTML tag.

    Args:
        article_html_section (str): Extracted HTML section
            (see `extract_article_html_section` for more context).

    Returns:
        Optional[str]: The extracted date string, e.g., "Jan 26th 2022", or None if not found.
    """
    # Example input:
    # >Jan 26th 2022</time>
    pattern = r">([^<]+)</time>"
    match = re.search(pattern, article_html_section)

    if match:
        return match.group(1).strip()
    
    print("   [WARNING] Couldn't extract the article date.")
    return None

def convert_iso_date_to_human_readable(article_date: str) -> str:
    """
    Convert an ISO date string (YYYY-MM-DD) into a human-readable format with ordinal day suffix 
    like 'Mar 17th 2018'.

    Args:
        article_date (str): The date string in ISO format, e.g., "2018-03-17".

    Returns:
        str: The formatted date string with abbreviated month and ordinal day,
             e.g., "Mar 17th 2018".
    """
    date_obj = datetime.strptime(article_date, "%Y-%m-%d")

    day = date_obj.day
    if 11 <= day <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")

    return date_obj.strftime(f"%b {day}{suffix} %Y")

def _retrieve_http_headers(USER_AGENTS: List[str], DEFAULT_HEADERS: dict[str, str]) -> dict[str, str]:
    """
    Generate HTTP request headers with a randomized User-Agent.

    This function creates a copy of the default HTTP headers and replaces 
    the 'User-Agent' field with a randomly selected string from the provided 
    list of User-Agent options. It is typically used to rotate user agents 
    when making multiple web requests to reduce the risk of blocking.

    Args:
        USER_AGENTS (List[str]): A list of User-Agent strings to randomly choose from.
        DEFAULT_HEADERS (dict[str, str]): A dictionary containing default HTTP headers.

    Returns:
        dict[str, str]: A new dictionary of HTTP headers with a randomized User-Agent.
    """
    http_headers = DEFAULT_HEADERS.copy()
    # Pick a random User-Agent from the list
    http_headers["User-Agent"] = random.choice(USER_AGENTS)

    return http_headers

def retrieve_and_save_article_date(json_path: str, article_html_section: str) -> str | None:
    """
    Retrieve the publication date (`article_date`) of a specific article from a JSON file.
    
    If the `article_date` is not already present in the JSON, it will be extracted
    from the provided HTML section, converted to ISO format, and the JSON file
    will be updated atomically to include the new date.

    Args:
        json_path (str): Path to the JSON file
        article_html_section (str): Extracted HTML section
    
    Returns:
        str | None: The `article_date` in ISO format (`YYYY-MM-DD`) if found or extracted,
                    otherwise `None`.
    """

    with open(json_path, "r", encoding="utf-8") as f:
        articles = json.load(f)

    matched_article = None

    article = articles[0]
    article_date = article.get("article_date")
    matched_article = article
    
    if not article_date:
        print("   [INFO] The json file didn't store article link, extracting...")
        article_date = _extract_article_date_from_html(article_html_section)
        article_date = _convert_human_readable_date_to_iso(article_date)

        matched_article["article_date"] = article_date

        tmp_path = f"{json_path}.tmp"

        # write to temp file first
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(articles, f, ensure_ascii=False, indent=4)

        # atomic replace
        os.replace(tmp_path, json_path)

    return article_date

def _find_article_date_idx(article_html_section: str, article_date: str) -> int | None:
    """
    Locate the last index of the substring f"{article_date}</time>" within the given 
    HTML section.

    For example, if:
        article_date = "Mar 17th 2018"

    the function searches for the exact pattern:
        "Mar 17th 2018</time>"

    If this pattern begins at position 250 in `article_html_section`, and the total
    length of the pattern is 21 characters, the function will return 271
    (i.e., 250 + 21), which represents the index immediately after the matched 
    substring ends.

    Args:
        article_html_section (str): Extracted HTML section according to the matched markers
        article_date (str): The publication date of the article 
            (e.g., "Mar 17th 2018").

    Returns:
        int | None: The ending index of the matched date pattern. Returns None 
        if the pattern is not found in `article_html_section`.
    """
    date_pattern = f"{article_date}</time>"
    article_date_start_idx = article_html_section.find(date_pattern)

    # this shouldn't happen
    if article_date_start_idx == -1:
        return None
    
    article_date_end_idx = article_date_start_idx + len(date_pattern)

    return article_date_end_idx

def _find_first_unmatched_closing_tag_end_idx(
    html: str,
    marker_text_with_closing: str
) -> int | None:
    """
    Find the end index of the first closing HTML tag that is not matched
    by a corresponding opening tag, starting right after a specified marker.

    Example:
        html = (
            'Jul 9th 2025</time>'
            '<span style=";">|</span>'
            '<span style=";">NEW YORK</span>'
            '<span style="">|</span>'
            '<span style="">4 min read</span>'
            '</div>'
        )

        marker_text_with_closing = 'Jul 9th 2025</time>'

        It returns the index of the last character (`>`) of the 
        first closing tag that does not have a corresponding opening tag.

    Args:
        html (str): HTML string.
        marker_text_with_closing (str): Marker including inner text and closing tag
            (e.g. 'Jul 9th 2025</time>').

    Returns:
        int | None: The index of the last character ('>') of the first unmatched closing tag
                    after the marker. Returns None if no unmatched closing tag is found.
    """
    marker_idx = html.find(marker_text_with_closing)
    if marker_idx == -1:
        return None

    scan_start = marker_idx + len(marker_text_with_closing)

    tag_pattern = re.compile(r"<(/?)([a-zA-Z0-9]+)(\s[^>]*)?>")
    stack: list[str] = []

    for tag_match in tag_pattern.finditer(html, scan_start):
        is_closing = tag_match.group(1) == "/"
        tag_name = tag_match.group(2).lower()
        tag_end_idx = tag_match.end() - 1

        if not is_closing:
            # Opening tag
            stack.append(tag_name)
        else:
            # Closing tag
            if stack and stack[-1] == tag_name:
                stack.pop()
            else:
                # First unmatched closing tag
                return tag_end_idx

    return None

def extract_content_html_section(article_html_section: str, article_date: str) -> str:
    """
    Extract the main content HTML immediately after the parent block 
    containing the article's date marker.

    Args:
        article_html_section (str): Extracted HTML section 
            (see `extract_article_html_section` for more context).
            
        article_date (str): The article's publication date (e.g., "Mar 17th 2018") 
            to locate the parent block ending with `</time>`.

    Returns:
        str: HTML content starting immediately after the parent block 
             containing the date marker.
    """
    # Find the parent block containing the article date marker
    start_idx = _find_first_unmatched_closing_tag_end_idx(article_html_section, f"{article_date}</time>")

    content_html_section = article_html_section[start_idx + 1:]
    
    print("\n[SUCCESS] Extracted another HTML section for subsequent image and text processing.")
    return content_html_section

# assume the html is not malformed
def find_tag_idx(content_html_section: str, tag_name: str) -> list[list[int]]:
    """
    Locate all complete HTML blocks of the form
    <tag_name ...> ... </tag_name> within a given HTML string and return their
    character index ranges.

    The returned indices include:
    - start_idx: the index of the '<' in the opening tag
    - end_idx: the index of the '>' in the corresponding closing tag

    This function assumes that tags of the same name are not nested. 

    Args:
        content_html_section (str): HTML snippet to search.
        tag_name (str): The HTML tag to find (e.g., "figure", "aside").

    Returns:
        list[list[int]]: A list of [start_idx, end_idx] pairs for each tag block.
                        Returns an empty list if no matching tags are found.
        
        - these ranges are inclusive ranges!
    """
    # Build a regex dynamically for the given tag_name
    pattern = re.compile(
        rf"<{tag_name}\b[^>]*>.*?</{tag_name}>",
        re.IGNORECASE | re.DOTALL
    )

    tag_idx_list = []
    for match in pattern.finditer(content_html_section):
        start_idx = match.start()
        end_idx = match.end() - 1
        tag_idx_list.append([start_idx, end_idx])

    return tag_idx_list

# the * makes all parameters after it keyword-only arguments.
def detect_special_tags(
    content_html_section: str,
    *,
    contains_substring: str | None = None,
    exact_tag_name: str | None = None
) -> bool:
    """
    Detect whether an opening HTML tag exists in the given HTML content based on
    either a substring match or an exact tag name match.

    The function supports two mutually exclusive detection modes:
    1) Substring match: detects any opening tag whose tag name contains the given substring.
    2) Exact match: detects any opening tag whose tag name matches the given name exactly.

    Only one detection mode is applied per call. If both parameters are provided,
    `contains_substring` takes priority.

    Examples:
        contains_substring="svelte"
            <aisveltewrap>
            <svelte-scroller-background-container>

        exact_tag_name="svg"
            <svg>
            <svg class="icon" width="24" height="24">

    Args:
        content_html_section (str): HTML content to be inspected.
        contains_substring (str | None): Substring to search for within tag names.
        exact_tag_name (str | None): Exact tag name to match (e.g. "svg").

    Returns:
        bool: True if a matching opening tag is found, otherwise False.
              Returns False if neither detection mode is specified.
    """
        
    if contains_substring:
        pattern = re.compile(
            rf"<\s*[a-zA-Z0-9\-_]*{re.escape(contains_substring)}[a-zA-Z0-9\-_]*\b",
            re.IGNORECASE,
        )
        found = bool(pattern.search(content_html_section)) # this is where the for loop is

        status = "FOUND" if found else "NOT FOUND"
        print(f"[INFO] Tag containing '{contains_substring}': {status}.")
        return found

    if exact_tag_name:
        pattern = re.compile(
            rf"<\s*{re.escape(exact_tag_name)}\b",
            re.IGNORECASE,
        )
        found = bool(pattern.search(content_html_section)) # this is where the for loop is
        
        status = "FOUND" if found else "NOT FOUND"
        print(f"[INFO] <{exact_tag_name}> tag: {status}.")
        return found
    
    return False

def _extract_other_images(
    base_dir: str,
    folder_path: str,
    USER_AGENTS: list[str],
    DEFAULT_HEADERS_THE_ECONOMIST: dict[str, str],
    max_retries: int,
    content_html_section: str,
    figure_idx_list: list[list[int]],
    structured_text_blocks_dict: dict[int, list],
) -> tuple[
    dict[str, dict[str, int | str | bool | None]],
    dict[int, int]
]:
    """
    Extract images from <figure> blocks and associate each image with its
    caption, reference, and the paragraph that immediately follows (after) it.

    Each image is downloaded and assigned a filename based on its paragraph
    order, then stored with structured metadata.

    Images are named logically by paragraph order rather than by figure,
    as multiple figures may appear under the same paragraph and each <figure> block
    may contain multiple images.

    Args:
        base_dir (str): Root directory of the project.
        folder_path (str): Directory path where images will be saved.   
        USER_AGENTS (list[str]): List of User-Agent strings for HTTP requests.
        DEFAULT_HEADERS_THE_ECONOMIST (dict[str, str]): Default HTTP headers for downloading images from The Economist.
        max_retries (int): Maximum number of retry attempts for image downloads.
        content_html_section (str): HTML content of the article section.
        
        figure_idx_list (list[list[int]]): List of [start_idx, end_idx] for each <figure> block.
        structured_text_blocks_dict (dict[int, list]): A dictionary mapping 1-based block indices to structured text blocks.
            Each block has the following keys:
                - heading (bool)
                - subheading (bool)
                - paragraph (bool)
                - end_idx (int)
                - content_text (str)
                (see `structure_article_text_blocks` for more context)

    Returns:
        images_metadata_dict (dict[str, dict[str, int | str | bool | None]]):
            Mapping from image filename (without extension) to structured
            image metadata. Each image entry contains:

                - paragraph (int):
                    1-based paragraph order of the text block that immediately
                    follows the <figure> in reading order.

                - link (str):
                    Absolute URL of the image source.
                    (e.g., "https://www.economist.com/interactive/international/2025/10/16/the-icy-cold-war-america-is-busy-losing/processed-images/1096/20250927_PDP504.jpg")

                - format (str):
                    Image file extension without the leading dot
                    (e.g., "jpg", "png").

                - multiple_img_in_a_figure (bool):
                    Whether the image belongs to a <figure> element that contains
                    more than one <img> tag.

                - is_figcaption_more_than_2 (bool):
                    Whether the associated <figcaption> contains more than two
                    caption or reference components.

                - caption (str | None):
                    Extracted caption text associated with the image, if present.

                - reference (str | None):
                    Extracted reference or credit text associated with the image,
                    if present.

            paragraph_image_counts_dict (dict[int, int]):
                Mapping from paragraph order to the total number of images
                associated with that paragraph.
    """

    end_idx_list = [block["end_idx"] for block in structured_text_blocks_dict.values()]

    paragraph_image_counts_dict = {}
    images_metadata_dict = {}

    def _largest_smaller_order(end_idx_list: list[int], idx: int) -> int:
        """
        Find the 1-based insertion position for `idx` in a strictly increasing list of end indices.

        This function returns the position where `idx` should be inserted **before the first
        element that is greater than `idx`**, assuming `end_idx_list` is strictly increasing.

        Assumptions:
            - `end_idx_list` is strictly increasing (each element is greater than the previous one).

        Args:
            end_idx_list (List[int]): A strictly increasing list of integers representing end indices.
            idx (int): The value for which the insertion position is calculated.

        Returns:
            int: The 1-based position where `idx` should be inserted.
                Returns `len(end_idx_list) + 1` if `idx` is greater than all elements in the list.
        """
        if not end_idx_list:
            return 1

        for i, end_idx in enumerate(end_idx_list, start=1):
            if end_idx > idx:
                return i

        return len(end_idx_list) + 1

    for figure_start_idx, figure_end_idx in figure_idx_list:

        # Find the paragraph order immediately after the figure
        paragraph_order = _largest_smaller_order(end_idx_list, figure_start_idx)

        # Extract HTML of the current figure
        figure_html_section = content_html_section[figure_start_idx: figure_end_idx + 1]
        figure_soup = BeautifulSoup(figure_html_section, "html.parser")

        multiple_img_in_a_figure = False
        number_img_in_figure = 0

        figure_img_list = []

        # Process each <img> individually
        for img_tag in figure_soup.find_all("img"):
            img_url = img_tag.get("currentsourceurl")
            if not img_url or not img_url.startswith("https://www.economist.com/"):
                continue
            number_img_in_figure += 1

            # the reason why we don't use img_index = number_img_in_figure
            # is because there could be multiple figures under the same paragraph_order
            if not paragraph_order in paragraph_image_counts_dict :
                paragraph_image_counts_dict[paragraph_order] = 1
            else :
                paragraph_image_counts_dict[paragraph_order] += 1

            img_index = paragraph_image_counts_dict.get(paragraph_order)
            
            # Ensure folder exists
            os.makedirs(folder_path, exist_ok=True)
            img_filename = f"{paragraph_order}_{img_index}"
            figure_img_list.append(img_filename)

            # Download the image
            _, img_extension = _download_and_save_image(
                base_dir,
                img_url,
                folder_path,
                img_filename,
                USER_AGENTS,
                DEFAULT_HEADERS_THE_ECONOMIST,
                max_retries
            )

            while not img_extension:
                print("   [INFO] Waiting for 8 minutes to retry...")
                time.sleep(480)

                _, img_extension = _download_and_save_image(
                base_dir,
                img_url,
                folder_path,
                img_filename,
                USER_AGENTS,
                DEFAULT_HEADERS_THE_ECONOMIST,
                max_retries
                )
            
            # Extract caption & reference**
            is_figcaption_more_than_2, figure_caption, figure_reference = _extract_figure_caption_reference(figure_soup)

            images_metadata_dict[img_filename] = {
                "paragraph": paragraph_order,
                "link": img_url,
                "format": img_extension[1:],
                "multiple_img_in_a_figure": False,
                "is_figcaption_more_than_2": False,
                "caption": figure_caption,
                "reference": figure_reference
            }

        if number_img_in_figure > 1:
            multiple_img_in_a_figure = True

        # multiple_img_in_a_figure and is_figcaption_more_than_2
        # are the same for all images in the same figure.
        for img_filename in figure_img_list:
            images_metadata_dict[img_filename].update({
                "multiple_img_in_a_figure": multiple_img_in_a_figure,
                "is_figcaption_more_than_2": is_figcaption_more_than_2
            })
    
    print("[SUCCESS] All other image extraction completed successfully.\n")

    return images_metadata_dict, paragraph_image_counts_dict

def _download_and_save_image(
    base_dir,
    img_url: str,
    folder_path: str,
    img_filename: str,
    USER_AGENTS: list[str],
    DEFAULT_HEADERS_THE_ECONOMIST: dict[str, str],
    max_retries: int = 10
) -> tuple[str, str]:
    """
    Download an image from a URL, detect its real format, convert unsupported formats
    to JPEG, and save it in a LaTeX-compatible form.

    The function attempts to download the image using two different methods:
    1) Direct HTTP requests with rotating headers.
    2) A persistent requests session as a fallback.

    Each method retries multiple times with random wait intervals between attempts.
    If the image is successfully retrieved, its actual format is detected from the
    binary content. Supported formats (JPEG, PNG) are saved directly, while
    unsupported formats (e.g., AVIF, WebP, BMP) are converted to JPEG.

    Args:
        base_dir: Root directory of the project.
        img_url (str): URL of the image to download.
        folder_path (str): Destination folder for saving the image.
        img_filename (str): Output filename without extension.
        USER_AGENTS (list[str]): List of User-Agent strings for HTTP requests.
        DEFAULT_HEADERS_THE_ECONOMIST (dict[str, str]): Default HTTP headers for downloading images from The Economist.
        max_retries (int, optional): Total number of download attempts across both
            methods. Defaults to 10.

    Returns:
        tuple[str, str]: A tuple containing:
            - file_path (str): Full path to the saved image.
            - file_extension (str): File extension used (".jpg" or ".png").

        Returns (None, None) if all retry attempts fail.
    """

    os.makedirs(folder_path, exist_ok=True)
    session = requests.Session()

    retries1 = max_retries // 2
    retries2 = max_retries - retries1

    def _process_and_save_image(content: bytes) -> tuple[str, str]:
        """
        Process image bytes and save it in a LaTeX-compatible format.

        This function opens image data from bytes, checks its format, and saves it 
        to a specified folder using a safe format for LaTeX. Supported formats 
        (JPEG, PNG) are saved as-is. Unsupported formats (e.g., AVIF, WebP, BMP) 
        are converted to JPEG.

        Args:
            content (bytes): Raw image data.

        Returns:
            tuple[str, str]: A tuple containing:
                - file_path (str): The full path where the image was saved.
                - file_extension (str): The file extension used (e.g., ".jpg" or ".png").
        """
        img = Image.open(BytesIO(content))
        real_format = img.format.lower()  # jpeg, png, webp, avif, bmp, etc.

        # LaTeX-safe formats
        if real_format in {"jpeg", "jpg", "png"}:
            file_extension = ".jpg" if real_format in {"jpeg", "jpg"} else ".png"
            file_path = os.path.join(folder_path, f"{img_filename}{file_extension}")
            img.save(file_path)
        else:
            # Convert unsupported formats (avif, webp, bmp → jpeg)
            img = img.convert("RGB")
            file_extension = ".jpg"
            file_path = os.path.join(folder_path, f"{img_filename}{file_extension}")
            img.save(file_path, format="JPEG")

        return file_path, file_extension

    # ---- Method 1: direct requests.get ----
    for attempt in range(retries1):
        try:
            print(f"Attempt {attempt + 1}/{max_retries}: {img_url}")
            http_headers = _retrieve_http_headers(USER_AGENTS, DEFAULT_HEADERS_THE_ECONOMIST)

            resp = requests.get(img_url, headers=http_headers, timeout=15)
            if resp.status_code == 200 and resp.content:
                file_path, file_extension = _process_and_save_image(resp.content)
                log_user_agent(http_headers["User-Agent"], "SUCCESS", base_dir, "user_agents_log.csv")
                print(f"   [SUCCESS] Saved image: {file_path}")
                return file_path, file_extension

            log_user_agent(http_headers["User-Agent"], "FAIL", base_dir, "user_agents_log.csv")
            print(f"   [FAIL] Received status {resp.status_code}. retrying in 2-5s...")
            time.sleep(random.uniform(2, 5))

        except Exception as e:
            print(f"   [FAIL] {e}, retrying in 2-5s...")
            log_user_agent(http_headers["User-Agent"], "FAIL", base_dir, "user_agents_log.csv")
            time.sleep(random.uniform(2, 5))

    # ---- Method 2: persistent session ----
    for attempt in range(retries2):
        try:
            print(f"Attempt {attempt + retries1 + 1}/{max_retries}: {img_url}")
            http_headers = _retrieve_http_headers(USER_AGENTS, DEFAULT_HEADERS_THE_ECONOMIST)

            resp = session.get(img_url, headers=http_headers, timeout=15)
            resp.raise_for_status()

            if resp.content:
                file_path, file_extension = _process_and_save_image(resp.content)
                log_user_agent(http_headers["User-Agent"], "SUCCESS", base_dir, "user_agents_log.csv")
                print(f"   [SUCCESS] Saved image → {file_path}")
                return file_path, file_extension

            log_user_agent(http_headers["User-Agent"], "FAIL", base_dir, "user_agents_log.csv")
            print(f"   [FAIL] Received status {resp.status_code}. retrying in 2-5s...")
            time.sleep(random.uniform(2, 5))

        except Exception as e:
            print(f"   [FAIL] {e}, retrying in 2-5s...")
            log_user_agent(http_headers["User-Agent"], "FAIL", base_dir, "user_agents_log.csv")
            time.sleep(random.uniform(2, 5))

    print(f"   [FAIL] Failed to fetch image after {max_retries} retries: {img_url}.")
    return None, None

def _extract_figure_caption_reference(
    figure_soup: BeautifulSoup,
) -> tuple[bool, str | None, str | None]:
    """
    Extract caption and reference text from a single <figure> block.

    This function inspects all <figcaption> elements within the provided
    BeautifulSoup object (which represents exactly one <figure> block)
    and extracts all cleaned text segments across all caption blocks.

    The function supports figures that contain multiple <figcaption> elements. 
    
    Based on the number of extracted segments, the 
    function infers whether the figure contains:

        1) a reference only, or
        2) a caption followed by a reference.

    The function assumes there are at most two text segments per <figure>. 
    If more than two segments are found, a flag is set to indicate that the 
    assumption may not hold.

    Args:
        figure_soup (BeautifulSoup):
            Parsed BeautifulSoup object representing a <figure> block in the article HTML.

    Returns:
        tuple[bool, str | None, str | None]:
            A tuple containing:
                - is_figcaption_more_than_2 (bool):
                    True if more than two text segments are found in <figcaption>.
                - img_caption (str | None):
                    Descriptive caption text extracted from the figure, if present.
                - img_reference (str | None):
                    Reference or credit text extracted from the figure, if present.

            If no <figcaption> or no valid text segments are found, or if
            is_figcaption_more_than_2 is True (i.e., more than two text segments
            are present), both img_caption and img_reference are returned as None.
    """
    img_caption = None
    img_reference = None

    # Searches the HTML for every <figcaption> tag
    # returns a list; could be empty or contain multiple caption blocks.
    caption_tags = figure_soup.find_all("figcaption")

    caption_parts = []

    is_figcaption_more_than_2 = False

    for cap in caption_tags:
        # .stripped_strings yields all text segments inside the tag, automatically removing surrounding whitespace
        for text in cap.stripped_strings:
            caption_parts.append(text.strip())

    # If only one text segment is extracted, it must be references only.
    if len(caption_parts) == 1:
        img_caption = None
        img_reference = caption_parts[0]
    
    # If two text segments are extracted, the first is caption, the second is reference.
    elif len(caption_parts) == 2:
        img_caption = caption_parts[0]
        img_reference = caption_parts[1]
    
    # Assumed that len(caption_parts) at most 2, therefore this case is for 0 segment
    # which means no caption or reference found.
    elif len(caption_parts) == 0:
        img_caption = None
        img_reference = None

    # the len(caption_parts) might > 2
    else:
        is_figcaption_more_than_2 = True
        img_caption = None
        img_reference = None

    return is_figcaption_more_than_2, img_caption, img_reference

    # no cover page
    # article_link = "https://www.economist.com/finance-and-economics/2002/09/05/preparing-for-the-next-one"
    # article_title = "Preparing for the next one"

    # cover page + caption + reference
    # article_link = "https://www.economist.com/culture/2025/07/09/what-superman-tells-you-about-american-foreign-policy"
    # article_title = "What Superman tells you about American foreign policy"

    # cover page + reference
    # article_link = "https://www.economist.com/the-world-this-week/2025/10/30/business"
    # article_title = "Business"

    # cover page + no caption + no reference
    # article_link = "https://www.economist.com/the-americas/2025/06/29/brazils-president-is-losing-clout-abroad-and-unpopular-at-home"
    # article_title = "Brazil’s president is losing clout abroad and unpopular at home"

def _extract_cover_page(
    base_dir: str,
    folder_path: str,
    USER_AGENTS: list[str],
    DEFAULT_HEADERS_THE_ECONOMIST: dict[str, str],
    max_retries: int,
    article_html_section: str,
    article_date: str
) -> tuple[bool, bool, dict[str, dict[str, str | bool | None]]]:
    """
    Extracts the cover page image(s) from an article HTML section, downloads them,
    and retrieves their caption and reference. 

    A cover page is usually found in the HTML section before the article's date.
    This function downloads all valid images within any <figure> tags in that section
    and extracts their associated captions and references.

    Downloaded images are saved in the specified folder with filenames like
    "cover_page_1", "cover_page_2", etc.

    Args:
        base_dir (str): Root directory of the project.
        folder_path (str): directory where the image will be saved.
            e.g., "The Economist Summarizer/data/database/2025-10-11/Businesses are grappling with a wave of cybercrime"
            
        USER_AGENTS (list[str]): List of User-Agent strings for HTTP requests.
        DEFAULT_HEADERS_THE_ECONOMIST (dict[str, str]): Default HTTP headers 
            configured for requests to *The Economist* website.

        max_retries (int, optional): Maximum number of retry attempts if 
            download fails.

        article_html_section (str): Extracted HTML section
            (see `extract_article_html_section` for THE context).

        article_date (str): The publication date of the article 
            (e.g., "Mar 17th 2018").
    
    Returns:
        tuple[bool, bool, dict[str, dict[str, str | bool | None]]]:
            A tuple containing:
                - cover_page_exists (bool):
                    True if at least one cover page image is found.
                - cover_page_more_than_2 (bool):
                    True if more than one cover page image is found.
                - cover_page_metadata_dict (dict):
                    Mapping from image filename (without extension) to structured metadata.
                    Each entry contains:
                        - link (str): Absolute URL of the image.
                        - format (str): Image file extension (e.g., "jpg", "png").
                        - multiple_img_in_a_figure (bool): True if the <figure> contains more than one image.
                        - is_figcaption_more_than_2 (bool): True if the <figcaption> contains more than two text segments.
                        - caption (str | None): Extracted caption text, if available.
                        - reference (str | None): Extracted reference/credit text, if available.
    """
    article_date_idx = _find_article_date_idx(article_html_section, article_date)
    cover_page_html = article_html_section[:article_date_idx + 1]

    figure_idx_list = find_tag_idx(cover_page_html, "figure")

    cover_page_exists = False
    cover_page_more_than_2 = False
    number_cover_page = 0

    cover_page_metadata_dict = {}

    for figure_start_idx, figure_end_idx in figure_idx_list:

        # Extract HTML of the current figure
        figure_html_section = cover_page_html[figure_start_idx: figure_end_idx + 1]
        figure_soup = BeautifulSoup(figure_html_section, "html.parser")

        multiple_img_in_a_figure = False
        number_img_in_figure = 0

        figure_img_list = []

        # Process each <img> individually
        for img_tag in figure_soup.find_all("img"):
            img_url = img_tag.get("currentsourceurl")
            if not img_url or not img_url.startswith("https://www.economist.com/"):
                continue

            number_img_in_figure += 1
            number_cover_page += 1
            cover_page_exists = True

            # Ensure folder exists
            os.makedirs(folder_path, exist_ok=True)
            img_filename = f"cover_page_{number_cover_page}"
            figure_img_list.append(img_filename)

            # Download the image
            _, img_extension = _download_and_save_image(
                base_dir,
                img_url,
                folder_path,
                img_filename,
                USER_AGENTS,
                DEFAULT_HEADERS_THE_ECONOMIST,
                max_retries
            )

            while not img_extension:
                print("   [INFO] Waiting for 8 minutes to retry...")
                time.sleep(480)
                
                _, img_extension = _download_and_save_image(
                base_dir,
                img_url,
                folder_path,
                img_filename,
                USER_AGENTS,
                DEFAULT_HEADERS_THE_ECONOMIST,
                max_retries
                )

            # Extract caption & reference
            is_figcaption_more_than_2, figure_caption, figure_reference = _extract_figure_caption_reference(figure_soup)

            cover_page_metadata_dict[img_filename] = {
                "link": img_url,
                "format": img_extension[1:],
                "multiple_img_in_a_figure": False,
                "is_figcaption_more_than_2": False,
                "caption": figure_caption,
                "reference": figure_reference
            }
        
        if number_img_in_figure > 1:
            multiple_img_in_a_figure = True

        # multiple_img_in_a_figure and is_figcaption_more_than_2
        # are the same for all images in the same figure.
        for img_filename in figure_img_list:
            cover_page_metadata_dict[img_filename].update({
                "multiple_img_in_a_figure": multiple_img_in_a_figure,
                "is_figcaption_more_than_2": is_figcaption_more_than_2
            })

    if number_cover_page > 1:
        cover_page_more_than_2 = True

    print("[SUCCESS] Cover page extraction completed successfully.\n")
    return cover_page_exists, cover_page_more_than_2, cover_page_metadata_dict

def _filter_non_overlapping_figures(figure_idx_list: list[list[int]], 
                                   *exclude_ranges_lists: list[list[int]]) -> list[list[int]]:
    """
    Filter a list of figure ranges to keep only those that do not overlap with any ranges in other lists.

    Each figure is represented by a [start_idx, end_idx] pair. The function removes any figure
    that overlaps with ranges in the provided exclusion lists. 

    Overlap is defined as:
        1. Partial overlap: any intersection of ranges (e.g., [100,200] and [150,250]).
        2. Subset: the figure is entirely contained within an exclusion range (e.g., [150,200] inside [100,300]).
        3. Superset: the figure entirely contains an exclusion range (e.g., [100,300] contains [150,200]).
        4. Touching boundaries: the figure and exclusion range share endpoints (e.g., [100,200] and [200,300]).

    Args:
        figure_idx_list (list[list[int]]):  List of [start_idx, end_idx] for each <figure> block.
        *exclude_ranges_lists (list[list[list[int]]]): One or more lists of ranges to exclude, 
            each element in the list should be [start_idx, end_idx].

    Returns:
        list[list[int]]: Filtered list of figure ranges that do not overlap with any exclusion ranges.

    Example:
        figure_idx_list = [[100, 200], [250, 300], [400, 500], [600, 700]]
        exclude_ranges_list1 = [[150, 260]]
        exclude_ranges_list2 = [[450, 460]]
        # Output: [600, 700]
    """
    # Flatten all other index lists into a single list of intervals
    flattened_exclude_ranges_list = [interval for sublist in exclude_ranges_lists for interval in sublist]

    filtered_figure_idx_list = []
    for fig_start_idx, fig_end_idx in figure_idx_list:
        has_overlap = False
        for exclude_start_idx, exclude_end_idx in flattened_exclude_ranges_list:
            # Check if there is any overlap
            if not (fig_end_idx < exclude_start_idx or fig_start_idx > exclude_end_idx):
                has_overlap = True
                break
        if not has_overlap:
            filtered_figure_idx_list.append([fig_start_idx, fig_end_idx])

    return filtered_figure_idx_list

def extract_image(
    base_dir: str,
    folder_path: str,
    USER_AGENTS: list[str],
    DEFAULT_HEADERS_THE_ECONOMIST: dict[str, str],
    max_retries: int,
    article_html_section: str,
    formatted_article_date: str,
    content_html_section: str,
    structured_text_blocks_dict: dict[int, list],
    figure_idx_list: list[list[int]],
    *exclude_ranges_lists: list[list[int]]
) -> tuple[
    bool,
    bool,
    dict[str, dict[str, str | bool | None]],
    dict[str, dict[str, int | str | bool | None]],
    dict[int, int]
]:
    """
    Extract all images including cover page and in-article images
    while resolving <figure> overlaps and attaching structured metadata to each image.

    The function consists of three sequential stages:

    1. **Cover page extraction**:
    Identifies <figure> blocks appearing before the article date, downloads all valid
    cover page images, and extracts their associated caption and reference.
    Each cover page image is stored with standardized filenames (e.g., "cover_page_1", 
    "cover_page_2") and structured metadata describing its metadata.

    2. **Figure range filtering**:
    Removes <figure> blocks that overlap with excluded HTML ranges. 
    This ensures that only valid <figure> block are processed in the next stage.

    3. **In-article image extraction**:
    Extracts images from the <figure> blocks in `content_html_section`
    , downloads them, and associates each image with:
        - its paragraph order,
        - caption and reference text (if available),
        - figure-level flags (e.g., multiple images per figure),
        - and other structured metadata.

    Args:
        base_dir (str): Root directory of the project.
        folder_path (str): directory where the image will be saved.
            e.g., "The Economist Summarizer/data/database/2025-10-11/Businesses are grappling with a wave of cybercrime"
        USER_AGENTS (list[str]): List of User-Agent strings for HTTP requests.
        DEFAULT_HEADERS_THE_ECONOMIST (dict[str, str]): Default HTTP headers 
            configured for requests to *The Economist* website.
        max_retries (int, optional): Maximum number of retry attempts if 
            download fails.
        article_html_section (str): Extracted HTML section
            (see `extract_article_html_section` for THE context).
        formatted_article_date (str): The publication date of the article 
            (e.g., "Mar 17th 2018").
        content_html_section (str): HTML content of the article section.
        structured_text_blocks_dict (dict[int, list]): A dictionary mapping 1-based block indices to structured text blocks.
            Each block has the following keys:
                - heading (bool)
                - subheading (bool)
                - paragraph (bool)
                - end_idx (int)
                - content_text (str)
                (see `structure_article_text_blocks` for more context)
        figure_idx_list (list[list[int]]):
            List of [start_idx, end_idx] for all <figure> blocks in the article body.
        *exclude_ranges_lists (list[list[int]]):
            One or more lists of index ranges to exclude when filtering figures
            (e.g., cover page ranges, aside blocks).

    Returns:
        tuple:
            (
                cover_page_exists (bool),
                cover_page_more_than_2 (bool),
                cover_page_metadata_dict (dict[str, dict[str, str | bool | None]]),
                images_metadata_dict (dict[str, dict[str, int | str | bool | None]]),
                paragraph_image_counts_dict (dict[int, int])
            )

        cover_page_exists:
            True if at least one cover page image is found.

        cover_page_more_than_2:
            True if more than one cover page image is found.

        cover_page_metadata_dict (dict):
            Mapping from image filename (without extension) to structured metadata.
            Each entry contains:
                - link (str): Absolute URL of the image.
                - format (str): Image file extension (e.g., "jpg", "png").
                - multiple_img_in_a_figure (bool): True if the <figure> contains more than one image.
                - is_figcaption_more_than_2 (bool): True if the <figcaption> contains more than two text segments.
                - caption (str | None): Extracted caption text, if available.
                - reference (str | None): Extracted reference/credit text, if available.

        images_metadata_dict (dict[str, dict[str, int | str | bool | None]]):
            Mapping from image filename (without extension) to structured
            image metadata. Each image entry contains:

                - paragraph (int):
                    1-based paragraph order of the text block that immediately
                    follows the <figure> in reading order.
                - link (str):
                    Absolute URL of the image source.
                    (e.g., "https://www.economist.com/interactive/international/2025/10/16/the-icy-cold-war-america-is-busy-losing/processed-images/1096/20250927_PDP504.jpg")
                - format (str):
                    Image file extension without the leading dot
                    (e.g., "jpg", "png").
                - multiple_img_in_a_figure (bool):
                    Whether the image belongs to a <figure> element that contains
                    more than one <img> tag.
                - is_figcaption_more_than_2 (bool):
                    True if more than two total caption or reference text segments are found
                    across all <figcaption> elements within the <figure> block.
                - caption (str | None):
                    Extracted caption text associated with the image, if present.
                - reference (str | None):
                    Extracted reference associated with the image,
                    if present.

            paragraph_image_counts_dict (dict[int, int]):
                Mapping from paragraph order to the total number of images
                associated with that paragraph.
    """
    # 1. Extract cover page images (if any)
    cover_page_exists, cover_page_more_than_2, cover_page_metadata_dict = _extract_cover_page(
        base_dir,
        folder_path,
        USER_AGENTS,
        DEFAULT_HEADERS_THE_ECONOMIST,
        max_retries,
        article_html_section,
        formatted_article_date,
    )

    # 2. Filter out figures that overlap with excluded ranges (for other images than cover page)
    filtered_figure_idx_list = _filter_non_overlapping_figures(
        figure_idx_list,
        *exclude_ranges_lists
    )

    # 3. Extract all other images 
    images_metadata_dict, paragraph_image_counts_dict = _extract_other_images(
        base_dir,
        folder_path,
        USER_AGENTS,
        DEFAULT_HEADERS_THE_ECONOMIST,
        max_retries,
        content_html_section,
        filtered_figure_idx_list,
        structured_text_blocks_dict
    )

    return cover_page_exists, cover_page_more_than_2, cover_page_metadata_dict, images_metadata_dict, paragraph_image_counts_dict

def find_immediate_parent(html: str, marker_text_with_closing: str) -> list[list[int]]:
    """
    Find the immediate parent element of a specified marker element in an HTML string.

    This function locates all occurrences of a marker element (defined by its inner text
    followed by its closing tag, e.g. "Explore more</h1>") and, for each occurrence,
    determines the character range of its immediate parent element.

    The algorithm uses a two-pass stack-based approach:
      1. A backward scan before the marker to locate the unmatched opening tag
         of the immediate parent.
      2. A forward scan after the marker to locate the corresponding closing tag
         of that parent.

    Self-closing HTML tags (e.g., <img>, <br>, <meta>) are ignored during parsing
    to prevent incorrect stack balancing.

    The function supports multiple occurrences of the marker within the same HTML
    string and returns the parent range for each occurrence.
        
    If the opening and closing tag names of the parent do not match, or if no valid
    parent is found for a marker, an empty list is appended for that marker in the
    returned results.

    The returned indices are inclusive and span the entire parent element, starting
    from the '<' of the opening tag and ending at the '>' of the corresponding closing tag.

    Args:
        html (str): The HTML string to search.
        marker_text_with_closing (str): Marker content consisting of inner text
            followed by its closing tag (e.g., "Explore more</h1>").

    Returns:
        list[list[int]]: A list of [start, end] index pairs, where each pair
        represents the inclusive character range of an immediate parent element,
        including the opening and closing tags. Returns an empty list if no valid
        parent is found or if the parent_tags_name do not match or `marker_text_with_closing`
        is not found.

        - If a parent cannot be determined for a specific marker (e.g., the parent opening 
          tag is missing, the corresponding closing tag is missing, or the opening and 
          closing tag names do not match), the corresponding entry in the outer list is an 
          empty list (`[]`).  
        - If no occurrences of the marker are found in the HTML, the function returns an 
          empty list (`[]`).
        - if the `marker_text_with_closing` is invalid (does not contain a closing tag),
          the function returns an empty list (`[]`).
    """
    parent_indices_list = []

    # Extract tag name and inner text from marker_text_with_closing
    # e.g. marker_text_with_closing="Explore more</h1>" 
    # then marker_tag_name="h1", marker_inner_text="Explore more"
    marker_tag_match = re.search(r"</([a-zA-Z0-9\-]+)>", marker_text_with_closing)
    if not marker_tag_match:
        print(f"[FAIL] Invalid marker format: expected inner text followed by a closing tag, e.g. 'Explore more</h1>'. \
              Got: {marker_text_with_closing}")
        return [] 

    marker_tag_name = marker_tag_match.group(1)
    marker_inner_text = marker_text_with_closing[:marker_tag_match.start()]

    # Find all occurrences of the marker element in HTML
    # re.IGNORECASE is for case-insensitive match
    marker_pattern = re.compile(
        rf"<{marker_tag_name}\b[^>]*>\s*{re.escape(marker_inner_text)}\s*</{marker_tag_name}>",
        re.IGNORECASE
    )

    SELF_CLOSING_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input",
                         "link", "meta", "param", "source", "track", "wbr"}
    # these tags 
    
    # Parse all HTML tags once (opening and closing)
    tag_pattern = re.compile(r"<(/?)([a-zA-Z0-9\-]+)(\s[^>]*)?>")
    all_tags = [
        {
            'is_closing': match.group(1) == '/',
            'name': match.group(2),
            'start': match.start(),
            'end': match.end() - 1
        }
        for match in tag_pattern.finditer(html)
        if match.group(2).lower() not in SELF_CLOSING_TAGS
    ]

    for marker_match in marker_pattern.finditer(html):
        marker_start_idx = marker_match.start()
        marker_end_idx = marker_match.end() - 1

        # Split tags before and after marker
        tags_before = [tag for tag in all_tags if tag['end'] < marker_start_idx]
        tags_after = [tag for tag in all_tags if tag['start'] > marker_end_idx]

        # --- Backward pass to find immediate parent opening tag ---
        stack = []
        parent_open_tag = None
        for tag in reversed(tags_before):
            if tag['is_closing']:
                stack.append(tag['name'].lower())
            else:
                if stack and stack[-1] == tag['name'].lower():
                    # Matching closing tag found, pop from stack
                    stack.pop()
                else:
                    parent_open_tag = tag
                    break

        if not parent_open_tag:
            print("[FAIL] No immediate parent opening tag parent found before marker")
            parent_indices_list.append([])
            continue

        # --- Forward pass to find corresponding closing tag ---
        stack = []
        parent_close_tag = None
        for tag in tags_after:
            if not tag['is_closing']:
                stack.append(tag['name'].lower())
            else:
                if stack and stack[-1] == tag['name'].lower():
                    # Matching opening tag found, pop from stack
                    stack.pop()
                else:
                    parent_close_tag = tag
                    break

        if not parent_close_tag:
            print("[FAIL] No closing tag found after marker")
            parent_indices_list.append([])
            continue

        # --- Verify tag names match ---
        if parent_open_tag['name'].lower() != parent_close_tag['name'].lower():
            print(f"[FAIL] Tag names do not match: {parent_open_tag['name']} vs {parent_close_tag['name']}")
            parent_indices_list.append([])
            continue

        parent_indices_list.append([parent_open_tag['start'], parent_close_tag['end']])

    return parent_indices_list

# assume the html is not malformed
def find_tag_idx_by_substring(content_html_section: str, substring: str) -> list[list[int]]:
    """
    Find all HTML tag blocks whose *tag name* contains the given substring
    (e.g., 'svelte'), returning their [start_idx, end_idx] ranges. (inclusive)
    
    Only blocks where the tag name contains the substring are matched.

    For example:
        <aisveltewrap> ... </aisveltewrap>
        <svelte-scroller-background-container> ... </svelte-scroller-background-container>

    Does NOT match:
        <div class="svelte-xyz"> ... </div>

    If contain nested matching tags, only the **outermost** interval is returned.

    Args:
        content_html_section (str): A section of HTML content to be inspected.
        substring (str): The substring to search for in tag names 
                         (case-insensitive).

    Returns:
        list[list[int]]: A list of [start_idx, end_idx] pairs representing
                         the inclusive character indices of each matched tag block.
                         Returns an empty list if no matching tags are found.
    """

    # Tag name must include substring, but attributes must not count
    tag_name_pattern = rf"[a-zA-Z0-9_\-]*{re.escape(substring)}[a-zA-Z0-9_\-]*"

    # Build regex for <tag ...>...</tag>
    full_tag_pattern = re.compile(
        rf"<({tag_name_pattern})\b[^>]*>.*?</\1>",
        re.IGNORECASE | re.DOTALL
    )

    # Collect all matched intervals
    intervals = [
        [match.start(), match.end() - 1]      # make end index inclusive
        for match in full_tag_pattern.finditer(content_html_section)
    ]

    if not intervals:
        return []

    # Remove nested intervals
    
    # Sort intervals by ,start_idx = match.start(), ascending
    # For intervals with the same start_idx, longer (outer) intervals first
    intervals.sort(key=lambda x: (x[0], -x[1]))

    outer_intervals = []
    for start_idx, end_idx in intervals:
        # If this interval is fully inside the last accepted one → skip it
        if outer_intervals:
            last_start, last_end = outer_intervals[-1]
            if last_start <= start_idx and end_idx <= last_end:
                continue
        
        outer_intervals.append([start_idx, end_idx])

    # Final sort by start_idx for readability
    outer_intervals.sort(key=lambda x: x[0])
    return outer_intervals

# assume the html is not malformed
def find_tag_with_inner_tag_idx_list(content_html_section: str, outer_tag: str, inner_tag: str) -> list[list[int]]:
    """
    Find all <outer_tag>...</outer_tag> blocks that contain a specific 
    <inner_tag>...</inner_tag> inside and return their start and end indices.

    Both outer_tag and inner_tag are treated as exact tag names. Nested inner tags are allowed.
    However, this function assumes that outer tags are not nested.

    Args:
        content_html_section (str): HTML snippet to search.
        outer_tag (str): The exact name of the outer tag (e.g., "aside").
        inner_tag (str): The exact name of the inner tag to check for (e.g., "ul").

    Returns:
        list[list[int]]: A list of [start_idx, end_idx] pairs for each 
                         <outer_tag> block containing a complete <inner_tag> block.
    """
    result_idx_list = []

    # Regex to find <outer_tag ...>...</outer_tag> blocks
    outer_pattern = re.compile(
        rf"<{outer_tag}\b[^>]*>.*?</{outer_tag}>",
        re.IGNORECASE | re.DOTALL
    )

    # Regex to check for <inner_tag>...</inner_tag> inside
    inner_pattern = re.compile(
        rf"<{inner_tag}\b[^>]*>.*?</{inner_tag}>",
        re.IGNORECASE | re.DOTALL
    )

    for match in outer_pattern.finditer(content_html_section):
        start_idx = match.start()
        end_idx = match.end() - 1
        outer_html = match.group()

        # Only keep if <inner_tag>...</inner_tag> exists inside
        if inner_pattern.search(outer_html):
            result_idx_list.append([start_idx, end_idx])

    return result_idx_list

def _generate_text_blocks_dict(content_html_section: str) -> tuple[dict[int, list[bool | int | str]], int]:
    """
    Extract sequential text blocks from an HTML snippet by scanning from left to right
    and splitting at the nearest closing tag among: </div>, </aside>, and </h2>.

    Each extracted block is stored in a dictionary using a 1-based index
    (`block_idx`) and has the following structure:

        block_idx: [
            heading (bool),
            subheading (bool),
            paragraph (bool),
            end_idx (int),
            content_text (str)
        ]

    where:
    - `end_idx` is the **last character index** (inclusive) of the corresponding
      closing tag relative to `content_html_section`.
    - `content_text` is the stripped plain-text representation of the HTML snippet.

    If no further closing tags are found, any remaining HTML (the "leftover" content)
    is processed once and added as a final block, with `end_idx` set to the last
    character index of `content_html_section`.

    The function also attempts to determine `first_block_start_idx`, which represents:
    - For the first extracted block with a closing tag: the start index of the
      matching opening tag (e.g. `<div`, `<aside`, `<h2>`) immediately preceding
      the closing tag.
    - For the first extracted block yet leftover-only content: the index of the nearest '<' character preceding
      the extracted text, or the current scan position if no match is found.

    Args:
        content_html_section (str): HTML snippet to search.

    Returns:
        tuple:
            - text_blocks_dict (dict[int, list[bool | int | str]]):
                A dictionary mapping 1-based block indices to extracted text block data.
            - first_block_start_idx (int):
                The inferred start index of the first extracted block
    """
    closing_tags = ["</div>", "</aside>", "</h2>"]
    text_blocks_dict = {}
    block_idx = 1
    pos = 0
    html_len = len(content_html_section)

    first_block_start_idx = 0  # default

    while pos < html_len:

        # Find nearest closing tag
        closing_tag_candidates = []
        for tag in closing_tags:
            # idx here is the start index of the closing tag
            closing_tag_start_idx = content_html_section.find(tag, pos)
            if closing_tag_start_idx != -1:
                closing_tag_candidates.append((closing_tag_start_idx, tag))

        if closing_tag_candidates:
            # Get the nearest closing tag and its end_idx(ie. last char index of the tag)
            nearest_idx, nearest_tag = min(closing_tag_candidates, key=lambda x: x[0])
            end_idx = nearest_idx + len(nearest_tag) - 1

            # Extract raw HTML between current position and nearest closing tag
            snippet = content_html_section[pos:nearest_idx]

            # Convert snippet into plain text
            content_text = BeautifulSoup(snippet, "html.parser").get_text().strip()

            if content_text:
                text_blocks_dict[block_idx] = [
                    False,  # heading
                    False,  # subheading
                    False,  # paragraph
                    end_idx,
                    content_text
                ]

                # TODO: might have bug
                # Set first_start_idx for the first element
                if block_idx == 1:
                    opening_tag = "<" + nearest_tag[2:-1]  # e.g., </div> -> <div
                    # .rfind() to find the last occurrence of <div, <aside, or <h2> before the closing tag
                    first_block_start_idx = content_html_section.rfind(opening_tag, pos, end_idx)
                block_idx += 1

            # Move pointer forward
            pos = end_idx + 1

        # Leftover content after the last closing tag
        else:
            leftover_snippet = content_html_section[pos:].strip()
            if leftover_snippet:
                soup = BeautifulSoup(leftover_snippet, "html.parser")
                content_text = soup.get_text().strip()
                if content_text:
                    text_blocks_dict[block_idx] = [
                        False,  # heading
                        False,  # subheading
                        False,  # paragraph
                        len(content_html_section) - 1,   # no closing tag
                        content_text
                    ]
                    if block_idx == 1:
                        # TODO: most likely have bug
                        # Find the start index of the opening tag immediately before content_text
                        first_word = content_text.split(maxsplit=1)[0]
                        text_start_idx = content_html_section.find(first_word, pos)

                        if text_start_idx != -1:
                            first_block_start_idx = content_html_section.rfind("<", pos, text_start_idx)
                        else:
                            first_block_start_idx = pos
            break

    return text_blocks_dict, first_block_start_idx

def _differentiate_heading_subheading_paragraph(text_blocks_dict: dict[int, list[bool | int | str]], 
                                     h2_idx_list: list[list[int]], aside_idx_list: list[list[int]]) -> dict[int, list[bool | int | str]]:
    """
    Classify extracted text blocks as heading, subheading, or paragraph based on
    their HTML positional context.

    This function updates each text block in `text_blocks_dict` by comparing the
    block's ending index (`text_block_end_idx`) against the index ranges of
    <h2> and <aside> blocks:

    - If `text_block_end_idx` falls within any range in `h2_idx_list`,
    the block is marked as a subheading.
    - If `text_block_end_idx` falls within any range in `aside_idx_list`,
    the block is marked as a heading.
    - If neither condition is met, the block is marked as a paragraph.

    The classification is mutually exclusive: a block is assigned only one role.

    Args:
        text_blocks_dict (dict[int, list[bool | int | str]]): A dictionary mapping 1-based block indices to extracted text block data.
                (see `extract_text` for more context).

        h2_idx_list (list[list[int]]): [[start_idx1, end_idx1], ...] positions of <h2> blocks in `content_html_section`

        aside_idx_list (list[list[int]]): [[start_idx1, end_idx1], ...] positions of <aside> blocks in `content_html_section`

    Returns:
        dict: Refined text_blocks_dict with updated heading, subheading, and paragraph flags.
    """
    if not text_blocks_dict:
        return text_blocks_dict
    
    for key, value in text_blocks_dict.items():
        heading, subheading, paragraph, text_block_end_idx, content_text = value

        # Check if end_idx is inside any <h2> block → mark it as subheading
        for h2_start_idx, h2_end_idx in h2_idx_list:
            if h2_start_idx <= text_block_end_idx <= h2_end_idx:
                subheading = True
                break

        # Check if end_idx is inside any <aside> block → mark it as heading
        for aside_start_idx, aside_end_idx in aside_idx_list:
            if aside_start_idx <= text_block_end_idx <= aside_end_idx:
                heading = True
                break

        # If still no flags are True → mark it as paragraph
        if not heading and not subheading:
            paragraph = True

        text_blocks_dict[key] = [heading, subheading, paragraph, text_block_end_idx, content_text]

    return text_blocks_dict

def _filter_text_blocks_dict(text_blocks_dict: dict[int, list], first_block_start_idx: int, *idx_lists: list[list[int]]) -> dict[int, list]:
    """
    Refine the text_blocks_dict by removing entries whose end_idx falls inside any
    range in idx_lists. Additionally, if a suppression range lies strictly
    between end_idx[n] and end_idx[n+1], then remove entry n+1 as well.

    Args:
        text_blocks_dict (dict[int, list]): Each value is:
            [heading: bool, subheading: bool, paragraph: bool, end_idx: int, text: str]
        first_block_start_idx (int): The inferred start index of the first extracted block within `content_html_section`.
            (see `_generate_text_blocks_dict` for more context).
        *idx_lists (list[list[int]]): Each list contains [start_idx, end_idx] pairs indicating HTML index
            regions whose corresponding text blocks should be removed.

    Returns:
        dict[int, list]: Filtered `text_blocks_dict` with eliminated blocks removed and
            remaining blocks renumbered sequentially from 1.
    """
    if not text_blocks_dict:
        return text_blocks_dict
    # ------------------------------------------
    # Step 1: Extract end_idx in order (for n / n+1 comparison)
    # ------------------------------------------
    text_blocks_entries = list(text_blocks_dict.values())
    text_blocks_end_idx_list = [entry[3] for entry in text_blocks_entries]

    # ------------------------------------------
    # Step 2: Build a set of end_idx values to eliminate
    # ------------------------------------------
    eliminate_end_idxs = set()

    for idx_list in idx_lists:
        for start, end in idx_list:

            # Rule 1: eliminate entries whose end_idx is inside the range
            for text_block_end_idx in text_blocks_end_idx_list:
                if start <= text_block_end_idx <= end:
                    eliminate_end_idxs.add(text_block_end_idx)

            # Rule 2: eliminate entry n+1 if (end_idx[n] < start and end < end_idx[n+1])
            for n in range(len(text_blocks_end_idx_list) - 1):
                left = text_blocks_end_idx_list[n]
                right = text_blocks_end_idx_list[n + 1]

                if left < start and end < right:
                    eliminate_end_idxs.add(right)

            # article_link = "https://www.economist.com/economic-and-financial-indicators/2025/11/06/economic-data-commodities-and-markets"  # Replace with the snapshot ID
            # article_title = "Economic data, commodities and markets"
            if first_block_start_idx < start and end < text_blocks_end_idx_list[0]:
                eliminate_end_idxs.add(text_blocks_end_idx_list[0])

    # ------------------------------------------
    # Step 3: Keep entries whose end_idx is NOT eliminated
    # ------------------------------------------
    refined_entries = [entry for entry in text_blocks_entries if entry[3] not in eliminate_end_idxs]

    # ------------------------------------------
    # Step 4: Renumber keys
    # ------------------------------------------
    return {i + 1: entry for i, entry in enumerate(refined_entries)}

def _convert_text_blocks_dict_to_nested_dict(
    text_blocks_dict: dict[int, list[bool | int | str]]
) -> dict[int, dict[str, bool | int | str]]:
    """
    Convert text blocks from a list-based format to a nested dictionary format.

    Example transformation:

        Input:
            text_blocks_dict = {
                1: [True, False, False, 245, "Introduction"]
            }

        Output:
            structured_text_blocks_dict = {
                1: {
                    "heading": True,
                    "subheading": False,
                    "paragraph": False,
                    "end_idx": 245,
                    "content_text": "Introduction"
                }
            }

    Args:
        text_blocks_dict (dict[int, list[bool | int | str]]):
            Dictionary mapping block index to list-based text blocks.

    Returns:
        dict[int, dict[str, bool | int | str]]:
            Dictionary mapping block index to a nested dictionary
            representing each text block.
    """
    structured_text_blocks_dict  = {}

    for block_idx, block in text_blocks_dict.items():
        heading, subheading, paragraph, end_idx, content_text = block

        structured_text_blocks_dict[block_idx] = {
            "heading": heading,
            "subheading": subheading,
            "paragraph": paragraph,
            "end_idx": end_idx,
            "content_text": content_text
        }

    return structured_text_blocks_dict

def extract_text(
    content_html_section: str, 
    h2_idx_list: list[list[int]], 
    aside_idx_list: list[list[int]], 
    *idx_lists: list[list[int]]
) -> dict[int, list[bool | int | str]]:
    """
    Extract and classify sequential text blocks from an HTML snippet.

    This function performs four main operations on the HTML content:

    1. **Generate text blocks**: Scans the HTML from left to right, splitting
       at the nearest closing tags among `</div>`, `</aside>`, and `</h2>`.
       Each block is represented as a list containing:
           [heading (bool), subheading (bool), paragraph (bool), end_idx (int), content_text (str)]

    2. **Differentiate block types**: Marks each block as a heading, subheading,
       or paragraph based on whether its `end_idx` falls within the ranges of
       `<h2>` or `<aside>` elements provided by `h2_idx_list` and `aside_idx_list`.

    3. **Filter blocks**: Removes blocks whose `end_idx` falls inside any of the
       ranges provided in `idx_lists`. Also applies suppression rules for
       blocks between sequential `end_idx` positions, and renumbers keys
       sequentially in the resulting dictionary.

    4. **Structure output**:
       Convert text blocks from a list-based format to a nested dictionary format.

    Args:
        content_html_section (str): HTML snippet to search.
        h2_idx_list (list[list[int]]): List of `[start_idx, end_idx]` ranges for `<h2>` elements.
        aside_idx_list (list[list[int]]): List of `[start_idx, end_idx]` ranges for `<aside>` elements.
        *idx_lists (list[list[int]]): Arbitrary number of lists containing
            `[start_idx, end_idx]` ranges of content to remove.

    Returns:
        dict[int, dict[str, bool | int | str]]:
            A dictionary mapping 1-based block indices to structured text blocks.
            Each block has the following keys:
                - heading (bool)
                - subheading (bool)
                - paragraph (bool)
                - end_idx (int)
                - content_text (str)
    """
    initial_text_blocks_dict, first_block_start_idx = _generate_text_blocks_dict(content_html_section)

    differentiated_text_blocks_dict = _differentiate_heading_subheading_paragraph(
        initial_text_blocks_dict,
        h2_idx_list,
        aside_idx_list
    )

    text_blocks_dict = _filter_text_blocks_dict(
        differentiated_text_blocks_dict,
        first_block_start_idx,
        *idx_lists
    )

    structured_text_blocks_dict = _convert_text_blocks_dict_to_nested_dict(text_blocks_dict)

    print("\n[SUCCESS] Text extraction completed successfully.\n")

    return structured_text_blocks_dict

def has_any_image_flag_true(
    flag_name: str,
    *metadata_dicts: dict[str, dict[str, int | bool | str | None]],
) -> bool:
    """
    Check whether any image metadata entry has a given boolean flag set to True.

    This function scans one or more image metadata dictionaries (e.g. cover page
    images and in-article images). If any image entry contains the specified
    flag with a value of True, the function returns True; otherwise, it returns False.

    if the dict is empty, return False

    Args:
        flag_name (str):
            Name of the boolean flag to check
            (e.g., "multiple_img_in_a_figure", "is_figcaption_more_than_2").

        *metadata_dicts (dict[str, dict]):
            One or more image metadata dictionaries. Each dictionary maps
            an image filename to its structured metadata.

    Returns:
        bool:
            True if at least one image has `flag_name == True`;
            False otherwise.
    """
    return any(
        image_meta.get(flag_name, False)
        for metadata_dict in metadata_dicts
        for image_meta in metadata_dict.values()
    )

def update_article_metadata_json(file_path: str, formatted_article_date: str, 
                                 cover_page_exists: bool, cover_page_more_than_2: bool, cover_page_metadata_dict: dict,
                                 images_metadata_dict: dict, paragraph_image_counts_dict: dict, structured_text_blocks_dict: dict,
                                 has_svg: bool, has_svelte: bool) -> None:
    """
    store all the metadata into the article JSON file
    """

    is_more_than_30_text_blocks = False

    multiple_images_in_a_figure = has_any_image_flag_true(
    "multiple_img_in_a_figure",
    cover_page_metadata_dict,
    images_metadata_dict
    )
    
    figcaption_more_than_2 = has_any_image_flag_true(
    "is_figcaption_more_than_2",
    cover_page_metadata_dict,
    images_metadata_dict
    )

    if len(structured_text_blocks_dict) > 30:
        is_more_than_30_text_blocks = True

    with open(file_path, "r", encoding="utf-8") as f:
        articles = json.load(f)
    article = articles[0]

    unusual_start_marker = article.get("manual_review_signals").get("unusual_start_marker")
    unusual_end_marker = article.get("manual_review_signals").get("unusual_end_marker")
    is_indicators_or_letters = article.get("manual_review_signals").get("is_indicators_or_letters")

    has_issue = any((
    unusual_start_marker,
    unusual_end_marker,
    is_indicators_or_letters,
    is_more_than_30_text_blocks,
    has_svg,
    has_svelte,
    cover_page_more_than_2,
    multiple_images_in_a_figure,
    figcaption_more_than_2,
    ))

    new_fields = {
    "formatted_article_date": formatted_article_date,
    "cover_page_exists": cover_page_exists,
    "cover_page_more_than_2": cover_page_more_than_2,
    "cover_page_metadata_dict": cover_page_metadata_dict,
    "images_metadata_dict": images_metadata_dict,
    "paragraph_image_counts_dict": paragraph_image_counts_dict,
    "structured_text_blocks_dict": structured_text_blocks_dict,
    "manual_review_signals": {
        "unusual_start_marker": unusual_start_marker,
        "unusual_end_marker": unusual_end_marker,
        "is_indicators_or_letters": is_indicators_or_letters,
        "is_more_than_30_text_blocks": is_more_than_30_text_blocks,
        "has_svg": has_svg,
        "has_svelte": has_svelte,
        "cover_page_more_than_2": cover_page_more_than_2,
        "multiple_images_in_a_figure": multiple_images_in_a_figure,
        "figcaption_more_than_2": figcaption_more_than_2
    },
    "requires_manual_review": has_issue
    }

    article.update(new_fields)

    # safer write (atomic replace)
    tmp_path = file_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=4)

    os.replace(tmp_path, file_path)

    print(f"\n[SUCCESS] Successfully updated the remaining metadata in {file_path}")

    return None

def main(USER_AGENTS: List[str],
         DEFAULT_HEADERS_THE_ECONOMIST: dict[str, str],
         base_dir: str, article_html_section, folder_path, file_path) -> None:
    """
    Main function to scrape both text and images from a single article on The Economist.

    Args:
        USER_AGENTS (List[str]): List of User-Agent strings for HTTP requests.
        DEFAULT_HEADERS_GOOGLE (dict[str, str]): Default HTTP headers for requests to Google.
        DEFAULT_HEADERS_THE_ECONOMIST (dict[str, str]): Default HTTP headers for downloading images from The Economist.
        base_dir (str): Root directory of the project.
        article_link (str): The original URL of the article on *The Economist* website, 
            e.g., "https://www.economist.com/science-and-technology/2025/10/08/hover-flies-are-long-distance-travellers"
        article_title (str): The title of the article.
            e.g., "Hover flies are long-distance travellers"
    
    Returns:
        None
    """
    iso_article_date = retrieve_and_save_article_date(file_path, article_html_section)

    formatted_article_date = convert_iso_date_to_human_readable(iso_article_date)

    content_html_section = extract_content_html_section(article_html_section, formatted_article_date)

    # h2_idx_list and aside_idx_list are used to differentiate headings, subheadings, and paragraphs
    h2_idx_list = find_tag_idx(content_html_section, "h2")
    aside_idx_list = find_tag_idx(content_html_section, "aside")

    figure_idx_list = find_tag_idx(content_html_section, "figure") 

    # these lists are used to filter out unwanted text blocks and images later
    svelte_idx_list = find_tag_idx_by_substring(content_html_section, "svelte") 
    svg_idx_list = find_tag_idx(content_html_section, "svg")
    explore_more_idx_list = find_immediate_parent(content_html_section, "Explore more</h1>")
    aside_with_ul_idx_list = find_tag_with_inner_tag_idx_list(content_html_section, "aside", "ul")
    figcaption_idx_list = find_tag_idx(content_html_section, "figcaption") 

    structured_text_blocks_dict \
        = extract_text(
        content_html_section,
        h2_idx_list,
        aside_idx_list,
        figure_idx_list,
        svelte_idx_list,
        svg_idx_list,
        explore_more_idx_list,
        aside_with_ul_idx_list,
        figcaption_idx_list
    )

    cover_page_exists, cover_page_more_than_2, cover_page_metadata_dict, images_metadata_dict, paragraph_image_counts_dict \
        = extract_image(
            base_dir,
            folder_path,
            USER_AGENTS,
            DEFAULT_HEADERS_THE_ECONOMIST,
            10,
            article_html_section,
            formatted_article_date,
            content_html_section,
            structured_text_blocks_dict,
            figure_idx_list,
            svelte_idx_list, 
            svg_idx_list, 
            explore_more_idx_list, 
            aside_with_ul_idx_list
        )
    
    has_svelte = detect_special_tags(
        content_html_section,
        contains_substring="svelte"
    )

    has_svg = detect_special_tags(
        content_html_section,
        exact_tag_name="svg"
    )

    update_article_metadata_json(file_path, formatted_article_date, 
                                 cover_page_exists, cover_page_more_than_2, cover_page_metadata_dict,
                                 images_metadata_dict, paragraph_image_counts_dict, structured_text_blocks_dict,
                                 has_svg, has_svelte)

    return None