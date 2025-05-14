from pathlib import Path
from ..glance.glance_registry import GlanceRegistry
from ..glance.subgroups import TopGroups

from .global_pages import (
    ongoing as glob_ongoing,
    published as glob_published,
)
from .subgroup_pages import (
    ongoing as sub_ongoing,
    overview as sub_overview,
    published as sub_published,
)


class MarkdownPageRenderer:
    def __init__(self, registry: GlanceRegistry, output_dir: Path, threshold_year: str):
        self.registry = registry
        self.output_dir = output_dir
        self.threshold = threshold_year
        self.mtime = registry.determine_last_modified_time()

    def write_global_pages(self):
        glob_published.published(
            self.registry.papers_filtered,
            output_dir=self.output_dir,
            last_modified=self.mtime,
            threshold=self.threshold,
        )
        glob_ongoing.ongoing_analyses(
            self.registry.analyses_filtered,
            output_dir=self.output_dir,
            last_modified=self.mtime,
        )

    def write_subgroup_pages(self):
        for g in TopGroups:
            sub_output = self.output_dir / g.output_dir
            sub_published.published_papers(
                self.registry.papers_filtered,
                output_dir=sub_output,
                subgroup_title=g.title,
                subgroup_id=g.id,
                last_modified=self.mtime,
                threshold=self.threshold,
            )
            sub_ongoing.ongoing_analyses(
                self.registry.analyses_filtered,
                output_dir=sub_output,
                subgroup_title=g.title,
                subgroup_id=g.id,
                last_modified=self.mtime,
            )
            sub_overview.overview(
                self.registry.papers_filtered,
                self.registry.analyses_filtered,
                output_dir=sub_output,
                subgroup_title=g.title,
                subgroup_id=g.id,
                last_modified=self.mtime,
                threshold=self.threshold,
            )

    def write_all(self):
        self.write_global_pages()
        self.write_subgroup_pages()
