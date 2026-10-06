import json
import os
import subprocess
import tempfile
import unittest

from skogai import install, store
from skogai.source import GitSource, blob_sha

DEFAULTS = {
    "files": [
        {
            "source": "fish/config.fish",
            "install": {"env": "SKOGAI_CONFIG_FISH_DIR", "xdg": "fish", "default": "/unused/fish"},
        }
    ]
}


def git(cwd, *args):
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=cwd, check=True, capture_output=True,
    )


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.realpath(self.tmp.name)
        self.dash = os.path.join(self.root, "dash")
        os.makedirs(os.path.join(self.dash, "fish"))
        subprocess.run(["git", "init", "-q", "-b", "main", self.dash], check=True)
        self.write_dash("config.defaults.json", json.dumps(DEFAULTS))
        self.write_dash("fish/config.fish", "set -g fish_greeting\n")
        self.commit("v1")

        self.store = os.path.join(self.root, "repo", ".skogai")
        with GitSource(self.dash) as s:
            store.init(self.store, s, out=lambda _: None)

        self.target_dir = os.path.join(self.root, "home", "fish")
        self.env = {"SKOGAI_CONFIG_FISH_DIR": self.target_dir}
        self.target = os.path.join(self.target_dir, "config.fish")
        self.lines = []

    def tearDown(self):
        self.tmp.cleanup()

    def write_dash(self, path, text):
        with open(os.path.join(self.dash, path), "w") as f:
            f.write(text)

    def commit(self, message):
        git(self.dash, "add", "-A")
        git(self.dash, "commit", "-q", "-m", message)

    def run_install(self, apply=False):
        return install.install(self.store, env=self.env, apply=apply, out=self.lines.append)

    def read(self, path):
        with open(path) as f:
            return f.read()

    def test_env_variable_wins_over_xdg_and_default(self):
        spec = {"env": "X_DIR", "xdg": "fish", "default": "/d"}
        self.assertEqual(install.install_dir(spec, {"X_DIR": "/a/"}), ("/a", "env"))
        self.assertEqual(install.install_dir(spec, {"XDG_CONFIG_HOME": "/x"}), ("/x/fish", "xdg"))
        self.assertEqual(install.install_dir(spec, {}), ("/d", "default"))

    def test_dry_run_writes_nothing(self):
        self.assertEqual(self.run_install(), 0)
        self.assertTrue(any(line.startswith("INSTALL") for line in self.lines))
        self.assertFalse(os.path.exists(self.target))

    def test_apply_copies_and_records(self):
        self.assertEqual(self.run_install(apply=True), 0)
        self.assertEqual(self.read(self.target), "set -g fish_greeting\n")
        record = json.loads(self.read(os.path.join(self.store, "installs.json")))
        self.assertEqual(record["fish/config.fish"]["path"], self.target)

    def test_second_run_is_up_to_date(self):
        self.run_install(apply=True)
        self.lines.clear()
        self.assertEqual(self.run_install(), 0)
        self.assertEqual(self.lines, ["up to date"])

    def test_store_update_is_installed_over_an_untouched_copy(self):
        self.run_install(apply=True)
        self.write_dash("fish/config.fish", "set -g fish_greeting\nset -g x 1\n")
        self.commit("v2")
        with GitSource(self.dash) as s:
            store.update(self.store, s, apply=True, out=lambda _: None)
        self.lines.clear()
        self.assertEqual(self.run_install(apply=True), 0)
        self.assertTrue(any(line.startswith("UPDATE") for line in self.lines))
        self.assertEqual(self.read(self.target), "set -g fish_greeting\nset -g x 1\n")

    def test_local_edit_after_install_is_not_overwritten(self):
        self.run_install(apply=True)
        with open(self.target, "w") as f:
            f.write("my own change\n")
        self.write_dash("fish/config.fish", "upstream\n")
        self.commit("v2")
        with GitSource(self.dash) as s:
            store.update(self.store, s, apply=True, out=lambda _: None)
        self.lines.clear()
        self.assertEqual(self.run_install(apply=True), 1)
        self.assertTrue(any(line.startswith("LOCAL-CHANGE") for line in self.lines))
        self.assertEqual(self.read(self.target), "my own change\n")

    def test_identical_existing_file_is_adopted(self):
        os.makedirs(self.target_dir)
        with open(self.target, "w") as f:
            f.write("set -g fish_greeting\n")
        self.assertEqual(self.run_install(apply=True), 0)
        self.assertTrue(any(line.startswith("RECORD") for line in self.lines))

    def test_different_unrecorded_file_is_not_overwritten(self):
        os.makedirs(self.target_dir)
        with open(self.target, "w") as f:
            f.write("someone else's\n")
        self.assertEqual(self.run_install(apply=True), 1)
        self.assertEqual(self.read(self.target), "someone else's\n")

    def test_hand_edited_store_copy_blocks_install(self):
        with open(os.path.join(self.store, "fish/config.fish"), "w") as f:
            f.write("edited in the store\n")
        self.assertEqual(self.run_install(apply=True), 1)
        self.assertFalse(os.path.exists(self.target))

    def test_entry_without_install_path_is_skipped(self):
        with open(os.path.join(self.store, "config.defaults.json"), "w") as f:
            json.dump({"files": [{"source": "fish/config.fish"}]}, f)
        self.assertEqual(self.run_install(apply=True), 0)
        self.assertTrue(any(line.startswith("SKIP") for line in self.lines))
        self.assertFalse(os.path.exists(self.target))

    def test_moved_install_path_is_noted_and_old_copy_kept(self):
        self.run_install(apply=True)
        new_dir = os.path.join(self.root, "elsewhere")
        self.env = {"SKOGAI_CONFIG_FISH_DIR": new_dir}
        self.assertEqual(self.run_install(apply=True), 0)
        self.assertTrue(any(line.startswith("NOTE") for line in self.lines))
        self.assertTrue(os.path.exists(self.target))
        self.assertTrue(os.path.exists(os.path.join(new_dir, "config.fish")))

    def test_bad_install_spec_is_refused_at_init(self):
        self.write_dash("config.defaults.json", json.dumps(
            {"files": [{"source": "fish/config.fish", "install": {"env": "X"}}]}))
        self.commit("bad")
        with GitSource(self.dash) as s:
            with self.assertRaises(store.StoreError):
                store.init(os.path.join(self.root, "other"), s, out=lambda _: None)


if __name__ == "__main__":
    unittest.main()
