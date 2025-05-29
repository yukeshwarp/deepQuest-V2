import requests
import os
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from newsapi import NewsApiClient
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import aiohttp
import asyncio
import logging
from crawl4ai import AsyncWebCrawler
import time

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# Load environment variables from .env
load_dotenv()

# API keys and headers
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
SEARCH_ENGINE_ID = os.getenv("SEARCH_ENGINE_ID")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")

HEADERS = {
    "User-Agent": "MyApp/1.0 (contact@example.com)"  # Customize this with your contact
}

# --- Retry Decorator ---
def retry_on_exception(max_retries=2, backoff=2):
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    logging.warning(f"Attempt {attempt+1} failed for {func.__name__}: {e}")
                    if attempt < max_retries:
                        time.sleep(backoff)
            logging.error(f"All retries failed for {func.__name__}: {last_exception}")
            raise last_exception
        return wrapper
    return decorator

# --- Asynchronous Retry Helper ---
async def async_retry_on_exception(func, *args, max_retries=2, backoff=2, **kwargs):
    last_exception = None
    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            logging.warning(f"Async attempt {attempt+1} failed for {func.__name__}: {e}")
            if attempt < max_retries:
                await asyncio.sleep(backoff)
    logging.error(f"All async retries failed for {func.__name__}: {last_exception}")
    raise last_exception

# --- Asynchronous Utilities ---

async def fetch_url(session, url, timeout=10):
    """Fetch the URL asynchronously and return the page content."""
    try:
        async with session.get(url, timeout=timeout) as response:
            if response.status == 200:
                return await response.text()
            else:
                logging.warning(f"Non-200 response for {url}: {response.status}")
                return None
    except asyncio.TimeoutError:
        logging.error(f"Timeout fetching {url}")
        return None
    except Exception as e:
        logging.error(f"Error fetching {url}: {e}")
        return None

async def crawl_websites(urls, timeout=10):
    """Crawl the top relevant websites asynchronously."""
    crawled_results = []
    try:
        async with aiohttp.ClientSession() as session:
            tasks = [async_retry_on_exception(fetch_url, session, url, timeout=timeout) for url in urls]
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            for idx, content in enumerate(responses):
                if isinstance(content, Exception):
                    logging.error(f"Exception during crawling {urls[idx]}: {content}")
                    crawled_results.append(f"[Crawled Website {idx + 1}] Error fetching content: {content}")
                elif content:
                    soup = BeautifulSoup(content, 'html.parser')
                    title = soup.title.string if soup.title else 'No title found'
                    description = soup.find('meta', attrs={'name': 'description'})
                    description = description['content'] if description else 'No description found'
                    crawled_results.append(f"[Crawled Website {idx + 1}] {title}\nDescription: {description}")
                else:
                    crawled_results.append(f"[Crawled Website {idx + 1}] Error fetching content")
    except Exception as e:
        logging.error(f"Error in crawl_websites: {e}")
    return crawled_results

async def crawl_with_async_webcrawler(urls, timeout=20):
    """Use AsyncWebCrawler to crawl through URLs and return markdown content."""
    crawl_results = []
    try:
        async with AsyncWebCrawler() as crawler:
            for url in urls:
                try:
                    result = await asyncio.wait_for(
                        async_retry_on_exception(crawler.arun, url=url, max_retries=2, backoff=2),
                        timeout=timeout
                    )
                    crawl_results.append(f"[Crawled Website (Markdown)] URL: {url}\n{result.markdown}\n")
                except asyncio.TimeoutError:
                    logging.error(f"Timeout crawling {url} with AsyncWebCrawler")
                    crawl_results.append(f"[Crawling Error] URL: {url} Error: Timeout")
                except Exception as e:
                    logging.error(f"Error crawling {url} with AsyncWebCrawler: {e}")
                    crawl_results.append(f"[Crawling Error] URL: {url} Error: {str(e)}")
    except Exception as e:
        logging.error(f"Error initializing AsyncWebCrawler: {e}")
    return crawl_results

# --- Synchronous Main Search Function ---

@retry_on_exception(max_retries=2, backoff=2)
def google_search_api_call(google_search_url, google_params):
    response = requests.get(google_search_url, params=google_params, timeout=15)
    response.raise_for_status()
    return response

