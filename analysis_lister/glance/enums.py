from enum import Enum, auto


class PublicationState(Enum):
    """Unified publication state for all GLANCE entry types.

    This enum captures the life cycle of an analysis entry across its transition
    from internal status to PUB, CONF, or journal paper.

    """

    CLOSED = auto()
    ONGOING_WO_EB = auto()
    ONGOING_WITH_EB = auto()
    PREAPPROVED = auto()
    PAST_PHASE0 = auto()  # Temporary state, should be overriden.
    PHASE1_OR_2 = auto()
    SUBMITTED_TO_JOURNAL = auto()
    PUBLISHED = auto()
    SUPERSEDED = auto()
    UNKNOWN = auto()
