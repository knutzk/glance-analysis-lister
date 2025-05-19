"""Enum classes for glance entries.


"""

from enum import Enum, auto


class PublicationState(Enum):
    """Unified publication state for all GLANCE entry types.

    This enum captures the life cycle of an analysis entry across its transition
    from internal status to PUB, CONF, or journal paper.

    Attributes:
        CLOSED (auto): The analysis is closed.
        INACTIVE (auto): The analysis is inactive.
        ONGOING_WO_EB (auto): The analysis is ongoing without an editorial board.
        ONGOING_WITH_EB (auto): The analysis is ongoing with an editorial board.
        PREAPPROVED (auto): The analysis is preapproved.
        PAST_PHASE0 (auto): The analysis has passed phase 0 (temporary state).
        PHASE1_OR_2 (auto): The analysis is in phase 1 or 2.
        SUBMITTED_TO_JOURNAL (auto): The analysis has been submitted to a journal.
        PUBLISHED (auto): The analysis has been published.
        SUPERSEDED (auto): The analysis has been superseded by another entry.
        UNKNOWN (auto): The publication state is unknown.

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


class SoftwareRelease(Enum):
    """Enum class for software release types.

    This enum class represents the different types of software releases.

    Attributes:
        R21 (str): Represents the R21 software release.
        R25 (str): Represents the R25 software release.
        UNKNOWN (str): Represents an unknown software release.

    """

    R21 = "R21"
    R25 = "R25"
    UNKNOWN = ""
