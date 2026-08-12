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


def _get_soup(url: str) -> BeautifulSoup:
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=10,
    )
    response.raise_for_status()

    return BeautifulSoup(
        response.content,
        "html.parser",
    )


def _get_last_page() -> int:
    soup = _get_soup(LISTING_URL)

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
    last_page = _get_last_page()
    product_links: list[str] = []

    for page in range(1, last_page + 1):
        url = f"{LISTING_URL}?page={page}"

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=10,
        )

        if response.status_code == 404:
            break

        response.raise_for_status()

        soup = BeautifulSoup(
            response.content,
            "html.parser",
        )

        product_list = soup.find_all(
            "div",
            class_="desc_info",
        )

        for item in product_list:
            link_tag = item.find("a", href=True)

            if not link_tag:
                continue

            product_links.append(
                urljoin(
                    BASE_URL,
                    link_tag["href"],
                )
            )

    return list(dict.fromkeys(product_links))