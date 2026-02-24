---
description: Automated regression testing with auto-fix (project)
---

# ARGUMENTS

Parse `$ARGUMENTS` for flags:
- `--batch N` — Number of features to test per cycle (1-10, default 5)
- `--continuous` — Keep testing in a loop until all passing features are tested or interrupted

The project is always the current working directory.

Examples:
- `/forge-regression` — test 5 features, single cycle
- `/forge-regression --batch 3` — test 3 features per cycle
- `/forge-regression --continuous` — keep testing in a loop
- `/forge-regression --continuous --batch 8` — combine flags

---

# GOAL

Automated regression testing of previously-passing features with auto-fix capability. This runs as a background-compatible process that detects regressions introduced by concurrent coding agents or sequential builds, and attempts to fix them automatically.

**This is NOT `/forge-test`.** The distinction:
- `/forge-test` = Interactive QA review with the user as product owner. Visual cohesion, UX, user journeys.
- `/forge-regression` = Automated background regression testing. Programmatic verification of passing features with auto-fix.

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

## 3. Passing features exist

Call `feature_get_stats` to check project status.

- If `total == 0`: "No features found. Run `/forge-init` first."
- If `passing == 0`: "No features have been implemented yet. Run `/forge-build` first to implement some features before running regression tests."

**Stop here** in either case.

---

# STARTUP — READ CONTEXT

Before the main loop, read these once for orientation:

```bash
# 1. Read the app spec for context
cat .autoforge/prompts/app_spec.txt

# 2. Recent git history
git log --oneline -20

# 3. Project structure
ls -la
```

---

# FEATURE SELECTION SCORING

To decide which passing features to test, score each one using a weighted formula that prioritizes high-impact, high-risk features:

```
test_score = (2 * dependent_count) + (5 if not_recently_tested) + min(dependency_count, 3)
```

Where:
- **`dependent_count`** = number of features that depend on this one. If this feature regresses, all its dependents are affected. Higher impact = test first.
- **`not_recently_tested`** = 5 bonus points if this feature has NOT been tested in the current session. Ensures rotation through all features.
- **`dependency_count`** = number of dependencies this feature has (capped at 3). Features with many dependencies have higher integration risk.

## How to compute scores

1. Call `feature_get_graph` to get all features with their dependency edges.
2. Filter for features where `status == "done"` (passing features).
3. For each passing feature:
   - Count how many OTHER features list it in their `dependencies` array → `dependent_count`
   - Count its own `dependencies` array length → `dependency_count`
   - Check if its ID is in the `tested_this_session` set → `not_recently_tested`
4. Sort by `test_score` descending.
5. Pick the top `--batch` features.

---

# MAIN REGRESSION TESTING LOOP

```
SET tested_this_session = empty set
SET cycle_number = 0
SET total_tested = 0
SET total_regressions = 0
SET total_fixed = 0
SET total_unfixed = 0
SET batch = (from --batch flag, default 5, clamped 1-10)
SET continuous = (true if --continuous flag present)
```

## LOOP START

### Step 1: Get All Features and Stats

```
cycle_number += 1

Call feature_get_stats
Call feature_get_graph
```

Display:
```
=== Regression Test Cycle {cycle_number} | {passing}/{total} passing ({percentage}%) ===
```

Filter the graph nodes to get all passing features (status == "done").

If no passing features remain (all regressed): exit with warning.

### Step 2: Score and Select Batch

Compute test scores for all passing features using the formula above.

Deprioritize features whose ID is already in `tested_this_session` (they lose the 5-point `not_recently_tested` bonus).

Select the top `--batch` features by score.

Display:
```
Selected for testing:
  #{id}  {name}  (score: {score})
  #{id}  {name}  (score: {score})
  ...
```

If no untested features remain AND `--continuous` is set → exit (full rotation complete).

### Step 3: Spawn Testing Subagents

Group the selected features into batches of 2-3 per subagent (to balance parallelism with context efficiency).

For each subagent batch:

