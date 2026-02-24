---
description: Interactive holistic review session — QA walkthrough with user (project)
---

# ARGUMENTS

Parse `$ARGUMENTS` for flags:
- `--ids 1,2,3` — Focus review on specific features and their interactions
- `--mobile` — Test mobile viewport (375x667) in addition to desktop
- `--a11y` — Include accessibility checks (contrast, ARIA labels, keyboard nav)

The project is always the current working directory.

Examples:
- `/forge-test` — full review
- `/forge-test --ids 5,8,12` — focus on features 5, 8, and 12
- `/forge-test --mobile` — include mobile viewport testing
- `/forge-test --a11y --mobile` — combine flags

---

# GOAL

Interactive holistic review of the running application with the user acting as product owner. You are the QA engineer. This is NOT automated regression testing — build-time oracles during `/forge-build` and `/forge-parallel` handle per-feature verification. `/forge-test` catches what oracles can't: visual cohesion, end-to-end user journeys, cross-feature integration, and overall UX.

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

## 3. Features exist and some are passing

Call `feature_get_stats` to check project status.

- If `total == 0`: "No features found. Run `/forge-init` first."
- If `passing == 0`: "No features have been implemented yet. Run `/forge-build` or `/forge-parallel` first to implement some features."

**Stop here** in either case.

---

# STEP 1: ANALYZE COMPLETED FEATURES

Call `feature_get_stats` for overall progress. Then call `feature_get_ready` (limit=50) and `feature_get_blocked` to get all non-passing features. For each passing feature you need details on, call `feature_get_by_id`.

If `--ids` was specified, filter to only those feature IDs (but still show overall progress context).

Read the app spec at `.autoforge/prompts/app_spec.txt` for route/URL context.

## Classify each passing feature

For each passing feature, classify it into one of these categories:

**Visible UI** — features with user-facing pages, components, navigation, forms, or visual output:
- Complete screens (pages with routes/URLs)
- Navigation and layout components (sidebars, headers, footers)
- Partially-built pages (some but not all sub-features done)

**Infrastructure** — features with no visible UI:
- Database schema, migrations
- API endpoints, middleware
- Auth backend, session handling
- Configuration, environment setup

To classify: read each feature's name, description, and verification steps. Features mentioning pages, routes, components, forms, buttons, or visual elements are UI. Features mentioning schema, endpoints, middleware, config, or backend logic are infrastructure.

---

# STEP 2: PRESENT REVIEW SUMMARY

Present a clear summary before doing anything else. Format:

```
Reviewing {ProjectName} ({passing}/{total} features passing)
═══════════════════════════════════════════════════════════

Navigation & Layout:
  - {feature name} (complete)

Complete screens you can check out:
  - {route}  — {description}
  - {route}  — {description}

Partially built:
  - {route}  — {what's done vs what's remaining}

Not yet reviewable (backend only):
  - {feature name}, {feature name}, ...
```

## Edge case: Nothing visual built yet

If ALL passing features are infrastructure (no visible UI):

```
Reviewing {ProjectName} ({passing}/{total} features passing)
═══════════════════════════════════════════════════════════

All {passing} completed features are infrastructure — there's no visible UI to
review yet:
  - {feature name}
  - {feature name}
  - ...

Coming up next in /forge-build:
  - Feature #{id}: {name}
  - Feature #{id}: {name}
  - Feature #{id}: {name}

Run /clear then /forge-build or /forge-parallel to continue building.
```

**Stop here.** Do NOT start a dev server when there's nothing visual to review.

---

# STEP 3: DEV SERVER

Only reach this step if there IS visible UI to review.

## Check if a dev server is already running

