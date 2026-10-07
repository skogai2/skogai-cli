import contextlib
import io
import json
import os
import tempfile
import unittest
from unittest import mock

from skogai import cli


class ConfigGetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.realpath(self.tmp.name)
        self.store = os.path.join(self.root, ".skogai")
        os.makedirs(self.store)
        with open(os.path.join(self.store, "config.defaults.json"), "w") as f:
            json.dump({"files": [{"source": "a.txt"}], "env": {"EDITOR": "vi", "PAGER": "less"}}, f)
        self.machine = os.path.join(self.root, "machine", "config.json")
        self.env = mock.patch.dict(os.environ, {"SKOGAI_CONFIG_JSON_FILE": self.machine})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["config", "get", *argv])
        return code, out.getvalue(), err.getvalue()

    def test_json_without_key_is_the_whole_merged_config(self):
        code, out, _ = self.run_cli("--store", self.store, "--json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), {"files": [{"source": "a.txt"}], "env": {"EDITOR": "vi", "PAGER": "less"}})

    def test_json_with_a_branch_key_nests_its_leaves(self):
        code, out, _ = self.run_cli("env", "--store", self.store, "--json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), {"EDITOR": "vi", "PAGER": "less"})

    def test_json_with_a_leaf_key_is_the_bare_value(self):
        code, out, _ = self.run_cli("env.EDITOR", "--store", self.store, "--json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), "vi")

    def test_json_array_value_is_a_real_array(self):
        code, out, _ = self.run_cli("files", "--store", self.store, "--json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), [{"source": "a.txt"}])

    def test_json_with_layer_prints_the_raw_value(self):
        code, out, _ = self.run_cli("env", "--layer", "base", "--store", self.store, "--json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), {"EDITOR": "vi", "PAGER": "less"})

    def test_json_and_source_together_is_refused(self):
        code, out, err = self.run_cli("--store", self.store, "--json", "--source")
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("cannot be used together", err)

    def test_text_output_is_unchanged_without_json(self):
        code, out, _ = self.run_cli("env.EDITOR", "--store", self.store, "--source")
        self.assertEqual(code, 0)
        self.assertEqual(out, "vi\t[base]\n")

    def test_a_store_without_defaults_is_an_error_not_an_empty_config(self):
        empty = os.path.join(self.root, "nothing", ".skogai")
        code, out, err = self.run_cli("--store", empty, "--json")
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("run skogai init first", err)

    def test_unset_key_still_exits_1(self):
        code, out, err = self.run_cli("nope", "--store", self.store, "--json")
        self.assertEqual(code, 1)
        self.assertIn("not set", err)


if __name__ == "__main__":
    unittest.main()
