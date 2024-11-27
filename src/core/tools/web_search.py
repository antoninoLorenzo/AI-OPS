"""
# TODO: add multiple search engine support
# TODO: improve web search with filters and stuff
"""
import random
from functools import lru_cache
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import newspaper
from bs4 import BeautifulSoup
from tool_parse import ToolRegistry

from src.utils import get_logger

logger = get_logger(__name__)


class Search:
    """Class to perform an online search."""

    usage: str = "Make an online search using a query string."

    def __init__(
            self,
            headers: dict = None,
            max_results: int = 3,
            num_threads: int = 3
    ):
        """
        :param headers: HTTP headers to use for requests. Defaults to a basic
            set of headers with a random User-Agent.
        :param max_results: maximum number of search results to process.
            Default is 3.
        :param num_threads: number of threads to use for concurrent fetching.
            Default is 3.
        """
        self.max_results = max_results
        self.num_threads = num_threads

        if headers:
            self.headers: dict = headers
        else:
            self.headers: dict = {
                'User-Agent': self.__user_agent(),
                'Accept': 'text/html',
                'Accept-Language': 'en-US',
                'Connection': 'keep-alive',
                'Referer': 'https://www.google.com',
                'Upgrade-Insecure-Requests': '1',
                'DNT': '1'
            }

        self.__exclusions = [
            'youtube.com',
            'github.com'
        ]

    def run(self, search_query: str) -> str:
        """Method exposed to the LLM to perform a web search.

        :param search_query: Query string to search.
        :return: Parsed content of the search results as a formatted string.
        """
        links = self.__google_search(search_query)

        results = []
        if not links:
            logger.error('No links found')
            return ''

        if len(links) == 1:
            title, content, _ = self.__parse(links[0])
            results = [f"# {title}\n{content}"]
        else:
            with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
                futures = [
                    executor.submit(self.__parse, link)
                    for link in links
                ]

                for future in as_completed(futures):
                    title, content, _ = future.result()
                    if title and content:
                        results.append(f"> Page: {title}\n{content}")

        return '\n\n'.join(results)

    def __google_search(
            self,
            search_query,
            results=3,
            timeout: int = 3
    ) -> list:
        """
        Conducts a Google search and retrieves links from the result page.

        :param search_query: Query string for Google search.
        :param results: Number of links to retrieve. Default is 3.
        :param timeout: Request timeout in seconds. Default is 3 seconds.

        :returns: a list of links."""
        try:
            response = requests.get(
                url="https://www.google.com/search",
                headers=self.headers,
                params={
                    "q": search_query,
                    "num": results,
                    "start": 0,
                    "safe": "active",
                    "hl": "en"
                },
                timeout=timeout,
            )
            response.raise_for_status()
        except requests.HTTPError as req_err:
            print(f'[!] Error: {req_err}')
            return []

        # Parse
        links = set()
        soup = BeautifulSoup(response.text, "html.parser")
        result_blocks = soup.find_all("div", attrs={"class": "g"})
        for block in result_blocks:
            link = block.find("a", href=True)
            if link and not self.__exclude(link['href']):
                links.add(link["href"])
        return list(links)

    def __exclude(self, link: str):
        """Check if a link is blacklisted.

        *Note: a link is blacklisted for parsing issues.*

        :returns: True if link is blacklisted"""
        # check if link is blacklisted
        parsed = urlparse(link)
        domain = '{uri.scheme}://{uri.netloc}/'.format(uri=parsed)

        if domain.startswith('https://www.'):
            domain = domain[len('https://www.'):]
        if domain.endswith('/'):
            domain = domain.replace('/', '')

        return domain in self.__exclusions

    @lru_cache(maxsize=64)  # the number is "random"
    def __parse(self, link: str) -> tuple:
        """Downloads a web page and parses it with `newspaper3k` library.

        :returns: tuple(title: str, content: str, tags: list)"""
        page = newspaper.Article(
            link,
            headers=self.headers,
            fetch_images=False
        )
        try:
            page.download()
            page.parse()
        except newspaper.ArticleException:
            return '', '', []
        return page.title, page.text, page.tags

    @staticmethod
    def __user_agent() -> str:
        """:returns: user_agent: str"""
        available = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:102.0) Gecko/20100101 Firefox/102.0',
            'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/116.0',
            # yeah, fuck apple
        )
        return available[random.randint(0, len(available) - 1)]