@retry_on_exception(max_retries=2, backoff=2)
def arxiv_api_call(arxiv_url):
    req = urllib.request.Request(arxiv_url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as response:
        return response.read().decode("utf-8")

@retry_on_exception(max_retries=2, backoff=2)
def sec_api_call(sec_url):
    return requests.get(sec_url, headers=HEADERS, timeout=15)

@retry_on_exception(max_retries=2, backoff=2)
def wikipedia_api_call(wikipedia_url, wiki_params):
    return requests.get(wikipedia_url, params=wiki_params, timeout=10)

@retry_on_exception(max_retries=2, backoff=2)
def newsapi_call(newsapi, query):
    return newsapi.get_everything(q=query, language='en', sort_by='relevancy', page_size=5)

def search_google(query):
    try:
        formatted_results = []
        crawled_data = []
        logging.info(f"Query: {query}")

        # --- Google Custom Search ---
        google_search_url = "https://www.googleapis.com/customsearch/v1"
        google_params = {
            "key": GOOGLE_API_KEY,
            "cx": SEARCH_ENGINE_ID,
            "q": query,
            "num": 5,
        }
        try:
            response = google_search_api_call(google_search_url, google_params)
            data = response.json()
            google_urls = []
            for i, item in enumerate(data.get("items", [])):
                formatted_results.append(
                    f"[Google Result {i + 1}] {item['title']} - {item['displayLink']}\n{item['snippet']}"
                )
                google_urls.append(item['link'])
        except Exception as e:
            logging.error(f"Google Search Error: {e}")
            formatted_results.append(f"Google Search Error: {str(e)}")
            google_urls = []

        # --- Crawl the top 3 websites (asynchronously) using AsyncWebCrawler ---
        if google_urls:
            try:
                crawled_data = asyncio.run(crawl_with_async_webcrawler(google_urls[:3]))
                logging.info(f"Crawled URLs: {google_urls[:3]}")
            except Exception as e:
                logging.error(f"Error running async crawler: {e}")
                crawled_data.append(f"Async Crawler Error: {str(e)}")

        # --- ArXiv Search ---
        try:
            encoded_query = urllib.parse.quote(query)
            arxiv_url = f"http://export.arxiv.org/api/query?search_query=all:{encoded_query}&start=0&max_results=3"
            xml_data = arxiv_api_call(arxiv_url)
            root = ET.fromstring(xml_data)
            ns = {'arxiv': 'http://www.w3.org/2005/Atom'}
            entries = root.findall('arxiv:entry', ns)
            for i, entry in enumerate(entries):
                title = entry.find('arxiv:title', ns)
                summary = entry.find('arxiv:summary', ns)
                title_text = title.text.strip() if title is not None else "No title"
                summary_text = summary.text.strip()[:300] + "..." if summary is not None else "No summary"
                formatted_results.append(f"[ArXiv Result {i + 1}] {title_text}\nSummary: {summary_text}")
        except Exception as e:
            logging.error(f"ArXiv Search Error: {e}")
            formatted_results.append(f"ArXiv Search Error: {str(e)}")

        # --- NewsAPI Search ---
        try:
            newsapi = NewsApiClient(api_key=NEWSAPI_KEY)
            articles = newsapi_call(newsapi, query)
            for i, article in enumerate(articles.get("articles", [])):
                formatted_results.append(
                    f"[News {i + 1}] {article['title']} ({article['source']['name']})\n{article['description']}\nURL: {article['url']}"
                )
        except Exception as e:
            logging.error(f"NewsAPI Error: {e}")
            formatted_results.append(f"NewsAPI Error: {str(e)}")

        # --- SEC API (General Data Search) ---
        try:
            sec_url = f"https://www.sec.gov/cgi-bin/browse-edgar?company={urllib.parse.quote(query)}&action=getcompany"
            sec_response = sec_api_call(sec_url)
            if sec_response.status_code == 200:
                if "No matching companies" in sec_response.text:
                    formatted_results.append(f"SEC API: No filings found for '{query}'.")
                else:
                    formatted_results.append(f"SEC API: Filings and data retrieved for {query}. Check SEC's website for details.")
            else:
                formatted_results.append(f"SEC API Error: {sec_response.status_code} - Unable to retrieve data from SEC.")
        except Exception as e:
            logging.error(f"SEC API Error: {e}")
            formatted_results.append(f"SEC API Error: {str(e)}")

        # --- Wikipedia Extract ---
        try:
            wikipedia_url = "https://en.wikipedia.org/w/api.php"
            wiki_params = {
                "action": "query",
                "prop": "extracts",
                "titles": query,
                "format": "json",
                "exintro": True,
                "explaintext": True
            }
            wiki_response = wikipedia_api_call(wikipedia_url, wiki_params)
            if wiki_response.status_code == 200:
                wiki_data = wiki_response.json()
                pages = wiki_data.get("query", {}).get("pages", {})
                for _, page in pages.items():
                    extract = page.get("extract")
                    if extract:
                        formatted_results.append(f"[Wikipedia]\n{extract}")
            else:
                formatted_results.append(f"Wikipedia Error: {wiki_response.status_code}")
        except Exception as e:
            logging.error(f"Wikipedia Error: {e}")
            formatted_results.append(f"Wikipedia Error: {str(e)}")

        # --- Ensure crawled results are included in output ---
        all_results = formatted_results + crawled_data
        # Remove empty entries
        all_results = [r for r in all_results if r and r.strip()]
        return "\n\n".join(all_results)

    except Exception as e:
        logging.critical(f"Unexpected error occurred: {e}")
        return f"Unexpected error occurred: {str(e)}"