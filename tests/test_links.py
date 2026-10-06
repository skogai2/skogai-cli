import os
import tempfile
import unittest

from skogai import links


class LinkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.realpath(self.tmp.name)
        self.repo = os.path.join(self.root, "repo")
        os.makedirs(os.path.join(self.repo, "fish"))
        self.manifest = os.path.join(self.repo, "links.txt")
        self.install = os.path.join(self.root, "home", "fish")
        self.lines = []

    def tearDown(self):
        self.tmp.cleanup()

    def write_manifest(self, body=None):
        with open(self.manifest, "w") as f:
            f.write(body if body is not None else f"# comment\n\nfish {self.install}\n")

    def run_links(self, mode):
        return links.run(self.manifest, mode, out=self.lines.append)

    def test_parse_skips_comments_and_blanks(self):
        entries = links.parse_manifest("# header\n\nfish ~/.config/fish\n")
        self.assertEqual(entries, [links.Entry("fish", "~/.config/fish")])

    def test_parse_rejects_line_without_target(self):
        with self.assertRaises(ValueError):
            links.parse_manifest("fish\n")

    def test_link_creates_missing_link(self):
        self.write_manifest()
        self.assertEqual(self.run_links("link"), 0)
        self.assertEqual(os.path.realpath(self.install), os.path.join(self.repo, "fish"))
        self.assertTrue(self.lines[0].startswith("linked"))

    def test_second_run_reports_ok(self):
        self.write_manifest()
        self.run_links("link")
        self.lines.clear()
        self.assertEqual(self.run_links("link"), 0)
        self.assertTrue(self.lines[0].startswith("ok"))

    def test_check_changes_nothing(self):
        self.write_manifest()
        self.assertEqual(self.run_links("check"), 1)
        self.assertTrue(self.lines[0].startswith("UNLINKED"))
        self.assertFalse(os.path.lexists(self.install))

    def test_real_file_is_never_overwritten(self):
        self.write_manifest()
        os.makedirs(os.path.dirname(self.install))
        with open(self.install, "w") as f:
            f.write("mine")
        self.assertEqual(self.run_links("link"), 1)
        self.assertTrue(self.lines[0].startswith("NOT-A-LINK"))
        with open(self.install) as f:
            self.assertEqual(f.read(), "mine")

    def test_wrong_link_is_reported_not_changed(self):
        self.write_manifest()
        elsewhere = os.path.join(self.root, "elsewhere")
        os.makedirs(elsewhere)
        os.makedirs(os.path.dirname(self.install))
        os.symlink(elsewhere, self.install)
        self.assertEqual(self.run_links("link"), 1)
        self.assertTrue(self.lines[0].startswith("WRONG-LINK"))
        self.assertEqual(os.readlink(self.install), elsewhere)

    def test_missing_source_is_reported(self):
        self.write_manifest(f"nope {self.install}\n")
        self.assertEqual(self.run_links("link"), 1)
        self.assertTrue(self.lines[0].startswith("MISSING-SRC"))

    def test_unknown_mode_is_rejected(self):
        self.write_manifest()
        with self.assertRaises(ValueError):
            self.run_links("bogus")


if __name__ == "__main__":
    unittest.main()
