"""Evaluate history-derived rules with factorial and component ablations."""

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from types import ModuleType, SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiment import (
    _load_scenes, _paired_diffs, _run_tests, _save_run, _write_json, _write_jsonl,
    load_baseline,
)
from voice_agent import rules
from voice_agent.simulator import run


PREVIOUS_COMMIT = "67570fd9578973bb779dcb2818221e791638c5cf"
FROZEN_VALIDATION = {
    "heldout_scenarios.jsonl": "de0a18a6fb82cd2a6800d37a9281ce48f075af4bf7dafc70e0ffa359dfefbfa3",
    "heldout_scenarios.md": "df63d11017f76d3ef50cff8b97c9155a3a1cb992c6f5aba39c044b9f62122c41",
    "confirmation_scenarios.jsonl": "2da5bfcee6ace3e15fef739c82e2dc2a08880d196cef552bfbf39f7e61a631e6",
    "confirmation_scenarios.md": "a33f69942c4daf04f274d8911e0d10a28d903de109ace64642aac0e3e447bf83",
}
COMPONENTS = ("correction", "selection", "ordinal", "ambiguity_guard")
VARIANTS = {
    "baseline": {"routing": False, "actions": False, "disabled": None},
    "routing_only": {"routing": True, "actions": False, "disabled": None},
    "action_only": {"routing": False, "actions": True, "disabled": None},
    "full": {"routing": True, "actions": True, "disabled": None},
    **{
        f"without_{component}": {"routing": True, "actions": True, "disabled": component}
        for component in COMPONENTS
    },
    "without_parser_fallback": {
        "routing": True, "actions": True, "disabled": None, "parser_fallback": False,
    },
}


def route_override(request, configuration):
    if not configuration["routing"]:
        return None
    features = rules.extract_reference(request)
    if (
        not configuration.get("parser_fallback", True)
        and features.rule == "unsupported"
        and request["risk"] == "low"
        and request["explicit_target"] is None
    ):
        return "small"
    return rules.model_override(request)


def decision_override(request, prediction, configuration):
    if not configuration["actions"]:
        return None
    features = rules.extract_reference(request)
    if (
        not configuration.get("parser_fallback", True)
        and features.rule == "unsupported"
        and request["risk"] == "low"
        and request["explicit_target"] is None
    ):
        return {"kind": "clarify"}
    options = {component: component != configuration["disabled"] for component in COMPONENTS}
    return rules.action_override(request, prediction, **options)


def make_variants():
    baseline = load_baseline()
    policies = {}
    for name, configuration in VARIANTS.items():
        def select(request, configuration=configuration):
            override = route_override(request, configuration)
            return override if override is not None else baseline.select_model(request)

        def decide(request, prediction, configuration=configuration):
            override = decision_override(request, prediction, configuration)
            return override if override is not None else baseline.choose_action(request, prediction)

        policies[name] = SimpleNamespace(
            select_model=select, choose_action=decide, retry_key=baseline.retry_key,
        )
    source = subprocess.check_output(
        ["git", "--no-optional-locks", "-C", str(ROOT), "show", f"{PREVIOUS_COMMIT}:voice_agent/policy.py"],
        encoding="utf-8",
    )
    previous = ModuleType("previous_routing_v1")
    exec(compile(source, f"{PREVIOUS_COMMIT}:voice_agent/policy.py", "exec"), previous.__dict__)
    policies["previous_v1"] = previous
    return baseline, policies


