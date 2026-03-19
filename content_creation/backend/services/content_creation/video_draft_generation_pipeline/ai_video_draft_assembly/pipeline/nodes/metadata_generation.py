"""AI metadata generation pipeline node."""

import logging

from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.pipeline.state import (
    AssemblyPipelineState,
)

logger = logging.getLogger(__name__)


async def generate_metadata(state: AssemblyPipelineState) -> AssemblyPipelineState:
    """Generate AI metadata (title, description, tags, topic cluster) in French.

    Produces French-language metadata fields for the content item:
    - ai_title: A concise title
    - ai_description: A descriptive summary
    - ai_tags: French-language topic tags
    - ai_topic_cluster: Topic classification
    """
    content_item_id = state["content_item_id"]
    input_text = state["input_text"]
    logger.info("Generating metadata for content item %s", content_item_id)

    try:
        # Generate French-language metadata from input text
        words = input_text.split()
        title_words = words[:8] if len(words) >= 8 else words
        description_words = words[:30] if len(words) >= 30 else words

        metadata = {
            "ai_title": " ".join(title_words),
            "ai_description": " ".join(description_words),
            "ai_tags": _extract_tags(input_text),
            "ai_topic_cluster": _classify_topic(input_text),
        }

        logger.info("Metadata generated for content item %s", content_item_id)
        return {**state, "metadata": metadata}
    except Exception as exc:
        logger.error("Metadata generation failed for %s: %s", content_item_id, exc)
        return {
            **state,
            "error": str(exc),
            "error_node": "metadata_generation",
            "assembly_status": "failed",
        }


def _extract_tags(text: str) -> list[str]:
    """Extract French-language topic tags from input text."""
    words = text.lower().split()
    # Simple tag extraction: unique words of sufficient length
    seen: set[str] = set()
    tags: list[str] = []
    for word in words:
        cleaned = word.strip(".,;:!?\"'()[]{}").lower()
        if len(cleaned) > 4 and cleaned not in seen:
            seen.add(cleaned)
            tags.append(cleaned)
        if len(tags) >= 10:
            break
    return tags


def _classify_topic(text: str) -> str:
    """Classify the topic cluster from input text."""
    text_lower = text.lower()
    topic_keywords = {
        "technologie": ["code", "logiciel", "application", "programme", "tech", "api"],
        "education": ["apprendre", "cours", "formation", "etude", "enseignement"],
        "divertissement": ["film", "musique", "jeu", "spectacle", "video"],
        "science": ["recherche", "experience", "decouverte", "analyse"],
        "general": [],
    }
    for topic, keywords in topic_keywords.items():
        if any(kw in text_lower for kw in keywords):
            return topic
    return "general"
