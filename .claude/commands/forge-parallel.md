---
description: Parallel build — spawn multiple coder agents (project)
---

# ARGUMENTS

Parse `$ARGUMENTS` for flags:
- `--workers N` — Number of concurrent workers (1-4, default 3)
- `--yolo` — Pass YOLO mode to workers (skip browser testing)
- `--max-batches N` — Maximum number of batch cycles before stopping (default: 3)
- `--regression` — Reserve 1 worker slot for a regression testing agent each batch cycle

The project is always the current working directory.

Examples:
- `/forge-parallel` — 3 workers
- `/forge-parallel --workers 2` — 2 workers
- `/forge-parallel --yolo --workers 4` — 4 workers, YOLO mode
- `/forge-parallel --max-batches 5` — stop after 5 batch cycles
- `/forge-parallel --regression --workers 4` — 3 coding workers + 1 testing agent
- `/forge-parallel --yolo --workers 2 --max-batches 10` — combine flags

---

# GOAL

Spawn multiple parallel coder subagents to implement features concurrently. The orchestrator claims features, dispatches background workers, polls for completion, and repeats in batch cycles until all features are done or limits are reached.

Each worker gets a self-contained implementation prompt and works independently. The orchestrator coordinates via the MCP feature database — atomic claim operations prevent double-work.

**When to use this vs `/forge-build`:**
- `/forge-build` — Sequential, one feature at a time, full verification oracle. Best for complex features, debugging, or when you want detailed control.
- `/forge-parallel` — Parallel, multiple features at once. Best for batch-building many independent features quickly. Especially effective with `--yolo` for rapid scaffolding.

---

# PREREQUISITES CHECK

## 1. Feature database exists

Check that `.autoforge/features.db` exists.

If it does NOT exist:

> "No feature database found at `.autoforge/features.db`.
>
> Run `/forge-init` first to create features from the app spec."

**Stop here** if the database is missing.

## 2. MCP feature server is available

Try calling `feature_get_stats`. If it fails:

> "The feature MCP server is not available. Ensure `.mcp.json` exists in your project root with the feature-mcp server entry.
>
> If you used `/forge-create`, this should already be set up. Try restarting Claude Code in the project directory."

**Stop here** if MCP tools are unavailable.

## 3. Features exist and are not all complete

Call `feature_get_stats` to check project status.

- If `total == 0`: "No features found. Run `/forge-init` first."
- If `passing == total`: "All {total} features are already passing! Nothing left to build."

**Stop here** in either case.

## 4. Generate orchestrator session ID

Generate a unique session ID for this orchestrator run:
```
orch_session_id = "orch-{8 random hex chars}"
```

Example: `orch-a1b2c3d4`

This ID prefixes all worker IDs to group them by session.

---

# STARTUP — READ CONTEXT ONCE

Before the main loop, read these files ONCE. Their content will be injected into every worker prompt, so the orchestrator pays the context cost once rather than per-worker.

```bash
# 1. Read the app spec (REQUIRED — injected into every worker)
cat .autoforge/prompts/app_spec.txt

# 2. Read progress notes for orientation (optional)
cat .autoforge/progress_notes.md 2>/dev/null || echo "No progress notes yet"

# 3. Recent git history for context
git log --oneline -20

# 4. List project structure
ls -la
```

Store the app spec content in a variable — you'll paste it into each worker prompt.

---

# STARTUP CLEANUP

Clear stale claims from crashed agents of previous sessions:

```
Call feature_clear_stale with timeout_minutes=30
```

**IMPORTANT:** Do NOT call `feature_clear_all_in_progress` — that would wipe active workers from a concurrent orchestrator session. Use `feature_clear_stale` which only clears old orphaned claims.

---

# MAIN ORCHESTRATOR LOOP

```
SET batch_number = 0
SET total_completed = 0
SET total_failed = 0
SET workers = (from --workers flag, default 3, clamped 1-4)
SET max_batches = (from --max-batches flag, default 3)
SET yolo = (true if --yolo flag present)
SET regression = (true if --regression flag present)
SET coding_workers = workers - 1 if regression else workers
SET tested_this_session = empty set (used when --regression is active)
```

