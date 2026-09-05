from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://www.wina.pl"
LISTING_URL = f"{BASE_URL}/3-wina"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/119.0.0.0 Safari/537.36"
    )
}


def _get_soup(session: requests.Session, url: str) -> BeautifulSoup:
    response = session.get(
        url,
        timeout=10,
    )
    response.raise_for_status()

    return BeautifulSoup(
        response.content,
        "lxml",
    )


def _get_last_page(session: requests.Session) -> int:
    soup = _get_soup(session, LISTING_URL)

    pagination = soup.find(
        "ul",
        class_="page-list",
    )

    if not pagination:
        return 1

    page_numbers = []

    for link in pagination.find_all("a"):
        text = link.get_text(strip=True)

        if text.isdigit():
            page_numbers.append(int(text))

    return max(page_numbers, default=1)


def fetch_winapl_product_links() -> list[str]:
    with requests.Session() as session:
        session.headers.update(HEADERS)

        last_page = _get_last_page(session)
        product_links: list[str] = []

        for page in range(1, last_page + 1):
            response = session.get(
                LISTING_URL,
                params={"page": page},
                timeout=10,
            )

            if response.status_code == 404:
                break

            response.raise_for_status()

            soup = BeautifulSoup(
                response.content,
                "lxml",
            )

            product_links_on_page = soup.select(
                "p.thumbnail.product-thumbnail > a[href]"
            )

            if not product_links_on_page:
                raise RuntimeError(
                    f"No Wina.pl product links found on "
                    f"page {page}: {response.url}"
                )

            for link_tag in product_links_on_page:
                href = link_tag["href"].strip()

                product_links.append(
                    urljoin(
                        BASE_URL,
                        href,
                    )
                )

    return list(dict.fromkeys(product_links))