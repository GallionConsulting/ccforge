---
description: Initialize features from app spec (project)
---

# ARGUMENTS

`$ARGUMENTS` is not used by this command. The project is always the current working directory.

---

# GOAL

Read the project's app specification and populate the feature database using MCP tools. This is the second step after `/forge-create` — it sets up all features with dependencies so `/forge-build` can implement them.

---

# PREREQUISITES CHECK

Before doing anything else, verify these prerequisites:

## 1. App spec exists

Check for the app spec file at `.autoforge/prompts/app_spec.txt`.

If it does NOT exist:

> "No app spec found at `.autoforge/prompts/app_spec.txt`.
>
> Run `/forge-create` first to create the project specification."

**Stop here** if the spec is missing.

## 2. MCP feature server is available

The feature MCP tools (`feature_create_bulk`, `feature_get_stats`, etc.) must be available. These are configured via `.mcp.json` in the project root, which `/forge-create` sets up.

If MCP tools are not available:

> "The feature MCP server is not configured. Ensure `.mcp.json` exists in your project root with the feature-mcp server entry.
>
> If you used `/forge-create`, this should already be set up. Try restarting Claude Code in the project directory."

**Stop here** if MCP tools are unavailable.

## 3. Check for existing features

Call `feature_get_stats` to check if features already exist in the database.

If features already exist (total > 0):

> "Features already exist in this project ({total} features, {passing} passing).
>
> `/forge-init` is meant for first-time initialization. If you want to start over:
>
> 1. Delete the feature database: `rm .autoforge/features.db`
> 2. Run `/forge-init` again
>
> If you want to add new features to an existing project, use `/forge-expand` instead."

**Stop here** if features already exist, unless the user explicitly confirms they want to proceed.

---

# YOUR ROLE — INITIALIZER AGENT

You are the **Initializer Agent**. Your job is to read the app specification and create all features in the database with proper dependencies. You do NOT implement any features — that's what `/forge-build` is for.

---

# STEP 1: Read the App Specification

Read `.autoforge/prompts/app_spec.txt` carefully. Understand:

- The project name and description
- Technology stack
- All feature categories and individual features
- Database schema
- API endpoints
- The `<feature_count>` value — this is how many features you must create

---

# STEP 2: Create Features via MCP

Use the `feature_create_bulk` tool to create all features. You can create features in batches if there are many (e.g., 50 at a time).

## Feature Count

**CRITICAL:** You must create exactly the number of features specified in `<feature_count>` in the app spec. Do not create more or fewer.

## Context Weight Estimation (MANDATORY)

For EVERY feature, you must estimate `context_weight` (1-5) based on the scope of code changes, number of files likely touched, and integration complexity:

| Weight | Level | Examples |
|--------|-------|---------|
| 1 | Trivial | Config change, static content, add favicon, simple text update |
| 2 | Small | Simple component, minor feature, single-file change |
| 3 | Typical | New component with logic, API endpoint, form with validation |
| 4 | Substantial | Multi-file feature, state management, complex UI interaction |
| 5 | Complex | Full subsystem, real-time features, auth flow, payment integration |

These weights help estimate feature scope for planning purposes. **Be accurate** — they inform expectations about implementation complexity.

## Feature Requirements

- Feature count must match the `feature_count` specified in app_spec.txt
- Reference tiers for other projects:
  - **Simple apps**: ~25-55 features (includes 5 infrastructure)
  - **Medium apps**: ~105 features (includes 5 infrastructure)
  - **Advanced apps**: ~155-205+ features (includes 5 infrastructure)
- Both "functional" and "style" categories
- Mix of narrow tests (2-5 steps) and comprehensive tests (10+ steps)
- At least 25% of features SHOULD have 10+ steps each (more for complex apps)
- Order features by priority: fundamental features first (the API assigns priority based on order)
- Cover every feature in the spec exhaustively
- **MUST include tests from ALL 20 mandatory categories** (see below)

---

# STEP 3: Feature Dependencies (MANDATORY)

Dependencies enable **parallel execution** of independent features. When specified correctly, multiple agents can work on unrelated features simultaneously.

## Dependency Rules

