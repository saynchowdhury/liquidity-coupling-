"""
seg_simulator.py — Discrete-event cascade simulator for Liquidity Coupling
Reproduces Table 2 from: "Liquidity Coupling in Autonomous Agent Networks"
Author: Sayan Mallick Chowdhury

Usage:
    python seg_simulator.py --nodes 10000 --alpha 0.20 --trials 100
"""

import argparse
import random
import statistics
import json
from dataclasses import dataclass, field
from typing import Optional
import sys

# ─────────────────────────────────────────────────────────────────────────────
# Core data structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Agent:
    agent_id: int
    lambda_out: float        # E[downstream obligations] — branching rate
    liquidity: float = 1.0   # normalized starting capital
    insolvent: bool = False
    escrow_locked: float = 0.0

@dataclass
class EscrowLink:
    creditor_id: int
    debtor_id: int
    credit_limit: float
    alpha: float
    stake: float = field(init=False)
    released: bool = False

    def __post_init__(self):
        self.stake = self.alpha * self.credit_limit

# ─────────────────────────────────────────────────────────────────────────────
# Liquidity Coupling Escrow — the core mechanism (also in liquidity_coupling.py)
# ─────────────────────────────────────────────────────────────────────────────

class LiquidityCoupledEscrow:
    """
    Implements the bilateral escrow mechanism described in Section 3 of the paper.
    The creditor locks alpha * credit_limit at link formation.
    On debtor insolvency, locked capital flows proportionally to downstream victims.
    On settlement, locked capital returns to the creditor.
    """

    def __init__(self, alpha: float, creditor: Agent, debtor: Agent,
                 credit_limit: float):
        if alpha < 0 or alpha > 1:
            raise ValueError("alpha must be in [0, 1]")
        self.alpha = alpha
        self.creditor = creditor
        self.debtor = debtor
        self.credit_limit = credit_limit
        self.stake = alpha * credit_limit

        # Lock creditor capital at escrow creation
        if creditor.liquidity < self.stake:
            raise RuntimeError(
                f"Creditor {creditor.agent_id} has insufficient liquidity "
                f"({creditor.liquidity:.3f}) to lock stake ({self.stake:.3f})"
            )
        creditor.liquidity -= self.stake
        creditor.escrow_locked += self.stake
        self.settled = False

    def on_insolvency(self, shortfall: float,
                      downstream_creditors: list["LiquidityCoupledEscrow"]) -> float:
        """
        Called when the debtor defaults. Distributes locked capital proportionally
        to cover downstream shortfalls. Returns total amount recovered by victims.

        Zero-buffer assumption: shortfall propagation is linear in (1-alpha).
        See Theorem 4.1 proof and the explicit Assumption at its head.
        """
        if self.settled:
            return 0.0
        self.settled = True

        # Release creditor's locked stake back (the escrow absorbs loss)
        absorb = min(self.stake, shortfall)
        recovered = absorb

        # Net shortfall passed downstream = shortfall - absorbed
        residual = max(0.0, shortfall - absorb)

        # Return stake remainder to creditor's free liquidity
        self.creditor.liquidity += (self.stake - absorb)
        self.creditor.escrow_locked -= self.stake

        return recovered, residual

    def on_settlement(self) -> None:
        """Called on successful task completion — full stake returns to creditor."""
        if self.settled:
            return
        self.settled = True
        self.creditor.liquidity += self.stake
        self.creditor.escrow_locked -= self.stake


# ─────────────────────────────────────────────────────────────────────────────
# Network builder
# ─────────────────────────────────────────────────────────────────────────────

def build_random_network(n_agents: int, lambda_mean: float,
                         alpha: float, seed: int = 42) -> tuple:
    """
    Builds a random directed agent graph where each agent has Poisson(lambda_mean)
    downstream connections. Corresponds to the homogeneous random graph used in
    Theorem 4.1. For scale-free experiments see Corollary 4.2 discussion.
    """
    rng = random.Random(seed)
    agents = [Agent(i, rng.gauss(lambda_mean, 0.1)) for i in range(n_agents)]
    escrows = {}

    for agent in agents:
        n_downstream = max(0, round(rng.gauss(agent.lambda_out, 0.3)))
        candidates = [a for a in agents if a.agent_id != agent.agent_id]
        targets = rng.sample(candidates, min(n_downstream, len(candidates)))
        for target in targets:
            key = (agent.agent_id, target.agent_id)
            if key not in escrows and agent.liquidity >= alpha * 1.0:
                escrows[key] = LiquidityCoupledEscrow(
                    alpha=alpha,
                    creditor=agent,
                    debtor=target,
                    credit_limit=1.0
                )
    return agents, escrows


# ─────────────────────────────────────────────────────────────────────────────
# Cascade simulator
# ─────────────────────────────────────────────────────────────────────────────

