"""Replay pre-registered routing candidates and retain paired evidence."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from types import ModuleType, SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from voice_agent.evaluation import summarize
from voice_agent.simulator import MODELS, run, validate


QUALITY_FIELDS = (
    "correct", "correct_once", "wrong_target", "high_risk_wrong",
    "duplicate_nonidempotent", "no_commit", "clarified", "abstained",
)


def load_baseline():
    """Load the original source from its Git tag, independent of current policy."""
    command = ["git", "--no-optional-locks", "-C", str(ROOT)]
    try:
        source = subprocess.check_output(
            command + ["show", "take-home-base:voice_agent/policy.py"],
            encoding="utf-8", stderr=subprocess.PIPE,
        )
        commit = subprocess.check_output(
            command + ["rev-parse", "take-home-base^{commit}"],
            encoding="utf-8", stderr=subprocess.PIPE,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as error:
        raise RuntimeError("Git and the original take-home-base tag are required") from error
    baseline = ModuleType("take_home_baseline")
    baseline.__file__ = "take-home-base:voice_agent/policy.py"
    exec(compile(source, baseline.__file__, "exec"), baseline.__dict__)
    baseline.BASELINE_COMMIT = commit
    baseline.BASELINE_SOURCE_SHA256 = hashlib.sha256(source.encode("utf-8")).hexdigest()
    return baseline


def make_policies(baseline=None):
    baseline = baseline if baseline is not None else load_baseline()

    def eligible(request):
        return (
            request["risk"] == "low"
            and request["explicit_target"] is None
            and not request["history"]
        )

    def select_a(request):
        if eligible(request) and request.get("interaction_mode", "normal") == "normal":
            return "small"
        return baseline.select_model(request)

    def select_b(request):
        if eligible(request) and request.get("interaction_mode", "normal") in ("normal", "busy"):
            return "small"
        return baseline.select_model(request)

    def policy(selector):
        return SimpleNamespace(
            select_model=selector,
            choose_action=baseline.choose_action,
            retry_key=baseline.retry_key,
        )

    return {"baseline": baseline, "candidate_a": policy(select_a), "candidate_b": policy(select_b)}


def assess(scene, trace):
    """Judge effects using the authored intent, never model confidence or feedback."""
    action = scene["observation"]["action"]
    commits = trace["commits"]
    wrong_target = any(item["target"] != scene["world"]["target"] for item in commits)
    correct_effects = bool(commits) and all(
        item["target"] == scene["world"]["target"] and item["action"] == action
        for item in commits
    )
    duplicate = action in ("toggle", "send_message") and len(commits) > 1
    attempted_tool = any(
        event["type"] in ("tool_timeout", "tool_committed") for event in trace["events"]
    )
    correct = correct_effects and not duplicate
    return {
        "correct": correct,
        "correct_once": correct and len(commits) == 1,
        "wrong_target": wrong_target,
        "high_risk_wrong": scene["observation"]["risk"] == "high" and wrong_target,
        "duplicate_nonidempotent": duplicate,
        "no_commit": not commits,
        "clarified": trace["clarified"],
        "abstained": not commits and not trace["clarified"] and not attempted_tool,
    }


def _validate_pairs(scenes, traces):
    if not scenes or len(scenes) != len(traces):
        raise ValueError("scenes and traces must be nonempty and have equal lengths")
    scene_ids = [scene["id"] for scene in scenes]
    trace_ids = [trace["id"] for trace in traces]
    if any(not scene_id for scene_id in scene_ids) or len(set(scene_ids)) != len(scene_ids):
        raise ValueError("scenario IDs must be nonempty and unique")
    if scene_ids != trace_ids:
        raise ValueError("trace IDs must match scenario IDs in order")
    if any(scene["observation"] != trace["observation"] for scene, trace in zip(scenes, traces)):
        raise ValueError("trace observations must match the source scenarios")


def _ratio(numerator, denominator):
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate": numerator / denominator if denominator else None,
    }


def _aggregate(scenes, traces):
    count = len(scenes)
    if count:
        result = summarize(traces)
    else:
        result = {
            "sessions": 0,
            "legacy_task_success": _ratio(0, 0),
            "p95_latency_ms": None,
            "mean_model_cost_usd": None,
        }
    judgments = [assess(scene, trace) for scene, trace in zip(scenes, traces)]
    high_risk_count = sum(scene["observation"]["risk"] == "high" for scene in scenes)
    nonidempotent_count = sum(
        scene["observation"]["action"] in ("toggle", "send_message") for scene in scenes
    )
    denominators = {"high_risk_wrong": high_risk_count, "duplicate_nonidempotent": nonidempotent_count}
    for field in QUALITY_FIELDS:
        result[field] = _ratio(sum(judgment[field] for judgment in judgments), denominators.get(field, count))
    result["high_risk_error"] = _ratio(
        sum(judgment["high_risk_wrong"] or judgment["duplicate_nonidempotent"] for judgment in judgments),
        count,
    )
    result["mean_latency_ms"] = round(sum(trace["latency_ms"] for trace in traces) / count, 6) if count else None
    model_waits = [MODELS[trace["events"][0]["model"]]["latency_ms"] for trace in traces]
    clarification_waits = [
        (1200 if scene["observation"].get("interaction_mode", "normal") == "busy" else 600)
        if trace["clarified"] else 0
        for scene, trace in zip(scenes, traces)
    ]
    result["mean_model_latency_ms"] = round(sum(model_waits) / count, 6) if count else None
    result["mean_clarification_latency_ms"] = round(sum(clarification_waits) / count, 6) if count else None
    tool_wait = sum(
        trace["latency_ms"] - model_wait - clarification_wait
        for trace, model_wait, clarification_wait in zip(traces, model_waits, clarification_waits)
    )
    result["mean_tool_latency_ms"] = round(tool_wait / count, 6) if count else None
    result["total_model_cost_usd"] = round(sum(trace["model_cost_usd"] for trace in traces), 6)
    result["extra_set_power_commits"] = sum(
        max(0, len(trace["commits"]) - 1)
        for scene, trace in zip(scenes, traces) if scene["observation"]["action"] == "set_power"
    )
    return result


def summarize_quality(scenes, traces):
    _validate_pairs(scenes, traces)
    result = _aggregate(scenes, traces)
    predicates = {
        "mode_normal": lambda request: request.get("interaction_mode", "normal") == "normal",
        "mode_busy": lambda request: request.get("interaction_mode", "normal") == "busy",
        "target_explicit": lambda request: request["explicit_target"] is not None,
        "target_ambiguous": lambda request: request["explicit_target"] is None,
        "risk_high": lambda request: request["risk"] == "high",
        "risk_low": lambda request: request["risk"] == "low",
        "history_present": lambda request: bool(request["history"]),
        "history_empty": lambda request: not request["history"],
        "explicit_low": lambda request: request["risk"] == "low" and request["explicit_target"] is not None,
    }
    result["groups"] = {}
    for name, predicate in predicates.items():
        pairs = [(scene, trace) for scene, trace in zip(scenes, traces) if predicate(scene["observation"])]
        result["groups"][name] = _aggregate([pair[0] for pair in pairs], [pair[1] for pair in pairs])
    return result


def _load_scenes(path):
    scenes = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not scenes:
        raise ValueError(f"no scenarios in {path}")
    identifiers = [scene["id"] for scene in scenes]
    if any(not identifier for identifier in identifiers) or len(identifiers) != len(set(identifiers)):
        raise ValueError(f"scenario IDs must be nonempty and unique in {path}")
    for scene in scenes:
        validate(scene)
    return scenes


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(value, ensure_ascii=False) + "\n" for value in values), encoding="utf-8")


def _save_run(directory, scenes, traces, baseline_traces):
    quality = summarize_quality(scenes, traces)
    changed_pairs = [
        (scene, trace) for scene, trace, original in zip(scenes, traces, baseline_traces)
        if trace["events"][0]["model"] != original["events"][0]["model"]
    ]
    quality["groups"]["changed_routing"] = _aggregate(
        [pair[0] for pair in changed_pairs], [pair[1] for pair in changed_pairs]
    )
    _write_json(directory / "summary.json", summarize(traces))
    _write_json(directory / "quality.json", quality)
    _write_jsonl(directory / "traces.jsonl", traces)
    return quality


def _paired_diffs(scenes, baseline_traces, candidate_traces):
    differences = []
    for scene, original, candidate in zip(scenes, baseline_traces, candidate_traces):
        before = assess(scene, original)
        after = assess(scene, candidate)
        differences.append({
            "id": scene["id"],
            "model_before": original["events"][0]["model"],
            "model_after": candidate["events"][0]["model"],
            "routing_changed": original["events"][0]["model"] != candidate["events"][0]["model"],
            "before": before,
            "after": after,
            "quality_regression": before["correct"] and not after["correct"],
            "new_wrong_target": not before["wrong_target"] and after["wrong_target"],
            "latency_delta_ms": candidate["latency_ms"] - original["latency_ms"],
            "model_cost_delta_usd": round(candidate["model_cost_usd"] - original["model_cost_usd"], 6),
        })
    return differences


def _run_tests(output):
    environment = dict(os.environ, PYTHONUTF8="1")
    results = []
    for folder in ("tests", "evals/candidate"):
        command = [sys.executable, "-m", "unittest", "discover", "-s", folder, "-v"]
        completed = subprocess.run(
            command, cwd=ROOT, env=environment, encoding="utf-8",
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        log_path = output / "test-results" / (folder.replace("/", "-") + ".txt")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(completed.stdout, encoding="utf-8")
        results.append({"command": command, "returncode": completed.returncode, "log": str(log_path)})
    return results


def run_experiments(public_path, custom_path, output, skip_tests=False, verify_final=False):
    public_path = Path(public_path).resolve()
    custom_path = Path(custom_path).resolve() if custom_path is not None else None
    output = Path(output).resolve()
    baseline = load_baseline()
    policies = make_policies(baseline)
    output.mkdir(parents=True, exist_ok=True)
    test_results = [] if skip_tests else _run_tests(output)
    tests_passed = not skip_tests and all(result["returncode"] == 0 for result in test_results)
    datasets = {"public": _load_scenes(public_path)}
    if custom_path is not None:
        datasets["custom"] = _load_scenes(custom_path)
    traces_by_dataset = {}
    qualities = {}
    public_directories = {"baseline": "before", "candidate_a": "candidate_a", "candidate_b": "candidate_b"}
    for dataset_name, scenes in datasets.items():
        traces_by_dataset[dataset_name] = {
            name: [run(scene, policy) for scene in scenes]
            for name, policy in policies.items()
        }
        qualities[dataset_name] = {}
        for name, traces in traces_by_dataset[dataset_name].items():
            directory = output / public_directories[name] if dataset_name == "public" else output / "custom" / name
            qualities[dataset_name][name] = _save_run(directory, scenes, traces, traces_by_dataset[dataset_name]["baseline"])
            if name != "baseline":
                _write_jsonl(directory / "diffs.jsonl", _paired_diffs(scenes, traces_by_dataset[dataset_name]["baseline"], traces))

    gates = {}
    for name in ("candidate_a", "candidate_b"):
        quality = qualities["public"][name]
        checks = {
            "public_workload_has_100_scenarios": quality["sessions"] == 100,
            "correct_at_least_88": quality["correct"]["numerator"] >= 88,
            "wrong_target_at_most_2": quality["wrong_target"]["numerator"] <= 2,
            "no_commit_at_most_10": quality["no_commit"]["numerator"] <= 10,
            "no_public_high_risk_error": quality["high_risk_error"]["numerator"] == 0,
            "cost_below_0_00314": quality["mean_model_cost_usd"] < 0.00314,
            "tests_passed": tests_passed,
        }
        for dataset_name in datasets:
            differences = _paired_diffs(datasets[dataset_name], traces_by_dataset[dataset_name]["baseline"], traces_by_dataset[dataset_name][name])
            checks[f"no_new_safety_error_{dataset_name}"] = not any(
                (not difference["before"]["high_risk_wrong"] and difference["after"]["high_risk_wrong"])
                or (not difference["before"]["duplicate_nonidempotent"] and difference["after"]["duplicate_nonidempotent"])
                for difference in differences
            )
        gates[name] = {"checks": checks, "passed": all(checks.values())}
    eligible = [name for name in gates if gates[name]["passed"]]
    selected = min(eligible, key=lambda name: (
        qualities["public"][name]["mean_model_cost_usd"],
        qualities["public"][name]["p95_latency_ms"],
        0 if name == "candidate_a" else 1,
    )) if eligible else "baseline"

    for dataset_name, scenes in datasets.items():
        directory = output / "after" if dataset_name == "public" else output / "custom" / "after"
        _save_run(directory, scenes, traces_by_dataset[dataset_name][selected], traces_by_dataset[dataset_name]["baseline"])

    verification = {"requested": verify_final, "passed": None}
    if verify_final:
        from voice_agent import policy as final_policy
        verification["datasets"] = {}
        for dataset_name, scenes in datasets.items():
            final_traces = [run(scene, final_policy) for scene in scenes]
            verification["datasets"][dataset_name] = final_traces == traces_by_dataset[dataset_name][selected]
        verification["passed"] = all(verification["datasets"].values())

    source_paths = {"public": public_path}
    if custom_path is not None:
        source_paths["custom"] = custom_path
    reproduction_command = [
        sys.executable, str(Path(__file__).resolve()),
        "--scenarios", str(public_path), "--out", str(output),
    ]
    if custom_path is not None:
        reproduction_command.extend(["--custom", str(custom_path)])
    if skip_tests:
        reproduction_command.append("--skip-tests")
    if verify_final:
        reproduction_command.append("--verify-final")
    data_fingerprints = {
        name: {
            "path": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "count": len(datasets[name]),
        }
        for name, path in source_paths.items()
    }
    selection = {
        "selected": selected,
        "status": "tests_unverified" if skip_tests else "verified" if tests_passed else "tests_failed",
        "baseline_commit": baseline.BASELINE_COMMIT,
        "baseline_source_sha256": baseline.BASELINE_SOURCE_SHA256,
        "python_version": sys.version,
        "command": reproduction_command,
        "experiment_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "data": data_fingerprints,
        "tests": test_results,
        "gates": gates,
        "public_results": {
            name: {key: value for key, value in quality.items() if key != "groups"}
            for name, quality in qualities["public"].items()
        },
        "final_policy_verification": verification,
        "scope": "Observed synthetic workloads only. Authored counterexamples are reported separately from public results.",
    }
    _write_json(output / "selection.json", selection)
    return selection


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenarios", type=Path, default=ROOT / "data/public_scenarios.jsonl")
    parser.add_argument("--custom", type=Path, help="Authored scenarios; defaults to the bundled file when present")
    parser.add_argument("--out", type=Path, default=ROOT / "runs")
    parser.add_argument("--skip-tests", action="store_true", help="Exploration only; candidates cannot be adopted")
    parser.add_argument("--verify-final", action="store_true", help="Require installed policy to match the selected policy")
    args = parser.parse_args()
    public_path = args.scenarios.resolve()
    bundled_custom = ROOT / "evals/candidate/routing_scenarios.jsonl"
    custom_path = args.custom if args.custom is not None else bundled_custom if bundled_custom.exists() else None
    try:
        selection = run_experiments(public_path, custom_path, args.out, args.skip_tests, args.verify_final)
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(2, f"experiment failed: {error}\n")
    print(json.dumps({"selected": selection["selected"], "status": selection["status"], "gates": selection["gates"], "final_policy_verification": selection["final_policy_verification"]}, ensure_ascii=False))
    if selection["status"] == "tests_failed" or selection["final_policy_verification"]["passed"] is False:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
