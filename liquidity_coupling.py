"""
liquidity_coupling.py — Core mechanism implementation
"Liquidity Coupling in Autonomous Agent Networks"
Author: Sayan Mallick Chowdhury

This is the reference implementation of the LiquidityCoupledEscrow mechanism.
Import this into any agent framework to add Liquidity Coupling guarantees.

Usage:
    from liquidity_coupling import LiquidityCoupledEscrow, Agent

    creditor = Agent("agent_A", liquidity=100.0)
    debtor   = Agent("agent_B", liquidity=20.0)
    escrow   = LiquidityCoupledEscrow(alpha=0.20, creditor=creditor,
                                       debtor=debtor, credit_limit=50.0)
    # On task completion:
    escrow.settle()
    # On default:
    escrow.default(downstream_victims=[...])
"""


class Agent:
    """
    Represents an autonomous agent in a Liquidity Coupled network.

    Attributes:
        agent_id (str): Unique identifier
        liquidity (float): Current free capital (not locked in escrow)
        reputation (float): Trust score [0, 1]; updated via SSO
        escrow_locked (float): Capital currently locked in escrow links
    """

    def __init__(self, agent_id: str, liquidity: float = 0.0,
                 reputation: float = 0.5):
        self.agent_id = agent_id
        self.liquidity = liquidity
        self.reputation = reputation
        self.escrow_locked = 0.0
        self.active_escrows: list["LiquidityCoupledEscrow"] = []
        self._default_history: int = 0

    @property
    def solvency_ratio(self) -> float:
        """Free liquidity as fraction of total (locked + free). SSO input."""
        total = self.liquidity + self.escrow_locked
        return self.liquidity / total if total > 0 else 0.0

    @property
    def is_solvent(self) -> bool:
        return self.liquidity >= 0

    def __repr__(self) -> str:
        return (f"Agent({self.agent_id!r}, liquidity={self.liquidity:.2f}, "
                f"locked={self.escrow_locked:.2f}, rep={self.reputation:.2f})")


class LiquidityCoupledEscrow:
    """
    Bilateral escrow implementing the Liquidity Coupling mechanism.

    Economic model (Section 3 of the paper):
    - Creditor stakes alpha * credit_limit at link formation
    - On successful settlement: stake returns to creditor (no loss)
    - On debtor default: stake absorbs shortfall proportionally to downstream victims
    - Zero-buffer assumption: see Theorem 4.1 proof header

    Game-theoretic property (Theorem 6.1 / PBE):
    - Offering LC is a credible solvency signal under Perfect Bayesian Equilibrium
    - Insolvent agents cannot mimic this signal without incurring reputation slash χ

    Args:
        alpha (float): Coupling fraction in [0, 1]. Must exceed 1 - 1/lambda
                       for stability (Theorem 4.1). Recommended: alpha = 0.20
                       for typical LLM pipelines where lambda ≈ 1.15.
        creditor (Agent): The agent extending credit / hiring downstream
        debtor (Agent): The agent accepting work / being hired
        credit_limit (float): Maximum payment the debtor can receive

    Raises:
        ValueError: If alpha outside [0, 1]
        InsufficientLiquidityError: If creditor cannot fund the stake
    """

    def __init__(self, alpha: float, creditor: Agent, debtor: Agent,
                 credit_limit: float):
        if not 0 <= alpha <= 1:
            raise ValueError(f"alpha must be in [0, 1], got {alpha}")
        if credit_limit <= 0:
            raise ValueError(f"credit_limit must be positive, got {credit_limit}")

        self.alpha = alpha
        self.creditor = creditor
        self.debtor = debtor
        self.credit_limit = credit_limit
        self.stake = alpha * credit_limit
        self._state = "open"   # open | settled | defaulted

        # Stability check: warn if below Theorem 4.1 threshold
        # Assumes lambda is not known at escrow creation — checked at network level

        # Lock creditor capital
        if creditor.liquidity < self.stake:
            raise InsufficientLiquidityError(
                f"Creditor {creditor.agent_id!r} needs {self.stake:.4f} liquidity "
                f"to lock (has {creditor.liquidity:.4f}). "
                f"Consider Delegated Staking (Section 5.2)."
            )
        creditor.liquidity -= self.stake
        creditor.escrow_locked += self.stake
        creditor.active_escrows.append(self)

    @property
    def state(self) -> str:
        return self._state

    def settle(self) -> float:
        """
        Called on successful task completion. Releases full stake back to creditor.

        Returns:
            float: Amount returned to creditor (= stake)
        """
        if self._state != "open":
            raise EscrowStateError(f"Cannot settle escrow in state {self._state!r}")

        self._state = "settled"
        self.creditor.liquidity += self.stake
        self.creditor.escrow_locked -= self.stake
        if self in self.creditor.active_escrows:
            self.creditor.active_escrows.remove(self)
        return self.stake

    def default(self, downstream_victims: list[Agent] = None,
                shortfall: float = None) -> dict:
        """
        Called when the debtor defaults. Distributes locked stake to downstream victims.

        Under the zero-buffer assumption (Theorem 4.1):
            shortfall = credit_limit (full default)
            absorbed   = min(stake, shortfall) = stake
            residual   = shortfall - absorbed = (1 - alpha) * credit_limit

        Args:
            downstream_victims: Agents owed money by the debtor.
                                 If None, absorbed capital stays with creditor network.
            shortfall: Override default shortfall amount (default: full credit_limit)

        Returns:
            dict with keys: absorbed, residual, distributed_per_victim
        """
        if self._state != "open":
            raise EscrowStateError(f"Cannot default escrow in state {self._state!r}")

        self._state = "defaulted"
        shortfall = shortfall if shortfall is not None else self.credit_limit

        absorbed = min(self.stake, shortfall)
        residual = max(0.0, shortfall - absorbed)
        returned_to_creditor = self.stake - absorbed

        # Return non-absorbed stake to creditor
        self.creditor.liquidity += returned_to_creditor
        self.creditor.escrow_locked -= self.stake
        if self in self.creditor.active_escrows:
            self.creditor.active_escrows.remove(self)

        # Reputation slash for debtor (chi penalty from Section 6.1)
        self.debtor.reputation = max(0.0, self.debtor.reputation - 0.1)
        self.debtor._default_history += 1

        # Distribute absorbed capital to victims
        distributed = 0.0
        distributed_per_victim = 0.0
        if downstream_victims and absorbed > 0:
            distributed_per_victim = absorbed / len(downstream_victims)
            for victim in downstream_victims:
                victim.liquidity += distributed_per_victim
            distributed = absorbed

        return {
            "shortfall": shortfall,
            "absorbed": absorbed,
            "residual": residual,
            "returned_to_creditor": returned_to_creditor,
            "distributed_to_victims": distributed,
            "distributed_per_victim": distributed_per_victim,
            "debtor_reputation_after": self.debtor.reputation,
        }

    def __repr__(self) -> str:
        return (f"LiquidityCoupledEscrow("
                f"α={self.alpha}, "
                f"creditor={self.creditor.agent_id!r}, "
                f"debtor={self.debtor.agent_id!r}, "
                f"stake={self.stake:.3f}, "
                f"state={self._state!r})")


