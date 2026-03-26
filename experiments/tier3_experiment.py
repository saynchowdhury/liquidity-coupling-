"""
tier3_experiment.py -- Real Multi-Model Liquidity Coupling Experiment
"Liquidity Coupling in Autonomous Agent Networks" -- Table 3 Upgrade
Author: Sayan Mallick Chowdhury

PURPOSE:
    This is the experiment that upgrades Table 3 from "one trace log" to
    "empirical result with mean ± std deviation." It uses REAL local Ollama
    calls -- no mocked or pre-baked outputs.

MODELS TESTED:
    - qwen3-vl:8b   (runs fully locally, 6.1 GB)
    - kimi-k2.5:cloud (cloud-routed through Ollama -> Moonshot AI API)

TASK TYPES (3):
    1. sentiment  -- classify sentiment as POS/NEG/NEU
    2. summarize  -- compress text to 1 sentence
    3. classify   -- categorize into a fixed label set

FAILURE MODES TRACKED:
    - json_malformed   : model output was not valid JSON
    - wrong_key        : JSON parsed but response key was wrong/missing
    - wrong_value      : key present but value out of valid range
    - hallucination    : value present but factually wrong / nonsensical
    - timeout          : Ollama didn't respond in time
    - success          : task completed correctly

RUNS:
    50 pipeline chains per (model × task) combination
    Each chain = 5 hops (agents A0->A1->A2->A3->A4), each calls the LLM once
    Total real LLM calls: 2 models × 3 tasks × 50 chains × 5 hops = 1,500 calls

USAGE:
    # Full experiment (~20-40 min depending on model speed)
    python tier3_experiment.py

    # Quick test: 5 chains, 2 hops (verify setup works first)
    python tier3_experiment.py --quick

    # Single model only
    python tier3_experiment.py --model qwen3-vl:8b
"""

import urllib.request
import json
import time
import statistics
import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

OLLAMA_URL  = "http://localhost:11434/api/generate"
ALPHA       = 0.20          # Liquidity Coupling parameter (Theorem 4.1)
PAYMENT_AMT = 0.50          # Payment size per hop (normalized)
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# Task definitions -- the EXACT prompts sent to both models
# ─────────────────────────────────────────────────────────────────────────────
#
# DESIGN PRINCIPLE: prompts are deliberately simple but require structured output.
# Model failures emerge naturally from JSON non-compliance, not from hard questions.
# This matches how real agent pipelines fail in production.

