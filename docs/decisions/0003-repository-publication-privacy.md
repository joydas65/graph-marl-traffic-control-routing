# Repository publication privacy and metadata sanitation

**Date:** 6 September 2026. **Classification:** repository hygiene, not scientific progress.

## Sanitation record and evidence boundaries

The completed, narrowly authorized repair corrected both author and committer
identity fields in six main commits. Eleven main commit IDs changed in total:
the six direct corrections and five structural descendants. The publication
branch's single feature commit was repaired separately.

This hygiene audit independently compared the original and replacement Git
objects using the private repair mapping. Corresponding trees, message bytes,
author and committer timestamps/timezones, and translated parent order were
preserved. Thirty-eight unaffected main commit objects remained identical.
The fourteen-file publication patch was also unchanged. The inherited
`baseline-shreya-dqn-original` tag object and target still match the preservation
record. All eight existing historical SHA references remain unchanged; they
identify historical validation provenance, not current checkout requirements.

Five old signature headers could not carry over after their signed parent
references changed. Their former GitHub-verified status is recorded in the
repair receipt; this audit did not repeat that historical remote query. The
replacement objects do not retain those invalidated signatures. Private backup
and mapping existence are recorded by the repair receipt; neither is published.

The later [PR #21 merge](https://github.com/joydas65/graph-marl-traffic-control-routing/pull/21)
is a **separate** GitHub-generated commit, not one of those five replacements.
Its two-parent topology and reviewed source tree were checked again, and GitHub
again reported a valid verified signature. Its legitimate service metadata was
not rewritten.

Targeted inspection still finds four local and two remote branches retaining
superseded affected ancestry. Their mapped equivalents are already represented
on sanitized main; the private disposition plan found no unique work, active
worktree use or open-PR association for those targets. Disposition remains a
proposal requiring fresh exact-ref authorization. No retained ref was changed.
The repair receipt also reports that a bounded sample of old objects remained
remotely retrievable; this task did not repeat that accessibility probe.
**Complete historical erasure is not established.**

## Decision: a bounded local push guard

[`check_push.py`](../../scripts/privacy/check_push.py) is a standard-library
checker using installed Git for read-only object inspection. The thin
[`pre-push`](../../scripts/privacy/pre-push) entry point invokes an installed
local snapshot, not whatever source happens to be in the current checkout.
The focused [synthetic Git tests](../../tests/test_publication_privacy_guard.py)
use temporary repositories and a filesystem-only bare remote, not GitHub.

The fixed historical trust boundary is the verified PR #21 merge:
`c9cf7ef9d8217d1badb8af2df9f473fb498a5632`.
It is an explicit local-policy value, never inferred from all local refs or
automatically advanced to a remote tip. Ordinary outgoing heads must descend
from it. A local denylist of superseded affected commit objects is checked
against full ancestry before historical exclusion, including merge-side
ancestry and objects already retained by another remote-tracking branch.

For every proposed branch update, the checker validates the old/new objects
and fast-forward relationship. New branches have an explicit zero-old-object
case. Deletion, non-fast-forward updates, unsupported refs/objects, missing
objects and malformed hook input require review; there is no rewrite bypass.
Every commit outside the fixed trusted ancestry has its **raw** author and
committer fields, message, committed paths and supported full-tree contents
checked. A sensitive value introduced and then removed within the same push
therefore remains detectable. Mailmap display names and safe configured
defaults cannot substitute for inspection of committed metadata.

The selected identity for future local work is `joydas65` with
`joydas.0111@gmail.com`; that personal email is intentionally public.
The local policy also records the existing approved account no-reply
attribution. A service-created merge outside trusted ancestry requires a
separately reviewed exact-object entry with expected author/committer fields
and merge topology. Merely spelling a service identity or attaching a signature
header is not proof of authorship or cryptographic verification. Unknown new
attribution requires review, not automatic rewriting of inherited work.

Policy keys are `version`, `trusted_checkpoint`, `blocked_commits`,
`sensitive_literals`, `allowed_identities`, `approved_service_commits`, and
`reviewed_home_path_blobs`.
Actual superseded identities and affected-object IDs belong only in reviewed
local policy/repair data. Public tests use synthetic identities; there is no
public blacklist or published private mapping.

The guard checks local-policy sensitive literals, home-directory paths,
credential-shaped material and committed private-evidence/key paths. It does
not classify every email, hash, number or slash as private, and it does not
exempt tests, documentation, JSON or XML. Supported material is bounded UTF-8
text; binary, symlink, submodule, unsupported-format and oversized material
requires review rather than being silently skipped. Diagnostics contain reason
codes, not matched values, paths or object IDs.

One unchanged historical synthetic fixture blob has explicit local review
approval for the generic home-path matcher only. Approval binds exact blob
bytes, not a filename, directory or file category. Sensitive-literal and
credential checks still apply, as do path/format/size checks; changed blobs
require review again. Commit messages and metadata are never covered by this
fixture exception. The historical fixtures themselves were not changed.

Inspection limits are 32 updates, 10,000 ancestry commits, 512 untrusted
commits, 4,096 files per tree, 128 KiB per commit object, 1 MiB per blob,
32 MiB of unique blob content, and a shared 30-second Git-inspection budget.
Replacement objects are disabled; shallow, grafted and partial/promisor
histories require review. Object inspection must not fetch missing content.

This is an accidental-leakage guard, **not complete DLP**. It does not prove
scientific correctness, permission to publish copyrighted material, absence of
all secrets, or cryptographic authorship. Local Git hooks are not a server-side
security boundary; clones do not inherit activation automatically.

## Repository-local installation and use

1. Review the checker and run only its focused offline tests:
   `python3 -S -B -m unittest discover -s tests -p 'test_publication_privacy_guard.py'`.
2. Run `sh scripts/privacy/pre-push --check-install`. Any configured
   `core.hooksPath` or existing default pre-push file/symlink stops this simple
   installation for review. Do not overwrite, disable or replace LFS,
   organizational or security hooks. Other hooks remain untouched.
3. With that gate clear, create a new private `privacy-guard` directory in the
   Git common directory. Install reviewed byte-copies of the checker and entry
   point there, a reviewed `policy.json`, and a `python-path` file containing
   one absolute path to the selected standard-library-capable interpreter.
   Keep policy and interpreter configuration private. Install the executable
   regular pre-push entry point in the default hook directory **last**, using
   non-overwriting copies. Do not change global/system configuration or a
   shell profile. This is a local installation, not a tracked configuration.
4. Verify the installed copies against the reviewed sources, existing-hook
   preservation, private configuration, and an explicit safe pre-push input.
   A missing checker, policy or interpreter, scanner exception, unsupported
   object or inspection limit must fail closed. Do not use `--no-verify` to
   publish a blocked change.
5. Keep `user.name`, `user.email` and `user.useConfigOnly=true` repository-local.
   Check identity-related environment overrides without printing their values.
   Before a push, inspect raw author **and** committer fields, messages and
   committed contents across the outgoing history; also review PR metadata.

The installed snapshot continues to run when an older branch lacks tracked
guard source. A branch not descending from the fixed checkpoint requires
review. Editing tracked guard code does not silently replace the installed
copy or advance trust: future installation changes require their own review.
Missing or deliberately disabled hook activation cannot be repaired by the
checker itself; verify activation rather than assuming every clone is guarded.

## Research continuity

This change does not alter B0/OD code, tests, contracts, historical evidence or
results. It provides no live integration, output writer, qualification consumer,
OD-calibration execution or treatment evidence. Readiness remains false.
After review of this hygiene PR and the private retained-ref plan, work should
return to the minimal OD integration layer, not another hygiene framework.