1. **Use `depends_on_indices`** (0-based array indices) to reference dependencies in `feature_create_bulk`
2. **Can only depend on EARLIER features** (index must be less than current position)
3. **No circular dependencies** allowed
4. **Maximum 20 dependencies** per feature
5. **Infrastructure features (indices 0-4)** have NO dependencies — they run FIRST
6. **ALL features after index 4** MUST depend on `[0, 1, 2, 3, 4]` (infrastructure)
7. **60% of features after index 10** should have additional dependencies beyond infrastructure

## Dependency Types

| Type | Example |
|------|---------|
| Data | "Edit item" depends on "Create item" |
| Auth | "View dashboard" depends on "User can log in" |
| Navigation | "Modal close works" depends on "Modal opens" |
| UI | "Filter results" depends on "Display results list" |

## Wide Graph Pattern (REQUIRED)

Create WIDE dependency graphs, not linear chains:

- **BAD:** A -> B -> C -> D -> E (linear chain, only 1 feature runs at a time)
- **GOOD:** A -> B, A -> C, A -> D, B -> E, C -> E (wide graph, parallel execution)

### Example

```json
[
  // INFRASTRUCTURE TIER (indices 0-4, no dependencies) - MUST run first
  { "name": "Database connection established", "category": "functional", "context_weight": 3 },
  { "name": "Database schema applied correctly", "category": "functional", "context_weight": 3 },
  { "name": "Data persists across server restart", "category": "functional", "context_weight": 4 },
  { "name": "No mock data patterns in codebase", "category": "functional", "context_weight": 2 },
  { "name": "Backend API queries real database", "category": "functional", "context_weight": 3 },

  // FOUNDATION TIER (indices 5-7, depend on infrastructure)
  { "name": "App loads without errors", "category": "functional", "context_weight": 3, "depends_on_indices": [0, 1, 2, 3, 4] },
  { "name": "Navigation bar displays", "category": "style", "context_weight": 2, "depends_on_indices": [0, 1, 2, 3, 4] },
  { "name": "Homepage renders correctly", "category": "functional", "context_weight": 3, "depends_on_indices": [0, 1, 2, 3, 4] },

  // AUTH TIER (indices 8-10, depend on foundation + infrastructure)
  { "name": "User can register", "context_weight": 4, "depends_on_indices": [0, 1, 2, 3, 4, 5] },
  { "name": "User can login", "context_weight": 4, "depends_on_indices": [0, 1, 2, 3, 4, 5, 8] },
  { "name": "User can logout", "context_weight": 2, "depends_on_indices": [0, 1, 2, 3, 4, 9] },

  // CORE CRUD TIER (indices 11-14) - WIDE GRAPH: all depend on login, not each other
  { "name": "User can create todo", "context_weight": 3, "depends_on_indices": [0, 1, 2, 3, 4, 9] },
  { "name": "User can view todos", "context_weight": 3, "depends_on_indices": [0, 1, 2, 3, 4, 9] },
  { "name": "User can edit todo", "context_weight": 3, "depends_on_indices": [0, 1, 2, 3, 4, 9, 11] },
  { "name": "User can delete todo", "context_weight": 3, "depends_on_indices": [0, 1, 2, 3, 4, 9, 11] }
]
```

---

# MANDATORY INFRASTRUCTURE FEATURES (Indices 0-4)

**CRITICAL:** Create these FIRST, before any functional features. These features ensure the application uses a real database, not mock data or in-memory storage.

**Note:** If the app spec indicates a stateless application (`<database>none</database>`), replace these with simplified infrastructure features appropriate for the app type (e.g., "App builds without errors", "App loads in browser", etc.) — but still create exactly 5 infrastructure features at indices 0-4.

| Index | Name | Test Steps |
|-------|------|------------|
| 0 | Database connection established | Start server, check logs for DB connection, health endpoint returns DB status |
| 1 | Database schema applied correctly | Connect to DB directly, list tables, verify schema matches spec |
| 2 | Data persists across server restart | Create via API, STOP server, START server, verify data still exists |
| 3 | No mock data patterns in codebase | Run grep for prohibited patterns, must return empty |
| 4 | Backend API queries real database | Check server logs, verify SQL queries appear for API calls |

**ALL other features MUST depend on indices [0, 1, 2, 3, 4].**

### Infrastructure Feature Descriptions

**Feature 0 - Database connection established:**
```
Steps:
1. Start the development server
2. Check server logs for database connection message
3. Call health endpoint (e.g., GET /api/health)
4. Verify response includes database status: connected
```

