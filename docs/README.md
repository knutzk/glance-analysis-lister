# Find your guide

Start with the demo to see what the package produces. Then use the topic guides
to understand and control your own group's pages. You do not need to know a
command name to choose where to go next.

## Try it first

- [Synthetic demo](../examples/README.md): generate a complete site without CERN credentials, then change its publication policy.
- [Add CERN data](cern-demo.md): display your own group's records alongside Demo in the same site.
- [Explore the live demo](../examples/demo/index.md): try the generated pages in this documentation site.

## Understand and use the package

| Your question | Guide |
| --- | --- |
| What comes from GLANCE, what is changed, and which files should I keep? | [Data and the curated registry](data.md) |
| Which analyses and publications appear for my group, and how can I change that? | [Choosing records](selection.md) |
| What do the cards, dates and statuses mean, and how do I search or share a view? | [Exploring the pages](pages.md) |
| Where do journal references come from, and how can I correct or add one? | [Citations](citations.md) |
| How do I put generated pages in my group's website and keep them updated? | [Building a group website](website.md) |
| Why is a record missing, what does a warning mean, or how do I resume a failed update? | [Warnings and recovery](problems.md) |

These guides introduce the data and decisions before the commands. They use
saved snapshots wherever possible; only fresh GLANCE downloads need CERN access.
Commands assume the repository root unless the guide says otherwise.

## Look up a precise detail

The **Reference** section collects supported options and contracts for integrations:

- [Commands and options](cli-reference.md)
- [Curated data format](curated-format.md)
- [Generated files, URLs and report fields](output-reference.md)
- [Python API](python-access.md)
- [Compatibility](compatibility.md) and [upgrading](upgrading.md)
- [Glossary](glossary.md)

## Extend or maintain the project

Start with the architecture to find the right layer, or follow the field example
to trace a concrete change from source data to a rendered page.

- [Architecture](architecture.md) and [field walkthrough](contributing-field.md)
- [Development and testing](development.md)
- [Maintaining the documentation](documentation.md)
- [Preparing releases](releases.md)
