import json
import os
import subprocess
import tempfile
import unittest

from skogai import store
from skogai.source import GitSource, blob_sha


def git(cwd, *args):
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=cwd, check=True, capture_output=True,
    )


def commit_all(repo, message):
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.realpath(self.tmp.name)
        # A stand-in for dash-skogai, with a local git history.
        self.dash = os.path.join(self.root, "dash")
        os.makedirs(os.path.join(self.dash, "fish"))
        subprocess.run(["git", "init", "-q", "-b", "main", self.dash], check=True)
        self.write_dash("config.defaults.json", '{"files": [{"source": "fish/config.fish"}]}\n')
        self.write_dash("fish/config.fish", "set -g fish_greeting\n")
        self.sha1 = commit_all(self.dash, "v1")
        self.store = os.path.join(self.root, "repo", ".skogai")
        self.lines = []

    def tearDown(self):
        self.tmp.cleanup()

    def write_dash(self, path, text):
        full = os.path.join(self.dash, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write(text)

    def read(self, path):
        with open(path) as f:
            return f.read()

    def src(self):
        return GitSource(self.dash)

    def init(self):
        with self.src() as s:
            return store.init(self.store, s, out=self.lines.append)

    def update(self, apply=False, ref="HEAD"):
        with self.src() as s:
            return store.update(self.store, s, ref, apply=apply, out=self.lines.append)

    def pins(self):
        return json.loads(self.read(os.path.join(self.store, "pins.json")))["files"]

    def base_sha(self):
        return json.loads(self.read(os.path.join(self.store, "config.json")))["base"]["sha"]

    def test_blob_sha_matches_git(self):
        data = b"hello\n"
        expected = subprocess.run(
            ["git", "hash-object", "--stdin"], input=data, capture_output=True, check=True
        ).stdout.decode().strip()
        self.assertEqual(blob_sha(data), expected)

    def test_init_copies_defaults_and_pins_the_commit(self):
        self.assertEqual(self.init(), 0)
        self.assertEqual(self.read(os.path.join(self.store, "fish/config.fish")), "set -g fish_greeting\n")
        self.assertEqual(self.base_sha(), self.sha1)
        self.assertEqual(self.pins(), {"fish/config.fish": blob_sha(b"set -g fish_greeting\n")})
        self.assertTrue(os.path.exists(os.path.join(self.store, "config.defaults.json")))

    def test_init_refuses_to_overwrite(self):
        self.init()
        with self.assertRaises(store.StoreError):
            self.init()

    def test_update_without_changes_is_clean(self):
        self.init()
        self.assertEqual(self.update(), 0)
        self.assertFalse(any("LOCAL-CHANGE" in line or "UPDATE" in line for line in self.lines))

    def test_update_dry_run_shows_diff_and_writes_nothing(self):
        self.init()
        self.write_dash("fish/config.fish", "set -g fish_greeting\nset -g x 1\n")
        sha2 = commit_all(self.dash, "v2")
        self.assertEqual(self.update(), 0)
        self.assertTrue(any(line.startswith("UPDATE") for line in self.lines))
        self.assertTrue(any("+set -g x 1" in line for line in self.lines))
        self.assertEqual(self.read(os.path.join(self.store, "fish/config.fish")), "set -g fish_greeting\n")
        self.assertEqual(self.base_sha(), self.sha1)
        self.assertNotEqual(sha2, self.sha1)

    def test_update_apply_moves_to_the_named_commit(self):
        self.init()
        self.write_dash("fish/config.fish", "set -g fish_greeting\nset -g x 1\n")
        sha2 = commit_all(self.dash, "v2")
        self.assertEqual(self.update(apply=True, ref=sha2), 0)
        self.assertEqual(self.read(os.path.join(self.store, "fish/config.fish")), "set -g fish_greeting\nset -g x 1\n")
        self.assertEqual(self.base_sha(), sha2)
        self.assertEqual(self.pins()["fish/config.fish"], blob_sha(b"set -g fish_greeting\nset -g x 1\n"))

    def test_local_edit_blocks_update_and_is_not_touched(self):
        self.init()
        local = os.path.join(self.store, "fish/config.fish")
        with open(local, "w") as f:
            f.write("my own change\n")
        self.write_dash("fish/config.fish", "upstream change\n")
        sha2 = commit_all(self.dash, "v2")
        self.assertEqual(self.update(apply=True, ref=sha2), 1)
        self.assertTrue(any(line.startswith("LOCAL-CHANGE") for line in self.lines))
        self.assertEqual(self.read(local), "my own change\n")
        self.assertEqual(self.base_sha(), self.sha1)

    def test_unpinned_file_in_the_way_is_a_local_change(self):
        self.init()
        # Drop the pin, so a file the defaults want exists but was never installed by us.
        with open(os.path.join(self.store, "pins.json"), "w") as f:
            json.dump({"files": {}}, f)
        self.assertEqual(self.update(), 1)
        self.assertTrue(any("not pinned" in line for line in self.lines))

    def test_missing_managed_file_counts_as_local_change(self):
        self.init()
        os.remove(os.path.join(self.store, "fish/config.fish"))
        self.assertEqual(self.update(), 1)

    def test_removed_upstream_is_reported_not_deleted(self):
        self.init()
        self.write_dash("config.defaults.json", '{"files": []}\n')
        sha2 = commit_all(self.dash, "v2")
        self.assertEqual(self.update(apply=True, ref=sha2), 0)
        self.assertTrue(any(line.startswith("REMOVED") for line in self.lines))
        self.assertTrue(os.path.exists(os.path.join(self.store, "fish/config.fish")))

    def test_unsafe_paths_in_defaults_are_refused(self):
        self.write_dash("config.defaults.json", '{"files": [{"source": "../etc/passwd"}]}\n')
        commit_all(self.dash, "bad")
        with self.assertRaises(store.StoreError):
            self.init()

    def test_update_before_init_says_so(self):
        with self.assertRaises(store.StoreError):
            self.update()


    def test_mode_only_change_upstream_is_applied(self):
        self.write_dash("scripts/run.sh", "#!/bin/sh\n")
        os.chmod(os.path.join(self.dash, "scripts/run.sh"), 0o755)
        self.write_dash("config.defaults.json", '{"files": [{"source": "scripts/run.sh"}]}\n')
        commit_all(self.dash, "exec")
        with self.src() as s:
            store.init(self.store, s, out=lambda _: None)
        local = os.path.join(self.store, "scripts/run.sh")
        self.assertEqual(os.stat(local).st_mode & 0o777, 0o755)

        os.chmod(os.path.join(self.dash, "scripts/run.sh"), 0o644)
        sha2 = commit_all(self.dash, "not executable any more")
        self.assertEqual(self.update(apply=True, ref=sha2), 0)
        self.assertEqual(os.stat(local).st_mode & 0o777, 0o644)
        self.assertTrue(any(line.startswith("MODE") for line in self.lines))

    def test_store_gitignores_machine_local_files(self):
        self.init()
        self.assertEqual(self.read(os.path.join(self.store, ".gitignore")),
                         "config.local.json\ninstalls.json\n")


if __name__ == "__main__":
    unittest.main()
