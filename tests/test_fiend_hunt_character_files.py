"""A newer character list reaches a PC's git checkout at start (Leo 2026-10-07)."""

import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.tasks.fiend_hunt import character_files as files

REPO_PATH = "data"
HAS_GIT = shutil.which("git") is not None


def git(folder, *args):
    subprocess.run(
        ["git", "-C", str(folder), *args],
        check=True,
        capture_output=True,
        env={
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.com",
            "PATH": __import__("os").environ["PATH"],
            "HOME": str(folder),
        },
    )


def remove(path):
    """rmtree that also deletes git's read-only object files (Windows refuses them)."""

    def writable(function, name, _error):
        os.chmod(name, stat.S_IWRITE)
        function(name)

    shutil.rmtree(path, onexc=writable)


def write_list(folder, costumes, pictures):
    data = folder / REPO_PATH
    (data / "costumes").mkdir(parents=True, exist_ok=True)
    listing = {"characters": [{"id": "A", "name_zh_cn": "甲", "costumes": costumes}]}
    (data / "characters.json").write_text(json.dumps(listing, ensure_ascii=False), "utf-8")
    for name in pictures:
        (data / "costumes" / f"{name}.webp").write_bytes(name.encode())


@unittest.skipUnless(HAS_GIT, "needs git")
class RefreshTest(unittest.TestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp())
        self.addCleanup(remove, self.folder)
        self.github = self.folder / "github"
        self.github.mkdir()
        git(self.github, "init", "-q", "-b", "main")
        write_list(self.github, [{"id": "A_1"}], ["A_1"])
        git(self.github, "add", ".")
        git(self.github, "commit", "-q", "-m", "first")
        self.pc = self.folder / "pc"
        git(self.folder, "clone", "-q", str(self.github), str(self.pc))
        data = self.pc / REPO_PATH
        update = self.pc / "configs" / "characters"
        patches = {
            "ROOT": self.pc,
            "REPO_PATH": REPO_PATH,
            "BUNDLED_FILE": data / "characters.json",
            "BUNDLED_PORTRAITS": data / "costumes",
            "UPDATE": update,
            "UPDATE_FILE": update / "characters.json",
            "UPDATE_PORTRAITS": update / "costumes",
            "UPDATE_BASE": update / "base.txt",
        }
        for name, value in patches.items():
            patcher = mock.patch.object(files, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def github_adds_a_costume(self):
        write_list(self.github, [{"id": "A_1"}, {"id": "A_2"}], ["A_1", "A_2"])
        git(self.github, "add", ".")
        git(self.github, "commit", "-q", "-m", "new costume")

    def ids(self):
        listing = json.loads(files.characters_file().read_text("utf-8"))
        return [c["id"] for c in listing["characters"][0]["costumes"]]

    def test_nothing_new(self):
        self.assertEqual("up to date", files.refresh())
        self.assertEqual(files.BUNDLED_FILE, files.characters_file())

    def test_a_newer_list_is_copied_beside_the_checkout(self):
        self.github_adds_a_costume()
        self.assertEqual("newer list copied (1 portraits)", files.refresh())
        self.assertEqual(["A_1", "A_2"], self.ids())
        self.assertEqual(files.UPDATE_PORTRAITS / "A_2.webp", files.portrait_file("A_2"))
        self.assertEqual(files.BUNDLED_PORTRAITS / "A_1.webp", files.portrait_file("A_1"))
        # the checkout itself is untouched: a pull later goes through
        status = subprocess.run(
            ["git", "-C", str(self.pc), "status", "--porcelain", "--", REPO_PATH],
            capture_output=True,
            text=True,
        ).stdout
        self.assertEqual("", status)

    def test_after_a_pull_the_shipped_list_is_used_again(self):
        self.github_adds_a_costume()
        files.refresh()
        git(self.pc, "pull", "-q")
        self.assertEqual(files.BUNDLED_FILE, files.characters_file())  # copy is stale
        self.assertEqual("up to date", files.refresh())
        self.assertFalse(files.UPDATE.exists())
        self.assertEqual(["A_1", "A_2"], self.ids())

    def test_a_checkout_ahead_of_github_keeps_its_own(self):
        write_list(self.pc, [{"id": "A_1"}, {"id": "A_9"}], ["A_1", "A_9"])
        git(self.pc, "add", ".")
        git(self.pc, "commit", "-q", "-m", "local")
        self.github_adds_a_costume()
        self.assertEqual("checkout not behind the branch", files.refresh())
        self.assertEqual(["A_1", "A_9"], self.ids())

    def test_no_network_changes_nothing(self):
        remove(self.github)
        self.assertEqual("fetch failed", files.refresh())
        self.assertEqual(files.BUNDLED_FILE, files.characters_file())

    def test_a_checkout_without_upstream_uses_the_remote_it_pulled_from(self):
        # Leo's PCs pull by hand (git pull mine <branch>): no upstream is set,
        # and another remote (the upstream project) lacks the branch
        git(self.pc, "branch", "--unset-upstream")
        git(self.pc, "remote", "rename", "origin", "mine")
        other = self.folder / "other"
        git(self.folder, "init", "-q", "-b", "elsewhere", str(other))
        git(self.pc, "remote", "add", "aaa", str(other))
        self.assertEqual(("mine", "main"), files._tracked_branch(subprocess.run))
        self.github_adds_a_costume()
        self.assertEqual("newer list copied (1 portraits)", files.refresh())

    def test_not_a_checkout(self):
        remove(self.pc / ".git")
        self.assertEqual("not a git checkout", files.refresh())


if __name__ == "__main__":
    unittest.main()
