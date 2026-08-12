from datetime import datetime
from sqlalchemy import UniqueConstraint

from sqlmodel import SQLModel, Field



class TranslationMapping(SQLModel, table=True):
    __tablename__ = "translation_mapping"

    __table_args__ = (
        UniqueConstraint(
            "field_name",
            "source_value",
            name="uq_translation_mapping_field_source",
        ),
    )

    id: int | None = Field(
        default=None,
        primary_key=True,
    )

    field_name: str = Field(index=True)
    source_value: str = Field(index=True)
    target_value: str

    active: bool = Field(default=True)

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
    )

    created_by: str | None = None


class TranslationReviewItem(SQLModel, table=True):
    __tablename__ = "translation_review_item"

    __table_args__ = (
        UniqueConstraint(
            "field_name",
            "source_value",
            name="uq_translation_review_item_field_source",
        ),
    )

    id: int | None = Field(
        default=None,
        primary_key=True,
    )

    field_name: str = Field(index=True)

    source_value: str = Field(index=True)

    status: str = Field(
        default="pending",
        index=True,
    )

    translation_mapping_id: int | None = Field(
        default=None,
        foreign_key="translation_mapping.id",
        index=True,
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
    )

    mapped_at: datetime | None = None

class TranslationReviewOccurrence(SQLModel, table=True):
    __tablename__ = "translation_review_occurrence"
    __table_args__ = (
        UniqueConstraint(
            "translation_review_item_id",
            "step_run_id",
            "source_url",
            name=(
                "uq_translation_review_occurrence_"
                "item_step_url"
            ),
        ),
    )

    id: int | None = Field(
        default=None,
        primary_key=True,
    )

    translation_review_item_id: int = Field(
        foreign_key="translation_review_item.id",
        index=True,
    )

    step_run_id: int = Field(
        foreign_key="scrape_step_run.id",
        index=True,
    )

    source_url: str = Field(index=True)

    status: str = Field(
        default="pending",
        index=True,
    )

    reprocessed_at: datetime | None = None

    reprocessed_step_run_id: int | None = Field(
        default=None,
        foreign_key="scrape_step_run.id",
        index=True,
    )

    reprocess_error: str | None = None

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
    )