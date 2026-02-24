# CCForge

**Version:** 1.0.2

**Autonomous feature-by-feature application development for Claude Code**

## What is CCForge?

CCForge is a slash command system that turns [Claude Code](https://docs.anthropic.com/en/docs/claude-code) into an autonomous application builder. It breaks your project into features, tracks them in a dependency-aware database, and implements them one by one -- with verification, retry logic, and parallel execution -- across as many sessions as it takes.

You describe the app you want. CCForge writes the spec, derives the features, resolves their dependencies, and builds them in topological order. Each feature is claimed, implemented, lint-checked, type-checked, and browser-tested before being committed. Features that fail are retried or flagged for human intervention. The whole system is designed to pick up where it left off, so you can close your laptop and resume tomorrow.

Built on the [AutoForge](https://github.com/AutoForgeAI/autoforge) architecture by Leon van Zyl, CCForge adapts AutoForge's long-running autonomous agent approach into a set of composable Claude Code slash commands (`/forge-create`, `/forge-build`, `/forge-parallel`, etc.) that work within the standard Claude Code workflow.

## Installation

**Requirements:** Python 3.11+, Claude Code CLI

```bash
python install_forge.py             # Install or update (idempotent)
python install_forge.py --check     # Verify installation health
python install_forge.py --uninstall # Remove everything
```

This copies core files to `~/.forge/` and registers `/forge-create` in `~/.claude/commands/` so it's available from any directory. All other commands are project-local -- copied into each project by `/forge-create`. See [INSTALLER.md](INSTALLER.md) for details.

---

## Workflow Overview

CCForge projects follow a linear pipeline. Each step has a dedicated slash command:

```
/forge-create  →  /forge-init  →  /forge-build     →  /forge-test
   (spec)          (features)     /forge-parallel       (QA)
                                   (implement)
```

### Typical Session

```bash
# 1. Create a new project spec interactively
/forge-create my-app
```

> **Important:** After `/forge-create` finishes, you must **restart Claude Code** before
> continuing. The forge commands are copied into your project directory during creation,
> and Claude Code must be restarted to detect them.

```bash
# 2. Restart Claude Code, then move into the project
cd my-app

# 3. Initialize features from the spec into the database
/forge-init

# 4. Build features one at a time (repeat until done)
/forge-build

# 5. Check progress at any point
/forge-status

# 6. Run interactive QA when features are complete
/forge-test
```

> **Tip:** Run `/clear` between different forge commands to keep the context window fresh.

### Parallel Build Session

```bash
# Build 3 features at once with YOLO mode (skip browser testing)
/forge-parallel --yolo --workers 3

# Build with concurrent regression testing
/forge-parallel --workers 4 --regression

# Run 5 batch cycles then stop
/forge-parallel --max-batches 5
```

### Fixing Failures

```bash
# See what failed and why
/forge-status

# Diagnose and fix features that exhausted retries
/forge-fix

# Fix specific features by ID
/forge-fix --ids 5,12

# Run automated regression testing
/forge-regression --continuous
```

### Expanding a Project

```bash
# Add new features to an existing project
/forge-expand

# Seed the conversation with what you want
/forge-expand Add a notification system with email and push support
```

---

## Command Reference

### `/forge-create` -- Create a project spec

Interactive wizard that builds a complete project specification through conversational phases (overview, tech stack, features, success criteria). Outputs an `app_spec.txt` and sets up the project directory with MCP server, templates, and skills.

```bash
/forge-create my-app              # Create spec at ./my-app
/forge-create /path/to/project    # Create spec at absolute path
```

**Requires:** A project directory path (mandatory argument).

**Creates:**
- `{project}/.autoforge/prompts/app_spec.txt` -- The full project spec
- `{project}/.mcp.json` -- MCP server config
- `{project}/mcp_server/`, `api/` -- Server and database code
- `{project}/.claude/commands/` -- Project-local forge commands
- `{project}/.claude/agents/` -- Project-local agent definitions
- `{project}/.claude/skills/` -- playwright-cli (browser testing) and frontend-design (UI quality)
- `{project}/.claude/templates/`, `CLAUDE.md` -- Templates and project instructions

> **Tip:** During the spec wizard, you can mention "use the frontend-design skill" in your description to have the build agents invoke it when implementing UI components. This activates a design-focused skill that guides Claude toward distinctive, production-grade interfaces rather than generic defaults. It's optional -- if you don't mention it, features are built with standard code quality practices.

> **Note:** After `/forge-create` completes, **restart Claude Code** before running `/forge-init`. The project-local commands (like `/forge-init`, `/forge-build`, etc.) are copied into the project directory during creation and won't be detected until Claude Code is restarted.

---

### `/forge-init` -- Initialize features from spec

Reads the app spec and populates the feature database. Creates features with dependencies, verification steps, and an `init.sh` dev environment setup script. Initializes git.

```bash
/forge-init                       # Initialize in current directory
```

**Requires:** `{project}/.autoforge/prompts/app_spec.txt` must exist (created by `/forge-create`).

---

### `/forge-build` -- Build features sequentially

Main build loop. Claims the next ready feature, implements it, verifies it (lint, typecheck, browser testing), commits, and moves on. Designed for multi-session execution -- pick up where you left off.

```bash
/forge-build                               # Build 1 feature
/forge-build --batch 3                     # Build up to 3 features then stop
/forge-build --yolo                        # Skip browser testing (lint/typecheck only)
/forge-build --ids 5,8,12                  # Only build these specific features
/forge-build --yolo --batch 5              # Combine flags
/forge-build --agent-id worker-1           # Set agent ID (for parallel use)
```

| Flag | Description |
|------|-------------|
| `--yolo` | Skip browser testing. Lint/typecheck still run. Good for rapid scaffolding. |
| `--batch N` | Build up to N features per session (default: 1, max: 3). |
| `--ids 1,2,3` | Only build these specific feature IDs. |
| `--agent-id <id>` | Agent identifier for parallel mode. Auto-generated UUID if omitted. |

**Stop conditions:** Batch limit reached, all features done, all remaining blocked/exhausted, or user interrupts (Ctrl+C).

**Verification flow (standard mode):**
1. Lint and typecheck pass
2. Dev server running
3. Browser oracle verifies each step (via playwright-cli)
4. Mock data grep (no fake data in production code)
5. Server restart persistence test (for CRUD features)

Features that fail verification 3 times are marked exhausted and skipped. Use `/forge-fix` to address them.

---

### `/forge-parallel` -- Parallel build with multiple agents

Spawns multiple coder subagents to implement features concurrently. Runs in batch cycles: claim features, dispatch workers, poll for completion, repeat.

```bash
/forge-parallel                                     # 3 workers
/forge-parallel --workers 2                         # 2 workers
/forge-parallel --yolo --workers 4                  # 4 workers, YOLO mode
/forge-parallel --max-batches 5                     # Stop after 5 cycles
/forge-parallel --regression --workers 4            # 3 coders + 1 tester
/forge-parallel --yolo --workers 2 --max-batches 10 # Combine flags
```

| Flag | Description |
|------|-------------|
| `--workers N` | Number of concurrent workers (1-4, default: 3). |
| `--yolo` | Pass YOLO mode to all workers (skip browser testing). |
| `--max-batches N` | Maximum batch cycles before stopping (default: unlimited). |
| `--regression` | Reserve 1 worker slot for a regression testing agent each batch cycle. |

**When to use:** Best for batch-building many independent features quickly. Especially effective with `--yolo` for rapid scaffolding. Use `/forge-build` for complex features that need detailed control.

**How it works:** Each worker gets a self-contained prompt and implements one feature independently. Atomic database claims prevent double-work. Workers commit independently -- git handles concurrent file changes. Stale claims from crashed workers are cleaned up automatically.

---

### `/forge-status` -- Project progress overview

Read-only status report showing progress bar, status breakdown, blocked features, and optionally the full dependency tree.

```bash
/forge-status                     # Progress bar + stats + failures + blocked
/forge-status --tree              # Also show ASCII dependency tree
/forge-status --graph             # Same as --tree
/forge-status --all               # Show full feature list with details
/forge-status --ids 1,2,3         # Show details for specific features
```

| Flag | Description |
|------|-------------|
| `--tree` / `--graph` | Include ASCII dependency tree visualization. |
| `--all` | Show every feature with full details. |
| `--ids 1,2,3` | Show detailed info for specific feature IDs. |

**Example output:**
```
AutoForge Status
════════════════

[========>...........................] 8/20 features passing

  Pending:      7
  In Progress:  1
  Passing:      8
  Failing:      4

Exhausted Retries (needs /forge-fix):
  #8  Payment Integration  — "Stripe SDK requires STRIPE_SECRET_KEY" (3 attempts)

Blocked Features:
  #16 Admin Panel — blocked by #13 (in progress), #15 (failing)

Next Ready: #14 — Email Notifications
```

---

### `/forge-test` -- Interactive QA review

Interactive QA session where the user acts as product owner. Catches what automated per-feature oracles cannot: visual cohesion, end-to-end user journeys, cross-feature integration, and UX issues.

```bash
/forge-test                       # Review all passing features
/forge-test --ids 1,2,3           # Focus on specific features
/forge-test --mobile              # Also test mobile viewport (375x667)
/forge-test --a11y                # Include accessibility checks
```

| Flag | Description |
|------|-------------|
| `--ids 1,2,3` | Focus review on specific features only. |
| `--mobile` | Test mobile viewport (375x667) in addition to desktop. |
| `--a11y` | Include accessibility checks. |

**How it works:** The agent starts the dev server, then walks through passing features interactively with you. You open the app in your browser; the agent assists on demand -- taking screenshots, investigating issues, running user journeys, and fixing problems it finds.

---

### `/forge-regression` -- Automated regression testing

Automated regression testing of previously-passing features with auto-fix. Spawns background testing subagents that verify features and attempt to fix any regressions found.

```bash
/forge-regression                              # Test 5 features, single cycle
/forge-regression --batch 3                    # Test 3 features per cycle
/forge-regression --continuous                 # Keep testing until full rotation
/forge-regression --continuous --batch 8       # Combine flags
```

| Flag | Description |
|------|-------------|
| `--batch N` | Features to test per cycle (1-10, default: 5). |
| `--continuous` | Keep cycling until all passing features are tested. |

**How it works:** Features are scored by impact (dependents, integration risk, untested bonus) and tested in priority order. Testing subagents verify each feature through browser testing, and if a regression is detected, they investigate and fix it automatically. Features that can't be fixed are left as failing for `/forge-fix`.

**Distinct from `/forge-test`:** Regression testing is automated and programmatic. `/forge-test` is interactive QA with the user. Use regression testing during builds (via `--regression` on `/forge-parallel`) and interactive QA at milestones.

---

### `/forge-fix` -- Fix failing features

Interactive failure resolution. Shows why features failed, lets you revise specs, delete features, or retry.

```bash
/forge-fix                        # Show features with 3+ failures (exhausted)
/forge-fix --ids 5,12             # Work on specific features by ID
/forge-fix --all-failing          # Show all failing features, not just exhausted
```

| Flag | Description |
|------|-------------|
| `--ids 1,2,3` | Work on specific features regardless of fail count. |
| `--all-failing` | Show all failing features, not just those with 3+ failures. |

**Resolution options per feature:**
1. **Revise** -- Rewrite the feature description (resets fail state for retry)
2. **Delete** -- Remove the feature (warns about downstream dependents)
3. **Retry** -- Clear fail state and let `/forge-build` try again
4. **Skip** -- Leave as-is

---

### `/forge-expand` -- Add features to existing project

Add new features to a project that already has a feature database. Different from `/forge-create` because the project already exists.

```bash
/forge-expand                                  # Expand current project
/forge-expand Add notifications and analytics  # Seed with description
```

**How it works:** Reads the existing spec and project status, asks what you want to add, derives features through conversation, then creates them with proper dependencies on existing features.

---

### Utility Commands

| Command | Description |
|---------|-------------|
| `/checkpoint` | Stage all changes and create a git commit with a detailed message. |
| `/check-code` | Run `ruff check .` and `mypy .` for lint and type checking. |
| `/review-pr <number>` | Comprehensive PR review (scope, safety, vision alignment, merge recommendation). |

---

## Architecture

### MCP Feature Server (`mcp_server/feature_mcp.py`)

A standalone MCP server providing 22 tools for feature lifecycle management. Started automatically by Claude Code via `.mcp.json`. All operations use atomic SQL with `BEGIN IMMEDIATE` transactions for parallel safety.

**Query tools:**
| Tool | Description |
|------|-------------|
| `feature_get_stats` | Progress stats (passing, in_progress, total, percentage, claimed list) |
| `feature_get_by_id` | Full feature details by ID |
| `feature_get_summary` | Minimal info (id, name, status, deps) |
| `feature_get_ready` | Features ready to implement (deps satisfied), sorted by scheduling score |
| `feature_get_blocked` | Features with unmet dependencies |
| `feature_get_graph` | Dependency graph (nodes + edges) |
| `feature_get_progress_bar` | ASCII progress bar with status counts |
| `feature_get_dependency_tree` | ASCII dependency tree visualization |

**Lifecycle tools:**
| Tool | Description |
|------|-------------|
| `feature_create` | Create a single feature |
| `feature_create_bulk` | Create multiple features with index-based dependency resolution |
| `feature_update` | Modify name/description/steps (resets fail state) |
| `feature_mark_in_progress` | Claim a feature for implementation |
| `feature_claim_and_get` | Atomically claim and retrieve feature details |
| `feature_mark_passing` | Mark feature as complete |
| `feature_mark_failing` | Mark as failing with reason (increments fail_count) |
| `feature_skip` | Move feature to end of priority queue |
| `feature_clear_in_progress` | Clear one feature's claim |
| `feature_clear_all_in_progress` | Reset orphaned claims (supports agent_id filter) |
| `feature_clear_stale` | Clear claims older than timeout (orphan detection) |

**Dependency tools:**
| Tool | Description |
|------|-------------|
| `feature_add_dependency` | Add a dependency (with cycle detection) |
| `feature_remove_dependency` | Remove a dependency |
| `feature_set_dependencies` | Replace all dependencies for a feature |

### Database (`api/database.py`)

SQLAlchemy models for SQLite storage. Database location: `{project_dir}/.autoforge/features.db`

- WAL mode on local filesystems, DELETE mode on network paths
- IMMEDIATE transactions for parallel-safe operations
- Automatic schema migrations
- Engine caching per project directory

### Dependency Resolver (`api/dependency_resolver.py`)

- Kahn's algorithm for topological sorting
- DFS-based cycle detection (max depth: 50)
- Scheduling score: `(1000 * unblock_potential) + (100 * depth) + (10 * priority)`
- Max 20 dependencies per feature

---

## Project Structure

```
ccforge/
├── install_forge.py                   # Global installer (--check, --uninstall)
├── INSTALLER.md                       # Installer documentation
├── requirements.txt                   # Python deps: mcp, sqlalchemy, pydantic
├── pyproject.toml                     # Ruff + mypy configuration
├── api/
│   ├── database.py                    # SQLAlchemy models, migrations
│   └── dependency_resolver.py         # Topological sort, cycle detection
├── mcp_server/
│   ├── feature_mcp.py                 # MCP server (22 tools)
│   └── requirements.txt              # MCP server dependencies
└── .claude/
    ├── commands/
    │   ├── forge-create.md            # /forge-create
    │   ├── forge-init.md              # /forge-init
    │   ├── forge-build.md             # /forge-build
    │   ├── forge-parallel.md          # /forge-parallel
    │   ├── forge-status.md            # /forge-status
    │   ├── forge-test.md              # /forge-test
    │   ├── forge-regression.md        # /forge-regression
    │   ├── forge-fix.md               # /forge-fix
    │   ├── forge-expand.md            # /forge-expand
    │   ├── checkpoint.md              # /checkpoint
    │   ├── check-code.md              # /check-code
    │   └── review-pr.md              # /review-pr
    ├── agents/
    │   ├── coder.md                   # Code implementation agent (Opus)
    │   ├── code-review.md             # Code review agent (Opus)
    │   └── deep-dive.md              # Technical investigation agent (Opus)
    ├── skills/
    │   ├── playwright-cli/            # Browser automation for testing
    │   └── frontend-design/           # Production-grade UI design
    └── templates/
        ├── app_spec.template.txt      # XML project spec template
        ├── initializer_prompt.template.md
        ├── coding_prompt.template.md
        ├── testing_prompt.template.md
        └── project-claude.template.md
```

---

## Code Quality

```bash
ruff check .                                    # Lint
mypy .                                          # Type check
python -m pytest test_dependency_resolver.py    # Dependency resolver tests
```

Configuration in `pyproject.toml`: ruff (line length 120, Python 3.11, E/F/I/W rules), mypy (Python 3.11, ignore missing imports).

---

## Acknowledgments

CCForge is built on the [AutoForge](https://github.com/AutoForgeAI/autoforge) architecture by Leon van Zyl. AutoForge is a long-running autonomous coding agent powered by the Claude Agent SDK that builds complete applications across multiple sessions. CCForge adapts that architecture into composable Claude Code slash commands for feature-by-feature development.

## Contributing

Contributions are welcome. Feel free to open an issue to report bugs or suggest features, or submit a pull request. For larger changes, opening an issue first to discuss the approach is appreciated.

## License

Licensed under the [GNU Affero General Public License v3.0](LICENSE). This license is inherited from the upstream [AutoForge](https://github.com/AutoForgeAI/autoforge) project, which is also licensed under AGPL-3.0. See the [LICENSE](LICENSE) file for the full text.
