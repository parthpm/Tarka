#!/usr/bin/env python3
"""
Tarka — adversarial deliberation layer on top of AI agents.

Tarka is a DETERMINISTIC HARNESS, not a third brain. All intelligence
lives inside the agents. Tarka mechanically executes a fixed protocol:
propose → critique × N → synthesize. Given the same agent outputs, it
always routes, formats, and presents identically. No LLM in the
orchestration layer. No smart routing. No AI deciding when to stop.

Usage:
    python tarka.py "design the caching layer for our API"
    python tarka.py "should we migrate from REST to GraphQL" --rounds 3
    python tarka.py "refactor the auth module" --cwd ./project
    python tarka.py "pick a database" --agents claude codex --quiet
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

# --- Colors (ANSI, no deps) ---

_RESET = "\033[0m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_AGENT_COLORS = {
    "claude": "\033[38;5;209m",  # orange
    "codex": "\033[38;5;114m",   # green
    "gemini": "\033[38;5;75m",   # blue
}


def _color(agent_name: str, text: str) -> str:
    c = _AGENT_COLORS.get(agent_name.lower(), "")
    return f"{c}{text}{_RESET}" if c else text


def _dim(text: str) -> str:
    return f"{_DIM}{text}{_RESET}"


def _bold(text: str) -> str:
    return f"{_BOLD}{text}{_RESET}"


# --- Agents ---

TIMEOUT = 180


@dataclass(frozen=True)
class Agent:
    """An AI agent accessible via CLI."""

    name: str
    command: list[str]  # must contain {prompt} placeholder

    def ask(self, prompt: str, cwd: str = ".", stream: bool = False) -> str:
        """Run the agent. If stream=True, print output to terminal as it arrives."""
        cmd = [part.replace("{prompt}", prompt) for part in self.command]
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, cwd=cwd,
        )
        # Kill the process if it exceeds the timeout, even during streaming.
        timer = threading.Timer(TIMEOUT, proc.kill)
        timer.start()
        try:
            if stream:
                chunks: list[str] = []
                for line in proc.stdout:
                    chunks.append(line)
                    sys.stdout.write(line)
                    sys.stdout.flush()
                proc.wait()
                if proc.returncode and proc.returncode < 0:
                    raise RuntimeError(f"{self.name} timed out after {TIMEOUT}s")
                return "".join(chunks).strip()
            else:
                stdout, stderr = proc.communicate()
                if proc.returncode and proc.returncode < 0:
                    raise RuntimeError(f"{self.name} timed out after {TIMEOUT}s")
                if proc.returncode != 0:
                    raise RuntimeError(f"{self.name} failed: {stderr.strip()}")
                return stdout.strip()
        finally:
            timer.cancel()


CLAUDE = Agent("Claude", ["claude", "-p", "{prompt}", "--no-input"])
CODEX = Agent("Codex", ["codex", "exec", "{prompt}"])
GEMINI = Agent("Gemini", ["gemini", "-p", "{prompt}"])

AGENTS = {"claude": CLAUDE, "codex": CODEX, "gemini": GEMINI}


# --- Prompts ---
#
# These are static templates with deterministic substitution. The prompts
# do the work — they are the product, not the code. Anti-sycophancy
# hardening is baked in: without it, RLHF-trained models perform
# "debate theater" and converge to the safe, conventional answer.

PROPOSE = """\
Propose an approach for the following task. Focus on key decisions,
tradeoffs, and risks. Be specific and concrete.

Commit to a clear position. Do not hedge with "it depends" — pick the
best path given what you know and defend it.

TASK: {task}"""

CRITIQUE = """\
You are reviewing another AI agent's proposal. Your job is genuine
adversarial review, not polite agreement.

Rules:
- You MUST find at least one substantive flaw or unstated assumption.
- If you agree with everything, you have FAILED at your job.
- Do not soften your critique. Be direct about what is wrong.
- Say what is missing, what breaks under pressure, and what you would do
  differently.
- If their proposal is genuinely strong, attack the implementation
  details, timeline assumptions, or edge cases.

Lock in your position: state clearly what you would change and why.
Do NOT concede unless presented with a logical refutation you cannot
counter.

TASK: {task}

THEIR PROPOSAL:
{proposal}"""

SYNTHESIZE = """\
Two experts debated the approach below. Synthesize their positions into
a concrete, actionable plan.

Rules:
- Where they disagree, pick the stronger argument and say WHY the other
  is wrong. Do not split the difference or hedge.
- Where both missed something, add it.
- Structure your output as:
  1. RECOMMENDATION: The approach to take (1-2 paragraphs)
  2. KEY DECISIONS: Bullet list of decisions made and rationale
  3. DISSENT: Where the losing argument had merit worth noting
  4. NEXT STEPS: Concrete actions, ordered

TASK: {task}