## LOOP START

### Step 1: Check Progress

```
batch_number += 1

Call feature_get_stats
```

Display:
```
=== Batch {batch_number} | {passing}/{total} passing ({percentage}%) | {in_progress} in progress ===
```

**Exit conditions:**
- If all features passing → exit with SUCCESS message
- If `--max-batches` set and `batch_number > max_batches` → exit gracefully

### Step 2: Get Ready Features

```
Call feature_get_ready with limit={workers * 2}
```

Filter out features with `fail_count >= 3` (exhausted — need `/forge-fix`).

**If no ready features:**
- If any features are still `in_progress` (other workers or concurrent session) → wait 30 seconds, then re-check `feature_get_stats`. Repeat up to 3 times. If still no ready features after waiting, exit.
- If no in-progress features either → exit (all done, all blocked, or all exhausted)

### Step 3: Claim Features for This Batch

For each ready feature (up to `coding_workers` count — i.e., `--workers` minus 1 if `--regression`):

```
worker_id = "{orch_session_id}-w{N}"    (e.g., "orch-a1b2c3d4-w1")

Call feature_claim_and_get with feature_id={id} and agent_id={worker_id}
```

If the claim fails (race condition — another agent got it first), skip and try the next ready feature.

Collect the list of successfully claimed features with their full details.

If zero features were successfully claimed, go back to Step 2 (retry with fresh ready list).

### Step 4: Spawn Background Worker Subagents

For each successfully claimed feature, spawn a background coder subagent:

```
Use the Task tool with:
    subagent_type: "coder"
    run_in_background: true
    description: "Build feature #{id}: {short_name}"
    prompt: <WORKER_PROMPT>  (see WORKER PROMPT TEMPLATE section below)
```

**IMPORTANT:** Spawn ALL workers (and the testing agent if `--regression`) in a SINGLE message with multiple Task tool calls in parallel. This maximizes concurrency.

Store each `task_id` for polling.

### Step 4b: Spawn Testing Agent (if `--regression`)

If `--regression` is active AND there are passing features to test:

1. Call `feature_get_graph` to get all features with dependency edges.
2. Filter for passing features (status == "done").
3. Score each passing feature using the regression testing formula:
   ```
   test_score = (2 * dependent_count) + (5 if not in tested_this_session) + min(dependency_count, 3)
   ```
4. Select top 3 features by score.
5. Spawn a testing subagent alongside the coding workers:

```
Use the Task tool with:
    subagent_type: "coder"
    run_in_background: true
    description: "Regression test features #{ids}"
    prompt: <TESTING_PROMPT>
```

The testing prompt follows the same format as `/forge-regression`'s testing subagent prompt (see the forge-regression command for the full template). Include:
- Project directory and app context
- The selected features with their verification steps
- Instructions to test each feature, fix regressions, and report PASS/FIXED/BROKEN results
- Parallel safety rules (only fix regression-related code, commit immediately)

Store this `task_id` alongside the coding worker task IDs for polling.

When processing testing agent results in Step 5:
- **PASS** results: Add feature IDs to `tested_this_session`
- **FIXED** results: Log the regression fix, add to `tested_this_session`
- **BROKEN** results: Log the unfixed regression, add to `tested_this_session`

Display testing results separately from coding results in Step 6:
```
"Testing agent: tested {N} features ({passed} pass, {fixed} fixed, {broken} broken)"
```

### Step 5: Poll for Worker Completion

```
SET active_workers = [list of {task_id, feature_id, feature_name, worker_id}]

POLL LOOP:
    For each active worker:
        Call TaskOutput with task_id={id}, block=false, timeout=5000

        If worker completed:
            Parse the worker's final message for "RESULT: PASS" or "RESULT: FAIL"

            If PASS:
                total_completed += 1
                Display: "Worker {worker_id}: PASS — {feature_name}"
                (Worker already called feature_mark_passing and committed)

            If FAIL:
                total_failed += 1
                Display: "Worker {worker_id}: FAIL — {feature_name}: {reason}"
                (Worker already called feature_mark_failing)

            Remove from active_workers list

    If all workers completed → break poll loop
    If workers still running → continue polling
```