```
Use the Task tool with:
    subagent_type: "coder"
    run_in_background: true
    description: "Regression test features #{ids}"
    prompt: <TESTING_PROMPT>  (see TESTING SUBAGENT PROMPT section below)
```

**IMPORTANT:** Spawn ALL testing subagents in a SINGLE message with multiple Task tool calls in parallel.

Store each `task_id` for polling.

### Step 4: Poll for Completion

```
POLL LOOP:
    For each active testing task_id:
        Call TaskOutput with task_id={id}, block=false, timeout=5000

        If subagent completed:
            Parse the subagent's result message for per-feature PASS/FIXED/BROKEN verdicts
            Remove from active tasks list

    If all subagents completed → break poll loop
    If subagents still running → continue polling
```

### Step 5: Process Results

For each completed subagent, parse its RESULTS block:

- **PASS** features: Add to `tested_this_session`. Increment `total_tested`.
- **FIXED** features: Add to `tested_this_session`. Increment `total_tested`, `total_regressions`, `total_fixed`.
- **BROKEN** features: Add to `tested_this_session`. Increment `total_tested`, `total_regressions`, `total_unfixed`.

### Step 6: Report Cycle Results

Display:
```
Cycle {cycle_number} complete:
  Tested: {batch_count} features
  Still passing: {pass_count}
  Regressions found: {regression_count} (fixed: {fixed_count}, unfixed: {unfixed_count})
  Running total: {total_tested} tested, {total_fixed} regressions fixed
```

### Step 7: Loop or Exit

- If `--continuous` is NOT set → exit
- If ALL passing features have been tested this session → exit (full rotation)
- Otherwise → loop back to Step 1

## LOOP EXIT

Display final summary:

```
=== Regression Testing Complete ===
Cycles run: {cycle_number}
Features tested: {total_tested}
Regressions found: {total_regressions}
  Fixed: {total_fixed}
  Unfixed: {total_unfixed}
Overall: {passing}/{total} passing ({percentage}%)
```

Suggest next steps (always recommend `/clear` first):
- If unfixed regressions: "Run `/clear` then `/forge-fix` to address the {total_unfixed} unfixed regressions."
- If features remain unbuilt: "Run `/clear` then `/forge-build` or `/forge-parallel` to continue building."
- If all passing and tested: "All features passing and verified! Run `/clear` then `/forge-test` for interactive QA."

---

# TESTING SUBAGENT PROMPT

Each background testing subagent receives this prompt. It tests 2-3 features and fixes any regressions found.

**Substitute these variables** when constructing the prompt:
- `{project_dir}` — Current working directory (absolute path from `pwd`)
- `{feature_list}` — The features to test (id, name, verification steps for each)
- `{app_spec_summary}` — Brief app context (project name, tech stack, dev server URL)

---

**Testing subagent prompt (paste with variables substituted):**

