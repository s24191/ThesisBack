import requests
from bs4 import BeautifulSoup
from typing import List

BASE_URL = "https://sklep-wina.pl"

LISTING_URL = (
    "https://sklep-wina.pl/pol_m_Oferta-100.html"
)

FILTER_PARAMS = {
    "filter_traits[27]": "3627,3628,693,139,141,138",
    "filter_traits[26]": "137",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/119.0.0.0 Safari/537.36"
    )
}

def _get_last_page(
    session: requests.Session,
) -> int:
    response = session.get(
        LISTING_URL,
        params={
            **FILTER_PARAMS,
            "counter": 0,
        },
        timeout=20,
    )
    response.raise_for_status()

    soup = BeautifulSoup(
        response.content,
        "lxml",
    )

    pagination = soup.find(
        "ul",
        class_="pagination",
    )

    if not pagination:
        return 1

    numeric_pages = [
        int(link.get_text(strip=True))
        for link in pagination.find_all("a", href=True)
        if link.get_text(strip=True).isdigit()
    ]

    return max(numeric_pages, default=1)



def fetch_sklep_wina_product_links() -> List[str]:
    with requests.Session() as session:
        session.headers.update(HEADERS)
        last_page = _get_last_page(session)
        product_links: list[str] = []

        for page in range(last_page):
            response = session.get(
                LISTING_URL,
                params={
                    **FILTER_PARAMS,
                    "counter": page,
                },
                timeout=30,
            )
            response.raise_for_status()

            soup = BeautifulSoup(
                response.content,
                "lxml",
            )

            product_list = soup.find_all(
                "div",
                class_="product_wrapper",
            )

            if not product_list:
                raise RuntimeError(
                    f"No Sklep Wina products found for "
                    f"counter={page}: {response.url}"
                )

            for item in product_list:
                out_of_stock = item.find(
                    "a",
                    class_="product-icon disable",
                )

                if out_of_stock:
                    continue

                link = item.find(
                    "a",
                    class_="product-icon",
                    href=True,
                )

                if not link:
                    continue

                product_links.append(
                    BASE_URL + link["href"]
                )

        return list(dict.fromkeys(product_links))