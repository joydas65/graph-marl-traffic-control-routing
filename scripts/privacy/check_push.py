#!/usr/bin/env python3
"""Bounded, fail-closed inspection of proposed branch pushes using Git objects.

The private policy and installed hook live outside the tracked tree. This is
an accidental-leakage guard, not provenance authentication or complete DLP.
"""

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import select
import subprocess
import sys
import time


MAX_BLOB_BYTES = 1024 * 1024
MAX_COMMIT_BYTES = 128 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024
MAX_POLICY_BYTES = 64 * 1024
MAX_INPUT_BYTES = 64 * 1024
MAX_UPDATES = 32
MAX_COMMITS = 512
MAX_ANCESTRY = 10000
MAX_FILES = 4096
MAX_SECONDS = 30
OID = re.compile(r"[0-9a-f]{40}\Z")
ZERO = "0" * 40
TEXT_SUFFIXES = frozenset({
    ".py", ".sh", ".md", ".json", ".xml", ".ini", ".tex", ".csv",
    ".tsv", ".toml", ".yaml", ".yml", ".cfg", ".sumocfg", ".txt", ".rst",
})
TEXT_NAMES = frozenset({".gitignore", "agents", "readme", "license", "copying", "pre-push"})
PRIVATE_PARTS = frozenset({
    ".local-evidence", ".private", "private", "private-evidence", "private_source",
    "private-source", "private-handover", ".aws", ".ssh", "credentials",
    "checkpoints", "__pycache__",
})
PRIVATE_SUFFIXES = frozenset({".pem", ".key", ".p12", ".pfx", ".pt", ".pth", ".ckpt"})
HOME_PATH = re.compile(r"(?:/(?:Users|home)/[^/\s\"'<>|]+(?:/|\b)|[A-Za-z]:[\\/]Users[\\/][^\\/\s\"'<>|]+)")
CREDENTIAL = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"
    r"|\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"
    r"|\bgh[pousr]_[A-Za-z0-9]{20,}\b"
    r"|\bgithub_pat_[A-Za-z0-9_]{20,}\b"
    r"|\bxox[baprs]-[A-Za-z0-9-]{16,}\b"
    r"|\b(?:sk_live|sk_test)_[A-Za-z0-9]{16,}\b"
    r"|\b(?:password|secret_access_key|api_key|access_token)\s*[:=]\s*[\"'][A-Za-z0-9/+_=.-]{12,}[\"']",
    re.IGNORECASE,
)


class GuardFailure(Exception):
    def __init__(self, code, review=False):
        self.code = code
        self.review = review


def reject(code, review=False):
    raise GuardFailure(code, review)


def exact_keys(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        reject("POLICY_SCHEMA", True)


def identity(value):
    exact_keys(value, ("name", "email"))
    if any(not isinstance(value[key], str) or not value[key]
           or len(value[key]) > 512 or any(c in value[key] for c in "\r\n\x00<>")
           for key in ("name", "email")):
        reject("POLICY_IDENTITY", True)
    return value["name"], value["email"]


def object_id(value):
    if not isinstance(value, str) or not OID.fullmatch(value) or value == ZERO:
        reject("POLICY_OBJECT_ID", True)
    return value


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            reject("POLICY_DUPLICATE_KEY", True)
        result[key] = value
    return result


def load_policy(path):
    with open(path, "rb") as stream:
        raw = stream.read(MAX_POLICY_BYTES + 1)
    if len(raw) > MAX_POLICY_BYTES:
        reject("POLICY_SIZE", True)
    policy = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object)
    exact_keys(policy, ("version", "trusted_checkpoint", "blocked_commits",
                        "sensitive_literals", "allowed_identities", "approved_service_commits",
                        "reviewed_home_path_blobs"))
    if type(policy["version"]) is not int or policy["version"] != 1:
        reject("POLICY_VERSION", True)
    for key in ("blocked_commits", "sensitive_literals", "allowed_identities",
                "approved_service_commits", "reviewed_home_path_blobs"):
        if not isinstance(policy[key], list) or len(policy[key]) > 1024:
            reject("POLICY_LIST", True)
    policy["trusted_checkpoint"] = object_id(policy["trusted_checkpoint"])
    policy["blocked_commits"] = {object_id(value) for value in policy["blocked_commits"]}
    policy["reviewed_home_path_blobs"] = {
        object_id(value) for value in policy["reviewed_home_path_blobs"]
    }
    policy["allowed_identities"] = {identity(value) for value in policy["allowed_identities"]}
    if not policy["allowed_identities"]:
        reject("POLICY_IDENTITY", True)
    if any(not isinstance(value, str) or not value or len(value) > 4096
           or "\x00" in value for value in policy["sensitive_literals"]):
        reject("POLICY_LITERAL", True)
    policy["sensitive_literals"] = tuple(value.casefold() for value in policy["sensitive_literals"])
    services = {}
    for service in policy["approved_service_commits"]:
        exact_keys(service, ("oid", "author", "committer"))
        oid = object_id(service["oid"])
        if oid in services:
            reject("POLICY_DUPLICATE_SERVICE", True)
        services[oid] = (identity(service["author"]), identity(service["committer"]))
    policy["approved_service_commits"] = services
    return policy


