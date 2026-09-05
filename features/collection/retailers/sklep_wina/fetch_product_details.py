from __future__ import annotations

import re
import time
from typing import Any
from urllib.parse import urljoin

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

def is_product_not_found_page(
    response: requests.Response,
    soup: BeautifulSoup,
) -> bool:
    final_url = response.url.lower()

    if "noproduct.php" in final_url:
        return True

    warning = soup.select_one(
        "#menu_messages_warning.menu_messages_error"
    )

    if warning and "produkt nie został znaleziony" in warning.get_text(
        " ",
        strip=True,
    ).lower():
        return True

    return False

def normalize_label(value: str) -> str:
    return clean_text(value).replace(":", "").lower()


def get_param_value(soup: BeautifulSoup, keyword: str) -> str | None:

    expected_label = normalize_label(keyword)

    for trait in soup.select("div.product_info_top div.param_trait"):
        label_element = trait.find("span")
        value_element = trait.find("strong")

        if not label_element or not value_element:
            continue

        label = normalize_label(label_element.get_text(" ", strip=True))

        if label != expected_label:
            continue

        linked_values = [
            clean_text(element.get_text(" ", strip=True))
            for element in value_element.find_all(["a", "span"])
            if clean_text(element.get_text(" ", strip=True))
        ]

        if linked_values:
            return ", ".join(dict.fromkeys(linked_values))

        value = clean_text(value_element.get_text(" ", strip=True))
        return value or None

    return None

def parse_price(value: str | None) -> float | None:

    if not value:
        return None

    match = re.search(r"(\d[\d\s\xa0]*[,.]\d{1,2})", value)

    if not match:
        return None

    cleaned = match.group(1).replace(" ", "").replace("\xa0", "")

    try:
        return float(cleaned.replace(",", "."))
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

    litre_match = re.search(r"(\d+(?:\.\d+)?)\s*l\b", normalized)
    if litre_match:
        return round(float(litre_match.group(1)) * 1000)

    millilitre_match = re.search(r"(\d+)\s*ml\b", normalized)
    if millilitre_match:
        return int(millilitre_match.group(1))

    return None


def parse_available(soup: BeautifulSoup) -> bool:
    basket_button = soup.find("button", id="projector_button_basket")

    if not basket_button:
        return False

    classes = basket_button.get("class", [])

    return (
        "disabled" not in classes
        and not basket_button.has_attr("disabled")
    )


def get_image_url(soup: BeautifulSoup, product_url: str) -> str | None:
    image_link = soup.select_one("a.projector_medium_image[href]")

    if image_link:
        return urljoin(product_url, image_link["href"].strip())

    zoom_image = soup.select_one("img.photo[data-zoom-image]")

    if zoom_image:
        return urljoin(
            product_url,
            zoom_image["data-zoom-image"].strip(),
        )

    og_image = soup.find("meta", property="og:image")

    if og_image and og_image.get("content"):
        return urljoin(
            product_url,
            og_image["content"].strip(),
        )

    return None

def parse_product_page(
    soup: BeautifulSoup,
    product_url: str,
    *,
    translation_mappings: TranslationMappings,
) -> dict[str, Any]:
    name_tag = soup.find("h1")

    if not name_tag:
        raise ValueError("Product name <h1> not found")

    raw_name = clean_text(name_tag.get_text(" ", strip=True))

    price_tag = soup.find(
        "strong",
        class_="projector_price_value price",
        id="projector_price_srp_wrapper2",
    )
    raw_price = (
        price_tag.get_text(" ", strip=True)
        if price_tag
        else None
    )

    country_tag = soup.find("a", class_="country")
    region_tag = soup.find("a", class_="region")

    raw_country = (
        country_tag.get_text(" ", strip=True)
        if country_tag
        else None
    )
    region = (
        clean_text(region_tag.get_text(" ", strip=True))
        if region_tag
        else None
    )

    raw_year = get_param_value(soup, "Rocznik")
    raw_alc_perc = get_param_value(soup, "Zawartość % alkoholu")
    raw_capacity = get_param_value(soup, "Objętość")
    raw_wine_type = get_param_value(soup, "Typ")
    raw_taste_profile = get_param_value(soup, "Smak")
    raw_grapes = get_param_value(soup, "Szczepy")

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

    alc_perc  = parse_alc_perc(raw_alc_perc)

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
        "wine_type": wine_type,
        "taste_profile": taste_profile,
        "region": region,
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
                    f"Temporary HTTP {response.status_code} for "
                    f"{product_url}; retrying in {delay}s "
                    f"({attempt}/{MAX_RETRIES})"
                )

                time.sleep(delay)
                continue

            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")

            if is_product_not_found_page(response, soup):
                return {
                    "error_type": "product_not_found",
                    "error": "Product no longer exists on Sklep Wina",
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
                f"Connection error for {product_url}; "
                f"retrying in {delay}s ({attempt}/{MAX_RETRIES}): {exc}"
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
