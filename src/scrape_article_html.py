import os
import time
import random
import requests
from bs4 import BeautifulSoup
from typing import List, Optional, Tuple
from datetime import datetime, timedelta
import re
import csv
import urllib.parse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
import json
from selenium_recaptcha_solver import RecaptchaSolver

def _get_random_chrome_options(USER_AGENTS: List[str]) -> Options:
    """
    Create Chrome Options with randomized User-Agent and unique debugging port.
    """
    port = random.randint(20000, 45000)
    user_agent = random.choice(USER_AGENTS)

    chrome_options = Options()
    chrome_options.add_argument(f"--remote-debugging-port={port}")
    chrome_options.add_argument(f"--user-agent={user_agent}")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    # chrome_options.add_argument("--headless")  # optional

    return chrome_options

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
    os.makedirs(os.path.dirname(csv_file), exist_ok=True)

    # Generate timestamp (e.g., 2025-11-17 14:32:10)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Append the User-Agent and status
    with open(csv_file, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, user_agent, status])

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

def _encode_url(url: str) -> str:
    """
    Encode a URL into a percent-encoded format.

    Args:
        url (str): The original URL to be encoded.

    Returns:
        str: The percent-encoded URL string, safe for inclusion in query parameters.
    """
    encoded_url = urllib.parse.quote(url, safe="")
    return encoded_url

def _solve_recaptcha(driver: WebDriver) -> tuple[bool, bool]:
    """
    Attempt to solve a Google reCAPTCHA v2 challenge using selenium-recaptcha-solver.

    This function locates the reCAPTCHA iframe on the page and attempts to
    automatically click and solve the checkbox challenge. If the solver fails,
    it inspects the exception message to determine whether Google has detected
    automated traffic.

    Args:
        driver (WebDriver): Selenium WebDriver instance used to interact with the page.

    Returns:
        tuple[bool, bool]:
            - success (bool): True if the CAPTCHA was successfully solved, otherwise False.
            - google_bot_detected (bool): True if Google detected automated traffic,
              otherwise False.
    """
    try:
        print("   [INFO] Attempting to solve reCAPTCHA...")
        solver = RecaptchaSolver(driver=driver)
        
        # The solver will automatically detect and solve the captcha
        recaptcha_iframe = driver.find_element("css selector", "iframe[src*='recaptcha']")
        time.sleep(random.uniform(1, 15))
        solver.click_recaptcha_v2(iframe=recaptcha_iframe)

        # Wait for submission to process
        time.sleep(3)
        print("   [SUCCESS] Successfully solve reCAPTCHA")
        return True, False
        
    except Exception as e:
        msg = str(e).lower()
        print(f"   [WARN] Fail to solve reCAPTCHA: {e}")

        if "automated" in msg or "unusual traffic" in msg:
            print("   [ERROR] Google detected automated traffic.")
            return False, True

        print
        # Other failure (captcha missing, solver crash, layout changed, etc.)
        return False, False

