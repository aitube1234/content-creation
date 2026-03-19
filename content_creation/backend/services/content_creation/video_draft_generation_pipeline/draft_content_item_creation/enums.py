"""Enumerations for draft content item creation."""

import enum


class CreationSource(str, enum.Enum):
    """Source that triggered the draft content item creation."""

    SCRIPT_TO_VIDEO = "script_to_video"
    CO_CREATOR_WORKSPACE = "co_creator_workspace"


class MetadataEngineWriteStatus(str, enum.Enum):
    """Status of metadata write to the Content Metadata Engine."""

    CONFIRMED = "confirmed"
    PENDING = "pending"
    FAILED = "failed"


class VersionEventType(str, enum.Enum):
    """Types of version history events tracked on a draft content item."""

    DRAFT_CREATED = "draft_created"
    SCENE_EDIT = "scene_edit"
    METADATA_OVERRIDE = "metadata_override"
    THUMBNAIL_CHANGE = "thumbnail_change"
    CONTRIBUTOR_INPUT = "contributor_input"
    HARMONISATION_OUTPUT = "harmonisation_output"


class ActorRole(str, enum.Enum):
    """Role of the actor who made a version history change."""

    LEAD_CREATOR = "lead_creator"
    CONTRIBUTOR = "contributor"


class ReportStatus(str, enum.Enum):
    """Status of an originality report."""

    COMPLETED = "completed"
    TIMEOUT = "timeout"
    FAILED = "failed"


class ContributionStatus(str, enum.Enum):
    """Status of a contributor's contribution in version history."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    OVERRIDDEN = "overridden"
