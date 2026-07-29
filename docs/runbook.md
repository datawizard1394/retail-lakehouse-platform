# Operations runbook

This runbook applies to the local portfolio implementation. It provides the
same diagnostic sequence that would be automated and integrated with incident
management in a production platform.

## Normal run

```bash
make generate
make run
make quality
```

Success criteria:

- command exits with code 0;
- `_meta/quality_report.json` has `passed: true`;
- `_meta/pipeline_manifest.json` has `quality_gate: PASSED`;
- expected bronze, silver, and gold row counts are non-zero; and
- the manifest contains a checksum for every published table.

## Quality-gate failure

1. Read the failed check names and observed counts in the quality report.
2. Preserve the source files and input fingerprint; do not edit raw evidence.
3. Classify the issue as schema drift, invalid domain value, duplicate key,
   orphan relationship, or financial reconciliation.
4. Correct the source contract or transformation in a reviewed change.
5. Add a regression fixture that reproduces the failure.
6. Rerun the same bounded input and compare manifests.

The pipeline never publishes gold tables after a source or silver contract
failure.

## Partial or interrupted write

Each data file is atomically promoted, but a process interruption can occur
between tables. Rerun with the unchanged source directory. The input-derived run
ID and deterministic transformations replace each table without duplication.
Treat the final manifest as the commit marker for a complete run.

## Unexpected checksum drift

1. Confirm the input fingerprint is unchanged.
2. Compare Python version, pipeline version, and ingestion timestamp.
3. Inspect ordering and decimal normalization changes.
4. Diff the smallest drifting table and its upstream source.
5. Do not accept drift by simply refreshing expected hashes; explain it in the
   change review.

## Backfill

The local engine processes a complete input snapshot. For a portfolio backfill,
place the desired bounded synthetic dataset in a separate source directory and
write to a separate output directory. Never mix the evidence for two input
fingerprints.

## Service objectives for a production adaptation

Suggested starting targets, not measured claims for this local demo:

- 99.5% scheduled-run success per month;
- gold freshness under 60 minutes after source availability;
- zero unquarantined contract violations;
- recovery point aligned to source replay retention; and
- recovery time under two hours for a routine rerun.