def _trigger_archive_save(article_link: str, USER_AGENTS) ->  tuple[str | None, bool]:
    """
    Submit a URL to archive.ph and wait for a fresh snapshot to be generated.

    This function automates the submission of a given article URL to archive.ph
    using Selenium. It handles CAPTCHA challenges, retries when necessary,
    and waits until the final snapshot URL becomes available.

    Args:
        article_link (str): The original URL of the article to archive, 
            e.g., "https://www.economist.com/science-and-technology/2025/10/08/hover-flies-are-long-distance-travellers"

    Returns:
        tuple[str | None, bool]:
          - The final archive.ph snapshot URL if successful; otherwise, None.
            e.g., "https://archive.ph/4EGba"
          - A boolean flag indicating whether Google bot detection was encountered.

    """
    encoded_url = _encode_url(article_link)
    save_url = f"https://archive.ph/submit/?anyway=1&url={encoded_url}"

    chrome_options = _get_random_chrome_options(USER_AGENTS)
    driver = webdriver.Chrome(options=chrome_options)

    try:
        print()
        print(f"Submitting to archive.ph: {article_link}")
        driver.get(save_url)
        time.sleep(3)

        # --- Phase 1: Handle reCAPTCHA ---
        MAX_CAPTCHA_ATTEMPTS = 2
        CAPTCHA_CHECK_DELAY = 3  # seconds

        google_bot_detected = False

        for attempt in range(1, MAX_CAPTCHA_ATTEMPTS + 1):

            if not _is_captcha_present(driver): 
                time.sleep(CAPTCHA_CHECK_DELAY)
                break

            print(f"   [INFO] Detected CAPTCHA (Attempt {attempt}/{MAX_CAPTCHA_ATTEMPTS})")

            solve_recaptcha, google_bot_detected = _solve_recaptcha(driver)

            print(f"google_bot_detected is {google_bot_detected}")

            if solve_recaptcha:
                break
            else:
                if google_bot_detected:
                    return None, google_bot_detected
                else:
                    driver.execute_script("location.reload()")
                    time.sleep(CAPTCHA_CHECK_DELAY)
                    driver.get(save_url)
        else:
            # Exhausted all attempts
            print(f"   [WARN] Could not bypass captcha after {MAX_CAPTCHA_ATTEMPTS} attempts.")
            return None, google_bot_detected

        # --- Phase 2: Wait for snapshot URL ---
        start_time = time.time()
        MAX_WAIT = 600  # 10 minutes total
        RETRY_INTERVAL = 10  # Check every 10 seconds

        print(f"   [SUCCESS] CAPTCHA bypassed successfully!")
        print()
        print("   [WAIT] Waiting for archive.ph to generate snapshot...")

        while True:
            current_url = driver.current_url
            if re.match(r"^https://archive\.ph/[A-Za-z0-9]{5}$", current_url):
                # to solve a bug where it couldn't find the website
                print(f"   [SUCCESS] Snapshot ready: {current_url}")
                return current_url, google_bot_detected
            
            if not re.match(r"^https://archive\.ph/wip/[A-Za-z0-9]{5}$", current_url):
                return None, google_bot_detected

            elapsed = time.time() - start_time
            if elapsed >= MAX_WAIT:
                print("   [WARN] Archive.ph still processing after 10 minutes — giving up.")
                return None, google_bot_detected

            print(f"   [WAIT] Archiving still in progress... ({int(elapsed)}s elapsed)")
            time.sleep(RETRY_INTERVAL)
            # retry by reloading the page every 45 seconds

    finally:
        driver.quit()

def _is_captcha_present(driver: WebDriver) -> bool:
    """
    Check whether a captcha is present on the current page using simple heuristics.

    The function inspects common captcha indicators such as iframe sources,
    known captcha CSS selectors, and verification-related page text.

    Args:
        driver (WebDriver): Selenium WebDriver instance used to inspect the page.

    Returns:
        bool: True if a captcha-like element is detected, otherwise False.
    """
    try:
        # Check for common iframe-based captchas
        for iframe in driver.find_elements(By.TAG_NAME, "iframe"):
            src = iframe.get_attribute("src") or ""
            # "recaptcha" → Google reCAPTCHA
            # "hcaptcha" → hCaptcha
            # "turnstile" → Cloudflare Turnstile
            if any(x in src for x in ("recaptcha", "hcaptcha", "turnstile")):
                return True

        # Check for common captcha classes or IDs
        if driver.find_elements(By.CSS_SELECTOR, ".g-recaptcha, #g-recaptcha, .h-captcha, .cf-turnstile"):
            return True

        # Simple text-based heuristic
        body_text = driver.find_element(By.TAG_NAME, "body").text.lower()
        if "verify" in body_text and any(x in body_text for x in ("human", "captcha")):
            return True

    except Exception:
        # If an unexpected error occurs, conservatively assume a captcha might be present
        return True

    return False

