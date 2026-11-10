"""Independent intent oracles and counterexamples for the routing experiment."""
import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from experiment import assess, load_baseline, make_policies, summarize_quality
from voice_agent.simulator import run, validate


class RoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).with_name("routing_scenarios.jsonl")
        cls.scenes = {
            scene["id"]: scene
            for scene in map(json.loads, path.read_text(encoding="utf-8").splitlines())
        }
        cls.policies = make_policies()

    def replay(self, scene_id, policy_name="baseline"):
        scene = copy.deepcopy(self.scenes[scene_id])
        trace = run(scene, self.policies[policy_name])
        return scene, trace

    def assert_single_correct(self, scene, trace):
        self.assertEqual(len(trace["commits"]), 1)
        self.assertEqual(trace["commits"][0]["target"], scene["world"]["target"])
        self.assertEqual(trace["commits"][0]["action"], scene["observation"]["action"])
        self.assertTrue(assess(scene, trace)["correct_once"])

    def test_all_fixtures_validate_and_ids_are_unique(self):
        self.assertEqual(len(self.scenes), 18)
        for scene in self.scenes.values():
            with self.subTest(scene=scene["id"]):
                validate(scene)

    def test_baseline_loaded_from_original_tag(self):
        baseline = load_baseline()
        self.assertEqual(baseline.BASELINE_COMMIT[:7], "fd44870")
        request = self.scenes["normal_single_candidate"]["observation"]
        self.assertEqual(baseline.select_model(request), "standard")

    def test_candidate_routes_and_missing_mode(self):
        for policy_name in ("candidate_a", "candidate_b"):
            for scene_id in ("normal_shared_clarify", "legacy_mode_missing"):
                with self.subTest(policy=policy_name, scene=scene_id):
                    request = self.scenes[scene_id]["observation"]
                    self.assertEqual(self.policies[policy_name].select_model(request), "small")
        request = self.scenes["busy_extra_clarify_answered"]["observation"]
        self.assertEqual(self.policies["candidate_a"].select_model(request), "standard")
        self.assertEqual(self.policies["candidate_b"].select_model(request), "small")

    def test_explicit_history_and_high_risk_routes(self):
        expected = {
            "explicit_missing_answered": "standard",
            "history_requires_strong": "strong",
            "high_ambiguous_answered": "small",
            "timeout_before_message": "standard",
        }
        for policy_name, policy in self.policies.items():
            for scene_id, model in expected.items():
                with self.subTest(policy=policy_name, scene=scene_id):
                    self.assertEqual(policy.select_model(self.scenes[scene_id]["observation"]), model)

    def test_new_names_and_request_ids_do_not_change_routing(self):
        request = copy.deepcopy(self.scenes["normal_single_candidate"]["observation"])
        changed = dict(request, request_id="unseen-request", text="启动另一个新设备。")
        for policy in self.policies.values():
            self.assertEqual(policy.select_model(request), policy.select_model(changed))
        explicit = dict(changed, explicit_target="unseen_target")
        for policy in self.policies.values():
            self.assertEqual(policy.select_model(explicit), "standard")

    def test_normal_same_decision_saves_model_cost_and_wait(self):
        scene, baseline = self.replay("normal_shared_clarify")
        for name in ("candidate_a", "candidate_b"):
            _, candidate = self.replay("normal_shared_clarify", name)
            self.assert_single_correct(scene, candidate)
            self.assertTrue(candidate["clarified"])
            self.assertEqual(candidate["latency_ms"], 780)
            self.assertEqual(baseline["latency_ms"] - candidate["latency_ms"], 150)
            self.assertAlmostEqual(baseline["model_cost_usd"] - candidate["model_cost_usd"], .002)

    def test_single_candidate_executes_once(self):
        for name in self.policies:
            scene, trace = self.replay("normal_single_candidate", name)
            self.assert_single_correct(scene, trace)
            self.assertFalse(trace["clarified"])
            self.assertEqual(trace["latency_ms"], 330 if name == "baseline" else 180)

    def test_low_risk_high_confidence_regression_is_exposed(self):
        scene, baseline = self.replay("small_confident_wrong")
        self.assert_single_correct(scene, baseline)
        for name in ("candidate_a", "candidate_b"):
            _, trace = self.replay("small_confident_wrong", name)
            verdict = assess(scene, trace)
            self.assertTrue(trace["acknowledged"])
            self.assertTrue(verdict["wrong_target"])
            self.assertFalse(verdict["correct"])
            self.assertFalse(verdict["high_risk_wrong"])
            self.assertEqual(trace["commits"][0]["target"], "side_light")

    def test_explicit_missing_target_clarifies_and_accounts_for_no_answer(self):
        for name in self.policies:
            scene, answered = self.replay("explicit_missing_answered", name)
            self.assert_single_correct(scene, answered)
            self.assertTrue(answered["clarified"])
            self.assertEqual(answered["latency_ms"], 930)
            scene, unanswered = self.replay("explicit_missing_unanswered", name)
            verdict = assess(scene, unanswered)
            self.assertTrue(unanswered["clarified"])
            self.assertTrue(verdict["no_commit"])
            self.assertFalse(verdict["abstained"])
            self.assertFalse(verdict["correct"])
            self.assertEqual(unanswered["latency_ms"], 850)

    def test_busy_extra_clarification_wait_is_measured(self):
        scene, baseline = self.replay("busy_extra_clarify_answered")
        _, candidate = self.replay("busy_extra_clarify_answered", "candidate_b")
        self.assert_single_correct(scene, baseline)
        self.assert_single_correct(scene, candidate)
        self.assertFalse(baseline["clarified"])
        self.assertTrue(candidate["clarified"])
        self.assertEqual(candidate["latency_ms"] - baseline["latency_ms"], 1050)
        self.assertEqual(candidate["latency_ms"], 1380)

    def test_busy_no_answer_reveals_completion_loss(self):
        scene, baseline = self.replay("busy_extra_clarify_unanswered")
        _, candidate = self.replay("busy_extra_clarify_unanswered", "candidate_b")
        self.assert_single_correct(scene, baseline)
        self.assertFalse(assess(scene, candidate)["correct"])
        self.assertTrue(assess(scene, candidate)["no_commit"])
        self.assertEqual(candidate["latency_ms"], 1300)

    def test_high_risk_unclear_target_always_clarifies(self):
        for name in self.policies:
            scene, answered = self.replay("high_ambiguous_answered", name)
            self.assert_single_correct(scene, answered)
            self.assertTrue(answered["clarified"])
            self.assertEqual(answered["latency_ms"], 780)
            scene, unanswered = self.replay("high_ambiguous_unanswered", name)
            self.assertTrue(unanswered["clarified"])
            self.assertEqual(unanswered["commits"], [])
            self.assertEqual(unanswered["latency_ms"], 700)
            self.assertFalse(assess(scene, unanswered)["high_risk_wrong"])

    def test_history_uses_strong_and_preserves_target(self):
        for name in self.policies:
            scene, trace = self.replay("history_requires_strong", name)
            self.assert_single_correct(scene, trace)
            self.assertEqual(trace["events"][0]["model"], "strong")
            self.assertEqual(trace["latency_ms"], 780)

    def test_neighboring_confidence_values_and_unnormalized_scores(self):
        for name in self.policies:
            scene, at_boundary = self.replay("threshold_at_boundary", name)
            self.assert_single_correct(scene, at_boundary)
            self.assertFalse(at_boundary["clarified"])
            _, below_score = self.replay("threshold_below_score", name)
            self.assertTrue(below_score["clarified"])
            self.assertEqual(len(below_score["commits"]), 1)
            _, below_margin = self.replay("threshold_below_margin", name)
            self.assertTrue(below_margin["clarified"])
            self.assertEqual(below_margin["commits"], [])

    def test_timeouts_reuse_original_key_for_nonidempotent_actions(self):
        for name in self.policies:
            for scene_id in ("timeout_before_message", "timeout_after_toggle"):
                with self.subTest(policy=name, scene=scene_id):
                    scene, trace = self.replay(scene_id, name)
                    self.assert_single_correct(scene, trace)
                    self.assertEqual(trace["latency_ms"], 830)
                    self.assertEqual(trace["commits"][0]["key"], scene["observation"]["request_id"] + ":action")
                    self.assertFalse(assess(scene, trace)["duplicate_nonidempotent"])
                    if scene_id == "timeout_after_toggle":
                        self.assertEqual(sum(event["type"] == "deduplicated" for event in trace["events"]), 1)

    def test_same_observations_cannot_identify_two_world_targets(self):
        east = self.scenes["indistinguishable_east"]
        west = self.scenes["indistinguishable_west"]
        east_observation = dict(east["observation"])
        west_observation = dict(west["observation"])
        east_observation.pop("request_id")
        west_observation.pop("request_id")
        self.assertEqual(east_observation, west_observation)
        self.assertEqual(east["models"], west["models"])
        for name in self.policies:
            _, east_trace = self.replay("indistinguishable_east", name)
            _, west_trace = self.replay("indistinguishable_west", name)
            self.assertTrue(assess(east, east_trace)["correct"])
            self.assertTrue(assess(west, west_trace)["wrong_target"])
            self.assertEqual(east_trace["commits"][0]["target"], west_trace["commits"][0]["target"])

    def test_set_power_duplicate_is_goal_complete_but_not_single_completion(self):
        scene, trace = self.replay("normal_single_candidate")
        trace["commits"].append(dict(trace["commits"][0], key="extra-command"))
        verdict = assess(scene, trace)
        self.assertTrue(verdict["correct"])
        self.assertFalse(verdict["correct_once"])
        self.assertFalse(verdict["duplicate_nonidempotent"])

    def test_low_risk_duplicate_toggle_is_still_high_risk_error(self):
        scene, trace = self.replay("timeout_after_toggle")
        trace["commits"].append(dict(trace["commits"][0], key="extra-command"))
        verdict = assess(scene, trace)
        self.assertFalse(verdict["correct"])
        self.assertFalse(verdict["high_risk_wrong"])
        self.assertTrue(verdict["duplicate_nonidempotent"])
        summary = summarize_quality([scene], [trace])
        self.assertEqual(summary["high_risk_error"]["numerator"], 1)
        self.assertEqual(summary["high_risk_error"]["denominator"], 1)

    def test_wrong_action_is_not_success(self):
        scene, trace = self.replay("normal_single_candidate")
        trace["commits"][0]["action"] = "toggle"
        verdict = assess(scene, trace)
        self.assertFalse(verdict["correct"])
        self.assertFalse(verdict["correct_once"])
        self.assertFalse(verdict["wrong_target"])

    def test_abstain_differs_from_timeout_before_commit_without_retry(self):
        baseline = self.policies["baseline"]
        abstaining = SimpleNamespace(
            select_model=baseline.select_model,
            choose_action=lambda request, prediction: {"kind": "abstain"},
            retry_key=baseline.retry_key,
        )
        scene = copy.deepcopy(self.scenes["normal_single_candidate"])
        trace = run(scene, abstaining)
        self.assertTrue(assess(scene, trace)["abstained"])
        self.assertTrue(assess(scene, trace)["no_commit"])
        no_retry = SimpleNamespace(
            select_model=baseline.select_model,
            choose_action=baseline.choose_action,
            retry_key=lambda request, timeout: None,
        )
        scene = copy.deepcopy(self.scenes["timeout_before_message"])
        trace = run(scene, no_retry)
        self.assertTrue(assess(scene, trace)["no_commit"])
        self.assertFalse(assess(scene, trace)["abstained"])

    def test_summary_rejects_missing_or_mismatched_traces(self):
        scene, trace = self.replay("normal_single_candidate")
        with self.assertRaises(ValueError):
            summarize_quality([scene], [])
        changed = dict(trace, id="unmatched-scene")
        with self.assertRaises(ValueError):
            summarize_quality([scene], [changed])


if __name__ == "__main__":
    unittest.main()
