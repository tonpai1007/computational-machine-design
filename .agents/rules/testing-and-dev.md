---
description: "Testing and development protocol: project-local .venv interpreter, mandatory 100% green suite before concluding changes, and regression-test requirements."
globs: ["tests/**", "**/*.py", "pyproject.toml"]
---

# Testing & Development Protocol

This rule governs how changes are verified in the Machine Design Intelligence Engine (MDIE).
A change is not finished until the suite is green.

---

## 1. Test Runner Invocation

Always invoke the suite with the project-local interpreter:

```powershell
.venv\Scripts\python.exe -m pytest
```

| Requirement | Rationale |
| :--- | :--- |
| **Use `.venv\Scripts\python.exe`** | The ambient `python` on Windows may fail to resolve the root packages, and a bare `pytest` may land in the wrong environment entirely. |
| **Use `-m pytest`** | Ensures the module resolves from the current working directory rather than a stale installed copy. |
| **Never declare success from a subset** | A targeted run (`pytest tests/test_x.py`) is fine while iterating, but the **full** suite must pass before concluding. |

Install or refresh the environment with the dev extra:

```powershell
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Pinned, verified dependency versions live in `requirements-lock.txt`.

---

## 2. Green Suite Is a Release Gate

- **Keep all unit and integration tests passing (100% green)** before concluding any code change.
- CI enforces this on every push via `.github/workflows/ci.yml`. A red suite locally is a red suite in CI.
- When a change is expected to alter numbers, **update the expectation deliberately and show the new derivation** — never relax an assertion just to make it pass.

---

## 3. Regression Tests Are Mandatory

Every bug fix ships with a test that **fails without the fix**. A fix with no test will silently regress on the next regeneration.

| Change type | Required assertion |
| :--- | :--- |
| Physics / solver | Golden value hand-computed from the governing equation (see `tests/test_solver_golden.py`) |
| Report / generator output | Assert the aggregate or exact value — not merely `> 0` |
| Placeholder or sentinel | Assert the sentinel string is **absent** from the output |
| Equilibrium / FBD | Summed reactions must equal the applied load |
| CAD / drawing regeneration | Artifact mtime must be newer than its source model |
| Load-case change | The printed equation and the printed diagram must describe the same load |

Weak assertions (`assert x > 0`, `assert len(out) > 50`) are what allow defects to reach a deliverable unnoticed.

---

## 4. Working Tree Discipline

- `scratch/` is disposable — never treat it as source and never commit it.
- Do not repurpose an existing rule file when adding a new rule; create a new one so history stays intact.
- Keep unrelated work-in-progress out of a commit. Stage the files that belong to the change at hand, and report what was deliberately left uncommitted.

---

## 5. Workflow Efficiency

The execution protocol — batching, single ground-truth dumps, edit-then-verify cadence, and no mid-task narration — is specified separately in `.agents/rules/agent-workflow.md`.