def _does_archived_link_exist(archived_link: str, USER_AGENTS: list[str], DEFAULT_HEADERS_GOOGLE: dict[str, str], 
                   max_retries: int = 3) -> bool:
    """
    Check whether a given archive.ph snapshot (archived_link) exists.

    This function verifies if the provided `archived_link` exists by sending an HTTP HEAD request.
    If the server returns status code 200, the archived link is considered to exist and the function
    returns True.

    If the server returns a 404 status code, the archived link is considered not to exist and the
    function returns False. For other responses or network errors, the request is retried up to
    `max_retries` times with a random delay between attempts. If all retry attempts fail, the
    function returns False.

    Args:
        archived_link (str): The archive.ph snapshot URL to check, e.g., "https://archive.ph/pNRmC".
        USER_AGENTS (list[str]): A list of User-Agent strings used for header rotation.
        DEFAULT_HEADERS_GOOGLE (dict[str, str]): Default HTTP headers to include in each request.
        max_retries (int, optional): Maximum number of retry attempts for network errors. Defaults to 3.

    Returns:
        bool: True if the archived link exists (status code == 200);
              False if it returns 404 or all retry attempts fail.
    """
    print()
    if not archived_link:
        return False
     
    for attempt in range(max_retries):
        try:
            http_headers = _retrieve_http_headers(USER_AGENTS, DEFAULT_HEADERS_GOOGLE)
            print(f"Attempt {attempt + 1}/{max_retries} to check: {archived_link}")

            response = requests.head(archived_link, headers=http_headers, allow_redirects=True, timeout=10)

            if response.status_code == 404:
                print(f"   [NOT EXIST] {archived_link}")
                return False

            if response.status_code == 200:
                print(f"   [EXIST] {archived_link}")
                return True

        except requests.RequestException as e:
            print(f"   [ERROR] Attempt {attempt + 1}/{max_retries} failed: {e}")
            time.sleep(random.uniform(2, 5))

    print(f"   [FAIL] Failed to verify {archived_link} after {max_retries} retries")
    return False

def _fetch_html(base_dir: str, url: str, USER_AGENTS: list[str], 
               DEFAULT_HEADERS_GOOGLE: dict[str, str], max_retries: int = 10) -> Optional[str]:
    """
    Fetch the HTML content of a URL using two different request methods with retry logic.

    This function attempts to retrieve the raw HTML content of a given URL using
    rotating User-Agent headers and configurable retry logic.

    The request process is divided into two methods:
    - Method 1: Uses a persistent requests.Session for connection reuse.
    - Method 2: Falls back to stateless requests.get calls.

    If the request is successful (status code 200), it returns the raw HTML content
    as a string.

    If the request fails due to rate limiting (429), server errors, or network errors,
    it retries up to `max_retries` times, waiting a random interval between attempts.
    If the page is not yet archived or does not exist (404), it will return None.
    If all attempts fail, it will return None.

    Args:
        base_dir (str): Root directory of the project.
        url (str): The target URL to fetch.
        USER_AGENTS (list[str]): A list of User-Agent strings used for header rotation.
        DEFAULT_HEADERS_GOOGLE (dict[str, str]): Default HTTP headers to include in each request.
        max_retries (int, optional): Maximum number of retry attempts for 403, 429, or 
            network errors. Defaults to 10.

    Returns:
        Optional[str]: The raw HTML content if successful; otherwise None.
    """
    session = requests.Session()

    # int() is a floor function
    retries1 = int(max_retries/2)
    retries2 = max_retries - retries1

    print()

    # this is the first method to sends the HTTP GET request
    for attempt in range(retries1):
        try:
            # for every attempt, retrieve a new random user agent
            http_headers = _retrieve_http_headers(USER_AGENTS, DEFAULT_HEADERS_GOOGLE)

            print(f"Attempt {attempt + 1}/{max_retries} to fetch: {url}")

            # Sends an HTTP GET request to the URL
            resp = session.get(url, headers=http_headers, timeout=15)

            if resp.status_code == 200:
                print(f"   [SUCCESS] Fetched: {url}")
                log_user_agent(http_headers["User-Agent"], "SUCCESS", base_dir, "user_agents_log.csv")
                # resp.text returns the raw HTML as a string
                return resp.text

            # (status code)429: Too Many Requests
            elif (resp.status_code == 429):
                wait_time = int(resp.headers.get("Retry-After", 5))  # use Retry-After header if present
                wait_time = max(wait_time, 3)  # at least 3 seconds
                print(f"   [FAIL] Received status {resp.status_code}. retrying in {wait_time}s...")
                log_user_agent(http_headers["User-Agent"], "FAIL", base_dir, "user_agents_log.csv")

                time.sleep(wait_time)
                continue    

            # If the archived_link is not found (e.g., https://archive.ph/abbbb)
            elif (resp.status_code == 404):
                print(f"   [FAIL] Received status {resp.status_code}.")
                return None

            else: 
                print(f"   [FAIL] Received status {resp.status_code}. retrying in 2-5s...")
                log_user_agent(http_headers["User-Agent"], "FAIL", base_dir, "user_agents_log.csv")
                # wait before next retry
                time.sleep(random.uniform(2, 5)) 
        
        except requests.HTTPError as e:
            print(f"   [FAIL] HTTP error {e.response.status_code}, retrying in 2-5s...")
            log_user_agent(http_headers["User-Agent"], "FAIL", base_dir, "user_agents_log.csv")
            time.sleep(random.uniform(2, 5))

        except requests.RequestException as e:
            print(f"   [FAIL] Network error on attempt {e}, retrying in 2-5s...")
            log_user_agent(http_headers["User-Agent"], "FAIL", base_dir, "user_agents_log.csv")
            time.sleep(random.uniform(2, 5))
    
    # this is the second method to sends the HTTP GET request
    for attempt in range(retries2):
        try:
            # for every attempt, retrieve a new random user agent
            http_headers = _retrieve_http_headers(USER_AGENTS, DEFAULT_HEADERS_GOOGLE)

            print(f"Attempt {attempt + retries1 + 1}/{max_retries} to fetch: {url}")
            resp = requests.get(url, headers=http_headers, timeout=15)

            # raise_for_status() will automatically raise (but not handle) a requests.HTTPError 
            # for any 4xx response and 5xx response
            resp.raise_for_status()

            if resp.status_code == 200:
                print(f"   [SUCCESS] Fetched: {url}")
                log_user_agent(http_headers["User-Agent"], "SUCCESS", base_dir, "user_agents_log.csv")
                return resp.text
            
            print(f"   [FAIL] Received status {resp.status_code}. retrying in 2-5s...")
            log_user_agent(http_headers["User-Agent"], "FAIL", base_dir, "user_agents_log.csv")
            time.sleep(random.uniform(2, 5))

        except requests.HTTPError as e:
            print(f"   [FAIL] HTTP error {e.response.status_code}, retrying in 2-5s...")
            log_user_agent(http_headers["User-Agent"], "FAIL", base_dir, "user_agents_log.csv")
            time.sleep(random.uniform(2, 5))

        except requests.RequestException as e:
            print(f"   [FAIL] Network error on attempt {e}, retrying in 2-5s...")
            log_user_agent(http_headers["User-Agent"], "FAIL", base_dir, "user_agents_log.csv")
            time.sleep(random.uniform(2, 5))

    print(f"   [FAIL] Failed to fetch {url} after {max_retries} retries.")
    return None

