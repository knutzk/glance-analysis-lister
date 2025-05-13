"""Enum definitions for GLANCE entry publication states.

"""

from enum import Enum, auto


class AnalysisPubState(Enum):
    """Publication state for an analysis entry."""
    CLOSED = auto()
    ONGOING_WO_EB = auto()
    WITH_EB = auto()
    PRE_APPROVED = auto()
    PUB_PREPARATION = auto()
    PAST_PHASE0 = auto()
    UNKNOWN = auto()


class ConfNotePubState(Enum):
    """Publication state for a CONF note entry."""
    PUBLISHED = auto()
    ONGOING = auto()
    SUPERSEDED = auto()
    UNKNOWN = auto()


class PaperPubState(Enum):
    """Publication state for a paper entry."""
    SUBMITTED = auto()
    PUBLISHED = auto()
    ONGOING = auto()
    UNKNOWN = auto()


class PubNotePubState(Enum):
    """Publication state for a PUB note entry."""
    INACTIVE = auto()
    PUBLISHED = auto()
    ONGOING = auto()
    SUPERSEDED = auto()
    UNKNOWN = auto()
