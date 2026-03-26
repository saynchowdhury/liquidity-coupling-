"""
run_experiment.py — One-command reproduction of Table 2
"Liquidity Coupling in Autonomous Agent Networks"
Author: Sayan Mallick Chowdhury

Usage:
    python run_experiment.py

Output: Prints Table 2 to terminal and saves results to results/table2_results.json
"""

import sys
import os
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from seg_simulator import run_alpha_sweep

OUTPUT_DIR = Path(__file__).parent.parent / "results"
OUTPUT_DIR.mkdir(exist_ok=True)

# Exact parameters from Section 8 of the paper
N_AGENTS   = 10_000
LAMBDA     = 1.15   # anchored from LLM pipeline traces
TRIALS     = 100    # number of independent cascade trials per alpha
ALPHAS     = [round(x * 0.05, 2) for x in range(1, 11)]  # 0.05 to 0.50
THRESHOLD  = 1 - 1 / LAMBDA

def print_table(results):
    print()
    print("=" * 68)
    print(f"  Table 2 Reproduction: Cascade Depth vs. Alpha (λ={LAMBDA}, N={N_AGENTS:,})")
    print("=" * 68)
    print(f"  {'α':>5} | {'Threshold':>9} | {'Mean Depth':>10} | {'±σ':>6} | {'Status':>10}")
    print("-" * 68)
    for r in results:
        stable = "✅ STABLE" if r["alpha"] > THRESHOLD else "⚠️  unsafe"
        print(f"  {r['alpha']:>5.2f} | {THRESHOLD:>9.4f} | {r['mean_depth']:>10.2f} | "
              f"{r['stdev_depth']:>6.2f} | {stable:>10}")
    print("=" * 68)
    key = next((r for r in results if r["alpha"] == 0.20), None)
    if key:
        print(f"\n  Paper reports: α=0.20 → 1.7 mean cascade depth")
        print(f"  Simulator:     α=0.20 → {key['mean_depth']:.1f} mean cascade depth")
        match = "✅ Match" if abs(key['mean_depth'] - 1.7) < 0.5 else "⚠️  Check parameters"
        print(f"  Verification: {match}")
    print()

def main():
    print("\nRunning Table 2 experiment...")
    print(f"  Agents: {N_AGENTS:,} | λ={LAMBDA} | Trials/alpha: {TRIALS}")
    print(f"  Stability threshold: α > {THRESHOLD:.4f}\n")

    results = run_alpha_sweep(
        n_agents=N_AGENTS,
        lambda_mean=LAMBDA,
        alphas=ALPHAS,
        trials=TRIALS,
        verbose=False,
    )

    print_table(results)

    out_path = OUTPUT_DIR / "table2_results.json"
    with open(out_path, "w") as f:
        json.dump({
            "paper": "Liquidity Coupling in Autonomous Agent Networks",
            "author": "Sayan Mallick Chowdhury",
            "parameters": {"n_agents": N_AGENTS, "lambda": LAMBDA, "trials": TRIALS},
            "results": results
        }, f, indent=2)

    print(f"  Results saved to: {out_path}\n")

if __name__ == "__main__":
    main()
