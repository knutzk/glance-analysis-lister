from typing import List
from analysis_lister.glance.analysis import Analysis
from analysis_lister.glance.paper import Paper
from analysis_lister.glance.enums import PublicationState


def render_analysis_table(analyses: List[Analysis]) -> str:
    lines = [
        "| Identifier | Title | EB PA A | Rel. | Start |",
        "| --- | --- | --- | --- | --- |",
    ]

    tickmark = "&#10003;&nbsp;"
    state_to_n_ticks = {
        PublicationState.PAST_PHASE0: 3,
        PublicationState.PREAPPROVED: 2,
        PublicationState.ONGOING_WITH_EB: 1,
    }

    for a in analyses:
        title = a.title_short.replace("|", "/")
        release_str = (
            "R25" if "R22" in a.keywords else "R21" if "R21" in a.keywords else ""
        )
        n_ticks = state_to_n_ticks.get(a.pub_state, 0)

        row = (
            f'| [{a.ref_code.replace("-", "&#8209;")}][{a.ref_code}] '
            f"| {title} "
            f"| {tickmark * n_ticks} "
            f"| {release_str} "
            f'| {a.date_start.replace("-", "&#8209;")} |'
        )
        lines.append(row)

    return "\n".join(lines) + "\n"


def render_paper_table(papers: List[Paper]) -> str:
    lines = [
        "| Identifier | Title | Submission | Publication |",
        "| --- | --- | --- | --- |",
    ]

    for p in papers:
        title = p.title_short.replace("|", "/")
        row = (
            f'| [{p.ref_code.replace("-", "&#8209;")}][{p.ref_code}] '
            f"| {title} "
            f'| {p.date_submission.replace("-", "&#8209;")} '
            f'| {p.date_publication.replace("-", "&#8209;")} |'
        )
        lines.append(row)

    return "\n".join(lines) + "\n"
