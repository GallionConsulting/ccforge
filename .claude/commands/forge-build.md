---
description: Build loop — implement features one by one (project)
---

# ARGUMENTS

Parse `$ARGUMENTS` for flags:
- `--yolo` — Skip browser testing, only verify lint/typecheck
- `--batch N` — Number of features to implement this session (default: 1)
- `--ids 1,2,3` — Only implement these specific feature IDs
- `--agent-id <id>` — Agent identifier for parallel mode (auto-generated UUID if omitted)

The project is always the current working directory.

Examples:
- `/forge-build` — implement 1 feature
- `/forge-build --batch 3` — implement 3 features then stop
- `/forge-build --yolo` — YOLO mode, 1 feature
- `/forge-build --ids 5,8,12` — implement only features 5, 8, and 12
- `/forge-build --yolo --batch 5` — combine flags

---

# GOAL

Implement features from the feature database. Each session handles a fixed number of features (default: 1, adjustable with `--batch N`) then stops, so the next `/forge-build` starts with a fresh context window. This prevents context degradation during long builds — run `/forge-build` repeatedly to work through the feature list.

---

# PREREQUISITES CHECK

Before entering the build loop, verify all prerequisites:

## 1. Feature database exists

Check that `.autoforge/features.db` exists.

If it does NOT exist:

> "No feature database found at `.autoforge/features.db`.
>
> Run `/forge-init` first to create features from the app spec."

**Stop here** if the database is missing.

## 2. MCP feature server is available

The feature MCP tools (`feature_get_stats`, `feature_get_ready`, etc.) must be available. These are configured via `.mcp.json` in the project root.

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

## 4. Dev server (check but don't block)

Check if a dev server is expected (look for `init.sh`, `package.json`, or similar). If the dev server isn't running, you'll start it during the build loop. This is not a hard prerequisite — some features don't need it.

---

# STARTUP CLEANUP

**Before entering the build loop**, reset orphaned in-progress features:

```
If --agent-id was provided:
    Call feature_clear_all_in_progress with agent_id={agent_id}
    (Only clears THIS agent's orphaned claims from previous sessions)
Else:
    Call feature_clear_all_in_progress
    (Clears ALL orphaned claims — safe for single-agent mode)
```

In single-agent mode, any in-progress feature at startup is orphaned from a previous crashed session. In parallel mode, only clearing this agent's claims avoids disrupting other active workers.

---

# BUILD LOOP

## Step 1: Orient Yourself

On the **first iteration only**, get your bearings:

```bash
# See your working directory
pwd

# Understand project structure
ls -la

# Read the app spec for overall context
cat .autoforge/prompts/app_spec.txt

# Read progress notes from previous sessions (if they exist)
cat .autoforge/progress_notes.md 2>/dev/null || echo "No progress notes yet"

# Check recent git history
git log --oneline -20
```

Call `feature_get_stats` to see current progress (passing/total).

## Step 2: Get Next Feature

Call `feature_get_ready` to get the next implementable feature (dependencies satisfied, not in progress).

**Before attempting any feature, check:**
- If `fail_count >= 3` on the feature → **skip it**. This feature has exhausted retries across sessions and needs human intervention via `/forge-fix`. Log it and move to the next ready feature.
- If `features_completed >= batch_limit` → **stop gracefully** (see Stop Conditions). Default batch limit is 1.

If no ready features are available:
- Check if all remaining features are blocked (dependencies not met) → report blockers
- Check if all remaining features have `fail_count >= 3` → report exhausted features
- Otherwise, all features are done — congratulations!

## Step 3: Claim and Implement

1. **Claim the feature:**
   ```
   Call feature_mark_in_progress with feature_id={id} and agent_id={agent_id}
   ```
   (If no `--agent-id` was provided, omit the `agent_id` parameter.)

2. **Read feature details** — understand name, description, and verification steps

3. **Implement the feature:**
   - Write the code (frontend and/or backend as needed)
   - Build whatever is required — missing pages, endpoints, components are YOUR job to create
   - Follow the app spec for requirements

4. **Run lint/typecheck directly** (inline — do NOT delegate to a subagent):
   ```bash
   # Run project-specific lint (detect from package.json, pyproject.toml, etc.)
   npm run lint 2>&1 || true
   npx tsc --noEmit 2>&1 || true
   ```
   Fix any errors before proceeding. The output is small and you need to see errors to fix them.

5. **Start/verify dev server** (inline — persistent side effect):
   - If the dev server isn't running, start it
   - Verify it starts without errors
   - Note the port for browser testing

