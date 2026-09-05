from __future__ import annotations

import re
import time
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.exceptions import (
    ConnectTimeout,
    ConnectionError,
    ReadTimeout,
)

from shared.translations.normalization import (
    TranslationMappings,
    UntranslatedValueError,
    clean_grapes,
    clean_text,
    normalize_product_name,
    translate_value,
)


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/119.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
}

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 3
REQUEST_TIMEOUT_SECONDS = 20
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def normalize_label(value: str) -> str:
    return clean_text(value).replace(":", "").lower()


def parse_price(value: str | None) -> float | None:
    if not value:
        return None

    match = re.search(
        r"(\d[\d\s\xa0]*[,.]\d{1,2})",
        value,
    )

    if not match:
        return None

    normalized = (
        match.group(1)
        .replace(" ", "")
        .replace("\xa0", "")
        .replace(",", ".")
    )

    try:
        return float(normalized)
    except ValueError:
        return None


def parse_year(value: str | None) -> int | None:
    if not value:
        return None

    match = re.search(
        r"\b(?:19|20)\d{2}\b",
        value,
    )

    return int(match.group()) if match else None


def parse_alc_perc(value: str | None) -> float | None:
    if not value:
        return None

    match = re.search(
        r"(\d+(?:[,.]\d+)?)\s*%",
        value,
    )

    if not match:
        return None

    try:
        return float(
            match.group(1).replace(",", ".")
        )
    except ValueError:
        return None


def parse_capacity_ml(value: str | None) -> int | None:
    if not value:
        return None

    normalized = value.lower().replace(",", ".")

    millilitre_match = re.search(
        r"(\d+)\s*ml\b",
        normalized,
    )

    if millilitre_match:
        return int(millilitre_match.group(1))

    litre_match = re.search(
        r"(\d+(?:\.\d+)?)\s*l\b",
        normalized,
    )

    if litre_match:
        return round(
            float(litre_match.group(1)) * 1000
        )

    return None

def get_product_attributes(
    soup: BeautifulSoup,
) -> dict[str, str]:
    attributes_container = soup.select_one(
        "div.product-attributes"
    )

    if not attributes_container:
        return {}

    attributes: dict[str, str] = {}

    for attribute_row in attributes_container.find_all(
        "div",
        recursive=False,
    ):
        value_element = attribute_row.find("span")

        if not value_element:
            continue

        value = clean_text(
            value_element.get_text(
                " ",
                strip=True,
            )
        )

        label_text = "".join(
            text.strip()
            for text in attribute_row.find_all(
                string=True,
                recursive=False,
            )
            if text.strip()
        )

        label = normalize_label(label_text)

        if label and value:
            attributes[label] = value

    return attributes
def get_attribute_value(
    attributes: dict[str, str],
    *possible_labels: str,
) -> str | None:
    for label in possible_labels:
        value = attributes.get(
            normalize_label(label)
        )

        if value:
            return value

    return None


def get_region_value(
    attributes: dict[str, str],
) -> str | None:
    for label, value in attributes.items():
        if label.startswith("region winiarski"):
            return value

    return get_attribute_value(
        attributes,
        "Region",
    )


def get_price_text(
    soup: BeautifulSoup,
) -> str | None:
    price_container = soup.select_one(
        "div.price"
    )

    if not price_container:
        return None

    discounted_price = price_container.select_one(
        "div.regular.discounted > span"
    )

    if discounted_price:
        return clean_text(
            discounted_price.get_text(
                " ",
                strip=True,
            )
        )

    regular_price = price_container.select_one(
        "div.regular:not(.discounted) > span"
    )

    if regular_price:
        return clean_text(
            regular_price.get_text(
                " ",
                strip=True,
            )
        )

    fallback_price = price_container.select_one(
        "div.regular > span"
    )

    if fallback_price:
        return clean_text(
            fallback_price.get_text(
                " ",
                strip=True,
            )
        )

    return None


def parse_available(
    soup: BeautifulSoup,
) -> bool:
    """
    cannot be determined reliably without JavaScript.

    will be treated as avaliable on the backend for now
    """
    return True
def get_image_url(
    soup: BeautifulSoup,
    product_url: str,
) -> str | None:
    image = soup.select_one(
        "div.pic picture img[src]"
    )

    if image:
        image_url = (
            image.get("data-src")
            or image.get("src")
        )

        if image_url:
            return urljoin(
                product_url,
                image_url.strip(),
            )

    og_image = soup.find(
        "meta",
        property="og:image",
    )

    if og_image and og_image.get("content"):
        return urljoin(
            product_url,
            og_image["content"].strip(),
        )

    return None


def is_product_not_found_page(
    response: requests.Response,
    soup: BeautifulSoup,
) -> bool:
    if response.status_code == 404:
        return True

    page_title = (
        clean_text(
            soup.title.get_text(
                " ",
                strip=True,
            )
        )
        if soup.title
        else ""
    )

    page_text = clean_text(
        soup.get_text(
            " ",
            strip=True,
        )
    ) or ""

    return (
        "nie znaleziono strony" in page_text.lower()
        or "page not found" in page_title.lower()
        or "404" in page_title
    )


