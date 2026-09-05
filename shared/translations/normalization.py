from __future__ import annotations

import re

import unicodedata
from typing import Mapping


TranslationMappings = Mapping[tuple[str, str], str]

POLISH_CHARACTER_TRANSLATION = str.maketrans(
    {
        "ą": "a",
        "ć": "c",
        "ę": "e",
        "ł": "l",
        "ń": "n",
        "ó": "o",
        "ś": "s",
        "ź": "z",
        "ż": "z",
    }
)

class UntranslatedValueError(ValueError):
    def __init__(
        self,
        *,
        field_name: str,
        source_value: str,
    ) -> None:
        self.field_name = field_name
        self.source_value = source_value

        super().__init__(
            f"Untranslated {field_name}: {source_value}"
        )

def clean_text(value: str | None) -> str | None:

    if not value:
        return None

    cleaned = " ".join(
        value.replace("\xa0", " ").split()
    )

    return cleaned or None

def normalize_translation_key(
    value: str | None,
) -> str | None:

    cleaned = clean_text(value)

    if not cleaned:
        return None

    text = cleaned.casefold()

    text = text.translate(POLISH_CHARACTER_TRANSLATION,)

    decomposed = unicodedata.normalize("NFKD", text,)

    without_diacritics = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )

    normalized = " ".join(without_diacritics.split())

    return normalized or None

def translate_value(
    *,
    field_name: str,
    value: str | None,
    translation_mappings: TranslationMappings,
    match_mode: str = "exact",
) -> str | None:
    source_value = normalize_translation_key(value)

    if not source_value:
        return None

    if match_mode == "exact":
        translated = translation_mappings.get(
            (field_name, source_value),
        )

        if translated:
            return translated

    elif match_mode == "contains":
        matching_mappings = [
            (mapping_key, target_value)
            for (
                mapping_field,
                mapping_key,
            ), target_value in translation_mappings.items()
            if (
                mapping_field == field_name
                and mapping_key in source_value
            )
        ]

        if matching_mappings:
            matching_mappings.sort(
                key=lambda item: len(item[0]),
                reverse=True,
            )

            return matching_mappings[0][1]

    else:
        raise ValueError(
            f"Unsupported translation match mode: "
            f"{match_mode}"
        )

    raise UntranslatedValueError(
        field_name=field_name,
        source_value=source_value,
    )

def clean_grapes(value: str | None) -> list[str]:
    cleaned_value = clean_text(value)

    if not cleaned_value:
        return []

    return [
        grape.strip()
        for grape in cleaned_value.split(",")
        if grape.strip()
    ]


PRODUCT_NAME_TYPE_SUFFIXES = {
    "white": {
        "białe",
        "biale",
        "white",
    },
    "red": {
        "czerwone",
        "red",
    },
    "rose": {
        "różowe",
        "rozowe",
        "rose",
    },
    "sparkling": {
        "musujące",
        "musujace",
        "sparkling",
    },
    "orange": {
        "pomarańczowe",
        "pomaranczowe",
        "orange",
    },
    "fortified": {
        "wzmacniane",
        "fortified",
    },
}

PRODUCT_NAME_TASTE_SUFFIXES = {
    "dry": {
        "wytrawne",
        "dry",
    },
    "semi-dry": {
        "półwytrawne",
        "polwytrawne",
        "semi-dry",
    },
    "semi-sweet": {
        "półsłodkie",
        "polslodkie",
        "semi-sweet",
    },
    "sweet": {
        "słodkie",
        "slodkie",
        "sweet",
    },
    "brut": {
        "brut",
    },
    "extra dry": {
        "extra dry",
    },
}

def normalize_product_name(
    name: str,
    *,
    alc_perc: float | None,
    wine_type: str | None,
    taste_profile: str | None,
) -> str:

    cleaned_name = clean_text(name) or name

    if alc_perc == 0:
        cleaned_name = re.sub(
            r"\s*\(\s*(?:bezalkoholowe|non-alcoholic)\s*\)\s*$",
            "",
            cleaned_name,
            flags=re.IGNORECASE,
        )

    type_suffixes = PRODUCT_NAME_TYPE_SUFFIXES.get(
        wine_type,
        set(),
    )

    taste_suffixes = PRODUCT_NAME_TASTE_SUFFIXES.get(
        taste_profile,
        set(),
    )

    for type_suffix in type_suffixes:
        for taste_suffix in taste_suffixes:
            suffix_pattern = (
                rf"\s+{re.escape(type_suffix)}"
                rf"\s+{re.escape(taste_suffix)}\s*$"
            )

            cleaned_name = re.sub(
                suffix_pattern,
                "",
                cleaned_name,
                flags=re.IGNORECASE,
            )

    return clean_text(cleaned_name) or name