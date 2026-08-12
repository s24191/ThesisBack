import requests
from bs4 import BeautifulSoup
from typing import List

BASE_URL = "https://sklep-wina.pl"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/119.0.0.0 Safari/537.36"
    )
}

FILTER_URL = (
    "https://sklep-wina.pl/pol_m_Oferta-100.html?"
    "filter_traits[27]=3627%2C3628%2C693%2C139%2C141%2C138&filter_pricerange=&"
    "filter_traits[32]=&filter_traits[24]=&filter_traits[25]=&filter_traits[26]=137&"
    "filter_traits[1617]=#filter_showall"
)


def fetch_sklep_wina_product_links() -> List[str]:
    r = requests.get(FILTER_URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.content, "html.parser")

    pagination = soup.find("ul", class_="pagination")
    last_page = 1

    if pagination:
        page_links = pagination.find_all("a", href=True)
        numeric_pages = [
            int(link.text.strip())
            for link in page_links
            if link.text.strip().isdigit()
        ]
        if numeric_pages:
            last_page = max(numeric_pages)

    product_links: List[str] = []

    for page in range(0, last_page):
        r = requests.get(
            (
                "https://sklep-wina.pl/pol_m_Oferta-100.html"
                "?filter_traits[27]=3627,3628,693,139,141,138&filter_traits[26]=137"
                f"&counter={page}"
            ),
            headers=HEADERS,
            timeout=30,
        )
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "html.parser")

        product_list = soup.find_all("div", class_="product_wrapper")

        for item in product_list:
            out_of_stock = item.find("a", class_="product-icon disable")
            if out_of_stock:
                continue

            link = item.find("a", class_="product-icon", href=True)
            if link:
                product_links.append(BASE_URL + link["href"])

    return product_links