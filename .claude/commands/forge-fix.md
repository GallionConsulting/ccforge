---
description: Interactive failure resolution — diagnose and fix failing features
---

# /forge-fix — Interactive Failure Resolution

Help the user understand why features failed and fix the root cause before retrying.

## Arguments

- No args → find all features with `fail_count >= 3` (exhausted retries)
- `--ids 1,2,3` → work on specific features by ID regardless of fail_count
- `--all-failing` → show all failing features, not just exhausted ones

## Instructions

You are an interactive assistant that helps users diagnose and resolve feature failures. You will present each failed feature, explain the failure, and let the user choose a resolution.

### Step 1: Identify Failed Features

**No arguments:**
1. Call **`feature_get_ready`** with limit=50 to get a snapshot of all features
2. Call **`feature_get_stats`** to understand overall progress
3. To find failed features, call **`feature_get_by_id`** for features that might be failing, OR iterate through features via **`feature_get_blocked`** and check their `fail_count`

More practically: call **`feature_get_progress_bar`** first for a quick overview, then call **`feature_get_blocked`** and **`feature_get_ready`** to find features with `fail_count >= 3`.

Since there's no single "get all failing" MCP tool, you'll need to check features. The best approach:
1. Call **`feature_get_stats`** — check if there are features that aren't passing or in-progress (those are candidates)
2. Call **`feature_get_ready`** with limit=50 — examine the `fail_count` field on each returned feature
3. Call **`feature_get_blocked`** — examine `fail_count` on blocked features too
4. Filter to features where `fail_count >= 3`

If no features have `fail_count >= 3`, check if there are any with `fail_count > 0` and offer to show those instead.

**`--ids X,Y,Z`:**
Call **`feature_get_by_id`** for each specified ID. Work on them regardless of fail_count.

**`--all-failing`:**
Same discovery as no-args, but include all features with `fail_count > 0` (not just >= 3).

### Step 2: Present Each Failed Feature

For each failed feature, display:

```
━━━ Feature #8: Payment Integration (failed 3x) ━━━

Description:
  Integrate Stripe payment processing with checkout flow

Failure reason:
  "Stripe SDK requires STRIPE_SECRET_KEY env var which is not configured.
   The checkout form renders but payment submission fails."

Depended on by: #16 (Admin Panel), #19 (Payment History)
```

To find "depended on by" (downstream dependents): call **`feature_get_blocked`** and check which features list this feature's ID in their `blocked_by` or `dependencies` field.

### Step 3: Offer Resolution Options

For each feature, ask the user:

```
What would you like to do?
  1. Revise the description — rewrite the spec so the agent can try differently
  2. Delete this feature — remove it entirely (warns about dependents)
  3. Retry — clear fail state without changes (you fixed something externally)
  4. Skip — leave as-is, move to the next failed feature
```

### Step 4: Execute the Chosen Resolution

**Option 1 — Revise the spec:**
1. Have a conversational back-and-forth with the user to understand what should change
2. Help them rewrite the feature name, description, and/or verification steps
3. Call **`feature_update`** with the revised fields
   - `feature_id`: the feature's ID
   - `name`: new name (or empty to keep current)
   - `description`: new description (or empty to keep current)
   - `steps`: new steps as JSON array string (or empty to keep current)
4. Confirm: "Feature #8 updated. Fail count reset to 0 — it will be retried on the next /forge-build run."

**Option 2 — Delete the feature:**
1. Check for downstream dependents by examining which features have this ID in their `dependencies`
2. If dependents exist, warn: "Deleting #8 will affect: #16 (Admin Panel), #19 (Payment History). Their dependencies on #8 will need to be removed."
3. Ask for confirmation
4. If confirmed:
   - For each dependent feature, call **`feature_remove_dependency`** to remove the reference
   - There is no "delete feature" MCP tool, so instead call **`feature_update`** to rename it to "[DELETED] Feature Name" and set description to "This feature has been deleted by the user." Then call **`feature_mark_passing`** to remove it from the active queue.
5. Confirm: "Feature #8 removed. Dependencies cleaned up for #16, #19."

**Option 3 — Retry (clear fail state):**
1. Call **`feature_update`** with just the current name (triggers fail_count reset)
   - Pass the feature's existing name as the `name` parameter — this counts as a change and resets fail_count/fail_reason
2. Confirm: "Feature #8 fail state cleared. It will be retried on the next /forge-build run."

**Option 4 — Skip:**
1. Do nothing. Move to the next feature.
2. Say: "Skipping #8 — no changes made."

### Step 5: Summary

After all features have been addressed, show a summary:

```
Fix Summary:
  Revised: #8 (Payment Integration)
  Deleted: #15 (Search Feature)
  Retried: #12 (File Upload)
  Skipped: #20 (Analytics)

Run /clear then /forge-build or /forge-parallel to continue building.
Run /clear then /forge-status to check progress.
```

## Error Handling

**No failed features found:**
```
All features are healthy. Nothing to fix.

Run /clear then /forge-status for a full progress overview, or /clear then /forge-build to continue building.
```

**Feature has no `fail_reason`:**
Show "No failure reason recorded" and suggest:
- Check recent git log for clues
- Run `/forge-status --ids X` for full feature details
- Consider revising the spec if the feature seems unclear

**MCP server not available:**
```
Could not connect to the feature MCP server.
Make sure features.db exists — run /clear then /forge-init to initialize.
```
