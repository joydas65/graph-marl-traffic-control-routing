"""Offline publication-guard checks using disposable Git objects only.

Every identity and sensitive fixture is synthetic. No research module is
imported, and every push uses a temporary filesystem-only bare repository.
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts" / "privacy" / "check_push.py"
HOOK = ROOT / "scripts" / "privacy" / "pre-push"
ZERO = "0" * 40
SAFE = {"name": "Public Researcher", "email": "researcher@example.invalid"}
OTHER = {"name": "Other Researcher", "email": "other@example.invalid"}
HISTORICAL = {"name": "Inherited Researcher", "email": "inherited@example.invalid"}
SERVICE = {"name": "Synthetic Merge Service", "email": "service@example.invalid"}
NOREPLY = {"name": "Public Researcher", "email": "researcher@noreply.example.invalid"}
SENSITIVE = "retired-" + "work-identity@" + "example.invalid"


class PublicationPrivacyGuardTests(unittest.TestCase):
    """Exercise committed objects, not the final worktree or configured name."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="privacy-guard-test-")
        self.addCleanup(self.temporary.cleanup)
        self.area = Path(self.temporary.name)
        self.repo = self.area / "repository"
        self.repo.mkdir()
        self.env = {
            "PATH": os.environ.get("PATH", os.defpath),
            "LC_ALL": "C",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
        }
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", SAFE["name"])
        self.git("config", "user.email", SAFE["email"])
        self.git("config", "commit.gpgSign", "false")
        self.git("config", "core.autocrlf", "false")
        self.sequence = 0
        self.base = self.commit(author=HISTORICAL, committer=HISTORICAL)
        self.policy = {
            "version": 1,
            "trusted_checkpoint": self.base,
            "blocked_commits": [],
            "sensitive_literals": [SENSITIVE],
            "reviewed_home_path_blobs": [],
            "allowed_identities": [SAFE, NOREPLY],
            "approved_service_commits": [],
        }
        self.policy_path = self.repo / ".git" / "synthetic-policy.json"
        self.save_policy()

    def command(self, arguments, *, data=None, env=None, cwd=None):
        return subprocess.run(
            arguments,
            cwd=cwd or self.repo,
            env=env or self.env,
            input=data,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def git(self, *arguments, env=None):
        result = self.command(["git", *arguments], env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def identity_env(self, author, committer):
        env = dict(self.env)
        for role, identity in (("AUTHOR", author), ("COMMITTER", committer)):
            env[f"GIT_{role}_NAME"] = identity["name"]
            env[f"GIT_{role}_EMAIL"] = identity["email"]
            env[f"GIT_{role}_DATE"] = "2026-01-01T00:00:00+0000"
        return env

    def commit(self, files=None, *, message="Synthetic safe checkpoint", author=SAFE, committer=SAFE):
        self.sequence += 1
        if files is None:
            files = {f"fixture-{self.sequence}.txt": "Public synthetic text.\n"}
        for name, content in files.items():
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if content is None:
                path.unlink()
            elif isinstance(content, bytes):
                path.write_bytes(content)
            else:
                path.write_text(content, encoding="utf-8")
        self.git("add", "--all")
        self.git("commit", "-q", "--allow-empty", "-m", message,
                 env=self.identity_env(author, committer))
        return self.git("rev-parse", "HEAD")

    def save_policy(self):
        self.policy_path.write_text(json.dumps(self.policy), encoding="utf-8")

    def update(self, oid, *, old=ZERO, branch="main"):
        return f"refs/heads/{branch} {oid} refs/heads/{branch} {old}\n"

    def check(self, updates, *, policy_path=None):
        return self.command(
            [sys.executable, "-B", str(CHECKER), "--repo", str(self.repo),
             "--policy", str(policy_path or self.policy_path)],
            data=updates,
        )

    def assert_sanitized(self, result):
        output = result.stdout + result.stderr
        self.assertTrue(output.strip(), "The guard must explain its outcome.")
        self.assertLessEqual(len(output), 300)
        self.assertRegex(output, r"\A[A-Z0-9_:= .\-\n]+\Z")
        self.assertNotIn(SENSITIVE, output)
        self.assertNotIn(str(self.area), output)
        self.assertNotIn(OTHER["email"], output)
        self.assertNotIn("Traceback", output)

    def assert_allowed(self, result):
        self.assert_sanitized(result)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def assert_blocked(self, result, code=None):
        self.assert_sanitized(result)
        self.assertNotEqual(result.returncode, 0, "Unsafe publication was allowed.")
        if code is not None:
            self.assertIn(":" + code + "\n", result.stdout + result.stderr)

    def make_merge(self, *, side_author=SAFE, merge_author=SAFE, merge_committer=SAFE):
        self.commit({"main-side.txt": "Main-side synthetic work.\n"})
        self.git("checkout", "-q", "-b", "side", self.base)
        self.commit({"merge-side.txt": "Side synthetic work.\n"}, author=side_author)
        self.git("checkout", "-q", "main")
        self.git("merge", "-q", "--no-ff", "-m", "Synthetic merge", "side",
                 env=self.identity_env(merge_author, merge_committer))
        return self.git("rev-parse", "HEAD")

    def install_snapshot(self):
        directory = self.repo / ".git" / "privacy-guard"
        directory.mkdir()
        shutil.copyfile(CHECKER, directory / "check_push.py")
        shutil.copyfile(HOOK, directory / "pre-push")
        shutil.copyfile(self.policy_path, directory / "policy.json")
        (directory / "python-path").write_text(sys.executable + "\n", encoding="utf-8")
        installed = self.repo / ".git" / "hooks" / "pre-push"
        shutil.copyfile(HOOK, installed)
        installed.chmod(0o755)
        return directory, installed

    def install_gate(self):
        return self.command(["sh", str(HOOK), "--check-install"])

    def test_selected_raw_author_and_committer_are_accepted(self):
        tip = self.commit()
        self.assert_allowed(self.check(self.update(tip, old=self.base)))

    def test_trusted_historical_attribution_is_not_rewritten(self):
        self.assert_allowed(self.check(self.update(self.base)))
        self.assert_allowed(self.check(self.update(self.commit())))

    def test_narrow_approved_no_reply_identity_is_accepted(self):
        self.assert_allowed(self.check(self.update(self.commit(author=NOREPLY, committer=NOREPLY))))

    def test_unsafe_author_with_safe_committer_is_blocked(self):
        self.assert_blocked(self.check(self.update(self.commit(author=OTHER))), "AUTHOR_IDENTITY")

    def test_safe_author_with_unsafe_committer_is_blocked(self):
        self.assert_blocked(self.check(self.update(self.commit(committer=OTHER))), "COMMITTER_IDENTITY")

    def test_safe_repository_config_does_not_override_committed_identity(self):
        tip = self.commit(author=OTHER, committer=OTHER)
        self.assertEqual(self.git("config", "user.email"), SAFE["email"])
        self.assert_blocked(self.check(self.update(tip)), "AUTHOR_IDENTITY")

    def test_mailmap_does_not_sanitize_raw_committed_identity(self):
        mailmap = f'{SAFE["name"]} <{SAFE["email"]}> {OTHER["name"]} <{OTHER["email"]}>\n'
        tip = self.commit({".mailmap": mailmap}, author=OTHER)
        self.assert_blocked(self.check(self.update(tip)), "AUTHOR_IDENTITY")

    def test_exact_approved_service_merge_is_accepted(self):
        tip = self.make_merge(merge_author=SERVICE, merge_committer=SERVICE)
        self.policy["approved_service_commits"] = [{"oid": tip, "author": SERVICE, "committer": SERVICE}]
        self.save_policy()
        self.assert_allowed(self.check(self.update(tip)))

    def test_service_identity_alone_is_not_approval(self):
        tip = self.make_merge(merge_author=SERVICE, merge_committer=SERVICE)
        self.assert_blocked(self.check(self.update(tip)))

    def test_service_exception_requires_a_merge(self):
        ordinary = self.commit(author=SERVICE, committer=SERVICE)
        self.policy["approved_service_commits"] = [{"oid": ordinary, "author": SERVICE, "committer": SERVICE}]
        self.save_policy()
        self.assert_blocked(self.check(self.update(ordinary)))

    def test_service_merge_approval_requires_exact_raw_metadata(self):
        merge = self.make_merge(merge_author=SERVICE, merge_committer=SERVICE)
        self.policy["approved_service_commits"] = [{"oid": merge, "author": SAFE, "committer": SERVICE}]
        self.save_policy()
        self.assert_blocked(self.check(self.update(merge)))

    def test_sensitive_commit_message_is_blocked_without_echo(self):
        self.assert_blocked(self.check(self.update(self.commit(message="Synthetic " + SENSITIVE))), "SENSITIVE_LITERAL")

    def test_removed_intermediate_sensitive_content_is_still_blocked(self):
        self.commit({"intermediate.txt": SENSITIVE})
        tip = self.commit({"intermediate.txt": None})
        self.assertFalse((self.repo / "intermediate.txt").exists())
        self.assert_blocked(self.check(self.update(tip)), "SENSITIVE_LITERAL")

    def test_tests_docs_json_and_xml_are_not_blanket_excluded(self):
        fixtures = {
            "tests/synthetic.py": 'value = "' + SENSITIVE + '"\n',
            "docs/synthetic.md": "Synthetic note: " + SENSITIVE + "\n",
            "configs/synthetic.json": json.dumps({"synthetic": SENSITIVE}),
            "configs/synthetic.xml": "<synthetic>" + SENSITIVE + "</synthetic>\n",
        }
        for path, content in fixtures.items():
            with self.subTest(path=path):
                self.git("checkout", "-q", "--detach", self.base)
                self.assert_blocked(self.check(self.update(self.commit({path: content}))))

    def test_private_home_path_and_credential_shapes_are_blocked(self):
        fixtures = [
            "/" + "Users" + "/" + "synthetic-machine" + "/document.txt",
            "/" + "home" + "/" + "synthetic-machine" + "/document.txt",
            "C:" + "\\" + "Users" + "\\" + "synthetic-machine" + "\\document.txt",
            "AK" + "IA" + "A" * 16,
        ]
        for index, content in enumerate(fixtures):
            with self.subTest(case=index):
                self.git("checkout", "-q", "--detach", self.base)
                self.assert_blocked(self.check(self.update(self.commit({"synthetic.txt": content}))))

    def test_exact_reviewed_home_path_fixture_blob_is_accepted(self):
        content = "/" + "Users" + "/synthetic-machine/document.txt\n"
        tip = self.commit({"synthetic.txt": content})
        blob = self.git("rev-parse", tip + ":synthetic.txt")
        self.policy["reviewed_home_path_blobs"] = [blob]
        self.save_policy()
        self.assert_allowed(self.check(self.update(tip)))

    def test_changed_home_path_blob_does_not_inherit_old_review(self):
        content = "/" + "Users" + "/synthetic-machine/document.txt\n"
        original = self.commit({"synthetic.txt": content})
        self.policy["reviewed_home_path_blobs"] = [self.git("rev-parse", original + ":synthetic.txt")]
        self.save_policy()
        changed = self.commit({"synthetic.txt": content + "Changed synthetic fixture.\n"})
        self.assert_blocked(self.check(self.update(changed)), "PRIVATE_HOME_PATH")

    def test_reviewed_home_blob_still_rejects_policy_literal_and_credential(self):
        home_path = "/" + "Users" + "/synthetic-machine/document.txt\n"
        for content, reason in ((SENSITIVE, "SENSITIVE_LITERAL"),
                                ("AK" + "IA" + "A" * 16, "CREDENTIAL_PATTERN")):
            with self.subTest(reason=reason):
                self.git("checkout", "-q", "--detach", self.base)
                tip = self.commit({"synthetic.txt": home_path + content})
                self.policy["reviewed_home_path_blobs"] = [self.git("rev-parse", tip + ":synthetic.txt")]
                self.save_policy()
                self.assert_blocked(self.check(self.update(tip)), reason)

    def test_reviewed_blob_does_not_exempt_commit_message_home_path(self):
        content = "/" + "Users" + "/synthetic-machine/document.txt\n"
        tip = self.commit({"synthetic.txt": content}, message="Synthetic message " + content)
        self.policy["reviewed_home_path_blobs"] = [self.git("rev-parse", tip + ":synthetic.txt")]
        self.save_policy()
        self.assert_blocked(self.check(self.update(tip)), "PRIVATE_HOME_PATH")

    def test_regex_alternation_is_not_a_private_home_username(self):
        alternation = "/" + "Users" + "/|/" + "home" + "/"
        self.assert_allowed(self.check(self.update(self.commit({"synthetic.txt": alternation}))))

    def test_accidental_private_evidence_path_is_blocked(self):
        path = ".local-" + "evidence/synthetic.txt"
        self.assert_blocked(self.check(self.update(self.commit({path: "Synthetic only.\n"}))))

    def test_sensitive_committed_filename_is_blocked(self):
        self.assert_blocked(self.check(self.update(self.commit({SENSITIVE + ".txt": "Synthetic only.\n"}))))

    def test_public_scholarly_text_and_hashes_are_not_generically_private(self):
        text = "Public Researcher; https://example.invalid/paper; " + SAFE["email"] + "\n"
        text += "Public artifact identity: " + "abc123" * 10 + "abcd\n"
        self.assert_allowed(self.check(self.update(self.commit({"references.md": text}))))

    def test_new_branch_is_scanned_from_fixed_trust_boundary(self):
        self.assert_allowed(self.check(self.update(self.commit(), branch="new-safe")))
        self.assert_blocked(self.check(self.update(self.commit(author=OTHER), branch="new-unsafe")))

    def test_disconnected_new_branch_requires_review(self):
        tree = self.git("rev-parse", "HEAD^{tree}")
        disconnected = self.git("commit-tree", tree, "-m", "Synthetic unrelated root",
                                env=self.identity_env(SAFE, SAFE))
        self.assert_blocked(self.check(self.update(disconnected, branch="unrelated")))

    def test_multiple_proposed_updates_are_all_checked(self):
        first = self.commit()
        second = self.commit()
        self.assert_allowed(self.check(self.update(first, branch="first") + self.update(second, branch="second")))
        third = self.commit(committer=OTHER)
        self.assert_blocked(self.check(self.update(second, branch="first") + self.update(third, branch="second")))

    def test_merge_side_unsafe_ancestry_is_not_hidden(self):
        self.assert_blocked(self.check(self.update(self.make_merge(side_author=OTHER))))

    def test_affected_history_on_other_remote_tracking_ref_is_not_trusted(self):
        affected = self.commit()
        self.policy["blocked_commits"] = [affected]
        self.save_policy()
        self.git("update-ref", "refs/remotes/origin/retained-synthetic", affected)
        self.assert_blocked(self.check(self.update(self.commit(), branch="republished")), "BLOCKED_HISTORY")

    def test_unknown_remote_tip_does_not_advance_fixed_trust_boundary(self):
        unsafe = self.commit(author=OTHER)
        self.assert_blocked(self.check(self.update(self.commit(), old=unsafe)))

    def test_malformed_input_and_unavailable_objects_fail_closed(self):
        tip = self.commit()
        for data in ("not a ref update\n", "\n", self.update("f" * 40), self.update("invalid"),
                     self.update(tip, old="f" * 40), self.update(tip) + self.update(tip)):
            with self.subTest(shape=len(data)):
                self.assert_blocked(self.check(data))

    def test_no_proposed_updates_is_a_safe_no_op(self):
        self.assert_allowed(self.check(""))

    def test_missing_or_malformed_policy_fails_closed(self):
        tip = self.commit()
        self.assert_blocked(self.check(self.update(tip), policy_path=self.area / "absent-policy.json"))
        self.policy_path.write_text("{", encoding="utf-8")
        self.assert_blocked(self.check(self.update(tip)))

    def test_partial_or_promisor_repository_requires_review_before_object_access(self):
        tip = self.commit()
        for key, value in (("extensions.partialClone", "synthetic"),
                           ("remote.synthetic.promisor", "true")):
            with self.subTest(setting=key):
                self.git("config", key, value)
                self.assert_blocked(self.check(self.update(tip)), "PARTIAL_CLONE")
                self.assert_blocked(self.check(self.update("f" * 40)), "PARTIAL_CLONE")
                self.git("config", "--unset", key)

    def test_binary_and_oversized_content_require_review(self):
        for index, content in enumerate((b"synthetic\x00binary", b"a" * (2 * 1024 * 1024 + 1))):
            with self.subTest(case=index):
                self.git("checkout", "-q", "--detach", self.base)
                self.assert_blocked(self.check(self.update(self.commit({"unsupported.txt": content}))))

    def test_unsupported_file_format_requires_review_even_if_textual(self):
        self.assert_blocked(self.check(self.update(self.commit({"unsupported.opaque": "Synthetic text.\n"}))))

    def test_symlink_and_gitlink_require_review(self):
        (self.repo / "synthetic-link").symlink_to("unavailable-synthetic-target")
        self.assert_blocked(self.check(self.update(self.commit({}))))
        self.git("checkout", "-q", "--detach", self.base)
        self.git("update-index", "--add", "--cacheinfo", f"160000,{self.base},synthetic-submodule")
        self.git("commit", "-q", "-m", "Synthetic unsupported gitlink", env=self.identity_env(SAFE, SAFE))
        self.assert_blocked(self.check(self.update(self.git("rev-parse", "HEAD"))))

    def test_unsupported_ref_and_object_types_require_review(self):
        tip = self.commit()
        self.git("tag", "-a", "synthetic-tag", "-m", "Synthetic tag")
        tag = self.git("rev-parse", "synthetic-tag")
        tree = self.git("rev-parse", "HEAD^{tree}")
        for data in (f"refs/tags/synthetic-tag {tag} refs/tags/synthetic-tag {ZERO}\n", self.update(tree),
                     f"refs/notes/synthetic {tip} refs/notes/synthetic {ZERO}\n"):
            with self.subTest(kind=data.split()[0]):
                self.assert_blocked(self.check(data))

    def test_deletion_and_non_fast_forward_are_blocked(self):
        tip = self.commit()
        self.assert_blocked(self.check(f"(delete) {ZERO} refs/heads/main {tip}\n"))
        self.assert_blocked(self.check(self.update(self.base, old=tip)))

    def test_install_gate_accepts_empty_default_location_without_installing(self):
        before = self.git("config", "--local", "--list")
        self.assert_allowed(self.install_gate())
        self.assertFalse((self.repo / ".git" / "hooks" / "pre-push").exists())
        self.assertEqual(self.git("config", "--local", "--list"), before)

    def test_existing_default_hook_and_symlink_are_preserved(self):
        installed = self.repo / ".git" / "hooks" / "pre-push"
        sentinel = b"#!/bin/sh\nexit 73\n"
        installed.write_bytes(sentinel)
        installed.chmod(0o755)
        self.assert_blocked(self.install_gate())
        self.assertEqual(installed.read_bytes(), sentinel)
        installed.unlink()
        installed.symlink_to("missing-synthetic-hook")
        self.assert_blocked(self.install_gate())
        self.assertTrue(installed.is_symlink())
        self.assertEqual(os.readlink(installed), "missing-synthetic-hook")

    def test_custom_hooks_path_is_preserved_including_empty_setting(self):
        for value in (str(self.area / "synthetic-hooks"), ""):
            with self.subTest(empty=not value):
                self.git("config", "core.hooksPath", value)
                before = (self.repo / ".git" / "config").read_bytes()
                self.assert_blocked(self.install_gate())
                self.assertEqual((self.repo / ".git" / "config").read_bytes(), before)
                self.assertFalse((self.repo / ".git" / "hooks" / "pre-push").exists())

    def test_effective_global_hooks_path_is_preserved_without_real_global_config(self):
        synthetic_global = self.area / "synthetic-global.gitconfig"
        self.git("config", "--file", str(synthetic_global), "core.hooksPath", "synthetic-hooks")
        self.env["GIT_CONFIG_GLOBAL"] = str(synthetic_global)
        before = synthetic_global.read_bytes()
        self.assert_blocked(self.install_gate())
        self.assertEqual(synthetic_global.read_bytes(), before)
        self.assertFalse((self.repo / ".git" / "hooks" / "pre-push").exists())

    def test_installed_snapshot_works_without_checkout_checker(self):
        tip = self.commit()
        _, installed = self.install_snapshot()
        self.assertFalse((self.repo / "scripts" / "privacy" / "check_push.py").exists())
        self.assert_allowed(self.command([str(installed), "synthetic", "filesystem-only"], data=self.update(tip)))

    def test_installed_hook_fails_closed_when_snapshot_dependency_is_missing(self):
        tip = self.commit()
        directory, installed = self.install_snapshot()
        for name in ("check_push.py", "policy.json", "python-path"):
            with self.subTest(dependency=name):
                path = directory / name
                original = path.read_bytes()
                path.unlink()
                self.assert_blocked(self.command([str(installed), "synthetic", "filesystem-only"], data=self.update(tip)))
                path.write_bytes(original)

    def test_malformed_installed_checker_fails_closed_without_traceback(self):
        tip = self.commit()
        directory, installed = self.install_snapshot()
        (directory / "check_push.py").write_text("def malformed(\n", encoding="utf-8")
        self.assert_blocked(self.command([str(installed), "synthetic", "filesystem-only"], data=self.update(tip)))

    def test_real_git_invokes_hook_and_blocks_unsafe_filesystem_push(self):
        remote = self.area / "remote.git"
        result = self.command(["git", "init", "-q", "--bare", str(remote)])
        self.assertEqual(result.returncode, 0, result.stderr)
        safe_tip = self.commit()
        self.install_snapshot()
        push = self.command(["git", "-c", "protocol.file.allow=always", "push", str(remote), "main:main"])
        self.assertEqual(push.returncode, 0, push.stderr)
        unsafe_tip = self.commit(author=OTHER)
        push = self.command(["git", "-c", "protocol.file.allow=always", "push", str(remote), "main:main"])
        self.assertNotEqual(push.returncode, 0)
        self.assertNotIn(OTHER["email"], push.stdout + push.stderr)
        result = self.command(["git", "--git-dir", str(remote), "rev-parse", "refs/heads/main"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), safe_tip)
        self.assertNotEqual(result.stdout.strip(), unsafe_tip)


if __name__ == "__main__":
    unittest.main()
