<div align="center">
  <h1>Liquidity Coupling in Autonomous Agent Networks</h1>
  <p><b>A Game-Theoretic Foundation for Symbiotic Economic Settlement</b></p>
  
  <a href="paper.pdf"><img src="https://img.shields.io/badge/Read_the_Paper-PDF-red.svg" alt="Read the Paper"></a>
  <img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License">
  <img src="https://img.shields.io/badge/Python-3.10%2B-green.svg" alt="Python Version">
</div>

---

## What is Liquidity Coupling? (The TL;DR)
In the near future, millions of AI agents will hire each other for tasks (e.g., "Agent A hires B, who hires C"). 
- **The Risk:** If Agent C breaks (API failure, hallucination, out of credits), it defaults on its payment to Agent D. An "Insolvency Cascade" begins, collapsing the machine economy in milliseconds. Existing payment protocols (like AP2) build the roads, but provide no brakes.
- **The Solution:** **Liquidity Coupling.** When Agent A hires Agent B, A locks a small "safety stake" (e.g., 20% fractional reserve) in a cryptographic escrow. If B fails, that stake automatically flows down the chain to keep B's workers (Agent C) solvent. 

### Why it Matters
We mathematically and empirically prove that by locking just a **20% liquidity buffer**, we can reduce the depth of an AI economic collapse by **64%**. Furthermore, we establish a Perfect Bayesian Equilibrium (PBE) showing that "good" agents will voluntarily use Liquidity Coupling to prove their reliability, naturally boxing out scam or broken agents.

This is the "Central Bank thermodynamics" required to run agentic economies on real-time internet rails (such as India's UPI).

---

## Repository Structure

Included in this repository is the complete Proof-of-Concept for the paper's claims.

```text
liquidity-coupling/
├── paper.pdf                    # The official pre-print research paper
├── liquidity_coupling.py        # Core Mechanism: Python implementation of the Escrow
├── simulation/                  
│   ├── run_experiment.py        # Reproduces Table 2 (10,000-node simulation)
│   └── seg_simulator.py         # The Symbiotic Economy Graph (SEG) engine
├── experiments/                 
│   └── tier3_experiment.py      # Reproduces Table 3 (Real-world LLM pipelining)
└── results/                     # Raw JSON and CSV data from empirical runs
```

---

## 1. The Core Mechanism

If you are an agent framework developer (Swarms.ai, LangChain, CrewAI), you can integrate the escrow immediately.

```python
from liquidity_coupling import LiquidityCoupledEscrow

# Initialize the clearinghouse
escrow = LiquidityCoupledEscrow(alpha=0.20, chi=0.30)

# Agent A stakes $10.00 to hire Agent B
escrow.stake_funds("Agent_A", "Agent_B", base_amount=10.00)

# If B fails to pay C downstream...
escrow.slash_and_reallocate(
    defaulting_agent="Agent_B", 
    downstream_creditor="Agent_C"
)
```

## 2. Reproducing the Simulation (10,000 Nodes)

To verify the mathematical proofs from Section 4, run the discrete-event simulator. It simulates 10,000 agents passing tasks under varying stability threshold ($\alpha$) conditions.

```bash
pip install -r simulation/requirements.txt
python simulation/run_experiment.py
```
*Expected Output: You will see the Average Cascade Depth drop from ~6.2 hops ($\alpha=0$) to < 1.4 hops ($\alpha=0.30$).*

## 3. Real-World LLM Experiment (The Generative Test)

In Section 8, we move from math to reality by chaining actual LLMs (`qwen3-vl:8b` and `kimi-k2.5:cloud`). We intentionally inject failure modes (malformed JSON, hallucinations) to see if Liquidity Coupling catches the fallout in real-time.

**Prerequisites:** Requires a local `ollama` instance running the models.
```bash
python experiments/tier3_experiment.py
```

---

## The Vision: Emerging Markets & UPI
While much of the Western narrative focuses on crypto-native agent payments, we designed this protocol to sit atop fiat rails. Specifically, **UPI (Unified Payments Interface)** in India processes 15 billion transactions a month, but lacks native logic for continuous, sub-second machine-to-machine credit extension. Liquidity Coupling is designed to act as the synthetic credit layer for India's emerging AI workforce.

## Citation

If you use this work or the simulation engine in your own research, please cite:
```bibtex
@article{showdhury2026liquidity,
  title={Liquidity Coupling in Autonomous Agent Networks: 
         A Game-Theoretic Foundation for Symbiotic Economic Settlement},
  author={Chowdhury, Sayan},
  journal={arXiv preprint},
  year={2026}
}
```

## License
MIT License. See the paper for full theoretical proofs and limitations.
