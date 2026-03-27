# Reproducibility & Evaluation Roadmap

### **To Amal, Jaiya, and Independent Reviewers:**
This document outlines the technical verification steps for the paper *Liquidity Coupling in Autonomous Agent Networks*. It is designed to facilitate 1:1 reproduction of the theoretical and empirical results by the ML/AI evaluation committee.

---

## 1. Quality & Technical Soundness
Reproduction of Theorem 4.1 (Cascade depth limits) and Theorem 6.1 (Game-theoretic stability) is supported through direct code execution.
- **Protocol Logic:** The core `LiquidityCoupledEscrow` class in `liquidity_coupling.py` provides the reference implementation of the stability mechanism.
- **Simulation Verification (`simulation/run_experiment.py`):** Replicates the discrete-event model of a 10,000-node homogeneous agent network. Proves the existence of a subcritical regime where $\alpha > 1 - 1/\lambda$ halts insolvency propagation.
- **Empirical LLM Validation (`experiments/tier3_experiment.py`):** Uses real inference chains via Ollama (`qwen3-vl:8b`) to observe generative failure signatures (e.g., malformed JSON) and their impact on the settlement graph.

## 2. Clarity & Presentation
The project is structured to separate orchestration logic from mechanism design logic.
- **Accessible Overview:** See `README.md` and the **Executive Summary** in the paper for a non-technical mapping of the insolvency cascade problem.
- **Implementation Mapping:** `liquidity_coupling.py` is isolated specifically to allow reviewers to audit the staking and reallocation logic without distraction from simulation boilerplate.

## 3. Significance & Deployment Potential
Existing Multi-Agent System (MAS) protocols primarily address the "payment rail" (how to send bits of money) but not the "solvency risk" (how to ensure the agent finishes the task without defaulting on downstream creditors). 
- **Symbiotic Credit Extension:** This mechanism enables fractional staking to replace 100% pre-funding, reducing capital friction in low-trust agentic environments.
- **Real-World Rails:** The paper identifies India's **Unified Payments Interface (UPI)** as a primary candidate for a production-scale liquidity coupling layer.

## 4. Originality & Methodology
The paper fuses epidemiological branching process theory (Galton-Watson) with standard Bayesian game theory (Perfect Bayesian Equilibrium) to establish a formal floor for agentic network stability.

---

## Technical Instructions for Verification

**1. Verifying Theoretical Stability (Simulation):**
```bash
cd simulation
python run_experiment.py
```
*Verification Target: Confirm that Average Cascade Depth converges to < 1.5 hops when the coupling parameter $\alpha \geq 0.20$.*

**2. Verifying Empirical LLM Failure Modes:**
*Requires `qwen3-vl:8b` via Ollama.*
```bash
cd experiments
python tier3_experiment.py --quick
```
*Verification Target: Observe the successful reallocation of staked funds from a hallucinating 'A2' node to an upstream 'A1' and downstream 'A3' node.*
