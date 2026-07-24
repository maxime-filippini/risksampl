# Market-data scope audit

## Conclusion

The current market-data epic is technically coherent, but it is scoped for a
materially larger system than VaR Labs currently is or needs to become for its
first public release.

The epic explicitly targets 10,000 active instruments, 25 years of history,
hundreds to thousands of daily calculations, independently scalable workers,
and a hard 09:00 business deadline. The current repository represents 50
instruments and 50 portfolios. Its local market-data export is 4.5 MB in
Parquet despite containing 1,445,272 long-format rows across multiple price
fields. The first release is a solo-developed public portfolio project with an
accepted single-host failure boundary, not an operational risk platform.

The valuable core should remain:

- immutable, identifiable market-data snapshots;
- reproducible Publications tied to pinned inputs and definitions;
- Corrections that supersede rather than overwrite;
- preserved provider evidence where licensing permits;
- calendar-correct calculations and explicit staleness;
- checksums, schema versions, and a deliberate legacy cutover.

The initial release should not include Redis, Celery, multiple queues, weekly
compaction, concurrent snapshot publishers, automated correction fan-out,
enterprise incident management, or a hard morning SLA.

Sources: [epic #21](https://github.com/maxime-filippini/risksampl/issues/21),
[`worker/data/etfs.json`](../worker/data/etfs.json),
[`worker/notebooks/ptfs.json`](../worker/notebooks/ptfs.json).

## Recommended first-release topology

Use one `risksampl-services` image containing one-shot CLI commands rather than
long-running worker roles:

1. Coolify schedules one daily publication command.
2. The command fetches provider data, preserves the raw response, validates it,
   writes one immutable canonical snapshot and manifest to R2, calculates all
   reference portfolios, writes one immutable Publication Revision, and updates
   PostgreSQL only after validation succeeds.
3. PostgreSQL records the run, current snapshot/publication pointers, and
   application-facing results.
4. Backfill and Correction commands use the same image and are invoked manually.
5. Sentry supplies error reporting, one uptime monitor, and one cron monitor.

This removes Redis, Celery Beat, three worker processes, queue canaries, and
queue recovery. A PostgreSQL advisory lock or unique run key is sufficient to
prevent overlapping publication commands at this scale.

Use one private R2 artifact bucket with explicit prefixes for Raw Provider
Responses, Canonical Market Data Snapshots, Market Data Input Snapshots, and
Publications. Use a separate operational-backup bucket with independent
credentials and retention. VaR Labs publishes VaR estimates and comparisons;
it does not publish or expose market data.

## Epic changes

The applied backlog reset revised
[#21](https://github.com/maxime-filippini/risksampl/issues/21) to:

- Replace the 10,000-instrument target with the measured initial scale of
  approximately 50 instruments and 50 reference portfolios.
- Make daily publication best effort, visibly timestamped, and monitored rather
  than a hard 09:00 SLA.
- Remove independent worker scaling from v1.
- Replace immutable deltas plus weekly compaction with one complete immutable
  canonical snapshot per successful ingestion. Measure storage and read
  performance before introducing deltas.
- Remove Redis/Celery, multi-queue routing, exact-cache outage operation,
  automated Correction fan-out, and comprehensive incident management from v1.
- Keep the Marketstack rights check as a production gate.

## Ticket-by-ticket recommendation

| Ticket | Recommendation | First-release scope |
| --- | --- | --- |
| [#22](https://github.com/maxime-filippini/risksampl/issues/22) First canonical snapshot | Rewritten and open | Publish one complete immutable Parquet snapshot and versioned manifest with checksum; load it directly into Polars. |
| [#23](https://github.com/maxime-filippini/risksampl/issues/23) Backfill and enable | Rewritten and open | Backfill one instrument, preserve its raw response, validate coverage, and enable it after success. |
| [#24](https://github.com/maxime-filippini/risksampl/issues/24) Suspend/reactivate | Closed as deferred | Use an `enabled` flag and explicit catch-up until effective-dated lifecycle history is demonstrated as necessary. |
| [#25](https://github.com/maxime-filippini/risksampl/issues/25) Incremental ingestion and validation | Rewritten and open | Fetch only recent provider data plus an overlap, merge a complete candidate snapshot, and produce versioned per-instrument errors and warnings. |
| [#26](https://github.com/maxime-filippini/risksampl/issues/26) Corporate actions | Closed as deferred | Preserve raw data and provider fields; defer a reconciliation engine and separate corporate-actions dataset. |
| [#27](https://github.com/maxime-filippini/risksampl/issues/27) Compaction | Closed as deferred | Add deltas and compaction only after measurement justifies them. |
| [#28](https://github.com/maxime-filippini/risksampl/issues/28) Pinned canonical input | Rewritten and open | Resolve the latest authoritative eligible snapshot once and load it directly into Polars. |
| [#29](https://github.com/maxime-filippini/risksampl/issues/29) Generalized staleness | Closed as superseded | Calendar mapping and instrument eligibility now belong to #25 and #30. |
| [#30](https://github.com/maxime-filippini/risksampl/issues/30) Publication inputs | Rewritten and open | Materialize the exact Market Data Input Snapshot once per successful Publication Revision. |
| [#31](https://github.com/maxime-filippini/risksampl/issues/31) Celery and Redis | Closed as superseded | Replaced by the single scheduled command in #38. |
| [#32](https://github.com/maxime-filippini/risksampl/issues/32) 09:00 SLA | Closed as superseded | Replaced by best-effort scheduling, bounded retry, visible freshness, and Sentry cron monitoring in #38. |
| [#33](https://github.com/maxime-filippini/risksampl/issues/33) Corrections | Rewritten and open | Publish explicit operator-triggered immutable Corrections. |
| [#34](https://github.com/maxime-filippini/risksampl/issues/34) Schema evolution | Closed as deferred | Schema declaration and rejection belong to #22; migration waits for an actual schema v2. |
| [#35](https://github.com/maxime-filippini/risksampl/issues/35) Artifact governance | Rewritten and open | Govern two private R2 buckets, checksums, retention, credentials, and the Marketstack licence gate. |
| [#36](https://github.com/maxime-filippini/risksampl/issues/36) Monitoring | Closed as superseded | Replaced by Sentry error, uptime, and cron monitoring in #38. |
| [#37](https://github.com/maxime-filippini/risksampl/issues/37) Legacy cutover | Rewritten and open | Cut over after the reduced workflow proves reproducibility and numerical equivalence. |
| [#38](https://github.com/maxime-filippini/risksampl/issues/38) Single-host topology | Created and open | Deploy one scheduled Python workflow with Coolify on Hetzner, PostgreSQL 18, R2, Sentry, and lightweight backups. |
| [#39](https://github.com/maxime-filippini/risksampl/issues/39) Resend contact form | Created and open | Deliver contact submissions through Resend and remove the database-backed inbox. |

All issue bodies were inspected on 2026-07-24. They were open, labeled
`ready-for-agent`, and had no comments.

## Revised dependency shape

Before the reset, the critical path was effectively:

`#22 → #23 → #25 → #27 → #31 → #32 → #33 → #37`

That path was dominated by deferred operational machinery. The applied
dependency path is:

`#22 → #23 → #25 → #28 → #30 → (#33, #35, #38) → #37`

Market calendars and retained publication provenance support the calculation
and publication steps. Manual Corrections remain available without blocking the
initial cutover.

Deployment ticket #38 does not block the first local canonical snapshot. It
defines the scheduled-command production topology and blocks only production
deployment and final cutover.

## Consequences for decisions made in the prior interview

Several earlier choices remain sound:

- SvelteKit owns the application and Drizzle owns PostgreSQL migrations.
- Python becomes `risksampl-services` and does not expose FastAPI.
- GitHub Actions builds immutable SHA-tagged images.
- Coolify manages one Hetzner VPS, PostgreSQL, runtime secrets, and deployment.
- PostgreSQL 18, standard R2 jurisdiction, Sentry, lightweight backups, and
  forward-only migrations remain appropriate.

These choices should be withdrawn from v1:

- Celery Beat and ingestion/calculation/maintenance workers;
- Redis and its persistence/recovery configuration;
- worker queue canaries;
- VPS-3 as an assumed minimum.

Begin with a Hetzner host sized around 4 vCPUs and 8 GB RAM, then resize only if
a representative end-to-end benchmark demonstrates the need.
