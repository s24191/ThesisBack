from __future__ import annotations

import re
import time
from typing import Any
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup
from requests.exceptions import ConnectTimeout, ConnectionError, ReadTimeout

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
    )
}

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 3
REQUEST_TIMEOUT_SECONDS = 20

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}



def normalize_label(value: str) -> str:
    return (clean_text(value) or "").replace(":", "").lower()


def get_data_sheet_value(
    soup: BeautifulSoup,
    keyword: str,
) -> str | None:
    expected_label = normalize_label(keyword)

    for label_element in soup.select("dl.data-sheet dt.name"):
        label = normalize_label(
            label_element.get_text(" ", strip=True)
        )

        if label != expected_label:
            continue

        value_element = label_element.find_next_sibling(
            "dd",
            class_="value",
        )

        if not value_element:
            return None

        linked_values = [
            clean_text(link.get_text(" ", strip=True))
            for link in value_element.find_all("a")
            if clean_text(link.get_text(" ", strip=True))
        ]

        if linked_values:
            return ", ".join(dict.fromkeys(linked_values))

        value = clean_text(
            value_element.get_text(" ", strip=True)
        )

        return value or None

    return None


def parse_price(value: str | None) -> float | None:
    if not value:
        return None

    cleaned = (
        value.replace("\xa0", " ")
        .replace("zł", "")
        .replace(" ", "")
        .replace(",", ".")
        .strip()
    )

    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_year(value: str | None) -> int | None:
    if not value:
        return None

    match = re.search(r"\b(?:19|20)\d{2}\b", value)

    return int(match.group()) if match else None

def parse_alc_perc(value: str | None) -> float | None:
    if not value:
        return None

    match = re.search(r"(\d+(?:[,.]\d+)?)\s*%", value)

    if not match:
        return None

    try:
        return float(match.group(1).replace(",", "."))
    except ValueError:
        return None

def parse_capacity_ml(value: str | None) -> int | None:
    if not value:
        return None

    normalized = value.lower().replace(",", ".")

    millilitre_match = re.search(r"(\d+)\s*ml\b", normalized)
    if millilitre_match:
        return int(millilitre_match.group(1))

    litre_match = re.search(r"(\d+(?:\.\d+)?)\s*l\b", normalized)
    if litre_match:
        return round(float(litre_match.group(1)) * 1000)

    return None

def parse_available(soup: BeautifulSoup) -> bool:
    add_to_cart_button = soup.select_one(
        'button[data-button-action="add-to-cart"]'
    )

    if not add_to_cart_button:
        return False

    return not add_to_cart_button.has_attr("disabled")

def get_image_url(
    soup: BeautifulSoup,
    product_url: str,
) -> str | None:
    image_tag = soup.select_one('img[itemprop="image"]')

    if image_tag and image_tag.get("src"):
        return urljoin(product_url, image_tag["src"].strip())

    og_image = soup.find("meta", property="og:image")

    if og_image and og_image.get("content"):
        return urljoin(product_url, og_image["content"].strip())

    return None

def is_product_page(soup: BeautifulSoup) -> bool:
    return bool(
        soup.select_one('h1[itemprop="name"]')
        and soup.select_one("dl.data-sheet")
    )

def has_redirected_to_non_product_page(
    response: requests.Response,
    requested_url: str,
    soup: BeautifulSoup,
) -> bool:
    requested_path = urlsplit(requested_url).path.rstrip("/")
    final_path = urlsplit(response.url).path.rstrip("/")

    redirected_to_different_path = requested_path != final_path

    return (
        redirected_to_different_path
        and not is_product_page(soup)
    )

def is_product_not_found_page(
    response: requests.Response,
    soup: BeautifulSoup,
) -> bool:
    final_url = response.url.lower()

    if "404" in final_url or "not-found" in final_url:
        return True

    page_text = soup.get_text(" ", strip=True).lower()

    not_found_phrases = [
        "produkt nie został znaleziony",
        "produkt nie istnieje",
        "nie znaleziono produktu",
        "strona nie istnieje",
    ]

    return any(phrase in page_text for phrase in not_found_phrases)

def parse_product_page(
    soup: BeautifulSoup,
    product_url: str,
    *,
    translation_mappings: TranslationMappings,
) -> dict[str, Any]:
    name_tag = soup.select_one('h1[itemprop="name"]')

    if not name_tag:
        raise ValueError("Product name <h1 itemprop='name'> not found")

    raw_name  = clean_text(name_tag.get_text(" ", strip=True))

    price_tag = soup.select_one('span[itemprop="price"]')

    raw_price = None
    if price_tag:
        raw_price = (
            price_tag.get("content")
            or price_tag.get_text(" ", strip=True)
        )

    raw_year = get_data_sheet_value(soup, "Rocznik")
    raw_country = get_data_sheet_value(soup, "Kraj")
    raw_region = get_data_sheet_value(soup, "Region")
    raw_wine_type = get_data_sheet_value(soup, "Rodzaj wina")
    raw_taste_profile = get_data_sheet_value(soup, "Smak")
    raw_grapes = get_data_sheet_value(soup, "Grona")
    raw_capacity = get_data_sheet_value(soup, "Pojemność")
    raw_alc_perc = get_data_sheet_value(
        soup,
        "Zawartość alkoholu",
    )

    alc_perc = parse_alc_perc(raw_alc_perc)

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

    country = translate_value(
        field_name="country",
        value=raw_country,
        translation_mappings=translation_mappings,
    )


    name = normalize_product_name(
        raw_name or "",
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
        "region": clean_text(raw_region),
        "wine_type": wine_type,
        "taste_profile": taste_profile,
        "grapes": clean_grapes(raw_grapes),

        "price": parse_price(raw_price),
        "available": parse_available(soup),
        "url": product_url,
        "image_url": get_image_url(soup, product_url),
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
                    f"Temporary HTTP {response.status_code}: "
                    f"retrying in {delay}s "
                    f"({attempt}/{MAX_RETRIES}) — {product_url}"
                )

                time.sleep(delay)
                continue

            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")

            if has_redirected_to_non_product_page(
                    response=response,
                    requested_url=product_url,
                    soup=soup,
            ):
                if attempt == MAX_RETRIES:
                    return {
                        "error_type": "redirected_to_non_product_page",
                        "error": (
                            "Product URL redirected to a non-product page "
                            "after multiple attempts"
                        ),
                        "url": product_url,
                        "final_url": response.url,
                    }

                delay = RETRY_DELAY_SECONDS * attempt

                print(
                    f"Product URL redirected to a non-product page; "
                    f"retrying in {delay}s ({attempt}/{MAX_RETRIES}) — "
                    f"{product_url}"
                )

                time.sleep(delay)
                continue

            if is_product_not_found_page(response, soup):
                return {
                    "error_type": "product_not_found",
                    "error": "Product no longer exists on Wina.pl",
                    "url": product_url,
                    "final_url": response.url,
                }

            return parse_product_page(
                soup=soup,
                product_url=product_url,
                translation_mappings=translation_mappings,
            )

        except (ConnectTimeout, ReadTimeout, ConnectionError) as exc:
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
                f"Connection error: retrying in {delay}s "
                f"({attempt}/{MAX_RETRIES}) — {product_url}"
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
