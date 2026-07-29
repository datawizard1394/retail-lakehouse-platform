# ADR 0001: Use a local-first reference engine

- **Status:** Accepted
- **Date:** 2026-07-28

## Context

A portfolio reviewer should be able to run and inspect the project without a
cloud subscription, credentials, a Spark cluster, or paid services. The design
must still make senior-level reliability concerns visible.

## Decision

Implement the domain pipeline with Python 3.11 standard-library primitives,
CSV contracts, deterministic generation, atomic writes, blocking quality gates,
and content-derived run IDs. Isolate cloud architecture as a documented
production evolution path and a clearly illustrative Terraform example.

## Consequences

Positive:

- complete tests run in seconds and offline;
- behavior is transparent and easy to review;
- rerun and failure semantics are directly testable; and
- no live infrastructure or employment experience is implied.

Trade-offs:

- CSV does not provide columnar performance or transactional table semantics;
- processing is single-node and snapshot-oriented; and
- cloud networking, identity, catalog, observability, and orchestration are
  represented as designs rather than deployed capabilities.

The package boundaries are intended to survive a later replacement of local I/O
with Spark and Delta Lake.