def fetch_latest_archived_link(base_dir: str, article_link: str, article_title: str, USER_AGENTS: list[str], 
                           DEFAULT_HEADERS_GOOGLE: dict[str, str]) -> str | None:
    """
    Locate and return the most recent archived snapshot URL (archived_link) of an article on archive.ph.

    This function accesses the archive.ph index page corresponding to the given article link, 
    parses all available hyperlinks, and identifies the latest snapshot that:
    1. Matches the pattern 'https://archive.ph/' followed by 5 alphanumeric characters.
    2. (Optionally) matches the first three words of the article title (case-insensitive).

    If no existing snapshot is found, the function triggers a new archive save and waits until
    the new snapshot (archived_link) becomes available.

    If an existing snapshot is found but is older than a predefined threshold (in days),
    the function triggers a new archive save and waits until the new snapshot (archived_link) becomes available.

    The function will repeatedly retry archive saving if the new archived_link doesn't exist
    on the web. When Google bot detection is encountered, a longer wait interval is used
    before retrying; otherwise, a shorter wait interval is applied.

    Args:
        base_dir (str): Root directory of the project.
        article_link (str): The original URL of the article on *The Economist* website, 
            e.g., "https://www.economist.com/science-and-technology/2025/10/08/hover-flies-are-long-distance-travellers"
        article_title (str): the article title.
            e.g., "Hover flies are long-distance travellers"
        USER_AGENTS (list[str]): A list of User-Agent strings for randomizing HTTP requests.
        DEFAULT_HEADERS_GOOGLE (dict[str, str]): Default HTTP headers for HTTP requests.

    Returns:
        str: The full URL of the matching archived snapshot on archive.ph.
            e.g., "https://archive.ph/4EGba" (archived_link)

    Raises:
        Exception: If no matching snapshot URL is found on the page.
    """

    archive_index_link = f"https://archive.ph/{article_link}"
    print(f"\n🕓 Accessing archive index: {archive_index_link}")

    html = _fetch_html(base_dir, archive_index_link, USER_AGENTS, DEFAULT_HEADERS_GOOGLE, max_retries=10)

    while not html:
        print("   [INFO] Waiting for 8 minutes to retry...")
        time.sleep(480)
        html = _fetch_html(base_dir, archive_index_link, USER_AGENTS, DEFAULT_HEADERS_GOOGLE, max_retries=10)

    soup = BeautifulSoup(html, "html.parser")
    
    # if article_title has fewer than 3 words, match_words takes all words
    match_words = article_title.lower().split()[:3]

    # Regex: matches https://archive.ph/ + 5 letters (case-insensitive)
    pattern = re.compile(r"^https://archive\.ph/[A-Za-z0-9]{5}$")

    latest_date = None
    # # the last_match_url is the latest archive.ph link that matches the given article title
    last_match_url = None  

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()

        if not pattern.match(href):
            continue
        
        if pattern.match(href):
            date_div = a.find("div")
        
        if date_div is None:
            continue  # skip if no date found

        date_str = date_div.get_text(strip=True)
        date_text = " ".join(date_str.split()[:3])  # keep only "DD MMM YYYY"

        # update last_match_url and latest_date
        last_match_url = href
        latest_date = date_text

    if not last_match_url:
        print("   [INFO] No existing snapshot found, triggering archive save...")
        archived_link, google_bot_detected = _trigger_archive_save(article_link, USER_AGENTS)

        # Wait in a loop until the archived snapshot becomes available
        # Potential issue: infinite loop if archive.ph fails to save the page
        while not _does_archived_link_exist(archived_link, USER_AGENTS, DEFAULT_HEADERS_GOOGLE, 3):
            if google_bot_detected:
                print("   [INFO] Waiting for 40 minutes to trigger archive save again...")
                time.sleep(2400)
                archived_link, google_bot_detected = _trigger_archive_save(article_link, USER_AGENTS)
            else:
                print("   [INFO] Waiting for 5 minutes to trigger archive save again...")
                time.sleep(300)
                archived_link, google_bot_detected = _trigger_archive_save(article_link, USER_AGENTS)
        return archived_link

    if last_match_url:
        snapshot_date = datetime.strptime(latest_date, "%d %b %Y")

        THRESHOLD_DAYS = 30

        if datetime.now() - snapshot_date > timedelta(days=THRESHOLD_DAYS):
            print(f"   [INFO] Snapshot is older than {THRESHOLD_DAYS} days, triggering archive save...")
            # Trigger a new save on archive.ph
            archived_link, google_bot_detected = _trigger_archive_save(article_link, USER_AGENTS)

            # Wait in a loop until the new archived snapshot becomes available
            # Potential issue: infinite loop if archive.ph fails to save the page
            while not _does_archived_link_exist(archived_link, USER_AGENTS, DEFAULT_HEADERS_GOOGLE, 3):
                if google_bot_detected:
                    print("   [INFO] Waiting for 40 minutes to trigger archive save again...")
                    time.sleep(2400)
                    archived_link, google_bot_detected = _trigger_archive_save(article_link, USER_AGENTS)
                else:
                    print("   [INFO] Waiting for 5 minutes to trigger archive save again...")
                    time.sleep(300)
                    archived_link, google_bot_detected = _trigger_archive_save(article_link, USER_AGENTS)
            return archived_link

        else: 
            print(f"\n[SUCCESS] Found snapshot: {last_match_url}")
            return last_match_url
        
    raise Exception(f"❌ No matching snapshot found for link: {article_link}")

