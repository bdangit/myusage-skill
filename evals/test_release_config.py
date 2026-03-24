"""
Evals for release-please configuration files.

EVAL-004: release-please-config.json and .release-please-manifest.json are valid JSON,
          config has release-type: simple with extra-files for plugin.json,
          and manifest version matches plugin.json version.
"""

import json
import os
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestReleaseConfig(unittest.TestCase):

    def test_eval_004_release_config_valid(self):
        """EVAL-004: Config and manifest are valid JSON, correctly configured, and versions in sync."""
        config_path = os.path.join(REPO_ROOT, "release-please-config.json")
        manifest_path = os.path.join(REPO_ROOT, ".release-please-manifest.json")
        plugin_path = os.path.join(REPO_ROOT, ".claude-plugin", "plugin.json")

        # Both files must exist
        self.assertTrue(os.path.exists(config_path), "release-please-config.json not found")
        self.assertTrue(os.path.exists(manifest_path), ".release-please-manifest.json not found")

        # Both must be valid JSON
        with open(config_path) as f:
            config = json.load(f)
        with open(manifest_path) as f:
            manifest = json.load(f)
        with open(plugin_path) as f:
            plugin = json.load(f)

        # config must have release-type: simple
        self.assertEqual(
            config.get("release-type"), "simple",
            f"Expected release-type: simple, got {config.get('release-type')!r}",
        )

        # config must have a packages entry for "."
        packages = config.get("packages", {})
        self.assertIn(".", packages, "Expected packages entry for '.' in config")

        # That package must have extra-files with an entry for plugin.json with jsonpath $.version
        extra_files = packages["."].get("extra-files", [])
        plugin_entry = next(
            (e for e in extra_files if isinstance(e, dict) and e.get("path") == ".claude-plugin/plugin.json"),
            None,
        )
        self.assertIsNotNone(
            plugin_entry,
            f"Expected extra-files entry with path .claude-plugin/plugin.json, got: {extra_files}",
        )
        self.assertEqual(
            plugin_entry.get("jsonpath"), "$.version",
            f"Expected jsonpath: $.version, got {plugin_entry.get('jsonpath')!r}",
        )

        # manifest must have a "." entry
        self.assertIn(".", manifest, "Expected '.' key in .release-please-manifest.json")

        # manifest version must be valid semver
        manifest_version = manifest["."]
        self.assertRegex(
            manifest_version,
            r"^\d+\.\d+\.\d+$",
            f"Manifest version {manifest_version!r} is not valid semver",
        )

        # manifest version must match plugin.json version
        plugin_version = plugin.get("version", "")
        self.assertEqual(
            manifest_version, plugin_version,
            f"Manifest version {manifest_version!r} does not match plugin.json version {plugin_version!r}",
        )


if __name__ == "__main__":
    unittest.main()
