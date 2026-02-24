---
description: Project progress overview — status breakdown and dependency tree
---

# /forge-status — Project Progress Overview

Show current feature progress, status breakdown, blocked features, and optionally the full dependency tree.

## Arguments

- No args → progress bar + stats + failing features + blocked list
- `--graph` or `--tree` → also show ASCII dependency tree
- `--all` → show full feature list with details
- `--ids 1,2,3` → show details for specific features

## Instructions

You are a read-only status reporter. Do NOT modify any features. Use the MCP tools below to gather data, then present it in the formatted output described.

### Step 1: Gather Data

Call these MCP tools (in parallel where possible):

1. **`feature_get_progress_bar`** → ASCII progress bar with status counts
2. **`feature_get_stats`** → JSON with passing, in_progress, total, percentage
3. **`feature_get_blocked`** → features with unmet dependencies

### Step 2: Get Additional Data Based on Arguments

- If `--graph` or `--tree` is specified: call **`feature_get_dependency_tree`**
- If `--all` is specified: call **`feature_get_ready`** (limit=50) to get the full feature list
- If `--ids X,Y,Z` is specified: call **`feature_get_by_id`** for each ID

### Step 3: Display Status Report

Format the output as follows:

```
AutoForge Status
════════════════

[========>...........................] 8/20 features passing

  Pending:      7
  In Progress:  1
  Passing:      8
  Failing:      4
```

**If `in_progress > 0`**, expand the "In Progress" line into a detailed section using the `claimed` array from `feature_get_stats`. The `claimed` array contains `{id, name, claimed_by, claimed_at}` for each in-progress feature.

When `claimed_by` is set (parallel mode — agent has claimed the feature):
```
In Progress (2):
  #5  User Auth      — claimed by orch-a1b2c3d4-w1 (12 min ago)
  #9  API Endpoints  — claimed by orch-a1b2c3d4-w2 (12 min ago)
```

When `claimed_by` is null (anonymous single-agent mode):
```
In Progress (1):
  #5  User Auth
```

**Stale claim warning:** If `claimed_at` is older than 30 minutes, flag it with a STALE warning:
```
  #11 Search Feature — claimed by orch-dead0000-w3 (47 min ago) ⚠ STALE
```

To calculate "N min ago": compare the `claimed_at` timestamp against the current time. Use UTC for comparison.

**If any features have `fail_count >= 3`**, show an "Exhausted Retries" section:

```
Exhausted Retries (needs /forge-fix):
  #8  Payment Integration  — "Stripe SDK requires STRIPE_SECRET_KEY" (3 attempts)
  #15 Search Feature       — "Elasticsearch not running" (4 attempts)
```

**If there are blocked features**, show them:

```
Blocked Features:
  #16 Admin Panel — blocked by #13 (in progress), #15 (failing)
  #18 Reports    — blocked by #16 (blocked)
```

**If there are ready features**, show the next one:

```
Next Ready: #14 — Email Notifications
```

### Step 4: Conditional Sections

**`--graph` / `--tree`**: Show the full dependency tree from `feature_get_dependency_tree`:

```
Dependency Tree:
  1. [PASS] Project Setup
  |-- 3. [PASS] Database Schema
  |   |-- 5. [PROG] User Authentication
  |   +-- 6. [PEND] API Endpoints
  +-- 4. [BLKD] Admin Panel
  2. [FAIL] Payment Integration
```

**`--all`**: Show every feature with full details (ID, name, status, category, fail_count if > 0, dependencies).

**`--ids X,Y,Z`**: Show detailed info for each requested feature including description and verification steps.

### Step 5: Suggest Next Steps

Based on the current status, recommend the most appropriate next action (always recommend `/clear` first):

- **If features are failing (fail_count >= 3):** "Run `/clear` then `/forge-fix` to address exhausted features."
- **If features are pending/ready:** "Run `/clear` then `/forge-build` or `/forge-parallel` to continue building."
- **If all features passing:** "All features passing! Run `/clear` then `/forge-test` for a final QA review."
- **If no features passing yet (only pending):** "Run `/clear` then `/forge-build` or `/forge-parallel` to start building."
- **If features are in progress with stale claims:** "Stale claims detected. Running `/clear` then `/forge-build` or `/forge-parallel` will auto-clean them."

Always include the most relevant suggestion based on the current state. If multiple apply, list them in priority order.

## Error Handling

If an MCP tool call fails or returns an error:
- Display what data you could gather
- Note which sections are unavailable
- Suggest the user check that the features database exists (run `/clear` then `/forge-init` first)

If no features exist at all, display:
```
No features found. Run /clear then /forge-init to initialize features from an app spec.
```