def fetch_article_html(base_dir: str, archived_link: str, USER_AGENTS: list[str], DEFAULT_HEADERS_GOOGLE: dict[str, str]) -> str:
    """
    Fetch and return the HTML content of the article.

    Args:
        base_dir (str): Root directory of the project.
        archived_link (str): The archived snapshot of the article hosted on archive.ph.
        USER_AGENTS (list[str]): List of User-Agent strings to rotate for requests.
        DEFAULT_HEADERS_GOOGLE (dict[str, str]): Default HTTP headers to use if needed.

    Returns:
        str: HTML content of the article as a string.
    """
    # the article_url is generated from fetch_archive_snapshot()
    # therefore it is guaranteed that it exist

    article_html = _fetch_html(base_dir, archived_link, USER_AGENTS, DEFAULT_HEADERS_GOOGLE, max_retries=10)

    while not article_html:
        print("   [INFO] Waiting for 8 minutes to retry...")
        time.sleep(480)
        article_html = _fetch_html(base_dir, archived_link, USER_AGENTS, DEFAULT_HEADERS_GOOGLE, max_retries=10)

    return article_html

def extract_article_html_section(
    article_html: str,
    start_markers: List[str],
    end_markers: List[str]
) -> tuple[str, str | None]:
    """
    Extract a subsection of an article's HTML based on the earliest matched
    start and end markers.

    This function identifies the earliest occurrence of any start marker in
    `start_markers` and any end marker in `end_markers`, and extracts the
    corresponding HTML section. The returned section **includes the exact_start_marker** 
    but **excludes the exact_end_marker**.

    Behavior:
        Case 1: Both start and end markers are found.
            - Returns HTML from the earliest start marker to immediately
              before the earliest end marker.
        Case 2: Start marker not found, end marker found.
            - Returns HTML from the start of the original HTML to immediately
              before the earliest end marker.
        Case 3: Start marker found, end marker not found.
            - Returns HTML from the earliest start marker to the end of the
              original HTML.
        Case 4: Neither start nor end marker found.
            - Returns the full original HTML.
    
    By the way, it should be always case 1.

    Args:
        article_html (str): Full HTML content of the article.
        start_markers (List[str]): A list of possible start markers indicating
            where extraction should begin.
        end_markers (List[str]): A list of possible end markers indicating
            where extraction should end.

    Returns:
        tuple[str, str | None]: A tuple consisting of:
            - Extracted HTML section according to the matched markers and the
              four cases described above.
            - The exact start marker that was matched, or "None" if no
              start marker was found.
            - The exact end marker that was matched, or "None" if no
              end marker was found.
    """
    
    def _extract_start_article_html_section(
        article_html: str,
        start_markers: List[str],
    ) -> Tuple[str, str | None]:
        """
        Extract a subsection of an article's HTML starting from the earliest matching
        start marker (inclusive).

        This function searches the provided HTML content for all markers in
        `start_markers` and identifies the earliest occurrence. If no markers are
        found, the full HTML is returned.

        Args:
            article_html (str): Full HTML content of the article.
            start_markers (List[str]): A list of possible start markers indicating
                where extraction should begin.

        Returns:
            Tuple[str, str | None]: A tuple consisting of:
                - The extracted HTML substring beginning from the earliest matched
                start marker, or the full HTML if none are found.
                - The matched start marker as a string, or "None" if no marker
                was found.
        """
        # Record (only) the first occurrence index of each start_marker found in the article_html
        # .find() will only return the first occurrence of that marker
        # if .find() returns -1, that means it didn't found that marker in the article_html
        start_positions = {
            marker: article_html.find(marker)
            for marker in start_markers
            if article_html.find(marker) != -1
        }

        # CASE 1 — none of the start markers were found
        # will return the full article_html
        if not start_positions:
            print("[WARNING] None of the start markers were found.")
            return article_html, None

        # CASE 2 — at least one marker found 
        # pick the earliest match among all start_markers
        exact_start_marker, start_idx = min(start_positions.items(), key=lambda x: x[1])

        print()
        print(f"[SUCCESS] Found start marker: '{exact_start_marker}'")

        # Return HTML from the start marker (it is inclusive) all the way to the end
        start_article_html_section = article_html[start_idx:]

        return start_article_html_section, exact_start_marker

    def _extract_end_article_html_section(
        article_html: str,
        end_markers: List[str]
    ) -> Tuple[str, str | None]:
        """
        Extract a subsection of an article's HTML ending immediately before the
        earliest matching end marker (exclusive).

        This function searches the provided HTML content for all markers in
        `end_markers` and identifies the earliest occurrence. If no markers are
        found, the full HTML is returned.

        Args:
            article_html (str): the HTML content of the article.
            end_markers (List[str]): A list of possible end markers indicating
                where extraction should end.

        Returns:
            Tuple[str, str | None]: A tuple consisting of:
                - The extracted HTML substring up to the earliest matched end
                marker, or the full HTML if none are found.
                - The matched end marker as a string, or "None" if no marker
                was found.
        """
        # Record (only) the first occurrence index of each end_marker found in the article_html
        # .find() will only return the first occurrence of that marker
        # if .find() returns -1, that means it didn't found that marker in the article_html
        end_positions = {
            marker: article_html.find(marker)
            for marker in end_markers
            if article_html.find(marker) != -1
        }

        # CASE 1 — none of the end markers were found
        # will return the full article_html
        if not end_positions:
            print("[WARNING] None of the end markers were found.")
            return article_html, None

        # CASE 2 — at least one marker found 
        # pick the earliest match among all end_markers
        exact_end_marker, end_idx = min(end_positions.items(), key=lambda x: x[1])

        print(f"[SUCCESS] Found end marker: '{exact_end_marker}'")

        # Return HTML from the beginning up to (but not including) the end marker
        end_article_html_section = article_html[:end_idx]

        return end_article_html_section, exact_end_marker

    start_article_html_section, exact_start_marker = _extract_start_article_html_section(article_html, start_markers)

    end_article_html_section, exact_end_marker = _extract_end_article_html_section(start_article_html_section, end_markers)

    article_html_section = end_article_html_section

    # Dynamic print message based on which markers were found
    if exact_start_marker and exact_end_marker:
        print(f"\n[SUCCESS] Extracted HTML section from '{exact_start_marker}' to '{exact_end_marker}'.")
    elif not exact_start_marker and exact_end_marker:
        print(f"\n[SUCCESS] Extracted HTML section from start of HTML to '{exact_end_marker}'.")
    elif exact_start_marker and not exact_end_marker:
        print(f"\n[SUCCESS] Extracted HTML section from '{exact_start_marker}' to end of HTML.")
    else:  # Neither marker found
        print("\n[SUCCESS] Extracted full HTML (no start or end markers found).")

    print()
    return article_html_section, exact_start_marker, exact_end_marker