Check for a running dev server (look for the process, try connecting to the expected port, or check if the project's dev command is running).

- **Already running:** Use the existing server. Note the URL. Set `started_server = false`.
- **Not running:** Start it. Set `started_server = true`.

Starting the dev server:
```bash
# Detect and run the project's dev command
# (check package.json scripts, init.sh, etc.)
npm run dev &
# or whatever the project uses
```

Tell the user the URL:

> "Dev server running on http://localhost:{PORT}
> Open it in your browser and let me know what you'd like to look at, or if you spot any issues."

---

# STEP 4: INTERACTIVE REVIEW

The user opens the app in their own browser. You are available to assist on demand:

## Available actions (respond to user requests):

**Answer questions:**
- "What does feature X do?"
- "Why does this page look like that?"
- Explain what's been built and what's coming

**Take screenshots:**
- Use `playwright-cli` to capture specific pages/states
- Show the user what you see

**Investigate issues:**
- User spots a bug → inspect code, check console errors, trace the issue
- Use `playwright-cli console` and `playwright-cli network` for debugging

**Run user journeys:**
- Walk through specific flows on request
- Test multi-step interactions (signup → login → dashboard → feature)

**Mobile testing** (if `--mobile` flag):
- Use `playwright-cli resize 375 667` to test mobile viewport
- Check responsive layout, touch targets, overflow issues
- Compare with desktop layout

**Accessibility checks** (if `--a11y` flag):
- Check color contrast ratios
- Verify ARIA labels on interactive elements
- Test keyboard navigation (Tab, Enter, Escape)
- Check focus indicators and skip links
- Verify semantic HTML structure

## What to look for (guide the conversation toward):

- **Visual cohesion** — consistent styling, colors, spacing across pages
- **Navigation flow** — links work, user journey makes sense end-to-end
- **Cross-feature integration** — features that individually pass but break together
- **Responsive layout** — content doesn't overflow, readable on different sizes
- **Overall UX** — does the app "feel right"? Only a human can judge this

---

# STEP 5: FIX ISSUES

When the user reports an issue or you discover one:

1. **Investigate** — read relevant code, check browser state
2. **Fix** — make targeted code changes
3. **Verify** — take a screenshot and show the user the fix
4. **Commit** (if the fix is substantial):
   ```bash
   git add -A
   git commit -m "fix: {description of what was fixed}" -m "Found during /forge-test review"
   ```

You have a fresh context budget — use it for targeted fixes. Don't try to rewrite large portions of the app.

---

# STEP 6: WRAP UP

When the user is satisfied or has no more feedback:

1. **Summarize** what was reviewed and any fixes made
2. **Clean up dev server:**
   - If `started_server == true` → stop the dev server
   - If `started_server == false` → leave it running (it was already running before this session)
3. **Close browser** if you opened one:
   ```bash
   playwright-cli close
   ```
4. **Suggest next steps** (always recommend `/clear` first):
   - If there are remaining features: "Run `/clear` then `/forge-build` or `/forge-parallel` to continue implementing features."
   - If all features pass: "All features are passing — your app is complete!"
   - If issues were found but not fixed: "Run `/clear` then `/forge-fix --ids {ids}` for the issues we identified."

---

# FEATURE TOOL REFERENCE

Available MCP tools for the review session:

| Tool | Purpose |
|------|---------|
| `feature_get_stats` | Progress statistics (passing/total counts) |
| `feature_get_by_id` | Get specific feature details by ID |
| `feature_get_ready` | Features ready to implement next |
| `feature_get_blocked` | Features blocked by unmet dependencies |
| `feature_get_progress_bar` | ASCII progress bar with status counts |

**Do NOT** modify feature statuses during `/forge-test`. This is a review session, not a build session. If you fix a regression and need to update status, that's the exception — mark it failing then passing after the fix is verified.

---

# BROWSER AUTOMATION

Use `playwright-cli` for screenshots, snapshots, and investigation:

```bash
playwright-cli open http://localhost:PORT   # Open browser
playwright-cli goto http://localhost:PORT/page  # Navigate
playwright-cli snapshot                      # Get element refs
playwright-cli screenshot                    # Take screenshot
playwright-cli screenshot --filename=review-homepage.png  # Named screenshot
playwright-cli resize 375 667               # Mobile viewport
playwright-cli console                       # Check JS errors
playwright-cli network                       # Monitor API calls
playwright-cli close                         # Close browser
```

Screenshots and snapshots save to `.playwright-cli/`. Read the files to see content.

---

# EDGE CASES

| Scenario | Behavior |
|----------|----------|
| No passing features | "No features have been implemented yet. Run `/clear` then `/forge-build` first." Stop. |
| All passing features are infrastructure | Show what's built, list upcoming visual features, suggest `/clear` then `/forge-build`. Do NOT start dev server. Stop. |
| Dev server already running | Use it. Don't start a second one. Don't stop it on exit. |
| Dev server not running | Start it. Stop it when session ends. |
| YOLO project | Especially valuable — YOLO skips per-feature browser checks, so this may be the first time anyone looks at the running app. Mention this to the user. |
| User has no feedback | Congratulate them and exit cleanly. |
| `--ids` specified | Focus on those features and their interactions, but show overall progress context. |

---

Begin by running the prerequisites check, then analyze features and present the review summary.
