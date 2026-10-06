import unittest

from skogai.env import check, resolve, var_name
from skogai.env.inventory import is_dir_var, parse_atuin_var_list

HOME = "/home/test"


class ResolveTests(unittest.TestCase):
    def test_app_var_wins_over_xdg(self):
        env = {"HOME": HOME, "XDG_CONFIG_HOME": "/xdg", "SKOGAI_CONFIG_FISH_DIR": "/app/fish/"}
        r = resolve("CONFIG", ["fish"], env)
        self.assertEqual((r.path, r.tier, r.var), ("/app/fish", "app", "SKOGAI_CONFIG_FISH_DIR"))

    def test_xdg_used_under_skogai_subdir(self):
        env = {"HOME": HOME, "XDG_CONFIG_HOME": "/xdg"}
        r = resolve("CONFIG", ["fish"], env)
        self.assertEqual((r.path, r.tier), ("/xdg/skogai/fish", "xdg"))

    def test_default_under_home_when_no_xdg(self):
        r = resolve("CACHE", [], {"HOME": HOME})
        self.assertEqual((r.path, r.tier), (f"{HOME}/.cache/skogai", "default"))

    def test_claude_area_has_no_xdg_tier(self):
        env = {"HOME": HOME, "XDG_CONFIG_HOME": "/xdg"}
        r = resolve("CLAUDE", [], env)
        self.assertEqual((r.path, r.tier), (f"{HOME}/claude", "default"))

    def test_trailing_slash_is_dropped(self):
        r = resolve("CLAUDE", [], {"HOME": HOME, "SKOGAI_CLAUDE_DIR": "/home/skogix/claude/"})
        self.assertEqual(r.path, "/home/skogix/claude")

    def test_root_defaults_to_home_skogai(self):
        self.assertEqual(resolve(None, [], {"HOME": HOME}).path, f"{HOME}/skogai")

    def test_var_name_components_become_upper_snake(self):
        self.assertEqual(var_name("CONFIG", ["my-tool"]), "SKOGAI_CONFIG_MY_TOOL_DIR")


class CheckTests(unittest.TestCase):
    def live_like(self):
        # The overlap seen on the live machine (docs/ENV-HANDOVER.md, fact B).
        return {
            "XDG_SKOGAI_DIR": "/home/skogix/skogai/",
            "SKOGAI_SKOGAI_DIR": "/home/skogix/skogai/",
            "SKOGAI_CONFIG_DIR": "/home/skogix/skogai/config",
            "XDG_SKOGAI_CONFIG_DIR": "/home/skogix/.config/skogai/",
        }

    def test_forbidden_xdg_skogai_name_is_error(self):
        findings = check({"XDG_SKOGAI_DIR": "/a/"}, [])
        self.assertIn(("error", "naming"), [(f.level, f.rule) for f in findings])

    def test_overlap_with_different_paths_is_error(self):
        findings = check(self.live_like(), [])
        overlap = [f for f in findings if f.rule == "overlap" and f.level == "error"]
        self.assertTrue(any("SKOGAI_CONFIG_DIR" in f.message for f in overlap))

    def test_same_path_under_two_names_is_warning(self):
        findings = check({"XDG_SKOGAI_DIR": "/a/", "SKOGAI_SKOGAI_DIR": "/a/"}, [])
        overlap = [f for f in findings if f.rule == "overlap"]
        self.assertEqual([f.level for f in overlap], ["warning"])

    def test_directory_value_without_trailing_slash_is_warning(self):
        findings = check({"SKOGAI_CONFIG_DIR": "/home/x/config"}, [])
        self.assertTrue(any(f.rule == "naming" and f.level == "warning" for f in findings))

    def test_secret_name_in_atuin_list_is_error(self):
        findings = check({}, ["GITHUB_TOKEN", "EDITOR"])
        errors = [f for f in findings if f.level == "error"]
        self.assertEqual(len(errors), 1)
        self.assertIn("GITHUB_TOKEN", errors[0].message)

    def test_unreadable_atuin_list_is_not_healthy(self):
        findings = check({}, None)
        self.assertEqual([(f.level, f.rule) for f in findings], [("warning", "unverified")])

    def test_clean_env_has_no_findings(self):
        env = {"SKOGAI_CLAUDE_DIR": "/home/skogix/claude/"}
        self.assertEqual(check(env, []), [])


class InventoryTests(unittest.TestCase):
    def test_atuin_parser_keeps_names_only(self):
        text = "export EDITOR=nvim\nexport SOME_API_KEY=supersecret\nnot a line\n"
        self.assertEqual(parse_atuin_var_list(text), ["EDITOR", "SOME_API_KEY"])

    def test_dir_var_detection(self):
        self.assertTrue(is_dir_var("SKOGAI_CLAUDE_DIR"))
        self.assertTrue(is_dir_var("XDG_SKOGAI_DIR"))
        self.assertFalse(is_dir_var("SKOGAI_SKOGIX_TODO"))
        self.assertFalse(is_dir_var("XDG_CONFIG_HOME"))


if __name__ == "__main__":
    unittest.main()