**Polling strategy:** Check each worker with `block=false`. If none completed, wait a bit and try again. The TaskOutput tool with `block=false` returns immediately with current status.

### Step 6: Report Batch Results

```
Display:
"Batch {batch_number} complete: {batch_completed} passed, {batch_failed} failed"
"Running total: {total_completed} completed, {total_failed} failed"
```

### Step 7: Loop Back

Go back to **Step 1** for the next batch cycle.

## LOOP EXIT

Display final summary:

```
=== Orchestrator Complete ===
Batches run: {batch_number}
Features completed: {total_completed}
Features failed: {total_failed}
Overall: {passing}/{total} passing ({percentage}%)
```

Suggest next steps (always recommend `/clear` first):
- If features remain incomplete: "Run `/clear` then `/forge-parallel` again to continue, or `/clear` then `/forge-build` for sequential mode."
- If exhausted features (fail_count >= 3): "Run `/clear` then `/forge-fix` to address failed features."
- If all passing: "All done! Run `/clear` then `/forge-test` for final QA."

---

# WORKER PROMPT TEMPLATE

Each background coder subagent receives this self-contained prompt. It includes everything the worker needs to implement a single feature independently.

**Substitute these variables** when constructing the prompt:
- `{project_dir}` — Current working directory (absolute path from `pwd`)
- `{worker_id}` — This worker's agent ID (e.g., "orch-a1b2c3d4-w1")
- `{mode}` — "YOLO" if `--yolo` flag, otherwise "STANDARD"
- `{app_spec_content}` — Full content of `.autoforge/prompts/app_spec.txt` (read once by orchestrator)
- `{feature_id}` — The feature ID
- `{feature_name}` — The feature name
- `{feature_category}` — The feature category
- `{feature_priority}` — The feature priority
- `{feature_description}` — The feature description
- `{feature_steps}` — The verification steps as a numbered list
- `{dependency_names}` — Names and IDs of dependency features (already passing)

---

**Worker prompt (paste this with variables substituted):**

```
You are a coding agent implementing a single feature in a parallel build.
Other agents are working on other features concurrently.

PROJECT DIRECTORY: {project_dir}
AGENT ID: {worker_id}
MODE: {mode}

== APP SPECIFICATION ==
{app_spec_content}

== YOUR FEATURE ==
Feature #{feature_id}: {feature_name}
Category: {feature_category}
Priority: {feature_priority}
Description: {feature_description}

Verification Steps:
{feature_steps}

Dependencies (already passing):
{dependency_names}

== PARALLEL SAFETY RULES ==
IMPORTANT: Other agents are working on other features concurrently.
- Work ONLY on feature #{feature_id}. Do NOT modify code unrelated to this feature.
- If you encounter unexpected file changes or merge conflicts, re-read the file before editing.
- Commit immediately after verification passes.
- Do NOT call feature_get_ready, feature_clear_all_in_progress, or any
  tool that affects other features' status.
- Do NOT call feature_create, feature_create_bulk, or any creation tools.

== GIT COMMIT RULES ==
- ALWAYS use simple -m flag for commit messages
- NEVER use heredocs (cat <<EOF) — they fail in sandbox mode
- For multi-line messages, use multiple -m flags

== IMPLEMENTATION PROTOCOL ==

1. Orient: Read project structure and recent git log (last 10 commits).
   ```bash
   ls -la {project_dir}
   git log --oneline -10
   ```

2. Implement feature #{feature_id} following the description and verification steps.
   Build whatever is needed — missing pages, endpoints, components are YOUR job.

3. Run lint/typecheck:
   Check for package.json (npm run lint, npx tsc --noEmit) or
   pyproject.toml (ruff check ., mypy .) and run the appropriate commands.
   Fix any errors before proceeding.

4. Start/verify dev server if needed (check if it's already running first).

{IF mode == "STANDARD":}
5. Verify with browser testing:
   - Open browser to dev server URL using playwright-cli
   - Execute each verification step from the feature
   - Check for console errors with playwright-cli console
   - Run mock data detection grep:
     grep -rn "globalThis\|devStore\|dev-store\|mockDb\|mockData\|fakeData\|sampleData\|dummyData\|testData\|STUB\|MOCK\|isDevelopment\|isDev" src/ --include="*.ts" --include="*.tsx" --include="*.js" --include="*.jsx" --include="*.vue" --include="*.svelte" | grep -v "node_modules" | grep -v "__tests__" | grep -v ".test." | grep -v ".spec." || echo "No mock patterns found"
   - For CRUD/data features: run server restart persistence test
     (create test data, stop server, restart, verify data persists)
   - Close browser with playwright-cli close when done

{IF mode == "YOLO":}
5. YOLO mode — skip browser testing. Lint/typecheck passing is sufficient.

6. If verification PASSES:
   - Call feature_mark_passing with feature_id={feature_id}
   - Git commit:
     git add -A
     git commit -m "feat: implement {feature_name}" -m "Feature #{feature_id} verified and passing"
   - Output your final message starting with: RESULT: PASS

7. If verification FAILS after up to 3 fix attempts:
   - Call feature_mark_failing with feature_id={feature_id} and reason="{specific failure description}"
   - Output your final message starting with: RESULT: FAIL: {what failed}

== IMPORTANT ==
Your FINAL message MUST start with "RESULT: PASS" or "RESULT: FAIL: {reason}".
This is how the orchestrator knows your outcome. Do not forget this line.
```

