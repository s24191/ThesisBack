from typing import Callable, Dict, List

from features.collection.retailers.mala_winnica.list_products import fetch_malawinnica_product_links
from features.collection.retailers.wina_pl.fetch_product_details import   (
    fetch_product_details as fetch_winapl_product_details,
)
from features.collection.retailers.sklep_wina.fetch_product_details import (
    fetch_product_details as sklep_wina_product_details,
)
from features.collection.retailers.sklep_wina.list_products import fetch_sklep_wina_product_links
from features.collection.retailers.wina_pl.list_products import fetch_winapl_product_links
from features.collection.retailers.mala_winnica.fetch_product_details import (
    fetch_product_details as malawinnica_product_details,
)
FetchFn = Callable[[], List[str]]

SITE_CONFIG: Dict[str, Dict[str, object]] = {
    "sklep_wina": {
        "name": "Sklep Wina",
        "base_url": "https://sklep-wina.pl",
        "fetch_fn": fetch_sklep_wina_product_links,
        "fetch_product_details_fn": sklep_wina_product_details ,
    },
    "winapl": {
        "name": "Wina.pl",
        "base_url": "https://wina.pl",
        "fetch_fn": fetch_winapl_product_links,
        "fetch_product_details_fn": fetch_winapl_product_details ,
    },
    "malawinnica": {
        "name": "Mala Winnica",
        "base_url": "https://malawinnica.pl",
        "fetch_fn": fetch_malawinnica_product_links,
        "fetch_product_details_fn": malawinnica_product_details,

    },
}