def simulate_cascade(agents: list, escrows: dict,
                     seed_agent_id: int) -> dict:
    """
    Simulates an insolvency cascade starting from seed_agent_id.
    Returns cascade statistics: depth, breadth, total affected nodes.

    Implements the branching process model from Section 4:
    - Each insolvent agent propagates shortfall to downstream creditors
    - With Liquidity Coupling: shortfall is reduced by alpha fraction
    - Without: full shortfall propagates (alpha=0 case)
    """
    agents[seed_agent_id].insolvent = True
    insolvent_queue = [seed_agent_id]
    visited = {seed_agent_id}

    hop_counts = {seed_agent_id: 0}
    cascade_depth = 0
    cascade_size = 1

    while insolvent_queue:
        current_id = insolvent_queue.pop(0)
        current_hop = hop_counts[current_id]
        cascade_depth = max(cascade_depth, current_hop)

        # Find all escrows where this agent is the DEBTOR
        debtor_links = [
            (key, esq) for key, esq in escrows.items()
            if key[1] == current_id and not esq.settled
        ]

        for (cred_id, deb_id), esq in debtor_links:
            shortfall = esq.credit_limit  # full miss under zero-buffer assumption
            recovered, residual = esq.on_insolvency(shortfall, [])

            # Residual shortfall propagates upstream to creditor
            if residual > 0 and esq.creditor.liquidity < residual:
                if cred_id not in visited:
                    esq.creditor.insolvent = True
                    visited.add(cred_id)
                    hop_counts[cred_id] = current_hop + 1
                    insolvent_queue.append(cred_id)
                    cascade_size += 1

    return {
        "cascade_depth": cascade_depth,
        "cascade_size": cascade_size,
        "affected_fraction": cascade_size / len(agents),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Experiment runner
# ─────────────────────────────────────────────────────────────────────────────

def run_alpha_sweep(n_agents: int, lambda_mean: float,
                    alphas: list, trials: int, verbose: bool = True) -> list:
    """
    Sweeps alpha values and measures cascade depth/size. Reproduces Table 2.
    """
    results = []

    for alpha in alphas:
        depths = []
        sizes = []

        for trial in range(trials):
            agents, escrows = build_random_network(
                n_agents, lambda_mean, alpha, seed=trial * 1000
            )
            seed_id = random.randint(0, n_agents - 1)
            stats = simulate_cascade(agents, escrows, seed_id)
            depths.append(stats["cascade_depth"])
            sizes.append(stats["cascade_size"])

        row = {
            "alpha": alpha,
            "mean_depth": round(statistics.mean(depths), 2),
            "stdev_depth": round(statistics.stdev(depths) if len(depths) > 1 else 0.0, 2),
            "mean_size": round(statistics.mean(sizes), 2),
            "affected_pct": round(statistics.mean(sizes) / n_agents * 100, 2),
        }
        results.append(row)

        if verbose:
            stable = "✅ STABLE" if alpha > 1 - 1/lambda_mean else "⚠️ UNSAFE"
            print(f"α={alpha:.2f} | depth={row['mean_depth']:.1f}±{row['stdev_depth']:.1f} "
                  f"| affected={row['affected_pct']:.1f}% | threshold={stable}")

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Liquidity Coupling Cascade Simulator — reproduces Table 2"
    )
    parser.add_argument("--nodes", type=int, default=10000)
    parser.add_argument("--lambda-mean", type=float, default=1.15,
                        help="Mean downstream branching rate (anchored from LLM traces)")
    parser.add_argument("--alpha", type=float, default=None,
                        help="Single alpha to test (if omitted, sweeps 0.05–0.50)")
    parser.add_argument("--trials", type=int, default=50)
    parser.add_argument("--output", type=str, default=None,
                        help="Save results as JSON to this path")
    args = parser.parse_args()

    threshold = 1 - 1 / args.lambda_mean
    print(f"\n{'='*60}")
    print(f"Liquidity Coupling Cascade Simulator v1.0")
    print(f"Agents: {args.nodes:,} | λ={args.lambda_mean} | Trials: {args.trials}")
    print(f"Stability threshold α > {threshold:.4f}  (Theorem 4.1)")
    print(f"{'='*60}\n")

    alphas = [args.alpha] if args.alpha else [
        round(x * 0.05, 2) for x in range(1, 11)  # 0.05 to 0.50
    ]

    results = run_alpha_sweep(
        n_agents=args.nodes,
        lambda_mean=args.lambda_mean,
        alphas=alphas,
        trials=args.trials,
    )

    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to {args.output}")

    print(f"\nKey result: at α=0.20, mean cascade depth = {next(r['mean_depth'] for r in results if r['alpha']==0.20):.1f}")
    print("Compare against Table 2 in the paper — should read ~1.7 hops\n")


if __name__ == "__main__":
    main()