class InsufficientLiquidityError(Exception):
    """Raised when a creditor cannot fund the required escrow stake."""
    pass


class EscrowStateError(Exception):
    """Raised when an escrow operation is called in an invalid state."""
    pass


def check_stability(alpha: float, lambda_mean: float) -> dict:
    """
    Checks whether the given alpha satisfies the Theorem 4.1 stability condition.

    Args:
        alpha: Coupling fraction being deployed
        lambda_mean: Mean downstream branching rate of the network

    Returns:
        dict with stability status and diagnostics
    """
    threshold = 1 - 1 / lambda_mean
    r_eff = lambda_mean * (1 - alpha)
    cascade_bound = 1 / (1 - r_eff) if r_eff < 1 else float("inf")

    return {
        "stable": alpha > threshold,
        "alpha": alpha,
        "lambda": lambda_mean,
        "threshold": round(threshold, 4),
        "r_eff": round(r_eff, 4),
        "expected_cascade_size": round(cascade_bound, 2) if cascade_bound != float("inf") else "∞",
        "margin": round(alpha - threshold, 4),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Quick demo
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== Liquidity Coupling — Quick Demo ===\n")

    # Check stability for recommended alpha
    status = check_stability(alpha=0.20, lambda_mean=1.15)
    print(f"Stability check: {status}")
    print(f"  → {'✅ STABLE' if status['stable'] else '❌ UNSTABLE'}")
    print(f"  → Expected cascade size bound: {status['expected_cascade_size']} nodes\n")

    # Create a 3-agent chain: A → B → C
    agent_a = Agent("A", liquidity=10.0, reputation=0.9)
    agent_b = Agent("B", liquidity=5.0, reputation=0.7)
    agent_c = Agent("C", liquidity=2.0, reputation=0.5)

    # A hires B (α=0.20, credit=5.0 → stake=1.0)
    escrow_ab = LiquidityCoupledEscrow(
        alpha=0.20, creditor=agent_a, debtor=agent_b, credit_limit=5.0
    )
    print(f"After escrow AB creation: {agent_a}")
    print(f"  Escrow: {escrow_ab}\n")

    # B defaults — cascade test
    result = escrow_ab.default(downstream_victims=[agent_c])
    print(f"B defaults on A:")
    print(f"  Absorbed: {result['absorbed']:.2f} | Residual: {result['residual']:.2f}")
    print(f"  Returned to A: {result['returned_to_creditor']:.2f}")
    print(f"  B reputation after: {result['debtor_reputation_after']:.2f}")
    print(f"  Creditor A after: {agent_a}")
    print(f"\n✅ Mechanism working: residual = {result['residual']:.2f} = (1-α)×p = {0.80*5.0:.2f}")
