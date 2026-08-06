from typing import Callable, Dict, List
from scripts.temp.sklep_wina_list import fetch_sklep_wina_product_links
from scripts.temp.winapl_list import fetch_winapl_product_links
from scripts.temp.malawinnica_list import fetch_malawinnica_product_links

FetchFn = Callable[[], List[str]]

SITE_CONFIG: Dict[str, Dict[str, object]] = {
    "sklep_wina": {
        "name": "Sklep Wina",
        "base_url": "https://sklep-wina.pl",
        "fetch_fn": fetch_sklep_wina_product_links,
    },
    "winapl": {
        "name": "Wina.pl",
        "base_url": "https://wina.pl",
        "fetch_fn": fetch_winapl_product_links,
    },
    "malawinnica": {
        "name": "Mala Winnica",
        "base_url": "https://malawinnica.pl",
        "fetch_fn": fetch_malawinnica_product_links,
    },
}