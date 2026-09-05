from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from typing import List

BASE_URL = "https://malawinnica.pl"
LISTING_URL = BASE_URL + "/c/wina"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/119.0.0.0 Safari/537.36"
    )
}


def _get_soup(session: requests.Session, url: str) -> BeautifulSoup:
    r = session.get(url, timeout=20)
    r.raise_for_status()
    return BeautifulSoup(r.content, "lxml")


def _get_last_page(session: requests.Session) -> int:
    soup = _get_soup(session, LISTING_URL)

    pagination = soup.select_one("div.pagination")

    if not pagination:
        return 1

    page_links = pagination.select("a[href*='page=']")

    if not page_links:
        return 1

    last_page_link = page_links[-1]

    return int(
        last_page_link["href"]
        .split("page=")[-1]
        .split("&")[0]
    )

def fetch_malawinnica_product_links() -> List[str]:
    with requests.Session() as session:
        session.headers.update(HEADERS)

        last_page = _get_last_page(session)
        product_links: List[str] = []

        for page in range(1, last_page + 1):
            r = session.get(
                LISTING_URL,
                params={"page": page},
                timeout=20,
            )
            r.raise_for_status()

            soup = BeautifulSoup(
                r.content,
                "lxml",
            )

            product_list = soup.select(
                "div.list a.product-box.simple[href]"
            )
            if not product_list:
                raise RuntimeError(
                    f"No product links found on Mała Winnica "
                    f"listing page {page}: {r.url}"
                )
            for product in product_list:

                href = product["href"].strip()

                if href.startswith("/p/"):
                    product_links.append(
                        urljoin(BASE_URL, href),
                    )
    return list(dict.fromkeys(product_links))