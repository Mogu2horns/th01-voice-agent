"""Check that factorial arms differ only in their declared components."""

import unittest

from ablation import VARIANTS, decision_override, make_variants, route_override


class AblationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline, cls.policies = make_variants()

    def request(self, history):
        return {
            "request_id": "factorial-spec", "text": "按刚才改好的，打开它。",
            "action": "set_power", "risk": "low", "explicit_target": None,
            "history": history, "interaction_mode": "normal",
        }

    def test_factorial_routing_and_action_are_separate(self):
        request = self.request(["用户：先选old_pad。", "用户：换成new_pad。"])
        prediction = {"candidates": [
            {"target": "old_pad", "confidence": 0.99},
            {"target": "new_pad", "confidence": 0.01},
        ]}
        for name in ("baseline", "routing_only", "action_only", "full"):
            with self.subTest(variant=name):
                policy = self.policies[name]
                self.assertEqual(policy.select_model(request), "standard" if VARIANTS[name]["routing"] else "strong")
                self.assertEqual(
                    policy.choose_action(request, prediction)["target"],
                    "new_pad" if VARIANTS[name]["actions"] else "old_pad",
                )
                self.assertEqual(policy.retry_key(request, {"original_key": "same-command"}), "same-command")

    def test_component_removal_keeps_full_router(self):
        request = self.request(["用户：换成new_pad。"])
        prediction = {"candidates": [
            {"target": "old_pad", "confidence": 0.99},
            {"target": "new_pad", "confidence": 0.01},
        ]}
        self.assertEqual(self.policies["full"].select_model(request), self.policies["without_correction"].select_model(request))
        self.assertEqual(self.policies["full"].choose_action(request, prediction)["target"], "new_pad")
        self.assertEqual(self.policies["without_correction"].choose_action(request, prediction)["target"], "old_pad")

    def test_parser_fallback_ablation_restores_rejected_behavior(self):
        request = self.request(["用户：new_pad的外观很有趣。"])
        prediction = {"candidates": [{"target": "new_pad", "confidence": 0.99}]}
        self.assertIsNone(route_override(request, VARIANTS["full"]))
        self.assertIsNone(decision_override(request, prediction, VARIANTS["full"]))
        self.assertEqual(route_override(request, VARIANTS["without_parser_fallback"]), "small")
        self.assertEqual(decision_override(request, prediction, VARIANTS["without_parser_fallback"]), {"kind": "clarify"})

    def test_previous_policy_is_independent_of_installed_product(self):
        request = self.request([])
        self.assertEqual(self.baseline.select_model(request), "standard")
        self.assertEqual(self.policies["previous_v1"].select_model(request), "small")


if __name__ == "__main__":
    unittest.main()