def find_article_subtitle(exact_start_marker: str | None, 
                           article_html_section: str) -> str | None:
    """
    Identify and extract the subtitle_text that immediately follows `exact_start_marker`
    within a `article_html_section`.

    The subtitle, when present, is always contained in the next `<h2>...</h2>` tag
    that appears directly after the `exact_start_marker`. If the content
    following the marker does not begin with an `<h2` opening tag, the article has
    no subtitle and the function returns `None`.

    # e.g., <h2 style="...">Financial centres brace themselves, hypothetically</h2>
    # The extracted subtitle will be "Financial centres brace themselves, hypothetically".

    Args:
        exact_start_marker (str | None): The exact start marker detected earlier. 
            (see `_extract_start_article_html_section` for more context)

        article_html_section (str): Extracted HTML section
            (see `extract_article_html_section` for more context).

    Returns:
        str | None: The cleaned subtitle text found inside `<h2>...</h2>`, or `None`
        if `exact_start_marker` is `None` or if the content immediately following
        the start marker does not begin with an `<h2>` block (i.e. the article has
        no subtitle) or the subtitle_text is an empty str.
    """
    if not exact_start_marker:
        print("[INFO] No subtitle found since there is no start marker found.")
        return None
    
    # article_html_section must start with exact_start_marker
    search_start_idx = len(exact_start_marker)

    # the subtitle will appear right after the title, however
    # the article could have no subtitle
    # therefore, we will determine whether the article has subtitle
    # by finding the next tag right after exact_start_marker is <h2> or not
    # if yes, then extract the subtitle_text
    # if no, then return None
    # eg. [article_title]</h1><h2

    # the reason why we use lstrip() is to ignore any leading spaces or line breaks 
    # in between exact_start_marker and <h2
    # l from lstrip() stands for left!
    segment = article_html_section[search_start_idx:].lstrip()
    if not segment.startswith("<h2"):
        print("[INFO] No subtitle found.")
        return None
    
    # find the index of the nearest closing </h2> tag
    # subtitle_close_idx points to the character right before the < of </h2>
    subtitle_end_idx = segment.find("</h2>", search_start_idx)

    # Extract the subtitle_text in between <h2> and </h2>.
    subtitle_start_idx = segment.rfind("<h2", search_start_idx, subtitle_end_idx) + 1
    soup = BeautifulSoup(segment[subtitle_start_idx : subtitle_end_idx], "html.parser")

    # .strip() removes extra spaces or line breaks.
    # good-to-have
    subtitle_text = soup.get_text(strip=True)

    if subtitle_text:
        print(f"[SUCCESS] Found subtitle: '{subtitle_text}'")
        return subtitle_text
    else: 
        print("[INFO] No subtitle found.")
        return None

