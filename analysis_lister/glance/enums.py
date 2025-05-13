from enum import Enum, auto


class PublicationState(Enum):
    """Unified publication state for all GLANCE entry types.

    This enum captures the life cycle of an analysis entry across its transition
    from internal status to PUB, CONF, or journal paper.

    The different states are:
        - CLOSED: The analysis is closed.
        - INACTIVE: The analysis is inactive.
        - ONGOING_WO_EB: The analysis is ongoing without an editorial board.
        - ONGOING_WITH_EB: The analysis is ongoing with an editorial board.
        - PREAPPROVED: The analysis is preapproved.
        - PAST_PHASE0: The analysis has passed phase 0 (temporary state, this
          should be overriden by a paper/CONF/PUB status).
        - PHASE1_OR_2: The analysis is in phase 1 or 2.
        - SUBMITTED_TO_JOURNAL: The analysis has been submitted to a journal.
        - PUBLISHED: The analysis has been published.
        - SUPERSEDED: The analysis has been superseded by another entry.
        - UNKNOWN: The publication state is unknown.

    """

    CLOSED = auto()
    INACTIVE = auto()
    ONGOING_WO_EB = auto()
    ONGOING_WITH_EB = auto()
    PREAPPROVED = auto()
    PAST_PHASE0 = auto()  # Temporary state, should be overriden.
    PHASE1_OR_2 = auto()
    SUBMITTED_TO_JOURNAL = auto()
    PUBLISHED = auto()
    SUPERSEDED = auto()
    UNKNOWN = auto()