6. **Feature verification — full protocol** (skip this step entirely if `--yolo`):

   Spawn a **feature verification oracle** subagent using the Task tool:

   ```
   Use the Task tool with:
     subagent_type: "general-purpose"
     description: "Verify feature #{id}: {feature_name}"
     prompt: |
       You are a feature verification oracle. Your job is to verify that feature #{id}
       "{feature_name}" works correctly through thorough testing against the running
       dev server.

       PROJECT DIRECTORY: {cwd}
       DEV SERVER: http://localhost:{port}

       FEATURE VERIFICATION STEPS:
       {paste the feature's verification steps here}

       YOUR PROTOCOL (execute ALL phases in order):

       ## Phase 1: Browser Verification
       1. Use playwright-cli to open the browser at the dev server URL
       2. Execute each verification step above using playwright-cli commands
          (open, snapshot, click, fill, screenshot, console, close)
       3. Take screenshots at key checkpoints
       4. Check for console errors with `playwright-cli console`

       ## Phase 2: Verification Checklist
       Complete ALL applicable checks:
       - Security: Feature respects role permissions; unauthenticated access blocked;
         API checks auth (401/403); no cross-user data leaks via URL manipulation
       - Real Data: Create unique test data (e.g., "ORACLE_TEST_{id}") via UI, verify
         it appears, refresh to confirm persistence, delete and verify removal. No
         unexplained pre-existing data (indicates mocks). Dashboard counts reflect
         real numbers
       - Navigation: All buttons/links route correctly, no 404s, back button works,
         edit/view/delete links have correct IDs
       - Integration: Zero JS console errors, no 500s in network tab, API data matches
         UI, loading/error states work

       ## Phase 3: Mock Data Detection (MANDATORY)
       Run this grep in the project directory:
       ```bash
       grep -rn "globalThis\|devStore\|dev-store\|mockDb\|mockData\|fakeData\|sampleData\|dummyData\|testData\|STUB\|MOCK\|isDevelopment\|isDev" src/ --include="*.ts" --include="*.tsx" --include="*.js" --include="*.jsx" --include="*.vue" --include="*.svelte" | grep -v "node_modules" | grep -v "__tests__" | grep -v ".test." | grep -v ".spec."
       ```
       Any hits in production code = FAIL. Report the specific files and patterns found.
       Also: create unique test data (e.g., "MOCK_CHECK_{id}"), verify it appears in
       the UI, then delete it and confirm removal. Unexplained pre-existing data that
       you did not create indicates mock implementations = FAIL.

       ## Phase 4: Server Restart Persistence Test (MANDATORY for CRUD/data features)
       If this feature creates, reads, updates, or deletes data:
       1. Create unique test data (e.g., "RESTART_TEST_{id}") via the UI
       2. Verify it appears in the UI
       3. Stop the dev server completely (find and kill the process)
       4. Restart the dev server
       5. Verify the test data still exists after restart
       6. Clean up test data
       If data disappears after restart = FAIL (in-memory storage detected).
       Skip this phase ONLY for purely UI-only features (styling, layout, static pages).

       IMPORTANT:
       - You are READ-ONLY. Do NOT edit any files.
       - Do NOT use eval or run-code commands in playwright-cli.
       - Close the browser with `playwright-cli close` when done.
       - Phases 3 and 4 are MANDATORY — do NOT skip them (unless Phase 4 does not
         apply because the feature has no data persistence aspect).
       - Do NOT return PASS unless ALL applicable phases pass.
       - Return a structured verdict:
         - "PASS" — all phases passed (include brief notes on each phase result)
         - "FAIL: {phase}: {specific error}" — which phase failed and why
         - Include brief notes on each phase result even on PASS
   ```

   The oracle is disposable. It handles screenshots, DOM snapshots, console logs,
   mock detection, persistence tests, and retry loops — keeping that heavy context
   out of your main window.

7. **Inline mock data grep** (skip if `--yolo`; runs AFTER the oracle returns PASS):

   After the oracle returns PASS, the **build agent itself** (not the oracle) runs
   a mock data grep as an independent double-check. This matches AutoForge's pattern
   where the agent verifies independently of the oracle.

   ```bash
   grep -rn "globalThis\|devStore\|dev-store\|mockDb\|mockData\|fakeData\|sampleData\|dummyData\|testData\|STUB\|MOCK\|isDevelopment\|isDev" src/ --include="*.ts" --include="*.tsx" --include="*.js" --include="*.jsx" --include="*.vue" --include="*.svelte" | grep -v "node_modules" | grep -v "__tests__" | grep -v ".test." | grep -v ".spec." || echo "No mock patterns found"
   ```

   - If **no hits**: proceed to Step 4 (mark passing).
   - If **hits found**: investigate each match. If any are genuine mock/placeholder
     data in production code, fix them before marking passing. False positives
     (e.g., a variable named "testDataValidator" in a validation library) can be
     ignored with a note in the commit message explaining why.
   - This is a safety net — the oracle should have caught mock patterns in Phase 3,
     but the build agent verifies independently.

