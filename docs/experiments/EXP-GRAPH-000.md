# EXP-GRAPH-000: GCQN/GCAC Handover Provenance Audit

## Status

Initial audit completed on 2 August 2026. No algorithm execution, repair, dependency installation, or training was performed.

All results in this record are static provenance evidence, not runtime evidence for either research implementation.

## Question

What was actually delivered in the private GCQN and GCAC handovers, how closely are the two trees related, and is either handover a provenance-complete repository suitable for a reproduction baseline?

## Evidence identity

- **Branch:** `audit/exp-graph-000-provenance`
- **Base commit:** `6a136079835fc3be11cfd549c7ac1faaaa371848`
- **Inventory-script runtime only:** Python 3.13.5; this is not a validated research or training environment
- **Inventory implementation:** Python standard library only
- **Private evidence:** two sets of deterministic JSON/CSV manifests stored outside Git
- **Seeds:** not applicable
- **Training configuration:** not applicable

## Procedure

1. Confirm that the two supplied roots are distinct directories and do not overlap the output directory.
2. Traverse both handovers read-only without following directory symlinks.
3. Inventory entry type, size, UTC modification time, and SHA-256 using relative POSIX paths only.
4. Detect internal duplicate hashes and compare equal relative paths across the two archives.
5. Record aggregate embedded Git structure and test whether GCQN's root `HEAD` resolves.
6. Run the inventory twice into separate private output directories.
7. Compare every generated output by SHA-256 and scan the manifests for absolute local-path leakage.

## Aggregate result

| Measure | GCQN | GCAC |
|---|---:|---:|
| Files | 29,184 | 13,140 |
| File bytes | 458,999,601 | 341,321,191 |
| Unreadable entries | 0 | 0 |
| Internal duplicate hash groups | 1,691 | 636 |
| Root Git marker | Yes | No |

Cross-archive results:

- 15,141 common relative paths;
- 12,906 equal-content files at equal relative paths;
- 210 different-content files at equal relative paths;
- 18,609 GCQN-only paths and 30 GCAC-only paths; and
- 9,740 cross-archive duplicate hash groups.

Both runs produced seven outputs, with zero SHA-256 mismatches. Fourteen private output files were scanned with zero absolute-path leaks.

## Interpretation

GCQN appears to be a larger incomplete or modified working-tree snapshot: it has root Git structure, but its recorded `HEAD` cannot be resolved to a commit. GCAC appears to be a smaller related source-tree export with no root Git provenance. Their strong overlap is consistent with common lineage but does not identify the authoritative paper implementation or the files that generated reported results.

## Decision

- Keep all detailed inventory evidence private and outside Git.
- Do not repair or train either handover yet.
- Treat neither archive as a reproduced baseline.
- Begin a separate semantic paper-to-code mapping audit.
- Obtain mentor confirmation of authoritative variant, result mapping, environment, and licence expectations.

## Public evidence

The aggregate technical interpretation is recorded in [`../research/shreya-drive-handover-audit.md`](../research/shreya-drive-handover-audit.md). Detailed relative paths, hashes, timestamps, duplicates, logs, checkpoints, and datasets are intentionally excluded.