def update_article_metadata_json(exact_start_marker: str, exact_end_marker: str, 
                                 article_subtitle: str, file_path: str, article_link: str) -> None:
    """
    store all the metadata into the article JSON file
    """
    if not exact_start_marker:
        unusual_start_marker = True
    else: 
        unusual_start_marker = False
    
    if exact_end_marker != "■":
        unusual_end_marker = True
    else:
        unusual_end_marker = False

    with open(file_path, "r", encoding="utf-8") as f:
        articles = json.load(f)

    article = articles[0]

    article_section = article.get("section", "").lower()

    if "indicators" in article_section or "letters" in article_section:
        is_indicators_or_letters = True
    else: 
        is_indicators_or_letters = False

    new_fields = {
    "article_subtitle": article_subtitle,
    "exact_start_marker": exact_start_marker,
    "exact_end_marker": exact_end_marker,
    "manual_review_signals": {
        "unusual_start_marker": unusual_start_marker,
        "unusual_end_marker": unusual_end_marker,
        "is_indicators_or_letters": is_indicators_or_letters,
    }
    }

    article.update(new_fields)

    # safer write (atomic replace)
    tmp_path = file_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=4)

    os.replace(tmp_path, file_path)

    print(f"\n[SUCCESS] Successfully updated partial metadata in {file_path}")

    return None

