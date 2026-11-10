"""Specification tests for history-derived rules, separate from frozen validation."""

import copy
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from voice_agent.rules import action_override, extract_reference, model_override


def request(text="打开那个。", history=None, **changes):
    value = {
        "request_id": "spec-request",
        "text": text,
        "action": "set_power",
        "risk": "low",
        "explicit_target": None,
        "history": [] if history is None else list(history),
        "interaction_mode": "normal",
    }
    value.update(changes)
    return value


def prediction(*candidates):
    return {
        "candidates": [
            {"target": target, "confidence": confidence}
            for target, confidence in candidates
        ]
    }


class HistoryRuleTests(unittest.TestCase):
    def test_latest_correction_overrides_prior_choice_and_model_rank(self):
        observed = request(
            "按刚才改好的，打开它。",
            ["用户：先选north_pad，还不要执行。", "用户：不对，换成south_pad。"],
        )
        features = extract_reference(observed)
        self.assertTrue(features.has_reference)
        self.assertEqual(features.target, "south_pad")
        self.assertEqual(features.rule, "correction")
        self.assertEqual(model_override(observed), "standard")
        self.assertEqual(
            action_override(observed, prediction(("north_pad", 0.97), ("south_pad", 0.03))),
            {"kind": "execute", "target": "south_pad"},
        )

    def test_multiple_corrections_use_last_user_revision(self):
        observed = request(
            "按刚才改好的，打开它。",
            [
                "用户：先选north_pad。",
                "用户：不对，换成south_pad。",
                "用户：改为west_pad。",
            ],
        )
        features = extract_reference(observed)
        self.assertEqual(features.target, "west_pad")
        self.assertEqual(features.rule, "correction")

    def test_side_question_preserves_prior_selection(self):
        observed = request(
            "现在打开刚才定好的那个。",
            [
                "用户：待会儿选north_pad，先别执行。",
                "助手：好的。",
                "用户：顺便问下，south_pad也能用吗？",
                "助手：也可以。",
            ],
        )
        features = extract_reference(observed)
        self.assertEqual(features.target, "north_pad")
        self.assertEqual(features.rule, "selection")
        self.assertEqual(
            action_override(observed, prediction(("south_pad", 0.95), ("north_pad", 0.05))),
            {"kind": "execute", "target": "north_pad"},
        )

    def test_deferring_execution_preserves_selected_target(self):
        observed = request(
            "现在打开刚才定好的那个。",
            ["用户：先选north_pad，还不要执行。"],
        )
        self.assertEqual(extract_reference(observed).target, "north_pad")

    def test_front_and_back_follow_user_mention_order(self):
        history = ["用户：我在考虑north_pad和south_pad。", "助手：你想选哪一个？"]
        candidates = prediction(("south_pad", 0.95), ("north_pad", 0.05))
        for text, expected in (
            ("就打开刚才说的前一个。", "north_pad"),
            ("就打开刚才说的后一个。", "south_pad"),
        ):
            with self.subTest(text=text):
                observed = request(text, history)
                features = extract_reference(observed)
                self.assertEqual(features.rule, "ordinal")
                self.assertEqual(features.target, expected)
                self.assertEqual(
                    action_override(observed, candidates),
                    {"kind": "execute", "target": expected},
                )

    def test_unresolved_multiple_options_require_clarification(self):
        observed = request(
            "打开刚才那个。",
            ["用户：north_pad和south_pad都可能要用。", "助手：两个都可用。"],
        )
        features = extract_reference(observed)
        self.assertIsNone(features.target)
        self.assertEqual(features.rule, "unresolved")
        self.assertEqual(model_override(observed), "small")
        self.assertEqual(
            action_override(observed, prediction(("north_pad", 0.99), ("south_pad", 0.01))),
            {"kind": "clarify"},
        )

    def test_assistant_statement_cannot_create_user_selection(self):
        observed = request(
            "打开刚才那个。",
            ["用户：我还没选好。", "助手：换成north_pad。"],
        )
        self.assertIsNone(extract_reference(observed).target)
        self.assertEqual(
            action_override(observed, prediction(("north_pad", 0.99))),
            {"kind": "clarify"},
        )

    def test_english_user_role_is_supported(self):
        observed = request("打开刚才那个。", ["User: 先选north_pad。"])
        self.assertEqual(extract_reference(observed).target, "north_pad")

    def test_negative_selection_invalidates_old_grounding(self):
        observed = request(
            "打开刚才那个。",
            ["用户：先选north_pad。", "用户：不要选north_pad。"],
        )
        self.assertIsNone(extract_reference(observed).target)
        self.assertEqual(
            action_override(observed, prediction(("north_pad", 0.99))),
            {"kind": "clarify"},
        )

    def test_selection_question_is_not_confirmation(self):
        observed = request("按刚才改好的，打开它。", ["用户：换成south_pad吗？"])
        self.assertIsNone(extract_reference(observed).target)
        self.assertEqual(
            action_override(observed, prediction(("south_pad", 0.99))),
            {"kind": "clarify"},
        )

    def test_cancelled_selection_is_not_executed(self):
        observed = request(
            "打开刚才那个。",
            ["用户：先选north_pad。", "用户：取消刚才的选择。"],
        )
        self.assertIsNone(extract_reference(observed).target)
        self.assertEqual(
            action_override(observed, prediction(("north_pad", 0.99))),
            {"kind": "clarify"},
        )

    def test_uncertain_new_choice_invalidates_old_grounding(self):
        observed = request(
            "打开刚才那个。",
            ["用户：先选north_pad。", "用户：可能换成south_pad。"],
        )
        self.assertIsNone(extract_reference(observed).target)

    def test_current_cancelled_operation_is_not_executed(self):
        observed = request(
            "先不要执行刚才那个。",
            ["用户：先选north_pad。"],
        )
        self.assertIsNone(extract_reference(observed).target)
        self.assertEqual(
            action_override(observed, prediction(("north_pad", 0.99))),
            {"kind": "clarify"},
        )

    def test_grounded_target_missing_from_candidates_clarifies(self):
        observed = request("打开刚才那个。", ["用户：先选north_pad。"])
        self.assertEqual(
            action_override(observed, prediction(("south_pad", 0.99))),
            {"kind": "clarify"},
        )

    def test_candidate_target_match_is_exact(self):
        observed = request("打开刚才那个。", ["用户：先选north_pad。"])
        self.assertEqual(
            action_override(observed, prediction(("north_pad_extra", 0.99))),
            {"kind": "clarify"},
        )

    def test_no_context_high_confidence_reference_still_clarifies(self):
        observed = request("打开那个。")
        self.assertEqual(model_override(observed), "small")
        self.assertEqual(
            action_override(observed, prediction(("north_pad", 0.99))),
            {"kind": "clarify"},
        )

    def test_plain_nonreferential_request_falls_back(self):
        observed = request("打开设备。")
        features = extract_reference(observed)
        self.assertFalse(features.has_reference)
        self.assertEqual(features.rule, "no_reference")
        self.assertIsNone(model_override(observed))
        self.assertIsNone(action_override(observed, prediction(("north_pad", 0.99))))

    def test_other_word_does_not_create_pronoun_reference(self):
        observed = request("检查其他设备。")
        self.assertFalse(extract_reference(observed).has_reference)

    def test_unknown_history_defers_to_original_policies(self):
        observed = request("打开刚才那个。", ["用户：north_pad看起来很有意思。"])
        features = extract_reference(observed)
        self.assertTrue(features.has_reference)
        self.assertIsNone(features.target)
        self.assertEqual(features.rule, "unsupported")
        self.assertIsNone(model_override(observed))
        self.assertIsNone(action_override(observed, prediction(("north_pad", 0.99))))

    def test_valid_selection_after_unknown_history_restores_grounding(self):
        observed = request(
            "打开刚才那个。",
            ["用户：north_pad看起来很有意思。", "用户：先选south_pad。"],
        )
        features = extract_reference(observed)
        self.assertEqual(features.rule, "selection")
        self.assertEqual(features.target, "south_pad")
        self.assertEqual(model_override(observed), "standard")
        self.assertEqual(
            action_override(observed, prediction(("south_pad", 0.2))),
            {"kind": "execute", "target": "south_pad"},
        )

    def test_side_question_after_unknown_history_preserves_fallback(self):
        observed = request(
            "打开刚才那个。",
            [
                "用户：north_pad看起来很有意思。",
                "用户：顺便问下，south_pad也能用吗？",
            ],
        )
        features = extract_reference(observed)
        self.assertEqual(features.rule, "unsupported")
        self.assertIsNone(features.target)
        self.assertIsNone(model_override(observed))
        self.assertIsNone(action_override(observed, prediction(("south_pad", 0.99))))

    def test_neutral_or_deferred_statement_after_unknown_preserves_fallback(self):
        for message in ("用户：好的。", "用户：先别执行。"):
            with self.subTest(message=message):
                observed = request(
                    "打开刚才那个。",
                    ["用户：north_pad看起来很有意思。", message],
                )
                features = extract_reference(observed)
                self.assertEqual(features.rule, "unsupported")
                self.assertIn("看起来", features.evidence)
                self.assertIsNone(model_override(observed))
                self.assertIsNone(action_override(observed, prediction(("north_pad", 0.99))))

    def test_new_negation_after_unknown_is_recognized_as_unresolved(self):
        observed = request(
            "打开刚才那个。",
            ["用户：north_pad看起来很有意思。", "用户：不要选north_pad。"],
        )
        features = extract_reference(observed)
        self.assertEqual(features.rule, "unresolved")
        self.assertIsNone(features.target)
        self.assertEqual(model_override(observed), "small")
        self.assertEqual(
            action_override(observed, prediction(("north_pad", 0.99))),
            {"kind": "clarify"},
        )

    def test_unknown_statement_clears_previous_grounding_and_defers(self):
        observed = request(
            "打开刚才那个。",
            ["用户：先选north_pad。", "用户：south_pad看起来很有意思。"],
        )
        features = extract_reference(observed)
        self.assertEqual(features.rule, "unsupported")
        self.assertIsNone(features.target)
        self.assertIsNone(model_override(observed))
        self.assertIsNone(action_override(observed, prediction(("north_pad", 0.99))))

    def test_ordinal_with_unsupported_history_also_defers(self):
        observed = request("打开前一个。", ["用户：north_pad看起来很有意思。"])
        self.assertEqual(extract_reference(observed).rule, "unsupported")
        self.assertIsNone(model_override(observed))
        self.assertIsNone(action_override(observed, prediction(("north_pad", 0.99))))

    def test_missing_mode_and_busy_do_not_predict_user_response(self):
        normal = request()
        legacy = dict(normal)
        legacy.pop("interaction_mode")
        busy = dict(normal, interaction_mode="busy")
        for observed in (normal, legacy, busy):
            with self.subTest(request=observed):
                self.assertEqual(model_override(observed), "small")
                self.assertEqual(
                    action_override(observed, prediction(("north_pad", 0.99))),
                    {"kind": "clarify"},
                )

    def test_single_candidate_and_unnormalized_scores_use_grounding(self):
        observed = request("打开刚才那个。", ["用户：先选north_pad。"])
        for candidates in (
            prediction(("north_pad", 0.1)),
            prediction(("south_pad", 0.9), ("north_pad", 0.8), ("west_pad", 0.7)),
        ):
            self.assertEqual(
                action_override(observed, candidates),
                {"kind": "execute", "target": "north_pad"},
            )

    def test_high_risk_and_explicit_target_defer_to_original_guards(self):
        for observed in (
            request(risk="high", action="send_message"),
            request(explicit_target="north_pad"),
        ):
            with self.subTest(request=observed):
                self.assertIsNone(model_override(observed))
                self.assertIsNone(action_override(observed, prediction(("south_pad", 0.99))))

    def test_action_component_ablations_preserve_route(self):
        cases = (
            ("correction", ["用户：不对，换成north_pad。"], "按刚才改好的，打开它。"),
            ("selection", ["用户：先选north_pad。"], "打开刚才那个。"),
            ("ordinal", ["用户：我在考虑north_pad和south_pad。"], "打开前一个。"),
        )
        for flag, history, text in cases:
            with self.subTest(flag=flag):
                observed = request(text, history)
                self.assertEqual(model_override(observed), "standard")
                self.assertIsNone(
                    action_override(observed, prediction(("north_pad", 0.99)), **{flag: False})
                )
                self.assertEqual(model_override(observed), "standard")
        observed = request()
        self.assertIsNone(
            action_override(observed, prediction(("north_pad", 0.99)), ambiguity_guard=False)
        )
        self.assertEqual(model_override(observed), "small")

    def test_new_identifiers_and_request_ids_do_not_change_rule(self):
        for target in ("new_gate", "zone-17", "台灯甲"):
            with self.subTest(target=target):
                observed = request(
                    "打开刚才那个。",
                    [f"用户：先选{target}。"],
                    request_id=f"unseen-{target}",
                )
                self.assertEqual(model_override(observed), "standard")
                self.assertEqual(
                    action_override(observed, prediction((target, 0.15))),
                    {"kind": "execute", "target": target},
                )

    def test_extraction_and_decisions_do_not_mutate_runtime_inputs(self):
        observed = request("打开刚才那个。", ["用户：先选north_pad。"])
        candidates = prediction(("south_pad", 0.9), ("north_pad", 0.1))
        original_request = copy.deepcopy(observed)
        original_prediction = copy.deepcopy(candidates)
        extract_reference(observed)
        model_override(observed)
        action_override(observed, candidates)
        self.assertEqual(observed, original_request)
        self.assertEqual(candidates, original_prediction)


if __name__ == "__main__":
    unittest.main()