---

# FEATURE TOOL REFERENCE

Available MCP tools for the orchestrator:

| Tool | Purpose |
|------|---------|
| `feature_get_stats` | Progress statistics (passing/total counts, claimed features) |
| `feature_get_ready` | Features ready to implement (deps satisfied, not claimed) |
| `feature_get_by_id` | Get specific feature details |
| `feature_claim_and_get` | Atomically claim and retrieve feature details |
| `feature_mark_passing` | Mark feature complete (used by workers) |
| `feature_mark_failing` | Mark as failing with reason (used by workers) |
| `feature_clear_stale` | Clear orphaned claims older than timeout |
| `feature_clear_all_in_progress` | Reset orphaned features (use with agent_id filter only) |

**Orchestrator-only tools** (workers should NOT use these):
- `feature_get_ready` — Only the orchestrator selects features
- `feature_clear_stale` — Only the orchestrator manages stale claims
- `feature_clear_all_in_progress` — Only in cleanup scenarios

---

# ERROR HANDLING

## Worker crashes or times out
- The orchestrator polls with `TaskOutput block=false`. If a worker never completes (stuck), its claimed feature will be cleaned up by `feature_clear_stale` on the next orchestrator run (or by another orchestrator).
- The orchestrator does NOT wait forever — if polling goes on for more than ~30 iterations with no progress, log the stuck workers and move on.

## All claims fail (race condition)
- If all `feature_claim_and_get` calls fail in Step 3, refresh the ready list and retry once. If still failing, another orchestrator is likely running — exit gracefully.

## No ready features but features remain
- Display the blocker summary (blocked features and their unmet deps)
- Suggest running `/forge-fix` for exhausted features or `/forge-build` for complex blocked features

---

# SESSION CONTINUITY

After the orchestrator exits, update `.autoforge/progress_notes.md`:

```markdown
## Orchestrator Session {date} ({orch_session_id})

### Summary
- Batches run: {batch_number}
- Features completed: {total_completed}
- Features failed: {total_failed}
- Workers per batch: {workers}
- Mode: {YOLO or STANDARD}

### Completed Features
- Feature #{id}: {name} — PASSING
- ...

### Failed Features
- Feature #{id}: {name} — {reason}
- ...

### Status
- {passing}/{total} features passing ({percentage}%)
- Stopped because: {reason}

### Notes
- {any important observations}
```

---

Begin by running the prerequisites check, then read the app spec and enter the main loop.