**Feature 1 - Database schema applied correctly:**
```
Steps:
1. Connect to database directly (sqlite3, psql, etc.)
2. List all tables in the database
3. Verify tables match what's defined in app_spec.txt
4. Verify key columns exist on each table
```

**Feature 2 - Data persists across server restart (CRITICAL):**
```
Steps:
1. Create unique test data via API (e.g., POST /api/items with name "RESTART_TEST_12345")
2. Verify data appears in API response (GET /api/items)
3. STOP the server completely (kill by port)
4. Verify server is stopped
5. RESTART the server
6. Query API again
7. Verify test data still exists
8. If data is GONE → CRITICAL FAILURE (in-memory storage detected)
9. Clean up test data
```

**Feature 3 - No mock data patterns in codebase:**
```
Steps:
1. Run: grep -r "globalThis\." --include="*.ts" --include="*.tsx" --include="*.js" src/
2. Run: grep -r "mockData\|testData\|fakeData\|sampleData\|dummyData" --include="*.ts" --include="*.tsx" --include="*.js" src/
3. Run: grep -r "TODO.*real\|TODO.*database\|TODO.*API\|STUB\|MOCK" --include="*.ts" --include="*.tsx" --include="*.js" src/
4. Run: grep -E "json-server|miragejs|msw" package.json
5. ALL grep commands must return empty (exit code 1)
```

**Feature 4 - Backend API queries real database:**
```
Steps:
1. Start server with verbose logging
2. Make API call (e.g., GET /api/items)
3. Check server logs
4. Verify SQL query appears (SELECT, INSERT, etc.) or ORM query log
```

---

# MANDATORY TEST CATEGORIES

Your features **MUST** include tests from ALL 20 categories. Minimum counts scale by complexity tier.

## Category Distribution (Reference Proportions)

The table below shows proportional distribution across 20 categories. Scale proportionally to your actual `feature_count` — for example, a 50-feature simple app would have ~1-3 features per category. **Infrastructure (5 features) is always fixed; distribute remaining features proportionally.**

| Category                         | % of Total |
| -------------------------------- | ---------- |
| **0. Infrastructure (REQUIRED)** | 5 fixed    |
| A. Security & Access Control     | ~8%        |
| B. Navigation Integrity          | ~10%       |
| C. Real Data Verification        | ~12%       |
| D. Workflow Completeness         | ~8%        |
| E. Error Handling                | ~6%        |
| F. UI-Backend Integration        | ~8%        |
| G. State & Persistence           | ~5%        |
| H. URL & Direct Access           | ~4%        |
| I. Double-Action & Idempotency   | ~3%        |
| J. Data Cleanup & Cascade        | ~4%        |
| K. Default & Reset               | ~3%        |
| L. Search & Filter Edge Cases    | ~5%        |
| M. Form Validation               | ~6%        |
| N. Feedback & Notification       | ~4%        |
| O. Responsive & Layout           | ~4%        |
| P. Accessibility                 | ~4%        |
| Q. Temporal & Timezone           | ~3%        |
| R. Concurrency & Race Conditions | ~3%        |
| S. Export/Import                 | ~2%        |
| T. Performance                   | ~2%        |

## Category Descriptions

**0. Infrastructure (REQUIRED - Priority 0)** - Database connectivity, schema existence, data persistence across server restart, absence of mock patterns. These MUST pass before any functional features can begin.

**A. Security & Access Control** - Unauthorized access blocking, permission enforcement, session management, role-based access, data isolation between users.

**B. Navigation Integrity** - Buttons, links, menus, breadcrumbs, deep links, back button behavior, 404 handling, post-login/logout redirects.

**C. Real Data Verification** - Data persistence across refreshes and sessions, CRUD operations with unique test data, related record updates, empty states.

**D. Workflow Completeness** - End-to-end CRUD for every entity, state transitions, multi-step wizards, bulk operations, form submission feedback.

**E. Error Handling** - Network failures, invalid input, API errors, 404/500 responses, loading states, timeouts, user-friendly error messages.

**F. UI-Backend Integration** - Request/response format matching, database-driven dropdowns, cascading updates, filters/sorts with real data, API error display.

**G. State & Persistence** - Refresh mid-form, session recovery, multi-tab behavior, back-button after submit, unsaved changes warnings.

**H. URL & Direct Access** - URL manipulation security, direct route access by role, malformed parameters, deep links to deleted entities, shareable filter URLs.