## Step 4: Handle Verification Result

**If the oracle returns PASS AND the inline mock data grep is clean (or lint/typecheck pass in YOLO mode):**

Both gates must pass before marking a feature as passing:
- Gate 1: Oracle returns PASS (all 4 phases)
- Gate 2: Inline mock data grep finds no production mock patterns (Step 3.7)

1. Mark the feature as passing:
   ```
   Call feature_mark_passing with feature_id={id}
   ```

2. Git commit:
   ```bash
   git add -A
   git commit -m "feat: implement {feature_name}" -m "Feature #{id} verified and passing"
   ```

**If the oracle returns FAIL or the inline mock grep finds issues:**

1. Read the oracle's error details (note which phase failed)
2. Attempt to fix the issue
3. Re-verify (spawn a new oracle or verify inline for simple fixes)
4. **Maximum 3 attempts per feature within this session**
5. If still failing after 3 attempts:
   ```
   Call feature_mark_failing with feature_id={id} and reason="Structured explanation of what failed and why"
   ```
   The `reason` should be specific while context is fresh — it will be read by `/forge-fix` later.
6. Move to the next feature

## Step 5: Periodic Regression Sweep

Every **5 completed features**, spawn a **regression sweep oracle** subagent:

```
Use the Task tool with:
  subagent_type: "general-purpose"
  description: "Regression sweep"
  prompt: |
    You are a regression sweep oracle. Test the dependency neighborhood of
    recently completed features to ensure nothing broke.

    RECENTLY COMPLETED FEATURES: {list feature IDs and names}

    For each feature, run its verification steps using playwright-cli.

    Return a concise summary:
    - "ALL PASS (N/N)" if everything works
    - "M REGRESSED: {feature_id}: {error}" for any regressions

    Keep response concise. Do NOT edit any files.
```

If regressions are found, fix them before continuing.

**Skip regression sweeps in YOLO mode.**

## Step 6: Next Feature

After completing (or failing) a feature:

1. Check stop conditions (see below)
2. If no stop condition met, go back to **Step 2**

---

# YOLO MODE (`--yolo`)

When `--yolo` is active:

- **Skip** all Playwright CLI / browser testing
- **Skip** the feature verification oracle subagent (Step 3.6)
- **Skip** the inline mock data grep (Step 3.7)
- **Skip** the regression sweep oracle
- **Only verify** lint and typecheck pass:
  ```bash
  npm run lint 2>&1
  npx tsc --noEmit 2>&1
  ```
- **Mark passing** after lint/typecheck succeeds and server starts cleanly
- Everything else (MCP tools, git commits, progress notes) stays the same

YOLO mode is for rapid prototyping when you want to scaffold features quickly without verification overhead. Switch to standard mode for production-quality development.

---

# BATCH MODE (`--batch N`)

Each session implements a fixed number of features then stops, ensuring context stays fresh.

- **Default: `--batch 1`** — implement 1 feature per session
- Use `--batch N` to increase (e.g., `--batch 3` for 3 features)
- Track a `features_completed` counter starting at 0
- After each feature is marked passing: `features_completed += 1`
- When `features_completed >= N`: stop gracefully

**Why default 1?** Each `/forge-build` invocation gets a fresh context window. By limiting features per session, context never degrades. Run `/forge-build` repeatedly (or use `/clear` between runs) to work through the full feature list. Increase `--batch` for lightweight features where context accumulation is less of a concern.

---

# SPECIFIC IDS MODE (`--ids 1,2,3`)

When `--ids` is specified:

- Only attempt the listed feature IDs
- Process them in the order given
- Use `feature_get_by_id` instead of `feature_get_ready` to get each feature
- Still check `fail_count >= 3` before each
- Skip if the feature is already passing

---

# STOP CONDITIONS

Stop the build loop when **any** of these occur:

## 1. Batch limit reached (default: 1 feature)

```
"Session complete — implemented {N} feature(s) this session ({passing}/{total} passing).

Run /clear then /forge-build to continue with the next feature, or /clear then /forge-parallel for parallel builds."
```

