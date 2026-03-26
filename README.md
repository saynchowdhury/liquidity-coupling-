<div align="center">
  <h1>Liquidity Coupling in Autonomous Agent Networks</h1>
  <p><b>A Game-Theoretic Foundation for Symbiotic Economic Settlement</b></p>
  
  <a href="paper.pdf"><img src="https://img.shields.io/badge/Read_the_Paper-PDF-red.svg" alt="Read the Paper"></a>
  <img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License">
  <img src="https://img.shields.io/badge/Python-3.10%2B-green.svg" alt="Python Version">
</div>

---

## Abstract

As the machine economy scales toward asynchronous, cross-platform workflows, autonomous agents will increasingly contract sub-agents to fulfill complex queries. However, independent agents lack inherent creditworthiness, creating a systemic risk: a single node failure (e.g., hallucination, API timeout) can trigger an insolvency cascade, halting upstream payments and collapsing the economic graph. 

This repository presents the reference implementation for **Liquidity Coupling**, a cryptographic escrow mechanism designed to halt sub-graph insolvency cascades. By requiring upstream agents to lock a fractional stability stake ($\alpha$), the protocol ensures downstream creditors are automatically reallocated funds if the intermediate agent defaults. 

Our findings demonstrate that a 20% fractional reserve requirement ($\alpha = 0.20$) reduces the average depth of an economic collapse by 64% in a dense agent network. Furthermore, under a Perfect Bayesian Equilibrium (PBE) framework, Liquidity Coupling satisfies the Cho-Kreps Intuitive Criterion, establishing a separating equilibrium where highly reliable agents voluntarily adopt the protocol to signal their solvency.

---

## Repository Structure

This repository contains the official proof-of-concept components for the associated research paper.

```text
liquidity-coupling/
├── paper.pdf                    # The official pre-print research paper
├── liquidity_coupling.py        # Core Mechanism: Python implementation of the Symbiotic Escrow
├── simulation/                  
│   ├── run_experiment.py        # Execution script for Table 2 (10,000-node simulation)
│   ├── seg_simulator.py         # The Symbiotic Economy Graph (SEG) simulator engine
│   └── requirements.txt         # Dependencies for the simulation
├── experiments/                 
│   └── tier3_experiment.py      # Execution script for Table 3 (Empirical LLM pipelining)
└── results/                     # Raw JSON and CSV empirical data outputs
```

---

## 1. Core Mechanism Integration

The fundamental escrow mechanism is available as a standalone Python module for integration into agent frameworks (e.g., Swarms.ai, LangChain).

```python
from liquidity_coupling import LiquidityCoupledEscrow

# Initialize the clearinghouse with defined parameters
escrow = LiquidityCoupledEscrow(alpha=0.20, chi=0.30)

# Agent A commits a $10.00 base stake to acquire Agent B's services
escrow.stake_funds("Agent_A", "Agent_B", base_amount=10.00)

# In the event of Agent B's failure to fulfill downstream obligations
escrow.slash_and_reallocate(
    defaulting_agent="Agent_B", 
    downstream_creditor="Agent_C"
)
```

## 2. Discrete-Event Simulation (10,000 Nodes)

To verify the theoretical proofs regarding branching process theory and cascade halts outlined in Section 4 of the paper, researchers can execute the discrete-event simulator. The simulator evaluates 10,000 agents passing tasks under varying stability thresholds.

```bash
pip install -r simulation/requirements.txt
python simulation/run_experiment.py
```
*Expected Output: Average Cascade Depth reduces significantly from approximately 6.2 hops ($\alpha=0$) to under 1.4 hops ($\alpha=0.30$).*

## 3. Empirical LLM Validation

Section 8 of the paper validates the mathematical model against real-world Generative AI constraints by chaining actual Large Language Models (`qwen3-vl:8b` and `kimi-k2.5:cloud`). The evaluation script intentionally injects standard failure modes (e.g., malformed JSON structures, API timeouts) to observe the mechanism's real-time reallocation efficiency.

**Prerequisites:** Requires a local `ollama` instance and the target models installed.
```bash
python experiments/tier3_experiment.py
```

---

## Future Directions: Application to Fiat Infrastructure
While contemporary literature frequently restricts agentic economies to cryptographically native ledgers, this research establishes a foundation for fiat-bridged protocols. Specifically, high-throughput systems such as India's Unified Payments Interface (UPI) process billions of rapid transactions but currently lack native logic for sub-second, multi-hop machine credit extension. Liquidity Coupling is proposed as a distinct, synthetic layer to facilitate large-scale agent economies over existing emerging-market rails.

## Citation

Please refer to the following format when referencing this mechanism or the associated data sets in academic literature:

```bibtex
@article{chowdhury2026liquidity,
  title={Liquidity Coupling in Autonomous Agent Networks: 
         A Game-Theoretic Foundation for Symbiotic Economic Settlement},
  author={Chowdhury, Sayan},
  journal={arXiv preprint},
  year={2026}
}
```

## License
MIT License. Please consult the embedded research paper (`paper.pdf`) for comprehensive game-theoretic proofs, topological limitations, and boundary conditions.
