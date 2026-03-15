#!/usr/bin/env python3
"""
Tarka — adversarial deliberation layer on top of AI agents.

Orchestrates CLI agents (Claude Code, Codex, Gemini CLI, etc.) into
structured debate to reduce hallucination and improve judgment.

Usage:
    python tarka.py "design the caching layer for our API"
    python tarka.py "should we migrate from REST to GraphQL" --rounds 3
    python tarka.py "write a go-to-market plan for the beta launch" --cwd ./project
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass


# --- Agents ---


@dataclass(frozen=True)
class Agent:
    """An AI agent accessible via CLI."""

    name: str
    command: list[str]  # must contain {prompt} placeholder

    def ask(self, prompt: str, cwd: str = ".") -> str:
        cmd = [part.replace("{prompt}", prompt) for part in self.command]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
        if result.returncode != 0:
            raise RuntimeError(f"{self.name} failed: {result.stderr.strip()}")
        return result.stdout.strip()


CLAUDE = Agent("Claude", ["claude", "-p", "{prompt}", "--no-input"])
CODEX = Agent("Codex", ["codex", "-q", "{prompt}"])


# --- Prompts ---

PROPOSE = """\
Propose an approach for the following task. Focus on key decisions,
tradeoffs, and risks. Be specific and concrete.

TASK: {task}"""

CRITIQUE = """\
You are reviewing another AI agent's proposal.

Find the flaws. Surface unstated assumptions. Identify edge cases and
overcomplications. Do NOT be agreeable — if you agree with everything,
you have failed at your job.

Say what's wrong, what's missing, and what you'd do differently.

TASK: {task}

THEIR PROPOSAL:
{proposal}"""

SYNTHESIZE = """\
Two experts debated the approach below. Synthesize their final positions
into a concrete plan.

Where they disagree, pick the stronger argument and say why.
Where both missed something, add it.

TASK: {task}

DEBATE:
{debate}"""


# --- Deliberation ---


def _parallel(agents: list[Agent], prompts: list[str], cwd: str) -> list[str]:
    """Ask multiple agents in parallel. Returns responses in input order."""
    with ThreadPoolExecutor(max_workers=len(agents)) as pool:
        futures = {
            pool.submit(agent.ask, prompt, cwd): i
            for i, (agent, prompt) in enumerate(zip(agents, prompts))
        }
        results = [None] * len(agents)
        for future in as_completed(futures):
            results[futures[future]] = future.result()
        return results


def deliberate(
    task: str,
    agents: tuple[Agent, Agent] = (CLAUDE, CODEX),
    rounds: int = 2,
    cwd: str = ".",
) -> str:
    a, b = agents

    # Phase 1 — independent proposals
    print(f"  {a.name} and {b.name} proposing independently...")
    pos_a, pos_b = _parallel(
        [a, b],
        [PROPOSE.format(task=task)] * 2,
        cwd,
    )

    log = [
        f"[{a.name} — proposal]\n{pos_a}",
        f"[{b.name} — proposal]\n{pos_b}",
    ]

    # Phase 2 — adversarial debate
    for r in range(1, rounds + 1):
        print(f"  Round {r}...")
        # a critiques b's position, b critiques a's — independent
        pos_a, pos_b = _parallel(
            [a, b],
            [
                CRITIQUE.format(task=task, proposal=pos_b),
                CRITIQUE.format(task=task, proposal=pos_a),
            ],
            cwd,
        )
        log.append(f"[{a.name} — round {r}]\n{pos_a}")
        log.append(f"[{b.name} — round {r}]\n{pos_b}")

    # Phase 3 — synthesis
    print(f"  {a.name} synthesizing...")
    return a.ask(
        SYNTHESIZE.format(task=task, debate="\n\n---\n\n".join(log)),
        cwd,
    )


# --- CLI ---


def main():
    parser = argparse.ArgumentParser(
        description="Adversarial deliberation layer on top of AI agents.",
    )
    parser.add_argument("task", help="the task to deliberate on")
    parser.add_argument("--rounds", type=int, default=2, help="debate rounds (default: 2)")
    parser.add_argument("--cwd", default=".", help="working directory for agents")
    args = parser.parse_args()

    print("Tarka\n")
    plan = deliberate(args.task, rounds=args.rounds, cwd=args.cwd)
    print("\n" + plan)


if __name__ == "__main__":
    main()
