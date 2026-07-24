# VaR Labs

VaR Labs is a public benchmark of Value at Risk estimates for fixed reference
portfolios. Its domain centers on reproducible daily publications rather than
live portfolio-risk monitoring.

## Language

**Market Data Input Snapshot**:
The complete, immutable set of normalized market observations used to calculate
one Publication. It preserves the values actually used even if the source later
changes or a correction is issued.
_Avoid_: Current market data, market-data cache

**Publication**:
An immutable, reproducible release of VaR results for one As-of Date, together
with the exact inputs and definitions from which those results were calculated.
_Avoid_: Daily run, database update

**Publication Revision**:
One immutable version of a Publication. Revisions for the same As-of Date form
an ordered history in which at most one revision is currently authoritative.
_Avoid_: Overwrite, replacement file

**Correction**:
A new Publication Revision that supersedes an earlier revision for the same
As-of Date while preserving the earlier revision and the reason for the change.
_Avoid_: Edit, backfill

**As-of Date**:
The market date represented by a Publication’s inputs and results.
_Avoid_: Run date, publication date