def audit_history(output, baseline):
    source = ROOT / "data/history_sessions.jsonl"
    sessions = [json.loads(line) for line in source.read_text(encoding="utf-8").split("\n") if line]
    details = []
    signals = {}
    feature_counts = {}
    original_context_conflicts = 0
    proposed_context_conflicts = 0
    for line_number, session in enumerate(sessions, 1):
        features = asdict(rules.extract_reference(session["observation"]))
        feature_counts[features["rule"]] = feature_counts.get(features["rule"], 0) + 1
        observed_signals = [event["signal"] for event in session["events"] if event["type"] == "user_signal"]
        for signal in observed_signals:
            signals[signal] = signals.get(signal, 0) + 1
        request = session["observation"]
        prediction = session["events"][0]["prediction"]
        proposed_action = rules.action_override(request, prediction)
        if proposed_action is None:
            proposed_action = baseline.choose_action(request, prediction)
        proposed_model = rules.model_override(request)
        if proposed_model is None:
            proposed_model = baseline.select_model(request)
        context_conflict = features["target"] is not None and any(
            commit["target"] != features["target"] for commit in session["commits"]
        )
        proposed_conflict = (
            features["target"] is not None and proposed_action["kind"] == "execute"
            and proposed_action["target"] != features["target"]
        )
        original_context_conflicts += context_conflict
        proposed_context_conflicts += proposed_conflict
        details.append({
            "source_line": line_number, "id": session["id"],
            "observation": session["observation"], "features": features,
            "observed_model": session["events"][0]["model"],
            "clarified": session["clarified"], "acknowledged": session["acknowledged"],
            "commits": session["commits"], "observed_signals": observed_signals,
            "proposed_model": proposed_model,
            "proposed_action_on_observed_prediction": proposed_action,
            "observed_commit_conflicts_with_parsed_history": context_conflict,
            "proposed_action_conflicts_with_parsed_history": proposed_conflict,
        })
    audit = {
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "sessions": len(sessions), "clarified": sum(item["clarified"] for item in sessions),
        "acknowledged": sum(item["acknowledged"] for item in sessions),
        "no_commit": sum(not item["commits"] for item in sessions),
        "observed_signals": signals, "derived_feature_counts": feature_counts,
        "observed_context_conflicts": original_context_conflicts,
        "proposed_context_conflicts_on_recorded_prediction": proposed_context_conflicts,
        "scope": "Observed behavior and derived syntax only. No world labels or counterfactual model outputs are available.",
    }
    _write_json(output / "history_audit.json", audit)
    _write_jsonl(output / "history_features.jsonl", details)
    return audit


def _explain(scene, trace, configuration):
    request = scene["observation"]
    features = rules.extract_reference(request)
    prediction = trace["events"][0]["prediction"]
    action = decision_override(request, prediction, configuration) if configuration else None
    return {
        "id": scene["id"], "features": asdict(features),
        "selected_model": trace["events"][0]["model"],
        "route_override": route_override(request, configuration) if configuration else None,
        "action_override": action,
        "fallback_to_baseline_action": action is None,
    }


def _counts(quality):
    return {
        "correct": quality["correct"]["numerator"],
        "wrong_target": quality["wrong_target"]["numerator"],
        "no_commit": quality["no_commit"]["numerator"],
        "clarified": quality["clarified"]["numerator"],
        "mean_cost_usd": quality["mean_model_cost_usd"],
        "mean_latency_ms": quality["mean_latency_ms"],
        "p95_latency_ms": quality["p95_latency_ms"],
    }


def _effects(results):
    measures = {name: _counts(quality) for name, quality in results.items()}
    factorial = {}
    for measure in measures["baseline"]:
        base = measures["baseline"][measure]
        routing = measures["routing_only"][measure]
        actions = measures["action_only"][measure]
        full = measures["full"][measure]
        factorial[measure] = {
            "routing_only_minus_baseline": round(routing - base, 8),
            "action_only_minus_baseline": round(actions - base, 8),
            "full_minus_baseline": round(full - base, 8),
            "interaction_full_minus_routing_minus_action_plus_baseline": round(full - routing - actions + base, 8),
        }
    components = {
        component: {
            measure: round(measures["full"][measure] - measures[f"without_{component}"][measure], 8)
            for measure in measures["full"]
        }
        for component in COMPONENTS
    }
    components["parser_fallback"] = {
        measure: round(measures["full"][measure] - measures["without_parser_fallback"][measure], 8)
        for measure in measures["full"]
    }
    return {"factorial": factorial, "full_minus_component_removed": components}


