# CLAUDE.md

## What This Is

Tarka is a deliberation layer that sits on top of AI agent CLIs (Claude Code, Codex, Gemini CLI, etc.). It orchestrates them into adversarial debate to reduce hallucination and improve judgment — for any task, not just code. The entire tool is `tarka.py`.

## Commands

```bash
python tarka.py "task description"
python tarka.py "task" --rounds 3 --cwd /path/to/project
```

## How to Work Here

- `tarka.py` is the whole project. One file. Keep it that way until there's a real reason to split.
- Adding a new agent = one `Agent(name, command)` instance. The command list uses `{prompt}` as a placeholder.
- Prompts are inline constants. Short enough that extracting to files adds complexity without value.
- Only dependency is Python 3.10+ stdlib. No pip install, no requirements.txt.

## Design Decisions

- Agents debate *approaches* first, not implementation. Implementation comes only after convergence.
- Phase 1 proposals and within-round critiques run in parallel via `ThreadPoolExecutor`. Between rounds is sequential (round N+1 depends on N).
- Synthesis is done by the first agent (the stronger reasoner by default).
- Error handling is minimal by design — if an agent CLI isn't installed, the subprocess error is clear enough.

## Principles

- One file until it hurts.
- No abstraction without a second use case.
- Make the prompts do the work, not the code.
