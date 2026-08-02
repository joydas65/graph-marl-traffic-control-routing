# GCQN/GCAC Drive Handover Provenance Audit

## Audit identity

- **Experiment:** `EXP-GRAPH-000`
- **Audit date:** 2 August 2026
- **Audit branch:** `audit/exp-graph-000-provenance`
- **Base commit:** `6a136079835fc3be11cfd549c7ac1faaaa371848`
- **Scope:** read-only inventory and structural provenance assessment of the local GCQN and GCAC handovers

Detailed relative paths, timestamps, hashes, duplicate membership, checkpoints, logs, and data remain in private manifests outside Git. This document records aggregate evidence only.

## Verdict

The two handovers are substantial and strongly related, but neither can yet be treated as an authoritative, reproducible paper repository.

- **GCQN** is the larger variant. It contains a root Git marker and additional embedded Git metadata, but the root `HEAD` does not resolve to a stored commit. It appears to be an incomplete or modified working-tree snapshot rather than a provenance-complete repository.
- **GCAC** is a smaller, highly overlapping variant. It has no root Git marker, although nested Git metadata is present. It appears to be a copied or exported source tree at its root, not a version-pinned repository.
- The archives share 12,906 equal-content files at equal relative paths and differ at 210 equal relative paths. GCAC has only 30 archive-specific paths, while GCQN has 18,609. This is consistent with shared code lineage, but it does not by itself establish which files produced the paper's reported results.

The handovers are suitable for the next semantic mapping and execution-readiness audits. They are not yet suitable for training claims, baseline reproduction claims, or algorithm repair.

## Method

The audit utility uses the Python standard library only. It walks each supplied root without following directory symlinks, records relative POSIX paths, entry types, sizes, UTC modification times, and SHA-256 values, and writes deterministic JSON and CSV evidence outside the repository.

The utility also reports internal duplicate hashes, equal relative paths with equal or different content, archive-specific paths, cross-archive duplicate hashes, unreadable entries, and aggregate Git-marker structure. Two independent inventory runs were byte-for-byte identical across all seven outputs.

These are static provenance findings only. They do not provide runtime evidence about imports, algorithm execution, simulator compatibility, training, evaluation, or reported performance.

No source file, dataset, checkpoint, log, or Git metadata in either handover was changed or copied into this repository.

## Aggregate inventory

| Measure | GCQN | GCAC |
|---|---:|---:|
| Files | 29,184 | 13,140 |
| Directories | 4,566 | 2,031 |
| File bytes | 458,999,601 | 341,321,191 |
| Readable files | 29,184 | 13,140 |
| Unreadable entries | 0 | 0 |
| Symlinks | 0 | 0 |
| Source-category entries | 2,917 | 2,651 |
| Configuration-category entries | 9,778 | 2,811 |
| Data-category entries | 601 | 581 |
| Checkpoint/model-category entries | 26 | 13 |
| Log-category entries | 45 | 10 |
| Documentation-category entries | 715 | 639 |
| Duplicate hash groups within archive | 1,691 | 636 |
| Files participating in internal duplicate groups | 12,229 | 3,814 |

Category counts are structural heuristics based on relative path components and extensions. They are useful for audit routing, not claims about semantic purpose.

## Git provenance

| Measure | GCQN | GCAC |
|---|---:|---:|
| Root Git marker | Present as a directory | Absent |
| Git directory markers across archive | 3 | 2 |
| Git file markers across archive | 2 | 2 |
| Structurally complete Git directories | 3 | 2 |
| Root `HEAD` resolves to a commit | No | Not applicable |

“Structurally complete” means that the marker contains the standard `HEAD`, configuration, refs, and objects structures. It does not prove that referenced commits and objects are complete. The failed GCQN root `HEAD` resolution is the reason this audit does not classify it as a full repository.

## Cross-archive comparison

| Relation | Count |
|---|---:|
| Union of relative paths | 33,780 |
| Relative paths present in both | 15,141 |
| Equal-content files at the same path | 12,906 |
| Different-content files at the same path | 210 |
| Same-type non-file entries at the same path | 2,025 |
| GCQN-only paths | 18,609 |
| GCAC-only paths | 30 |
| Cross-archive duplicate hash groups | 9,740 |

The large common-content set and the very small GCAC-only set suggest that GCAC is a related variant derived from a shared code base, while GCQN contains substantially more material. This is a structural inference; author intent and experimental lineage still require mentor confirmation or stronger provenance evidence.

## Status of earlier Drive observations

The earlier Drive review suggested that GCQN had root Git metadata, GCAC did not, and both contained source, configuration, data, model/checkpoint, and log material. Those statements are now locally verified at aggregate level.

Any earlier observation about specific internal filenames, directories, remotes, branches, commits, model artifacts, or experiment logs is still classified as **previously observed, not yet locally verified within this public audit**. Those details must remain private and require a later semantic audit before they support a research claim.

## Missing provenance and unresolved questions

- The authoritative commit or release used for the 2025 paper is not established.
- GCQN's root Git metadata cannot resolve its recorded `HEAD` commit.
- GCAC has no root-level version history.
- Archive export procedure, creation date, and completeness criteria are not documented by this audit.
- The mapping from archive variants to paper tables, figures, configurations, seeds, and reported numbers is not established.
- Dependency versions, simulator version, entry points, and expected runtime remain outside this audit's scope.
- Licence and redistribution terms for handover contents remain unconfirmed.

## Decision

Preserve the archives as read-only private evidence. Proceed next to a non-executing semantic map that relates paper components to code areas and identifies candidate entry points, configurations, environments, models, metrics, and artifacts without repairing or training them. Ask Shreya to confirm the authoritative variant and paper-result mapping before claiming reproduction.
