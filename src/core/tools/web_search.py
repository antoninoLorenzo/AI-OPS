import random
from functools import lru_cache
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

from newspaper import Article, ArticleException
from googlesearch import search as google_search
from requests import HTTPError

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
        if not links:
            logger.error(f'no links found for {search_query}')
            return ''
        
        links = [link for link in links if not self.__exclude(link)]
        results = []
        if len(links) == 1:
            title, content, _ = self.__parse(links[0])
            if len(content) == 0:
                return ''
            results = [f"# {title} ({links[0]})\n{content}"]
        elif len(links) > 1:
            with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
                futures = [
                    executor.submit(self.__parse, link)
                    for link in links
                ]

                for future in as_completed(futures):
                    title, content, link = future.result()
                    if title and content:
                        results.append(f"# {title} ({link})\n{content}")
        else:
            logger.warning('all links were excluded from search')
            return ''
        
        # TODO: for now just return back a single result to limit context length.
        return results[0]

    def __google_search(
        self,
        search_query,
        num_results=3
    ) -> list:
        """
        Conducts a Google search and retrieves links from the result page.

        :param search_query: Query string for Google search.
        :param results: Number of links to retrieve. Default is 3.

        :returns: a list of links."""
        try:
            return list(
                google_search(
                    search_query,
                    num_results=num_results,
                    unique=True,
                    region="us",
                    lang="en"
                )
            )
        except HTTPError as err:
            logger.error(f'googlesearch raised {err.response.status_code}: {err}')
            return []

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

        exclude = domain in self.__exclusions
        if exclude:
            logger.info(f'found blacklisted link: {link}')
        return exclude

    @lru_cache(maxsize=64)  # the number is "random"
    def __parse(self, link: str) -> tuple:
        """Downloads a web page and parses it with `newspaper3k` library.

        :returns: tuple(title: str, content: str, tags: list, link: str)"""
        page = Article(
            link,
            headers=self.headers,
            fetch_images=False
        )
        try:
            page.download()
            page.parse()
        except (ArticleException, Exception):
            return '', '', ''
        return page.title, page.text, link

    @staticmethod
    def __user_agent() -> str:
        """:returns: user_agent: str"""
        available = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:102.0) Gecko/20100101 Firefox/102.0',
            'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/116.0',
            # yeah, fuck apple
        )
        return available[random.randint(0, len(available) - 1)]