class Git:
    """Read-only Git commands with bounded output and a shared wall-clock budget."""

    def __init__(self, repo):
        self.repo = Path(repo).resolve(strict=True)
        self.deadline = time.monotonic() + MAX_SECONDS
        self.env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        self.env.update(GIT_NO_REPLACE_OBJECTS="1", GIT_NO_LAZY_FETCH="1", GIT_OPTIONAL_LOCKS="0",
                        GIT_TERMINAL_PROMPT="0", GIT_CONFIG_NOSYSTEM="1",
                        GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)

    def run(self, *args, limit=MAX_COMMIT_BYTES, accepted=(0,)):
        if time.monotonic() >= self.deadline:
            reject("TIME_LIMIT", True)
        with subprocess.Popen(["git", "--no-replace-objects", *args], cwd=self.repo,
                              env=self.env, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as process:
            output = bytearray()
            try:
                while True:
                    remaining = self.deadline - time.monotonic()
                    if remaining <= 0:
                        reject("TIME_LIMIT", True)
                    readable, _, _ = select.select([process.stdout], [], [], remaining)
                    if not readable:
                        reject("TIME_LIMIT", True)
                    chunk = os.read(process.stdout.fileno(), min(65536, limit + 1 - len(output)))
                    if not chunk:
                        break
                    output.extend(chunk)
                    if len(output) > limit:
                        reject("OBJECT_SIZE_LIMIT", True)
                code = process.wait(timeout=max(0.001, self.deadline - time.monotonic()))
            except BaseException:
                process.kill()
                process.wait()
                raise
        if code not in accepted:
            reject("GIT_OBJECT_UNAVAILABLE", True)
        return bytes(output), code

    def require_commit(self, oid):
        raw, _ = self.run("cat-file", "-t", oid)
        if raw != b"commit\n":
            reject("UNSUPPORTED_OBJECT_TYPE", True)

    def ancestry(self, oid):
        raw, _ = self.run("rev-list", "--max-count=" + str(MAX_ANCESTRY + 1), oid,
                          limit=(MAX_ANCESTRY + 1) * 41)
        values = raw.decode("ascii").splitlines()
        if len(values) > MAX_ANCESTRY:
            reject("ANCESTRY_LIMIT", True)
        if not values or any(not OID.fullmatch(value) for value in values):
            reject("ANCESTRY_FORMAT", True)
        return set(values)


def read_updates(raw):
    if len(raw) > MAX_INPUT_BYTES:
        reject("INPUT_LIMIT", True)
    lines = raw.decode("utf-8").splitlines()
    if len(lines) > MAX_UPDATES:
        reject("UPDATE_LIMIT", True)
    updates = []
    destinations = set()
    for line in lines:
        fields = line.split()
        if len(fields) != 4:
            reject("MALFORMED_INPUT", True)
        local_ref, new, remote_ref, old = fields
        if not OID.fullmatch(new) or not OID.fullmatch(old):
            reject("MALFORMED_INPUT", True)
        if new == ZERO:
            reject("DELETION")
        if not remote_ref.startswith("refs/heads/"):
            reject("UNSUPPORTED_REF", True)
        if not (local_ref == "HEAD" or local_ref.startswith("refs/heads/")):
            reject("UNSUPPORTED_REF", True)
        if remote_ref in destinations:
            reject("DUPLICATE_DESTINATION", True)
        destinations.add(remote_ref)
        updates.append((local_ref, new, remote_ref, old))
    return updates


def scan_text(value, policy, *, reviewed_home_path_blob=False):
    folded = value.casefold()
    if any(literal in folded for literal in policy["sensitive_literals"]):
        reject("SENSITIVE_LITERAL")
    if not reviewed_home_path_blob and HOME_PATH.search(value):
        reject("PRIVATE_HOME_PATH")
    if CREDENTIAL.search(value):
        reject("CREDENTIAL_PATTERN")


def scan_path(path, policy):
    scan_text(path, policy)
    parts = tuple(path.split("/"))
    if (not parts or any(part in ("", ".", "..") for part in parts) or path.startswith("/")
            or any(ord(character) < 32 or ord(character) == 127 for character in path)):
        reject("TREE_PATH_FORMAT", True)
    folded = tuple(part.casefold() for part in parts)
    name = folded[-1]
    suffix = PurePosixPath(name).suffix
    if (set(folded) & PRIVATE_PARTS or name == ".env" or name.startswith(".env.")
            or suffix in PRIVATE_SUFFIXES or PurePosixPath(name).stem in ("credentials", "secrets")
            or name in ("id_rsa", "id_ed25519", "id_ecdsa")):
        reject("PRIVATE_MATERIAL_PATH")
    if suffix not in TEXT_SUFFIXES and name not in TEXT_NAMES:
        reject("UNSUPPORTED_CONTENT_FORMAT", True)


def raw_identity(value):
    match = re.fullmatch(r"([^\r\n\x00<>]+) <([^\r\n\x00<>]+)> -?\d+ [+-]\d{4}", value)
    if match is None:
        reject("COMMIT_IDENTITY_FORMAT", True)
    return match.group(1), match.group(2)


def scan_commit(git, oid, policy, scanned_blobs, totals):
    raw, _ = git.run("cat-file", "commit", oid)
    header, separator, message = raw.partition(b"\n\n")
    if not separator:
        reject("COMMIT_FORMAT", True)
    scan_text(header.decode("utf-8"), policy)
    fields = {}
    for line in header.decode("utf-8").splitlines():
        if line.startswith(" "):
            continue
        key, delimiter, value = line.partition(" ")
        if not delimiter:
            reject("COMMIT_FORMAT", True)
        fields.setdefault(key, []).append(value)
    if any(len(fields.get(key, [])) != 1 for key in ("tree", "author", "committer")):
        reject("COMMIT_FORMAT", True)
    author = raw_identity(fields["author"][0])
    committer = raw_identity(fields["committer"][0])
    service = policy["approved_service_commits"].get(oid)
    approved_service = service == (author, committer) and len(fields.get("parent", [])) >= 2
    if author not in policy["allowed_identities"] and not approved_service:
        reject("AUTHOR_IDENTITY", True)
    if committer not in policy["allowed_identities"] and not approved_service:
        reject("COMMITTER_IDENTITY", True)
    for value in (*author, *committer, message.decode("utf-8")):
        scan_text(value, policy)
    raw_tree, _ = git.run("ls-tree", "-r", "-z", "--full-tree", oid,
                         limit=MAX_FILES * 4096)
    entries = raw_tree.split(b"\x00")
    if entries[-1] != b"" or len(entries) - 1 > MAX_FILES:
        reject("TREE_SIZE_OR_FORMAT", True)
    for entry in entries[:-1]:
        metadata, delimiter, path_bytes = entry.partition(b"\t")
        parts = metadata.split(b" ")
        if not delimiter or len(parts) != 3:
            reject("TREE_FORMAT", True)
        mode, kind, blob_bytes = parts
        if mode not in (b"100644", b"100755") or kind != b"blob":
            reject("UNSUPPORTED_TREE_OBJECT", True)
        scan_path(path_bytes.decode("utf-8"), policy)
        blob = blob_bytes.decode("ascii")
        if not OID.fullmatch(blob):
            reject("TREE_FORMAT", True)
        if blob in scanned_blobs:
            continue
        size, _ = git.run("cat-file", "-s", blob)
        size = int(size)
        if size < 0 or size > MAX_BLOB_BYTES:
            reject("BLOB_SIZE_LIMIT", True)
        totals[0] += size
        if totals[0] > MAX_TOTAL_BYTES:
            reject("TOTAL_CONTENT_LIMIT", True)
        content, _ = git.run("cat-file", "blob", blob, limit=MAX_BLOB_BYTES)
        if len(content) != size or b"\x00" in content:
            reject("BINARY_OR_OBJECT_FORMAT", True)
        # Local review may approve only a known synthetic home-path fixture's
        # exact bytes. All other checks, including every pathname, still apply.
        scan_text(content.decode("utf-8"), policy,
                  reviewed_home_path_blob=blob in policy["reviewed_home_path_blobs"])
        scanned_blobs.add(blob)


def check(repo, policy_path, raw_input):
    policy = load_policy(policy_path)
    updates = read_updates(raw_input)
    git = Git(repo)
    _, partial = git.run("config", "--get-regexp",
                         r"^(extensions\.partialclone|remote\..*\.(promisor|partialclonefilter))$",
                         accepted=(0, 1))
    if partial == 0:
        reject("PARTIAL_CLONE", True)
    shallow, _ = git.run("rev-parse", "--is-shallow-repository")
    if shallow != b"false\n":
        reject("INCOMPLETE_ANCESTRY", True)
    common, _ = git.run("rev-parse", "--git-common-dir")
    common_path = Path(os.fsdecode(common.rstrip(b"\n")))
    if not common_path.is_absolute():
        common_path = git.repo / common_path
    if os.path.lexists(common_path / "info" / "grafts"):
        reject("GRAFTED_ANCESTRY", True)
    git.require_commit(policy["trusted_checkpoint"])
    trusted = git.ancestry(policy["trusted_checkpoint"])
    outgoing = set()
    for local_ref, new, remote_ref, old in updates:
        for ref in (local_ref, remote_ref):
            if ref != "HEAD":
                git.run("check-ref-format", ref)
        git.require_commit(new)
        ancestry = git.ancestry(new)
        if ancestry & policy["blocked_commits"]:
            reject("BLOCKED_HISTORY")
        if policy["trusted_checkpoint"] not in ancestry:
            reject("CHECKPOINT_NOT_ANCESTOR", True)
        if old != ZERO:
            git.require_commit(old)
            _, code = git.run("merge-base", "--is-ancestor", old, new, accepted=(0, 1))
            if code != 0:
                reject("NON_FAST_FORWARD")
        outgoing.update(ancestry - trusted)
        if len(outgoing) > MAX_COMMITS:
            reject("COMMIT_LIMIT", True)
    scanned_blobs = set()
    totals = [0]
    for oid in sorted(outgoing):
        scan_commit(git, oid, policy, scanned_blobs, totals)
    if time.monotonic() > git.deadline:
        reject("TIME_LIMIT", True)


class QuietParser(argparse.ArgumentParser):
    def error(self, message):
        reject("ARGUMENTS", True)


def main():
    try:
        parser = QuietParser(description=__doc__, add_help=False)
        parser.add_argument("--repo", required=True)
        parser.add_argument("--policy", required=True)
        args = parser.parse_args()
        check(args.repo, args.policy, sys.stdin.buffer.read(MAX_INPUT_BYTES + 1))
    except GuardFailure as error:
        status = "REVIEW_REQUIRED" if error.review else "BLOCKED"
        print("PRIVACY_GUARD=" + status + ":" + error.code)
        return 1
    except (Exception, KeyboardInterrupt):
        print("PRIVACY_GUARD=REVIEW_REQUIRED:INSPECTION_ERROR")
        return 1
    print("PRIVACY_GUARD=PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
