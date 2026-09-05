from datetime import datetime

from pydantic import BaseModel, Field


class TranslationReviewItemRead(BaseModel):
    id: int

    field_name: str
    source_value: str
    status: str

    translation_mapping_id: int | None = None

    created_at: datetime
    mapped_at: datetime | None = None

    occurrence_count: int


class TranslationReviewOccurrenceRead(BaseModel):
    id: int

    translation_review_item_id: int
    source_url: str

    status: str
    created_at: datetime

    original_step_run_id: int
    original_run_id: int
    site_key: str
    site_name: str

    reprocessed_at: datetime | None = None
    reprocessed_step_run_id: int | None = None
    reprocess_error: str | None = None


class ResolveTranslationReviewRequest(BaseModel):
    target_value: str = Field(
        min_length=1,
        max_length=255,
    )


class TranslationReviewActionResponse(BaseModel):
    id: int

    field_name: str
    source_value: str
    status: str

    translation_mapping_id: int | None = None
    affected_occurrences: int