DEBATE:
{debate}"""


# --- Deliberation ---
#
# The protocol is fixed and deterministic:
#   1. Both agents propose independently (parallel)
#   2. Each agent critiques the other's proposal (parallel within round,
#      serial across rounds — round N+1 sees round N's output)
#   3. First agent synthesizes the full debate log (serial, streamed)
#
# Tarka makes zero decisions. The user controls agents, rounds, and
# timeout. Tarka executes the protocol exactly as specified.


def _parallel(agents: list[Agent], prompts: list[str], cwd: str) -> list[str | None]:
    """Ask multiple agents in parallel. Returns responses in input order."""
    with ThreadPoolExecutor(max_workers=len(agents)) as pool:
        futures = {
            pool.submit(agent.ask, prompt, cwd): i
            for i, (agent, prompt) in enumerate(zip(agents, prompts))
        }
        results: list[str | None] = [None] * len(agents)
        errors: list[str] = []
        for future in as_completed(futures):
            idx = futures[future]
            try:
                results[idx] = future.result()
            except Exception as e:
                errors.append(f"{agents[idx].name}: {e}")
        if errors:
            alive = [r for r in results if r is not None]
            if not alive:
                raise RuntimeError("All agents failed:\n" + "\n".join(errors))
            for err in errors:
                print(f"  {_dim(f'warning: {err}')}")
        return results


def _header(label: str) -> None:
    bar = "\u2501" * 60
    print(f"\n{bar}")
    print(f"  {_bold(label)}")
    print(f"{bar}\n")


def _agent_block(agent: Agent, label: str, text: str) -> None:
    tag = _color(agent.name, f"[{agent.name}]")
    sep = _dim("\u2500" * 56)
    print(f"\n{tag} {_dim(label)}")
    print(sep)
    print(text)
    print()


def deliberate(
    task: str,
    agents: tuple[Agent, Agent] = (CLAUDE, CODEX),
    rounds: int = 2,
    cwd: str = ".",
    quiet: bool = False,
) -> str:
    a, b = agents
    t0 = time.time()

    # --- Phase 1: independent proposals (parallel) ---
    _header(f"Phase 1 \u2014 Proposals  ({a.name} + {b.name})")
    t1 = time.time()
    pos_a, pos_b = _parallel(
        [a, b],
        [PROPOSE.format(task=task)] * 2,
        cwd,
    )
    print(_dim(f"  done ({time.time() - t1:.0f}s)"))

    if pos_a is None and pos_b is None:
        raise RuntimeError("Both agents failed to propose.")
    if pos_a is None:
        pos_a = f"[{a.name} failed \u2014 echoing {b.name}'s proposal]\n{pos_b}"
    if pos_b is None:
        pos_b = f"[{b.name} failed \u2014 echoing {a.name}'s proposal]\n{pos_a}"

    if not quiet:
        _agent_block(a, "proposal", pos_a)
        _agent_block(b, "proposal", pos_b)

    log = [
        f"[{a.name} \u2014 proposal]\n{pos_a}",
        f"[{b.name} \u2014 proposal]\n{pos_b}",
    ]

    # --- Phase 2: adversarial critique (parallel per round, serial across rounds) ---
    for r in range(1, rounds + 1):
        _header(f"Phase 2 \u2014 Round {r}/{rounds}")
        t1 = time.time()
        crit_a, crit_b = _parallel(
            [a, b],
            [
                CRITIQUE.format(task=task, proposal=pos_b),
                CRITIQUE.format(task=task, proposal=pos_a),
            ],
            cwd,
        )
        print(_dim(f"  done ({time.time() - t1:.0f}s)"))

        if crit_a is not None:
            pos_a = crit_a
        if crit_b is not None:
            pos_b = crit_b

        if not quiet:
            if crit_a:
                _agent_block(a, f"round {r} critique", crit_a)
            if crit_b:
                _agent_block(b, f"round {r} critique", crit_b)

        log.append(f"[{a.name} \u2014 round {r}]\n{pos_a}")
        log.append(f"[{b.name} \u2014 round {r}]\n{pos_b}")

    # --- Phase 3: synthesis (streamed to terminal) ---
    _header(f"Phase 3 \u2014 Synthesis  ({a.name})")
    t1 = time.time()
    result = a.ask(
        SYNTHESIZE.format(task=task, debate="\n\n---\n\n".join(log)),
        cwd,
        stream=True,
    )
    total = time.time() - t0
    synth_time = time.time() - t1
    print(f"\n{'\u2501' * 60}")
    print(_dim(f"  synthesis {synth_time:.0f}s  |  total {total:.0f}s"))
    print(f"{'\u2501' * 60}")
    return result


# --- CLI ---


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deterministic deliberation harness for AI agent CLIs.",
    )
    parser.add_argument("task", help="the task to deliberate on")
    parser.add_argument(
        "--rounds", type=int, default=2,
        help="number of debate rounds (default: 2)",
    )
    parser.add_argument("--cwd", default=".", help="working directory for agents")
    parser.add_argument(
        "--agents", nargs=2, default=["claude", "codex"],
        choices=list(AGENTS.keys()), metavar="AGENT",
        help=f"which two agents to use (choices: {', '.join(AGENTS)}; default: claude codex)",
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="only show synthesis, not the full debate",
    )
    parser.add_argument(
        "--timeout", type=int, default=180,
        help="per-agent call timeout in seconds (default: 180)",
    )
    args = parser.parse_args()

    global TIMEOUT
    TIMEOUT = args.timeout

    agent_a = AGENTS[args.agents[0]]
    agent_b = AGENTS[args.agents[1]]

    print(
        f"\n{_bold('Tarka')}  "
        f"{_dim(f'{agent_a.name} vs {agent_b.name}  \u2022  {args.rounds} rounds')}"
    )

    try:
        deliberate(
            args.task,
            agents=(agent_a, agent_b),
            rounds=args.rounds,
            cwd=args.cwd,
            quiet=args.quiet,
        )
    except RuntimeError as e:
        print(f"\n{_bold('Error:')} {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print(f"\n{_dim('interrupted')}")
        sys.exit(130)


if __name__ == "__main__":
    main()
