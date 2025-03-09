import functools

from src.core.tools.web_search import Search

from newspaper import ArticleException
from requests import HTTPError, Response
from pytest import mark


class MockArticle:
    def __init__(self, link, headers, **kwargs):
        self.link = link
        self.headers = headers
        self.title = ''
        self.text = ''

    def download(self):
        # use link parameter to test failure (empty link is appropriate)
        if self.link == '':
            raise ArticleException()

    def parse(self):
        self.title = f'parsed {self.link}'
        self.text = f'content for {self.link}'
        

def mock_search(search_query: str, num_results: int, mock_links = [], **kwargs):
    if search_query == '':
        err = Response()
        err.status_code = 404
        raise HTTPError(response=err)
    return mock_links


@mark.parametrize('parameters', [
    {
        'name': 'empty_query',
        'search_query': '',
        'mock_links': [''],
        # search returns an empty string on failure
        'expected': 0  # expected empty string   
    },
    {
        'name': 'no_links_found',
        'search_query': 'some query',
        'mock_links': [''],
        'expected': 0      
    },
    {
        'name': 'exclusions_found',
        'search_query': 'some query',
        'mock_links': ['https://github.com/antoninoLorenzo/AI-OPS', 'youtube.com/some_shi'],
        'expected': 1  # expected some content
    }
])
def test_search_unit(
    monkeypatch,
    parameters
):
    monkeypatch.setattr(
        'src.core.tools.web_search.google_search',
        functools.partial(mock_search, mock_links=parameters['mock_links'])
    )

    monkeypatch.setattr(
        'src.core.tools.web_search.Article',
        MockArticle
    )

    web_search = Search()
    result = web_search.run(parameters['search_query'])
    assert (len(result) > 0) == parameters['expected']


@mark.parametrize('parameters', [
    {
        'name': 'empty_query',
        'search_query': '',
        'expected': 0  
    },
    {
        'name': 'search1',
        'search_query': 'Blind SQLi',
        'expected': 1
    },
    {
        'name': 'search2',
        'search_query': 'Jenkins 2.263 vulnerabilities RCE',
        'expected': 1
    },
    {
        'name': 'search3',
        'search_query': 'php file upload',
        'expected': 1
    },
    {
        'name': 'search4',
        'search_query': 'CVE-2024-2201',
        'expected': 1
    }
])
def test_search_full(parameters):
    web_search = Search()
    result = web_search.run(parameters['search_query'])
    assert (len(result) > 0) == parameters['expected']
