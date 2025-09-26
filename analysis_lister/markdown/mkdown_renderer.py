"""Generate Markdown pages for analyses and papers.


"""

from pathlib import Path
from ..glance.glance_registry import GlanceRegistry
from ..glance.subgroups import TopGroups
from .global_pages import (
    ongoing as glob_ongoing,
    published as glob_published,
    confnotes as glob_confnotes,
    pubnotes as glob_pubnotes,
)
from .subgroup_pages import (
    ongoing as sub_ongoing,
    overview as sub_overview,
    published as sub_published,
)


class MarkdownPageRenderer:
    """Class to generate Markdown pages for analyses and papers.

    This class generates Markdown pages for analyses and papers, both
    globally and for specific subgroups. It uses the GlanceRegistry
    to access the necessary data and creates the pages in the specified
    output directory. The pages include information about ongoing
    analyses, published papers, and an overview of all analyses and
    papers for each subgroup.

    The generated pages are saved in the specified output directory.

    Attributes:
        registry (GlanceRegistry): The GlanceRegistry instance to access data.
        output_dir (Path): The directory where the generated pages will be saved.
        threshold (str): The year threshold for filtering papers.
        mtime (str): The last modified time for the pages.
        analyses (list): Cached list of analyses.
        papers (list): Cached list of papers.

    Methods:
        write_global_pages(): Generate global overview pages (ongoing + published).
        write_subgroup_pages(): Generate ongoing, published, and overview pages for
        each subgroup.
        write_all(): Generate both global and subgroup pages.

    """

    def __init__(self, registry: GlanceRegistry, output_dir: Path, threshold_year: str):
        self.registry = registry
        self.output_dir = output_dir
        self.threshold = threshold_year
        self.mtime = registry.last_modified_time

        # Cache the commonly used data
        self.analyses = registry.analyses
        self.papers = registry.papers
        self.confnotes = registry.confnotes
        self.pubnotes = registry.pubnotes

    def write_global_pages(self):
        """Generate global overview pages (ongoing + published)."""
        glob_published.published(
            self.papers,
            output_dir=self.output_dir,
            last_modified=self.mtime,
            threshold=self.threshold,
        )
        glob_ongoing.ongoing_analyses(
            self.registry,
            output_dir=self.output_dir,
            last_modified=self.mtime,
        )
        glob_confnotes.confnotes(
            self.confnotes,
            output_dir=self.output_dir,
            last_modified=self.mtime,
            threshold=self.threshold,
        )
        glob_pubnotes.pubnotes(
            self.pubnotes,
            output_dir=self.output_dir,
            last_modified=self.mtime,
            threshold=self.threshold,
        )

    def write_subgroup_pages(self):
        """Generate ongoing, published, and overview pages for each subgroup."""
        for g in TopGroups:
            sub_output = self.output_dir / g.output_dir
            sub_output.mkdir(parents=True, exist_ok=True)

            sub_published.published_papers(
                self.papers,
                output_dir=sub_output,
                subgroup_title=g.title,
                subgroup_id=g.id,
                last_modified=self.mtime,
                threshold=self.threshold,
            )
            sub_ongoing.ongoing_analyses(
                self.analyses,
                output_dir=sub_output,
                subgroup_title=g.title,
                subgroup_id=g.id,
                last_modified=self.mtime,
            )
            sub_overview.overview(
                self.papers,
                self.analyses,
                output_dir=sub_output,
                subgroup_title=g.title,
                subgroup_id=g.id,
                last_modified=self.mtime,
                threshold=self.threshold,
            )

    def write_all(self):
        """Generate both global and subgroup pages."""
        self.write_global_pages()
        self.write_subgroup_pages()