**I. Double-Action & Idempotency** - Double-click submit, rapid delete clicks, back-and-resubmit, button disabled during processing, concurrent submissions.

**J. Data Cleanup & Cascade** - Parent deletion effects on children, removal from search/lists/dropdowns, statistics updates, soft vs hard delete.

**K. Default & Reset** - Form defaults, sensible date picker defaults, dropdown placeholders, reset button behavior, filter/pagination reset on context change.

**L. Search & Filter Edge Cases** - Empty search, whitespace-only, special characters, quotes, long strings, zero-result combinations, filter persistence.

**M. Form Validation** - Required fields, email/password/numeric/date formats, min/max constraints, uniqueness, specific error messages, server-side validation.

**N. Feedback & Notification** - Success/error feedback for all actions, loading spinners, disabled buttons during submit, progress indicators, toast behavior.

**O. Responsive & Layout** - Layouts at desktop (1920px), tablet (768px), and mobile (375px), no horizontal scroll, touch targets, modal fit, text overflow.

**P. Accessibility** - Tab navigation, focus rings, screen reader compatibility, ARIA labels, color contrast, labels on form fields, error announcements.

**Q. Temporal & Timezone** - Timezone-aware display, accurate timestamps, date picker constraints, overdue detection, date sorting across boundaries.

**R. Concurrency & Race Conditions** - Concurrent edits, viewing deleted records, pagination during updates, rapid navigation, late API response handling.

**S. Export/Import** - Full/filtered export, import with valid/duplicate/malformed files, round-trip data integrity.

**T. Performance** - Page load with 100/1000 records, search response time, infinite scroll stability, upload progress, memory/console errors.

---

# ABSOLUTE PROHIBITION: NO MOCK DATA

Features must include tests that **actively verify real data** and **detect mock data patterns**.

**Include these specific tests:**

1. Create unique test data (e.g., "TEST_12345_VERIFY_ME")
2. Verify that EXACT data appears in UI
3. Refresh page — data persists
4. Delete data — verify it's gone
5. If data appears that wasn't created during test — FLAG AS MOCK DATA

**Prohibited patterns the coding agent must NOT use:**

- Hardcoded arrays of fake data
- `mockData`, `fakeData`, `sampleData`, `dummyData` variables
- `// TODO: replace with real API`
- `setTimeout` simulating API delays with static data
- Static returns instead of database queries
- `globalThis.` (in-memory storage pattern)
- `json-server`, `mirage`, `msw` (mock backends)
- `Map()` or `Set()` used as primary data store

---

# STEP 4: Create init.sh

Create a script called `init.sh` in the project root that future agents can use to quickly set up and run the development environment. The script should:

1. Install any required dependencies
2. Start any necessary servers or services
3. Print helpful information about how to access the running application

Base the script on the technology stack specified in `app_spec.txt`.

---

# STEP 5: Initialize Git

Create a git repository and make your first commit with:

- `init.sh` (environment setup script)
- `README.md` (project overview and setup instructions)
- Any initial project structure files

Commit message: `"Initial setup: init.sh, project structure, and features created via API"`

---

# STEP 6: Create Project Structure

Set up the basic project structure based on what's specified in `app_spec.txt`. This typically includes directories for frontend, backend, and any other components mentioned in the spec.

---

# CRITICAL INSTRUCTION

**IT IS CATASTROPHIC TO REMOVE OR EDIT FEATURES IN FUTURE SESSIONS.**

Features can ONLY be marked as passing (via the `feature_mark_passing` tool with the feature_id). Never remove features, never edit descriptions, never modify testing steps. This ensures no functionality is missed.

---

# ENDING THIS SESSION

Once you have completed all steps above:

1. Commit all work with a descriptive message
2. Verify features were created using the `feature_get_stats` tool
3. Leave the environment in a clean, working state
4. Report a summary:

> "Initialization complete!
>
> **Features created:** {total} features across {categories} categories
> **Dependencies:** {with_deps} features have dependencies configured
> **Infrastructure:** 5 mandatory infrastructure features at indices 0-4
>
> **Next step:** `/clear` then `/forge-build` to implement features one at a time, or `/forge-parallel` to build with multiple agents."

**IMPORTANT:** Do NOT attempt to implement any features. Your job is setup only. Feature implementation will be handled by `/forge-build` sessions. Starting implementation here would waste context that should be used for thorough feature specification.
