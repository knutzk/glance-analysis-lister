"""Enum classes for glance entries.


"""

from enum import Enum


class PublicationState(Enum):
    """Unified publication state for all GLANCE entry types.

    This enum captures the life cycle of an analysis entry across its transition
    from internal status to PUB, CONF, or journal paper.

    Each member carries its own name as value, so that the registry snapshot
    stores a readable state instead of a number whose meaning would depend on
    the order the members are declared in.

    Attributes:
        CLOSED (str): The analysis is closed.
        INACTIVE (str): The analysis is inactive.
        ONGOING_WO_EB (str): The analysis is ongoing without an editorial board.
        ONGOING_WITH_EB (str): The analysis is ongoing with an editorial board.
        PREAPPROVED (str): The analysis is preapproved.
        PAST_PHASE0 (str): The analysis has passed phase 0 (temporary state).
        PHASE1_OR_2 (str): The analysis is in phase 1 or 2.
        SUBMITTED_TO_JOURNAL (str): The analysis has been submitted to a journal.
        PUBLISHED (str): The analysis has been published.
        SUPERSEDED (str): The analysis has been superseded by another entry.
        UNKNOWN (str): The publication state is unknown.

    """

    CLOSED = "CLOSED"
    INACTIVE = "INACTIVE"
    ONGOING_WO_EB = "ONGOING_WO_EB"
    ONGOING_WITH_EB = "ONGOING_WITH_EB"
    PREAPPROVED = "PREAPPROVED"
    PAST_PHASE0 = "PAST_PHASE0"  # Temporary state, should be overriden.
    PHASE1_OR_2 = "PHASE1_OR_2"
    SUBMITTED_TO_JOURNAL = "SUBMITTED_TO_JOURNAL"
    PUBLISHED = "PUBLISHED"
    SUPERSEDED = "SUPERSEDED"
    UNKNOWN = "UNKNOWN"


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