def parse_product_page(
    soup: BeautifulSoup,
    product_url: str,
    *,
    translation_mappings: TranslationMappings,
) -> dict[str, Any]:
    name_tag = soup.select_one("h1.name")

    if not name_tag:
        raise ValueError(
            "Product name h1.name was not found"
        )

    raw_name = clean_text(
        name_tag.get_text(
            " ",
            strip=True,
        )
    )

    if not raw_name:
        raise ValueError("Product name is empty")

    raw_price = get_price_text(soup)
    price = parse_price(raw_price)

    if price is None:
        raise ValueError(
            f"Price could not be parsed: {raw_price!r}"
        )

    attributes = get_product_attributes(soup)

    raw_country = get_attribute_value(
        attributes,
        "Kraj pochodzenia",
        "Kraj",
    )

    raw_region = get_region_value(attributes)

    raw_wine_type = get_attribute_value(
        attributes,
        "Kolor",
        "Typ wina",
        "Rodzaj wina",
    )

    raw_taste_profile = get_attribute_value(
        attributes,
        "Rodzaj",
        "Smak",
        "Słodycz",
    )

    raw_grapes = get_attribute_value(
        attributes,
        "Szczep",
        "Szczepy",
        "Odmiana winogron",
    )

    raw_year = get_attribute_value(
        attributes,
        "Rocznik",
        "Vintage",
    )

    raw_alc_perc = get_attribute_value(
        attributes,
        "Zawartość alkoholu",
        "Alkohol",
        "Zawartość % alkoholu",
    )

    raw_capacity = get_attribute_value(
        attributes,
        "Pojemność",
        "Objętość",
        "Volume",
    )

    country = translate_value(
        field_name="country",
        value=raw_country,
        translation_mappings=translation_mappings,
    )

    wine_type = translate_value(
        field_name="wine_type",
        value=raw_wine_type,
        translation_mappings=translation_mappings,
        match_mode="contains",
    )

    taste_profile = translate_value(
        field_name="taste_profile",
        value=raw_taste_profile,
        translation_mappings=translation_mappings,
    )

    alc_perc = parse_alc_perc(raw_alc_perc)

    name = normalize_product_name(
        raw_name,
        alc_perc=alc_perc,
        wine_type=wine_type,
        taste_profile=taste_profile,
    )

    return {
        "name": name,
        "year": parse_year(raw_year),
        "alc_perc": alc_perc,
        "capacity_ml": parse_capacity_ml(raw_capacity),
        "country": country,
        "region": clean_text(raw_region)
        if raw_region
        else None,
        "wine_type": wine_type,
        "taste_profile": taste_profile,
        "grapes": clean_grapes(raw_grapes),
        "price": price,
        "available": parse_available(soup),
        "url": product_url,
        "image_url": get_image_url(
            soup,
            product_url,
        ),
    }


def fetch_product_details(
    product_url: str,
    *,
    translation_mappings: TranslationMappings,
) -> dict[str, Any]:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(
                product_url,
                headers=HEADERS,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )

            if response.status_code in RETRYABLE_STATUS_CODES:
                if attempt == MAX_RETRIES:
                    return {
                        "error_type": "temporary_http_error",
                        "error": (
                            f"HTTP {response.status_code} after "
                            f"{MAX_RETRIES} attempts"
                        ),
                        "url": product_url,
                        "final_url": response.url,
                    }

                delay = RETRY_DELAY_SECONDS * attempt

                print(
                    f"Temporary HTTP {response.status_code} for "
                    f"{product_url}; retrying in {delay}s "
                    f"({attempt}/{MAX_RETRIES})"
                )

                time.sleep(delay)
                continue

            response.raise_for_status()

            soup = BeautifulSoup(
                response.content,
                "lxml",
            )

            if is_product_not_found_page(
                response,
                soup,
            ):
                return {
                    "error_type": "product_not_found",
                    "error": (
                        "Product no longer exists on "
                        "Mała Winnica"
                    ),
                    "url": product_url,
                    "final_url": response.url,
                }

            return parse_product_page(
                soup=soup,
                product_url=str(response.url),
                translation_mappings=translation_mappings,
            )

        except (
            ConnectTimeout,
            ReadTimeout,
            ConnectionError,
        ) as exc:
            if attempt == MAX_RETRIES:
                return {
                    "error_type": "connection_error",
                    "error": (
                        f"Connection error after "
                        f"{MAX_RETRIES} attempts: {exc}"
                    ),
                    "url": product_url,
                    "final_url": product_url,
                }

            delay = RETRY_DELAY_SECONDS * attempt

            print(
                f"Connection error for {product_url}; "
                f"retrying in {delay}s "
                f"({attempt}/{MAX_RETRIES}): {exc}"
            )

            time.sleep(delay)

        except requests.HTTPError as exc:
            return {
                "error_type": "http_error",
                "error": f"HTTP error: {exc}",
                "url": product_url,
                "final_url": product_url,
            }

        except UntranslatedValueError as exc:
            return {
                "error_type": "untranslated_value",
                "error": str(exc),
                "url": product_url,
                "final_url": product_url,
                "translation_field": exc.field_name,
                "source_value": exc.source_value,
            }

        except Exception as exc:
            return {
                "error_type": "parser_error",
                "error": str(exc),
                "url": product_url,
                "final_url": product_url,
            }

    return {
        "error_type": "unknown_error",
        "error": "Unknown scraper error",
        "url": product_url,
        "final_url": product_url,
    }