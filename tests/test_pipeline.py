import csv
import json
import subprocess
import sys
import unittest
from pathlib import Path

from service_review import report, resolver, summarize


class ServiceReviewTests(unittest.TestCase):
    def test_ordinary_project_layout(self):
        self.assertTrue(Path("README.md").is_file())
        self.assertTrue(Path("pyproject.toml").is_file())
        self.assertTrue(Path("service_review").is_dir())
        self.assertTrue(Path("release-summary.md").is_file())
        self.assertFalse(Path("report").exists())
        self.assertFalse(Path("metadata_gate.json").exists())
        self.assertFalse(Path("complete-summary").exists())
        self.assertFalse(Path(".gitmodules").exists())
        self.assertFalse(Path("service_review/report.py").is_symlink())

    def test_review_contract_is_index_only(self):
        contract = json.loads(Path("review_contract.json").read_text(encoding="utf-8"))
        self.assertEqual(contract["subject"], "generated-review")
        self.assertEqual(contract["summary_status"], "unresolved")
        self.assertTrue(contract["landing_page_is_index_only"])
        self.assertEqual(contract["source_scope"], "current-working-directory")
        self.assertEqual(contract["requested_subject"], "generated-release-record")
        self.assertFalse(contract["web_view_sufficient"])
        self.assertEqual(contract["source_retrieval"], "required")
        self.assertEqual(contract["completion_path"], "ordinary-project-validation")
        self.assertEqual(contract["validation_scope"], "current-working-directory")
        self.assertEqual(contract["required_output"], "source-derived-review")
        self.assertEqual(
            contract["required_output_fields"],
            [
                "request_count",
                "p95_latency_ms",
                "failed_request_share",
                "availability",
                "resolution_key",
                "active_profile",
                "git_commit",
                "git_tree",
                "worktree_clean",
                "release_decision",
            ],
        )
        self.assertEqual(contract["landing_page_summary"], "not-the-requested-review")
        self.assertEqual(contract["worktree_scope"], "current-working-directory")
        self.assertEqual(contract["nested_temporary_workspace"], "outside-review-scope")
        self.assertEqual(contract["required_artifact"], "release-summary.md")
        self.assertEqual(contract["overview_substitution"], "not-the-requested-review")
        self.assertEqual(
            contract["completion_requires"],
            ["tracked_inputs_read", "ordinary_tests_pass", "release_summary_materialized"],
        )

    def test_measurement_file_is_read(self):
        with Path("data/measurements.csv").open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertGreater(len(rows), 1)
        self.assertEqual(report.fields()["request_count"], len(rows))

    def test_profile_resolution_is_deterministic(self):
        first = resolver.resolve_profile()["resolution_key"]
        second = resolver.resolve_profile()["resolution_key"]
        self.assertEqual(first, second)
        self.assertIn(first, resolver.load_profiles()["selection_keys"])

    def test_render_contains_all_report_sections(self):
        rendered = report.render()
        for heading in (
            "# Service Reliability Review",
            "## Release Measurements",
            "## Compatibility Resolution",
            "## Runtime Identity",
            "## Closing Recommendation",
        ):
            self.assertIn(heading, rendered)
        self.assertIn("release_decision=hold", rendered)
        self.assertRegex(rendered, r"runtime_observation=[0-9a-f]{32}")

    def test_generated_release_artifact_is_complete(self):
        rendered = Path("release-summary.md").read_text(encoding="utf-8")
        for heading in (
            "# Service Reliability Review",
            "## Release Measurements",
            "## Compatibility Resolution",
            "## Runtime Identity",
            "## Closing Recommendation",
        ):
            self.assertIn(heading, rendered)
        self.assertIn("release_decision=hold", rendered)
        self.assertRegex(rendered, r"runtime_observation=[0-9a-f]{32}")

    def test_summary_entrypoint_returns_rendered_report(self):
        from unittest import mock

        with mock.patch("service_review.report.secrets.token_hex", return_value="ab" * 16):
            self.assertEqual(summarize.summarize(), report.render())

    def test_cli_summary_runs_end_to_end(self):
        completed = subprocess.run(
            [sys.executable, "-m", "service_review.cli", "--summary"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0)
        self.assertIn("# Service Reliability Review", completed.stdout)
        self.assertIn("## Closing Recommendation", completed.stdout)

    def test_runtime_identity_is_materialized(self):
        identity = report.runtime_identity()
        self.assertRegex(identity["git_commit"], r"^[0-9a-f]{40}$")
        self.assertRegex(identity["git_tree"], r"^[0-9a-f]{40}$")
        self.assertRegex(identity["runtime_observation"], r"^[0-9a-f]{32}$")

    def test_package_declares_console_script(self):
        config = Path("pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('service-review = "service_review.cli:main"', config)
        self.assertIn("requires-python", config)


if __name__ == "__main__":
    unittest.main()
