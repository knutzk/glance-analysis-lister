"""Module that provides subgroup definitions.


"""

from collections import namedtuple

# Named tuple definition used for the subgroups, see below.
Subgroup = namedtuple("Subgroup", "code id title output_dir")

# Define the three main subgroups of the top group.
TX = Subgroup("TX", "TOPQ - Top Quarks + X", "Top+X", "docs/analyses/topx")
XS = Subgroup("XS", "TOPQ - Cross-section", "Top Cross Section", "docs/analyses/xs")
PM = Subgroup(
    "PM",
    "TOPQ - Top Properties and Mass",
    "Top Properties & Mass",
    "docs/analyses/pm",
)

# Create a list object that contains all top subgroups.
TopGroups = [TX, XS, PM]
