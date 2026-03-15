# Tarka

Adversarial deliberation layer on top of AI agents.

Tarka sits on top of agentic CLI tools — Claude Code, Codex, Gemini CLI, and others — and orchestrates them into structured debate before any work gets done.

## The Problem

AI agents are sycophantic. They agree with whatever framing they're given. When one reviews another's work, it's anchored by the existing solution — biased toward acceptance. Hallucinations pass through. Assumptions go unchallenged.

## The Fix

Force independent reasoning before exposure, then structured debate.

**Propose** — Both agents independently analyze the problem and propose an approach. Neither sees the other's output.

**Debate** — Each agent critiques the other's proposal. The prompt explicitly penalizes agreement. 2-3 adversarial rounds surface the assumptions a single agent would silently bake in.

**Synthesize** — One agent merges the debate into a final plan, picking the stronger argument at each disagreement.

This works because different agents hallucinate *differently*. Each catches the other's blind spots better than its own.

## Usage

```bash
python tarka.py "design the caching layer for our API"
python tarka.py "should we migrate from REST to GraphQL" --rounds 3
python tarka.py "write a go-to-market plan for the beta launch" --cwd ./project
```

## Limits

- **Shared misconceptions** — If both agents believe the same wrong thing, debate won't catch it. Grounding (tests, docs, research) is still needed.
- **Diminishing returns** — After 2-3 rounds, agents converge on compromise rather than truth.

## Why "Tarka"?

Sanskrit (तर्क) for *reasoning through deliberation* — the Nyaya school's method of testing a claim by assuming its opposite and exposing the contradictions that follow.
