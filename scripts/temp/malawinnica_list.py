import requests
from bs4 import BeautifulSoup
from typing import List

BASE_URL = "https://malawinnica.pl"
LISTING_URL = BASE_URL + "/kategoria-produktu/wina/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/119.0.0.0 Safari/537.36"
    )
}


def _get_soup(url: str) -> BeautifulSoup:
    r = requests.get(url, headers=HEADERS, timeout=10)
    r.raise_for_status()
    return BeautifulSoup(r.content, "html.parser")


def _get_last_page() -> int:

    soup = _get_soup(LISTING_URL)
    pagination = soup.find("ul", class_="page-numbers")
    last_page = 1

    if pagination:
        page_links = pagination.find_all("a", href=True)
        numeric_pages = []
        for link in page_links:
            text = link.text.strip()
            if text.isdigit():
                numeric_pages.append(int(text))
        if numeric_pages:
            last_page = max(numeric_pages)

    return last_page


def fetch_malawinnica_product_links() -> List[str]:

    last_page = _get_last_page()
    product_links: List[str] = []

    for page in range(1, last_page + 1):
        if page == 1:
            url = LISTING_URL
        else:
            url = LISTING_URL.rstrip("/") + f"/page/{page}/"

        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 404:
            break
        r.raise_for_status()

        soup = BeautifulSoup(r.content, "html.parser")

        product_list = soup.find_all("li", class_="product")
        if not product_list:
            product_list = soup.find_all("div", class_="product")

        for item in product_list:
            out_of_stock = item.find(class_="out-of-stock")
            if out_of_stock:
                continue

            link_tag = item.find("a", href=True)
            if not link_tag:
                continue

            href = link_tag["href"]
            if href.startswith("http"):
                product_links.append(href)
            else:
                product_links.append(BASE_URL.rstrip("/") + "/" + href.lstrip("/"))

    return product_links