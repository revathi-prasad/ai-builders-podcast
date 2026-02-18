# Research Roadmap

> Open research directions for extending the AI Podcast Generator

This project serves as a testbed for multi-agent coordination, reinforcement learning, and cultural adaptation research. Below are research questions that can be explored using this codebase.

---

## Multi-Agent Coordination

| RQ | Question | Relevant Code |
|----|----------|---------------|
| RQ1 | Do explicit handoff protocols reduce context reset and information withholding failures? | `src/models/state.py` (LightweightHandoff), `src/verification/fm_monitors.py` |
| RQ2 | Does graph-structured memory outperform linear context for multi-modal synthesis? | `src/graph/manager.py`, `src/graph/schema.py` |
| RQ3 | What is the optimal verification granularity in multi-agent systems? | `src/verification/quality_checkers.py`, `src/verification/fm_monitors.py` |

## Reinforcement Learning for Multi-Agent Systems

| RQ | Question | Relevant Code |
|----|----------|---------------|
| RQ4 | Does FM-augmented reward shaping improve credit assignment vs sparse rewards? | `src/verification/fm_monitors.py`, `src/rl/reward_model.py` |
| RQ5 | Can training only the Planner agent achieve most of the quality gains? | `src/rl/trainer.py`, `src/agents/graph.py` |
| RQ6 | What reward function best balances accuracy vs engagement for creative content? | `src/rl/reward_model.py` (CompositeRewardModel) |

## Cultural Adaptation

| RQ | Question | Relevant Code |
|----|----------|---------------|
| RQ7 | Does a debate-based architecture produce more culturally sensitive content? | `src/agents/generator.py` (persona system) |
| RQ8 | Which cultural adaptation patterns generalize across languages vs require tuning? | `src/agents/generator.py` (DEFAULT_PERSONAS) |
| RQ9 | Does cultural adaptation measurably improve engagement for target audiences? | `src/agents/synthesizer.py`, `src/rl/reward_model.py` |

## Information Preservation and Provenance

| RQ | Question | Relevant Code |
|----|----------|---------------|
| RQ10 | What KG schema best preserves provenance across modalities? | `src/graph/schema.py` |
| RQ11 | Does temporal awareness improve detection of outdated facts? | `src/graph/schema.py` (valid_from/valid_until fields) |

## Failure Mode Analysis

| RQ | Question | Relevant Code |
|----|----------|---------------|
| RQ12 | Which MAST failure modes are most prevalent in podcast generation? | `src/verification/fm_monitors.py` |
| RQ13 | How do early-stage failures cascade to downstream agents? | `src/agents/graph.py` (workflow), `src/verification/fm_monitors.py` |

## Voice Generation RL

| RQ | Question | Relevant Code |
|----|----------|---------------|
| RQ14 | Can RL fine-tune TTS for podcast-specific prosody? | `src/agents/synthesizer.py` |
| RQ15 | Can implicit listener engagement signals serve as TTS reward? | `src/rl/reward_model.py` (EngagementRewardModel) |
| RQ16 | Does joint end-to-end RL outperform stage-wise optimization? | `src/rl/trainer.py`, `src/agents/graph.py` |
| RQ17 | Does RL fine-tuning maintain voice identity consistency? | `src/agents/synthesizer.py` |

---

## Getting Started with Research

1. **Understand the architecture**: Read [ARCHITECTURE_v2.md](ARCHITECTURE_v2.md) for the full system design
2. **Pick a research question**: Choose an RQ above and explore the relevant code
3. **Run the baseline**: `python -m src --topic "your topic" --verbose` to see the current pipeline in action
4. **Extend**: Implement variations and compare against the baseline

## Related Work

- [AgentFlow](https://arxiv.org/abs/2510.05592) — In-the-Flow RL for multi-agent systems
- [MAST](https://arxiv.org/abs/2503.13657) — Multi-agent failure taxonomy
- [Graphiti](https://github.com/getzep/graphiti) — Temporal knowledge graphs for agents
- [DPO](https://arxiv.org/abs/2305.18290) — Direct Preference Optimization (Rafailov et al., 2023)
- [GRPO](https://arxiv.org/abs/2402.03300) — Group Relative Policy Optimization (Shao et al., 2024)

---

Contributions and research collaborations are welcome.
