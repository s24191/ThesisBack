from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from shared.models import TranslationMapping
from shared.translations.normalization import TranslationMappings, normalize_translation_key


async def load_active_translation_mappings(
    session: AsyncSession,
) -> TranslationMappings:
    result = await session.execute(
        select(TranslationMapping).where(
            TranslationMapping.active.is_(True)
        )
    )
    mappings = result.scalars().all()

    return {
        (
            mapping.field_name,
            normalize_translation_key(
                mapping.source_value,
            )
            or mapping.source_value,
        ): mapping.target_value
        for mapping in mappings
    }