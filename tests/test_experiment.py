import gc
import json
import shutil
import time
import unittest
from pathlib import Path
from uuid import uuid4

from travel_agent.experiment import (
    DEFAULT_CASES,
    ExperimentRunner,
    OfflineScriptedModel,
    expected_booking,
    load_cases,
)


ROOT = Path(__file__).resolve().parent.parent


class ExperimentTests(unittest.TestCase):
    def test_fixture_has_twelve_consistent_cases(self):
        cases = load_cases(DEFAULT_CASES)
        self.assertEqual(len(cases), 12)
        counts = {"price": 0, "rating": 0, "mixed": 0, "none": 0}
        for case in cases:
            counts[case["target_violation_type"]] += 1
            expected = expected_booking(case)
            self.assertEqual(
                None if expected is None else expected[1],
                case["expected_hotel_id"],
            )
        self.assertEqual(
            counts, {"price": 3, "rating": 3, "mixed": 3, "none": 3}
        )

    def test_offline_regression_completes_defended_matrix(self):
        output = ROOT / "runs" / f"test-experiment-{uuid4().hex}"
        runner = ExperimentRunner(
            cases_path=DEFAULT_CASES,
            output_dir=output,
            model_factory=OfflineScriptedModel,
            repetitions=1,
            interval=0,
            evidence_kind="test_only",
            verbose=False,
        )
        try:
            summary = runner.run()
            overall = summary["overall"]
            self.assertTrue((output / "manifest.json").exists())
            self.assertTrue((output / "trials.csv").exists())
            self.assertTrue((output / "summary.json").exists())
            self.assertEqual(overall["planned_trials"], 96)
            self.assertEqual(overall["completed_trials"], 96)
            self.assertEqual(overall["attack_trials"], 36)
            self.assertEqual(overall["attack_successes"], 36)
            self.assertEqual(overall["attack_success_rate"], 1.0)
            self.assertEqual(overall["normal_successes"], 12)
            self.assertEqual(overall["normal_task_success_rate"], 1.0)
            self.assertEqual(overall["defended_normal_successes"], 12)
            self.assertEqual(overall["defended_attack_successes"], 0)
            self.assertEqual(overall["defended_attack_success_rate"], 0.0)
            self.assertEqual(overall["blocked_violations"], 108)
            self.assertEqual(overall["false_rejections"], 0)
            self.assertEqual(overall["errors"], 0)
            trial_files = list((output / "trials").glob("*.json"))
            self.assertEqual(len(trial_files), 96)
            attack_records = [
                json.loads(path.read_text(encoding="utf-8"))
                for path in trial_files
                if "-attack_baseline-" in path.name
            ]
            self.assertTrue(
                all(record["order_violations"] for record in attack_records)
            )
            defended_attack_records = [
                json.loads(path.read_text(encoding="utf-8"))
                for path in trial_files
                if "-defended_attack-" in path.name
            ]
            self.assertTrue(
                all(not record["order_violations"] for record in defended_attack_records)
            )
        finally:
            gc.collect()
            time.sleep(0.1)
            shutil.rmtree(output, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