```
You are a regression testing agent. Test the following features and FIX any regressions you find.

Other agents may be building new features concurrently — do NOT interfere with their work.

PROJECT DIRECTORY: {project_dir}

== APP CONTEXT ==
{app_spec_summary}

== FEATURES TO TEST ==
{For each feature:}
Feature #{id}: {name}
  Verification Steps:
  {numbered list of steps}

{End for each}

== PROTOCOL FOR EACH FEATURE ==

For each feature listed above:

1. Call feature_get_by_id with feature_id={id} to get full current details.

2. Verify the feature:
   - Check that the relevant code exists and compiles (read source files)
   - Run lint/typecheck if applicable:
     Check for package.json (npm run lint, npx tsc --noEmit) or
     pyproject.toml (ruff check ., mypy .) and run the appropriate commands.
   - Start/verify dev server if needed (check if already running first)
   - Open browser using playwright-cli to the relevant page
   - Execute each verification step from the feature
   - Check for console errors with playwright-cli console
   - Take screenshots to verify visual state

3. If feature PASSES all verification steps:
   - Note "PASS" for this feature
   - Move to the next feature

4. If feature FAILS (regression detected):
   a. Call feature_mark_failing with feature_id={id} and reason="{specific failure}"
   b. Investigate the root cause:
      - Check console errors and network requests
      - Read relevant source code
      - Check recent git commits (git log --oneline -10) for changes that might have caused it
   c. Fix the regression — edit the code to resolve the issue
   d. Verify the fix:
      - Re-run the failing verification steps
      - Ensure no new issues introduced
   e. If fix works:
      - Call feature_mark_passing with feature_id={id}
      - Git commit the fix:
        git add -A
        git commit -m "fix: regression in {feature_name}" -m "Feature #{id} re-verified after fix"
      - Note "FIXED" with what was broken and what you fixed
   f. If cannot fix after 2 attempts:
      - Leave as failing (feature_mark_failing already called)
      - Note "BROKEN" with the reason you couldn't fix it
      - Move to the next feature — do NOT spend more time on it

== PARALLEL SAFETY ==
- Only fix code directly related to the regression you found
- Do NOT refactor, clean up, or modify unrelated code
- Commit fixes immediately after verifying
- Other agents may be building new features concurrently — respect their work
- Do NOT call feature_get_ready, feature_clear_all_in_progress, or any tool that affects other features' status
- Do NOT call feature_create, feature_create_bulk, or any creation tools

== GIT COMMIT RULES ==
- ALWAYS use simple -m flag for commit messages
- NEVER use heredocs (cat <<EOF) — they fail in sandbox mode
- For multi-line messages, use multiple -m flags

== RESULT FORMAT ==
Your FINAL message MUST contain a RESULTS block in exactly this format:

RESULTS:
- Feature #{id}: PASS
- Feature #{id}: FIXED (was: {what was broken}, fix: {what you did})
- Feature #{id}: BROKEN (cannot fix: {reason})

This is how the orchestrator parses your outcome. Do not omit this block.
```

---

# FEATURE TOOL REFERENCE

Available MCP tools for regression testing:

| Tool | Purpose |
|------|---------|
| `feature_get_stats` | Progress statistics (passing/total counts) |
| `feature_get_graph` | All features with dependency edges (for scoring) |
| `feature_get_by_id` | Full feature details for testing |
| `feature_mark_failing` | Mark feature as regressed (used by testing subagents) |
| `feature_mark_passing` | Mark feature as passing again after fix (used by testing subagents) |

**Do NOT use these tools from regression testing:**
- `feature_get_ready` — Not relevant (we test passing features, not pending ones)
- `feature_clear_all_in_progress` — Could disrupt concurrent build agents
- `feature_create` / `feature_create_bulk` — No feature creation during testing

---

# ERROR HANDLING

## No dev server running
- If browser testing is needed and no dev server is detected, start one.
- Check `package.json` for `dev` or `start` scripts, or other project-specific commands.

## Testing subagent crashes
- If a subagent never returns results, its features are simply not marked as tested.
- They will be picked up in the next cycle (they retain their `not_recently_tested` bonus).

## All features regress
- If `feature_get_stats` shows 0 passing after a cycle, stop testing and report.
- Suggest running `/forge-fix` or investigating the root cause.

## Concurrent build agents modifying code
- Testing agents may encounter code that was just changed by a build agent.
- If a file read fails or shows unexpected content, re-read before editing.
- Commit regression fixes immediately to minimize conflicts.

---

# EDGE CASES

| Scenario | Behavior |
|----------|----------|
| Only 1-2 passing features | Test them all in a single subagent (no need to split) |
| All features already tested this session | Exit with "Full rotation complete" message |
| Feature passes but has no verification steps | Skip it (nothing to verify) — note in output |
| Regression fix introduces new issues | Leave the feature as failing, note the cascading problem |
| `--continuous` with no regressions found | Keep cycling until all features tested, then exit |
| `--batch` larger than passing count | Test all passing features (don't error) |

---

Begin by running the prerequisites check, then read context, score features, and enter the testing loop.