Only suggest `/forge-test` in the exit message if visual UI features have been completed (pages, screens, navigation — not just backend infrastructure). Check what you completed before deciding. If suggesting `/forge-test`, prefix with `/clear`.

## 2. All features done

```
"All {total} features are passing! Project build is complete.

Run /clear then /forge-test to do a final QA review, or start using your app!"
```

## 3. All remaining features blocked or exhausted

```
"Cannot continue — remaining features are blocked or have exhausted retries:

Blocked ({blocked_count}):
- Feature #{id}: {name} — waiting on #{dep_id}, #{dep_id}

Exhausted retries ({exhausted_count}):
- Feature #{id}: {name} — failed {fail_count} times: {fail_reason}

Run /clear then /forge-fix to address failed features, or resolve blocking dependencies."
```

## 4. User interrupts (Ctrl+C)

Immediate stop. No cleanup needed — orphaned in-progress features are cleaned up on next `/forge-build` start.

---

# SESSION CONTINUITY

## Progress Notes

After each feature (pass or fail), update `.autoforge/progress_notes.md`:

```markdown
## Session {date}

### Completed
- Feature #{id}: {name} — PASSING
- Feature #{id}: {name} — PASSING

### Failed
- Feature #{id}: {name} — {brief reason}

### Status
- {passing}/{total} features passing
- Batch: {completed}/{batch_limit} features this session
- Stopped because: {reason}

### Notes
- {any important observations for next session}
```

## Git Log

Read `git log --oneline -20` at the start of each session to understand what previous sessions accomplished.

## App Spec

Read `.autoforge/prompts/app_spec.txt` at the start of each session for overall project context.

---

# TEST-DRIVEN DEVELOPMENT MINDSET

Features are **test cases** that drive development. If functionality doesn't exist, **BUILD IT** — you are responsible for implementing ALL required functionality. Missing pages, endpoints, database tables, or components are NOT blockers; they are your job to create.

**When to skip a feature (EXTREMELY RARE):**

Only skip for truly external blockers: missing third-party credentials (Stripe keys, OAuth secrets), unavailable external services, or unfulfillable environment requirements. **NEVER** skip because a page, endpoint, component, or data doesn't exist yet — build it.

---

# GIT COMMIT RULES

- ALWAYS use simple `-m` flag for commit messages
- NEVER use heredocs (`cat <<EOF`) — they fail in sandbox mode
- For multi-line messages, use multiple `-m` flags:

```bash
git add -A
git commit -m "feat: implement {feature name}" -m "Feature #{id} verified and passing"
```

---

# FEATURE TOOL REFERENCE

Available MCP tools for the build loop:

| Tool | Purpose |
|------|---------|
| `feature_get_stats` | Progress statistics (passing/total counts) |
| `feature_get_ready` | Next implementable features (deps satisfied) |
| `feature_get_by_id` | Get specific feature details |
| `feature_mark_in_progress` | Claim a feature |
| `feature_mark_passing` | Mark feature complete |
| `feature_mark_failing` | Mark as failing with `reason` (increments `fail_count`) |
| `feature_skip` | Move feature to end of queue |
| `feature_clear_in_progress` | Clear one feature's in-progress status |
| `feature_clear_all_in_progress` | Reset orphaned in-progress features (supports `agent_id` filter) |
| `feature_clear_stale` | Clear claims older than a timeout (orphan detection in parallel mode) |

**Do NOT** call `feature_create`, `feature_create_bulk`, `feature_add_dependency`, or other creation/modification tools. Features are read-only during the build loop.

---

# BROWSER AUTOMATION (Standard Mode)

Use `playwright-cli` for browser testing (via the oracle subagent):

```bash
playwright-cli open http://localhost:PORT   # Open browser
playwright-cli goto http://localhost:PORT/page  # Navigate
playwright-cli snapshot                      # Get element refs
playwright-cli click e5                      # Click element
playwright-cli type "search query"           # Type text
playwright-cli fill e3 "value"               # Fill form field
playwright-cli screenshot                    # Take screenshot
playwright-cli console                       # Check JS errors
playwright-cli close                         # Close browser
```

Screenshots and snapshots save to `.playwright-cli/`. The oracle reads them and returns a concise verdict.

---

# EMAIL INTEGRATION (Development Mode)

When building features that require email (password resets, verification, notifications):

- Configure the app to **log emails to the terminal** instead of sending them
- Check terminal/server logs for generated links during testing
- This allows full testing of email-dependent flows without external services

---

Begin by running the prerequisites check, then enter the build loop.
