import json
import os
import tempfile
import unittest

from skogai import config


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.realpath(self.tmp.name)
        self.store = os.path.join(self.root, ".skogai")
        os.makedirs(self.store)
        self.machine = os.path.join(self.root, "machine", "config.json")
        os.makedirs(os.path.dirname(self.machine))
        self.env = {"SKOGAI_CONFIG_JSON_FILE": self.machine}

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, path, data):
        with open(path, "w") as f:
            json.dump(data, f)

    def layers(self):
        return config.load_layers(self.store, self.env)

    def test_objects_merge_and_arrays_replace(self):
        self.put(os.path.join(self.store, "config.defaults.json"), {
            "env": {"A": "base", "B": "base"},
            "files": [{"source": "a"}, {"source": "b"}],
        })
        self.put(self.machine, {"env": {"B": "machine"}})
        self.put(os.path.join(self.store, "config.json"), {"files": [{"source": "c"}]})
        result = config.merged(self.layers())
        self.assertEqual(result["env"], {"A": "base", "B": "machine"})
        self.assertEqual(result["files"], [{"source": "c"}])

    def test_source_names_the_layer_that_set_each_value(self):
        self.put(os.path.join(self.store, "config.defaults.json"), {"env": {"A": 1, "B": 2}})
        self.put(self.machine, {"env": {"B": 3}})
        got = {k: (v, src) for k, v, src in config.get(self.layers(), "env")}
        self.assertEqual(got, {"env.A": (1, "base"), "env.B": (3, "machine")})

    def test_replaced_array_leaves_no_stale_base_entries(self):
        self.put(os.path.join(self.store, "config.defaults.json"),
                 {"files": [{"source": "a"}, {"source": "b"}]})
        self.put(os.path.join(self.store, "config.json"), {"files": [{"source": "c"}]})
        hits = config.get(self.layers(), "files")
        self.assertEqual(hits, [("files", [{"source": "c"}], "repo")])

    def test_local_files_sit_above_their_shared_file(self):
        self.put(self.machine, {"x": "machine"})
        self.put(config._local(self.machine), {"x": "machine.local"})
        self.put(os.path.join(self.store, "config.json"), {"x": "repo"})
        self.put(os.path.join(self.store, "config.local.json"), {"x": "repo.local"})
        self.assertEqual(config.get(self.layers(), "x"), [("x", "repo.local", "repo.local")])

    def test_machine_path_defaults_to_xdg(self):
        path = config.machine_config_path({"XDG_CONFIG_HOME": "/x"})
        self.assertEqual(path, "/x/skogai/config.json")

    def test_secret_looking_key_is_refused(self):
        self.put(os.path.join(self.store, "config.json"), {"github": {"api_token": "abc"}})
        with self.assertRaises(config.ConfigError):
            self.layers()

    def test_invalid_json_is_an_error(self):
        with open(os.path.join(self.store, "config.json"), "w") as f:
            f.write("{not json")
        with self.assertRaises(config.ConfigError):
            self.layers()

    def test_non_object_is_an_error(self):
        self.put(os.path.join(self.store, "config.json"), ["a"])
        with self.assertRaises(config.ConfigError):
            self.layers()

    def test_layer_value_returns_raw_value_from_one_layer(self):
        self.put(os.path.join(self.store, "config.defaults.json"), {"env": {"A": 1}})
        self.put(self.machine, {"env": {"A": 2}})
        self.assertEqual(config.layer_value(self.layers(), "base", "env.A"), 1)
        self.assertEqual(config.layer_value(self.layers(), "machine", "env.A"), 2)
        self.assertIsNone(config.layer_value(self.layers(), "repo", "env.A"))

    def test_missing_files_are_empty_layers(self):
        self.assertEqual(config.merged(self.layers()), {})
        self.assertEqual(config.get(self.layers(), None), [])


if __name__ == "__main__":
    unittest.main()
