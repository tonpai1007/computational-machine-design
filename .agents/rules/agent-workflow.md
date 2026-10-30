---
description: "Agent workflow efficiency and verification protocol: batching rules, single ground-truth dumps, edit-then-verify cadence, and no mid-task narration."
globs: ["**/*.md", "**/*.py", "Project/**"]
---

# Agent Workflow & Verification Protocol

This rule governs **how work is executed**, not what the output looks like. It exists
because the most common failure mode in this repo is not a wrong answer — it is a
*correct* answer delivered after 40 avoidable round trips.

---

## 1. Batching (the single biggest lever)

- **Emit every independent tool call in one response.** Reading 3 files, searching
  2 patterns, and running 1 check are *one* message, not three.
- Never serialize `read A` → `read B` → `edit A` when `edit A` does not depend on
  `read B`. Read both first, edit both second.
- If you already know the path, do not `search` for it.

## 2. Establish ground truth ONCE

- **Dump solver output to JSON once** (`scratch/gt.json`) and reference it for the
  rest of the task. Re-running the solver to re-read the same number is wasted work.
- Read the reference doc **once**, fully, before editing it.
- Prefer a single script that **computes and prints everything** over many
  narrow probe commands.

## 3. Edit in batches, then verify once

- Do **not** run a verification sweep after every single edit. Fix all known issues,
  then verify the whole surface at the end.
- For N independent edits to one file, prefer one script with explicit
  `assert lines[i] == ...` anchors over N editor round trips.
- Anchor-guarded scripts (`assert lines[203] == '```'`) fail loudly instead of
  silently writing to the wrong offset.

## 4. Fix root cause, not the artifact

- When a wrong number appears in a report, **find the line that produced it**
  (`grep` the generator) and fix that. Editing the output file alone means the bug
  returns on the next run.
- A sentinel/placeholder value (e.g. `1e6`) reaching a deliverable is a
  **physics-model defect**, not a formatting defect. Return `None`/omit at the source.

## 5. Write the regression test that would have caught it

Every bug fix ships with an assertion that fails without the fix:

| Bug class | Required guard |
|---|---|
| Unbalanced FBD / equilibrium | reactions summed must equal the applied load |
| Wrong aggregation (mean vs sum) | assert the aggregate, not just "> 0" |
| Placeholder / sentinel value | assert the sentinel string is **absent** from the output |
| Load-case inconsistency | assert equation and diagram describe the same load |
| Stale render | assert artifact mtime > model mtime |
| Golden physics value | assert against a hand-computed constant |

Weak assertions like `assert min_safety_factor > 0` or `len(scad) > 50` are what
let these bugs reach a deliverable in the first place.

## 6. Never narrate mid-task

- **No progress updates between tool calls.** Do not stop to explain, ask "what are
  we doing", or summarize what you are about to do. Run the commands, then report once.
- Do not ask for confirmation on work already explicitly requested. If scope is
  genuinely ambiguous, ask **once, up front, batched into a single question**.
- Report at the end: what changed, what was verified, what was left undone, and any
  explicit limitations.
- Honest interim admission is still required: if the approach is wrong, say so
  plainly rather than continuing to grind.

## 7. Avoid known-failing patterns

- **Thai/non-ASCII paths** (`Project/chair/chairส่งงาน.md`): `editor` old_text
  matching is fragile and PowerShell quoting mangles UTF-8. Write a
  `python -X utf8` script with `encoding='utf-8'` and use it.
- **Long heredoc pipelines** through PowerShell lose quoting; write the script to
  `scratch/` first, then run it.
- `scratch/` is disposable — never treat it as source, never commit it.
- Do **not** repurpose an existing rule file when adding a new rule; create a new one.

## 8. Definition of done

- `python -m pytest` green (100%).
- The specific bug's regression test exists and demonstrably fails without the fix.
- Final sweep run **once**: no stale values, balanced fences, sequential headings,
  referenced images exist, artifacts newer than their source model.
- Leftovers explicitly listed: uncommitted files, junk artifacts, known limitations.