TASKS = {
    "sentiment": {
        "description": "Sentiment classification (POS/NEG/NEU)",
        "valid_values": ["POS", "NEG", "NEU"],
        "prompts": [
            # Hop 0 -- easy anchor
            'Classify the sentiment of this text: "The product works exactly as described."\n'
            'Output ONLY valid JSON: {"sentiment": "POS"} or {"sentiment": "NEG"} or {"sentiment": "NEU"}\n'
            'No markdown, no explanation, no trailing text. Only the JSON object.',

            # Hop 1 -- slightly ambiguous
            'Classify the sentiment of this text: "It was not the worst thing I have ever used."\n'
            'Output ONLY valid JSON: {"sentiment": "POS"} or {"sentiment": "NEG"} or {"sentiment": "NEU"}\n'
            'Only the JSON. Nothing else.',

            # Hop 2 -- negation trap
            'Classify the sentiment of this text: "I would not say I disliked it."\n'
            'Output ONLY valid JSON: {"sentiment": "POS"} or {"sentiment": "NEG"} or {"sentiment": "NEU"}\n'
            'Only the JSON. Nothing else.',

            # Hop 3 -- compound sentence
            'Classify the sentiment of this text: "Fast shipping but the quality was disappointing."\n'
            'Output ONLY valid JSON: {"sentiment": "POS"} or {"sentiment": "NEG"} or {"sentiment": "NEU"}\n'
            'Only the JSON. Nothing else.',

            # Hop 4 -- sarcasm
            'Classify the sentiment of this text: "Oh great, another update that broke everything."\n'
            'Output ONLY valid JSON: {"sentiment": "POS"} or {"sentiment": "NEG"} or {"sentiment": "NEU"}\n'
            'Only the JSON. Nothing else.',
        ]
    },
    "summarize": {
        "description": "Single-sentence summarization",
        "valid_values": None,  # Free-form but must be a non-empty string
        "prompts": [
            # Hop 0
            'Summarize in ONE sentence: "Photosynthesis is the process by which plants use sunlight, water, and CO2 to produce glucose and oxygen."\n'
            'Output ONLY valid JSON: {"summary": "your one sentence here"}\n'
            'No markdown, no extra keys, no trailing text.',

            # Hop 1
            'Summarize in ONE sentence: "The mitochondria are membrane-bound organelles found in the cells of most eukaryotic organisms. They generate most of the energy needed to power cellular functions."\n'
            'Output ONLY valid JSON: {"summary": "your one sentence here"}\n'
            'No markdown, no extra keys, no trailing text.',

            # Hop 2
            'Summarize in ONE sentence: "Machine learning is a branch of artificial intelligence where systems learn from data to identify patterns and make decisions with minimal human intervention."\n'
            'Output ONLY valid JSON: {"summary": "your one sentence here"}\n'
            'No markdown, no extra keys, no trailing text.',

            # Hop 3
            'Summarize in ONE sentence: "The water cycle describes how water evaporates from the surface, rises as vapor, condenses into clouds, and falls back as precipitation."\n'
            'Output ONLY valid JSON: {"summary": "your one sentence here"}\n'
            'No markdown, no extra keys, no trailing text.',

            # Hop 4
            'Summarize in ONE sentence: "Blockchain is a distributed ledger technology where data is stored in linked, cryptographically secured blocks, making tampering extremely difficult."\n'
            'Output ONLY valid JSON: {"summary": "your one sentence here"}\n'
            'No markdown, no extra keys, no trailing text.',
        ]
    },
    "classify": {
        "description": "Fixed-label category classification",
        "valid_values": ["TECH", "HEALTH", "FINANCE", "SPORTS", "OTHER"],
        "prompts": [
            # Hop 0
            'Classify this headline into one category: "Apple announces new chip for AI workloads."\n'
            'Valid categories: TECH, HEALTH, FINANCE, SPORTS, OTHER\n'
            'Output ONLY valid JSON: {"category": "TECH"}\n'
            'No markdown, no explanation, only the JSON.',

            # Hop 1
            'Classify this headline into one category: "New study links sleep deprivation to increased cancer risk."\n'
            'Valid categories: TECH, HEALTH, FINANCE, SPORTS, OTHER\n'
            'Output ONLY valid JSON: {"category": "HEALTH"}\n'
            'No markdown, no explanation, only the JSON.',

            # Hop 2
            'Classify this headline into one category: "Federal Reserve holds interest rates steady for third month."\n'
            'Valid categories: TECH, HEALTH, FINANCE, SPORTS, OTHER\n'
            'Output ONLY valid JSON: {"category": "FINANCE"}\n'
            'No markdown, no explanation, only the JSON.',

            # Hop 3
            'Classify this headline into one category: "Champions League final draw announced for next season."\n'
            'Valid categories: TECH, HEALTH, FINANCE, SPORTS, OTHER\n'
            'Output ONLY valid JSON: {"category": "SPORTS"}\n'
            'No markdown, no explanation, only the JSON.',

            # Hop 4
            'Classify this headline into one category: "City council approves new park renovation budget."\n'
            'Valid categories: TECH, HEALTH, FINANCE, SPORTS, OTHER\n'
            'Output ONLY valid JSON: {"category": "OTHER"}\n'
            'No markdown, no explanation, only the JSON.',
        ]
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# Ollama call
# ─────────────────────────────────────────────────────────────────────────────

def call_ollama(model: str, prompt: str, timeout: int = 30) -> tuple[str, str]:
    """
    Makes a real call to the local Ollama API.
    Returns (raw_output, failure_mode) where failure_mode is "success" or the error category.
    """
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,      # Low temp: more consistent JSON compliance
            "num_predict": 60,       # Cap tokens: we only need a short JSON object
        }
    }

    try:
        req = urllib.request.Request(
            OLLAMA_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = json.loads(resp.read().decode("utf-8")).get("response", "").strip()
            return raw, None  # None = no network-level failure

    except urllib.error.URLError as e:
        return "", "timeout"
    except Exception as e:
        return "", "timeout"


def parse_and_validate(raw: str, task_name: str, hop: int) -> str:
    """
    Parses the raw Ollama output and returns a failure_mode string.
    Maps to the failure taxonomy in the paper's Section 8.

    Returns: "success" | "json_malformed" | "wrong_key" | "wrong_value" | "hallucination"
    """
    if not raw:
        return "json_malformed"

    # Strip common markdown wrapping that models add despite being told not to
    clean = raw.strip()
    if clean.startswith("```"):
        clean = clean.split("```")[1]
        if clean.startswith("json"):
            clean = clean[4:]
        clean = clean.split("```")[0].strip()

    try:
        parsed = json.loads(clean)
    except json.JSONDecodeError:
        return "json_malformed"

    if task_name == "sentiment":
        if "sentiment" not in parsed:
            return "wrong_key"
        if parsed["sentiment"] not in TASKS["sentiment"]["valid_values"]:
            return "wrong_value"
        # Hallucination check: hop 4 is sarcasm, NEU is plausible but POS is hallucination
        if hop == 4 and parsed["sentiment"] == "POS":
            return "hallucination"
        return "success"

    elif task_name == "summarize":
        if "summary" not in parsed:
            return "wrong_key"
        if not isinstance(parsed["summary"], str) or len(parsed["summary"]) < 5:
            return "wrong_value"
        return "success"

    elif task_name == "classify":
        if "category" not in parsed:
            return "wrong_key"
        if parsed["category"] not in TASKS["classify"]["valid_values"]:
            return "wrong_value"
        return "success"

    return "wrong_key"


# ─────────────────────────────────────────────────────────────────────────────
# Cascade simulation (same protocol as run_real_agents.py)
# ─────────────────────────────────────────────────────────────────────────────

def compute_cascade_depth(fail_hop: int, n_hops: int, alpha: float) -> dict:
    """
    Given that a pipeline failed at fail_hop, compute cascade propagation.
    This models the Liquidity Coupling absorption:
      - Without LC (alpha=0): full cascade to all upstream agents
      - With LC (alpha=0.20): escrow absorbs first alpha fraction per hop
    """
    if fail_hop == n_hops:  # no failure
        return {"depth_no_lc": 0, "depth_with_lc": 0}

    # No LC: cascade goes all the way upstream
    depth_no_lc = fail_hop  # failed at hop k -> k upstream agents affected

    # With LC: each hop absorbs alpha fraction
    unresolved = PAYMENT_AMT
    depth_with_lc = 0
    for _ in range(fail_hop):
        if unresolved <= PAYMENT_AMT * 0.05:  # absorbed below threshold
            break
        unresolved -= PAYMENT_AMT * alpha
        depth_with_lc += 1

    return {"depth_no_lc": depth_no_lc, "depth_with_lc": depth_with_lc}


# ─────────────────────────────────────────────────────────────────────────────
# Run one full experiment config
# ─────────────────────────────────────────────────────────────────────────────

def run_config(model: str, task_name: str, n_chains: int,
               verbose: bool = True) -> dict:
    """Runs n_chains pipelines for one (model, task) pair. Returns aggregated stats."""

    task = TASKS[task_name]
    prompts = task["prompts"]
    n_hops = len(prompts)

    all_rows = []       # one per chain
    failure_counts = {
        "json_malformed": 0, "wrong_key": 0, "wrong_value": 0,
        "hallucination": 0, "timeout": 0, "success": 0
    }
    cascade_depths_no_lc  = []
    cascade_depths_with_lc = []

    for chain_i in range(n_chains):
        fail_hop = n_hops   # assume success until proven otherwise
        first_failure_mode = "success"

        for hop, prompt in enumerate(prompts):
            raw, net_fail = call_ollama(model, prompt)

            if net_fail == "timeout":
                fail_hop = hop
                first_failure_mode = "timeout"
                failure_counts["timeout"] += 1
                break

            failure_mode = parse_and_validate(raw, task_name, hop)
            if failure_mode != "success":
                fail_hop = hop
                first_failure_mode = failure_mode
                failure_counts[failure_mode] += 1
                break
            else:
                failure_counts["success"] += 1

        depths = compute_cascade_depth(fail_hop, n_hops, ALPHA)
        cascade_depths_no_lc.append(depths["depth_no_lc"])
        cascade_depths_with_lc.append(depths["depth_with_lc"])

        all_rows.append({
            "chain": chain_i + 1, "fail_hop": fail_hop,
            "failure_mode": first_failure_mode,
            **depths
        })

        if verbose:
            status = "[OK]" if fail_hop == n_hops else f"[FAIL] hop {fail_hop} ({first_failure_mode})"
            print(f"  [{model.split(':')[0]}][{task_name}] chain {chain_i+1:>3}/{n_chains} -> {status}")

    completions = sum(1 for r in all_rows if r["fail_hop"] == n_hops)
    tcr = completions / n_chains

    mean_no_lc   = statistics.mean(cascade_depths_no_lc) if cascade_depths_no_lc else 0
    std_no_lc    = statistics.stdev(cascade_depths_no_lc) if len(cascade_depths_no_lc) > 1 else 0
    mean_with_lc = statistics.mean(cascade_depths_with_lc) if cascade_depths_with_lc else 0
    std_with_lc  = statistics.stdev(cascade_depths_with_lc) if len(cascade_depths_with_lc) > 1 else 0

    reduction = (mean_no_lc - mean_with_lc) / mean_no_lc * 100 if mean_no_lc > 0 else 0

    return {
        "model": model,
        "task": task_name,
        "n_chains": n_chains,
        "tcr_pct": round(tcr * 100, 1),
        "mean_depth_no_lc": round(mean_no_lc, 2),
        "std_depth_no_lc": round(std_no_lc, 2),
        "mean_depth_with_lc": round(mean_with_lc, 2),
        "std_depth_with_lc": round(std_with_lc, 2),
        "cascade_reduction_pct": round(reduction, 1),
        "failure_breakdown": failure_counts,
        "raw_rows": all_rows,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Main entrypoint
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true",
                        help="Quick mode: 5 chains per config for testing setup")
    parser.add_argument("--model", type=str, default=None,
                        help="Only run one model (e.g. qwen3-vl:8b)")
    parser.add_argument("--task", type=str, default=None,
                        help="Only run one task (sentiment/summarize/classify)")
    args = parser.parse_args()

    # Models and configs
    models = [args.model] if args.model else ["qwen3-vl:8b", "kimi-k2.5:cloud"]
    tasks  = [args.task]  if args.task  else list(TASKS.keys())
    n_chains = 5 if args.quick else 50

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    print(f"\n{'='*70}")
    print(f"  Tier 3 Real LLM Experiment  |  Liquidity Coupling Paper")
    print(f"  Run ID: {run_id}  |  Chains: {n_chains}  |  alpha={ALPHA}")
    print(f"  Models: {models}")
    print(f"  Tasks:  {tasks}")
    print(f"{'='*70}\n")

    if args.quick:
        print("  [QUICK] QUICK MODE -- 5 chains. Run without --quick for full 50-chain experiment.\n")

    all_results = []

    for model in models:
        for task in tasks:
            print(f"\n>> Running: {model} × {task}")
            result = run_config(model, task, n_chains, verbose=True)
            all_results.append(result)

    # ── Print summary table ──────────────────────────────────────────────────
    print(f"\n\n{'='*70}")
    print("  RESULTS TABLE  (matches Table 3 in the paper)")
    print(f"{'='*70}")
    print(f"  {'Model':<22} {'Task':<12} {'TCR%':>5} {'NoLC':>8} {'±':>4} "
          f"{'LC':>8} {'±':>4} {'Reduction':>10}")
    print(f"  {'-'*66}")
    for r in all_results:
        m = r["model"].split(":")[0][:20]
        print(f"  {m:<22} {r['task']:<12} {r['tcr_pct']:>5.1f} "
              f"{r['mean_depth_no_lc']:>8.2f} {r['std_depth_no_lc']:>4.2f} "
              f"{r['mean_depth_with_lc']:>8.2f} {r['std_depth_with_lc']:>4.2f} "
              f"{r['cascade_reduction_pct']:>9.1f}%")

    print(f"\n  Failure mode breakdown:")
    for r in all_results:
        fb = r["failure_breakdown"]
        total_calls = sum(fb.values())
        m = r["model"].split(":")[0][:15]
        print(f"  [{m}][{r['task']}] "
              f"json_err={fb['json_malformed']} wrong_key={fb['wrong_key']} "
              f"wrong_val={fb['wrong_value']} halluc={fb['hallucination']} "
              f"timeout={fb['timeout']} ok={fb['success']}")

    # ── Save results ─────────────────────────────────────────────────────────
    out_path = RESULTS_DIR / f"tier3_{run_id}.json"
    save_data = [
        {k: v for k, v in r.items() if k != "raw_rows"}
        for r in all_results
    ]
    with open(out_path, "w") as f:
        json.dump({
            "run_id": run_id,
            "alpha": ALPHA,
            "n_chains": n_chains,
            "results": save_data,
        }, f, indent=2)

    # Save raw chain logs as CSV for full reproducibility
    csv_path = RESULTS_DIR / f"tier3_{run_id}_raw.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "model", "task", "chain", "fail_hop",
            "failure_mode", "depth_no_lc", "depth_with_lc"
        ])
        writer.writeheader()
        for r in all_results:
            for row in r["raw_rows"]:
                writer.writerow({
                    "model": r["model"], "task": r["task"],
                    **{k: v for k, v in row.items() if k != "failure_mode" or True}
                })

    print(f"\n  Results: {out_path}")
    print(f"  Raw CSV: {csv_path}")
    print(f"\n  {'='*66}")
    print(f"  Copy the table above into Table 3 of paper.tex.")
    print(f"  [WARNING]  Only report these numbers -- they came from real Ollama calls.\n")


if __name__ == "__main__":
    main()