def main(USER_AGENTS: List[str], DEFAULT_HEADERS_GOOGLE: dict[str, str],
         base_dir: str, article_link: str, article_title: str, file_path: str) -> None:
    """
    Main function to scrape article HTML and article subtitle.

    Args:
        USER_AGENTS (List[str]): List of User-Agent strings for HTTP requests.
        DEFAULT_HEADERS_GOOGLE (dict[str, str]): Default HTTP headers for requests to Google.
        base_dir (str): Root directory of the project.
        article_link (str): The original URL of the article on *The Economist* website, 
            e.g., "https://www.economist.com/science-and-technology/2025/10/08/hover-flies-are-long-distance-travellers"
        article_title (str): The title of the article.
            e.g., "Hover flies are long-distance travellers"
    
    Returns:
        None
    """

    archived_link = fetch_latest_archived_link(base_dir, article_link, article_title, USER_AGENTS, DEFAULT_HEADERS_GOOGLE)

    article_html = fetch_article_html(base_dir, archived_link, USER_AGENTS, DEFAULT_HEADERS_GOOGLE)

    start_marker1 = f"{article_title}</h1>"
    start_marker2 = f"{article_title} </h1>"
    start_marker3 = f"{article_title}  </h1>"

    end_marker1 = "■"
    end_marker2 = "This article appeared in"
    end_marker3 = "Reuse this content"
    end_marker4 = "Explore more</h3>"
    
    start_markers = [start_marker1, start_marker2, start_marker3]
    end_markers = [end_marker1, end_marker2, end_marker3, end_marker4]

    article_html_section, exact_start_marker, exact_end_marker = extract_article_html_section(article_html, start_markers, end_markers)
    
    article_subtitle = find_article_subtitle(exact_start_marker, article_html_section)

    update_article_metadata_json(exact_start_marker, exact_end_marker, article_subtitle,file_path, article_link)

    return article_html_section
