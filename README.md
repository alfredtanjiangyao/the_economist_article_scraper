# THE ECONOMIST Article Scraper

<p align="left">
  <img src="assets/the_economist_logo.png" alt="The Economist Logo" width="200">
</p>

We develop a tool to scrape articles from *The Economist* for personal use, including text and images, without a subscription.

## Installation and Running

1. Retrieve the code from github:

    ```sh
    $ git clone https://github.com/alfredtanjiangyao/the_economist_article_scraper.git
    ```

2. Setup and activate a virtual environment:

    ```sh
    $ brew install python@3.11
    $ python3.11 src/setup_environment.py
    $ source .venv1/bin/activate
    ```

3. Run the scraper

   You can scrape any article from The Economist by updating the `article_link` and `article_title` variables in `main.py`.

   Then run:
   ```sh
   $ python3 src/main.py
   ```
   
   All outputs will be saved in `data/{article_title}`.

   [Watch Demo Video](assets/scrape_article_demo.mp4)

## Directory Structure

The project directory structure is documented in `directory_tree.txt`.  

To generate or update the directory tree, run:

```sh
$ python3 src/generate_directory_tree.py
```

## Dashboard

The scraper uses a list of user agents defined in `config.yaml` to avoid server blocks. Each request selects a random user agent, making it appear as if the requests come from different browsers or devices. This helps reduce the chance of being detected or blocked by the server. 

We also provide a Streamlit dashboard to monitor the success rate of each use agent. 

![Dashboard Showcase GIF](assets/dashboard_showcase.gif)

To launch the dashboard:

```sh
$ streamlit run dashboard/streamlit_app.py
```

[Watch Demo Video](assets/launch_dashboard_demo.mp4)

If you notice that certain user agents have a low success rate, you can **comment them out in `config.yaml`**. The scraper will skip any commented user agents during user agent rotation.

## Credit
- Streamlit config.toml - https://github.com/streamlit/demo-stockpeers/blob/main/.streamlit/config.toml