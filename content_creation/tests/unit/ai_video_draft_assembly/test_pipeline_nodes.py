"""Unit tests for LangGraph pipeline nodes."""

import uuid

import pytest

from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.pipeline.nodes.visual_generation import (
    generate_visuals,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.pipeline.nodes.voiceover_generation import (
    generate_voiceover,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.pipeline.nodes.scene_sequencing import (
    sequence_scenes,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.pipeline.nodes.transition_generation import (
    generate_transitions,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.pipeline.nodes.metadata_generation import (
    generate_metadata,
    _extract_tags,
    _classify_topic,
)
from backend.services.content_creation.video_draft_generation_pipeline.ai_video_draft_assembly.pipeline.nodes.thumbnail_generation import (
    generate_thumbnails,
    MINIMUM_THUMBNAILS,
)


def _base_state(**overrides):
    state = {
        "content_item_id": uuid.uuid4(),
        "creator_id": uuid.uuid4(),
        "input_text": "Ceci est un texte de test pour la génération de vidéo avec du contenu suffisant.",
        "input_type": "script",
        "input_locale": "fr",
        "scenes": [],
        "visual_assets": [],
        "voice_segments": [],
        "transitions": [],
        "metadata": {},
        "thumbnails": [],
        "assembly_status": "processing",
        "video_draft_url": None,
        "error": None,
        "error_node": None,
        "run_id": str(uuid.uuid4()),
        "thread_id": str(uuid.uuid4()),
    }
    state.update(overrides)
    return state


class TestVisualGeneration:
    @pytest.mark.asyncio
    async def test_generates_scenes_and_visuals(self):
        state = _base_state()
        result = await generate_visuals(state)
        assert len(result["scenes"]) > 0
        assert len(result["visual_assets"]) > 0
        assert result.get("error") is None

    @pytest.mark.asyncio
    async def test_each_scene_has_visual_asset_id(self):
        state = _base_state()
        result = await generate_visuals(state)
        for scene in result["scenes"]:
            assert "visual_asset_id" in scene
            assert "scene_id" in scene


class TestVoiceoverGeneration:
    @pytest.mark.asyncio
    async def test_generates_voice_segments(self):
        state = _base_state(
            scenes=[
                {"scene_id": "s1", "text_content": "Bonjour le monde", "voice_segment_id": "v1"},
                {"scene_id": "s2", "text_content": "Comment allez-vous", "voice_segment_id": "v2"},
            ]
        )
        result = await generate_voiceover(state)
        assert len(result["voice_segments"]) == 2
        assert result.get("error") is None

    @pytest.mark.asyncio
    async def test_voice_segments_are_french(self):
        state = _base_state(
            scenes=[{"scene_id": "s1", "text_content": "Bonjour", "voice_segment_id": "v1"}]
        )
        result = await generate_voiceover(state)
        for seg in result["voice_segments"]:
            assert seg["locale"] == "fr-FR"


class TestSceneSequencing:
    @pytest.mark.asyncio
    async def test_assigns_sequence_indices(self):
        state = _base_state(
            scenes=[
                {"scene_id": "s1", "pacing_value": 1.0},
                {"scene_id": "s2", "pacing_value": 1.5},
            ],
            voice_segments=[
                {"scene_id": "s1", "duration_seconds": 5.0},
                {"scene_id": "s2", "duration_seconds": 3.0},
            ],
        )
        result = await sequence_scenes(state)
        assert result["scenes"][0]["sequence_index"] == 0
        assert result["scenes"][1]["sequence_index"] == 1
        assert result.get("error") is None

    @pytest.mark.asyncio
    async def test_pacing_affects_duration(self):
        state = _base_state(
            scenes=[{"scene_id": "s1", "pacing_value": 2.0}],
            voice_segments=[{"scene_id": "s1", "duration_seconds": 5.0}],
        )
        result = await sequence_scenes(state)
        assert result["scenes"][0]["duration_seconds"] == 10.0


class TestTransitionGeneration:
    @pytest.mark.asyncio
    async def test_generates_transitions_between_scenes(self):
        state = _base_state(
            scenes=[
                {"scene_id": "s1"},
                {"scene_id": "s2"},
                {"scene_id": "s3"},
            ]
        )
        result = await generate_transitions(state)
        assert len(result["transitions"]) == 2
        assert result["transitions"][0]["from_scene_id"] == "s1"
        assert result["transitions"][0]["to_scene_id"] == "s2"

    @pytest.mark.asyncio
    async def test_no_transitions_for_single_scene(self):
        state = _base_state(scenes=[{"scene_id": "s1"}])
        result = await generate_transitions(state)
        assert len(result["transitions"]) == 0


class TestMetadataGeneration:
    @pytest.mark.asyncio
    async def test_generates_all_metadata_fields(self):
        state = _base_state(
            input_text="Ceci est un texte long pour tester la génération de métadonnées avec suffisamment de mots pour le titre et la description"
        )
        result = await generate_metadata(state)
        metadata = result["metadata"]
        assert "ai_title" in metadata
        assert "ai_description" in metadata
        assert "ai_tags" in metadata
        assert "ai_topic_cluster" in metadata

    def test_extract_tags(self):
        tags = _extract_tags("Bonjour le monde est merveilleux et technologique")
        assert len(tags) > 0
        assert all(len(t) > 4 for t in tags)

    def test_classify_topic_technology(self):
        topic = _classify_topic("Cette application code un logiciel avec une api")
        assert topic == "technologie"

    def test_classify_topic_general(self):
        topic = _classify_topic("Un texte sans mots clés spécifiques")
        assert topic == "general"


class TestThumbnailGeneration:
    @pytest.mark.asyncio
    async def test_generates_minimum_thumbnails(self):
        state = _base_state()
        result = await generate_thumbnails(state)
        assert len(result["thumbnails"]) >= MINIMUM_THUMBNAILS
        assert result.get("error") is None

    @pytest.mark.asyncio
    async def test_thumbnail_urls_are_s3(self):
        state = _base_state()
        result = await generate_thumbnails(state)
        for url in result["thumbnails"]:
            assert url.startswith("s3://")