def evaluate(output, verify_final=False):
    output = Path(output).resolve()
    for filename, expected in FROZEN_VALIDATION.items():
        path = ROOT / "evals/candidate" / filename
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"frozen independent validation changed: {filename}")
    baseline, policies = make_variants()
    paths = {
        "public": ROOT / "data/public_scenarios.jsonl",
        "known_counterexamples": ROOT / "evals/candidate/routing_scenarios.jsonl",
        "heldout": ROOT / "evals/candidate/heldout_scenarios.jsonl",
        "confirmation": ROOT / "evals/candidate/confirmation_scenarios.jsonl",
    }
    datasets = {name: _load_scenes(path) for name, path in paths.items()}
    tests = _run_tests(output)
    tests_passed = all(item["returncode"] == 0 for item in tests)
    results = {}
    traces = {}
    for dataset, scenes in datasets.items():
        traces[dataset] = {name: [run(scene, policy) for scene in scenes] for name, policy in policies.items()}
        results[dataset] = {}
        for name, run_traces in traces[dataset].items():
            directory = output / dataset / name
            results[dataset][name] = _save_run(directory, scenes, run_traces, traces[dataset]["baseline"])
            _write_jsonl(directory / "diffs.jsonl", _paired_diffs(scenes, traces[dataset]["baseline"], run_traces))
            _write_jsonl(directory / "decisions.jsonl", [
                _explain(scene, trace, VARIANTS.get(name)) for scene, trace in zip(scenes, run_traces)
            ])
    gates = {}
    for name in VARIANTS:
        if name == "baseline":
            continue
        public = results["public"][name]
        checks = {
            "tests_passed": tests_passed,
            "public_correct_at_least_88": public["correct"]["numerator"] >= 88,
            "public_wrong_at_most_2": public["wrong_target"]["numerator"] <= 2,
            "public_cost_at_most_baseline": public["mean_model_cost_usd"] <= 0.00314,
        }
        for dataset in datasets:
            paired = _paired_diffs(datasets[dataset], traces[dataset]["baseline"], traces[dataset][name])
            checks[f"no_new_safety_error_{dataset}"] = not any(
                (not row["before"]["high_risk_wrong"] and row["after"]["high_risk_wrong"])
                or (not row["before"]["duplicate_nonidempotent"] and row["after"]["duplicate_nonidempotent"])
                for row in paired
            )
        for dataset in ("known_counterexamples", "heldout", "confirmation"):
            quality = results[dataset][name]
            original = results[dataset]["baseline"]
            checks[f"completion_noninferior_{dataset}"] = quality["correct"]["numerator"] >= original["correct"]["numerator"]
            checks[f"wrong_noninferior_{dataset}"] = quality["wrong_target"]["numerator"] <= original["wrong_target"]["numerator"]
        gates[name] = {"checks": checks, "passed": all(checks.values())}

    def priority(name):
        qualities = [results[dataset][name] for dataset in datasets]
        configuration = VARIANTS[name]
        complexity = int(configuration["routing"]) + (4 - int(configuration["disabled"] is not None) if configuration["actions"] else 0)
        return (
            sum(quality["wrong_target"]["numerator"] for quality in qualities),
            -sum(quality["correct"]["numerator"] for quality in qualities),
            results["public"][name]["mean_model_cost_usd"],
            results["public"][name]["p95_latency_ms"], complexity,
        )

    eligible = [name for name, gate in gates.items() if gate["passed"]]
    selected = min(eligible, key=priority) if eligible else "baseline"
    for dataset, scenes in datasets.items():
        _save_run(output / "after" / dataset, scenes, traces[dataset][selected], traces[dataset]["baseline"])
    verification = {"requested": verify_final, "passed": None}
    if verify_final:
        from voice_agent import policy as installed
        verification["datasets"] = {
            dataset: [run(scene, installed) for scene in scenes] == traces[dataset][selected]
            for dataset, scenes in datasets.items()
        }
        verification["passed"] = all(verification["datasets"].values())
    fingerprints = {
        name: {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "scenarios": len(datasets[name])}
        for name, path in paths.items()
    }
    source_files = [Path(__file__).resolve(), ROOT / "voice_agent/rules.py"]
    summary = {
        "selected": selected, "configuration": VARIANTS[selected],
        "tests_passed": tests_passed, "tests": tests,
        "baseline_commit": baseline.BASELINE_COMMIT, "previous_commit": PREVIOUS_COMMIT,
        "implementation_commit": subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], encoding="utf-8").strip(),
        "source_sha256": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in source_files},
        "data": fingerprints, "frozen_validation_sha256": FROZEN_VALIDATION,
        "data_roles": {
            "public": "Previously observed public development workload",
            "known_counterexamples": "Previously observed directed counterexamples",
            "heldout": "Independent first validation, now diagnostic after round-one rejection",
            "confirmation": "Fresh independently authored synthetic confirmation after parser-fallback revision",
        },
        "history": audit_history(output, baseline),
        "gates": gates,
        "results": {dataset: {name: _counts(quality) for name, quality in variants.items()} for dataset, variants in results.items()},
        "effects": {dataset: _effects(variants) for dataset, variants in results.items()},
        "final_policy_verification": verification,
        "scope": "Separate synthetic datasets. Aggregate counts rank candidates only, without estimating deployment frequencies. P95 factorial differences are descriptive, not additive latency attribution.",
        "reproduction_command": [sys.executable, str(Path(__file__).resolve()), "--out", str(output)] + (["--verify-final"] if verify_final else []),
    }
    _write_json(output / "ablation.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "runs/ablation")
    parser.add_argument("--verify-final", action="store_true")
    args = parser.parse_args()
    try:
        result = evaluate(args.out, args.verify_final)
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(2, f"ablation failed: {error}\n")
    print(json.dumps({
        "selected": result["selected"], "tests_passed": result["tests_passed"],
        "results": result["results"], "final_policy_verification": result["final_policy_verification"],
    }, ensure_ascii=False))
    return 0 if result["tests_passed"] and result["final_policy_verification"]["passed"] is not False else 1


if __name__ == "__main__":
    raise SystemExit(main())
