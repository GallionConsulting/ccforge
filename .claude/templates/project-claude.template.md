# [PROJECT_NAME]

[PROJECT_DESCRIPTION]

## Tech Stack

[TECH_STACK_SUMMARY]

## Feature Tracking

This project uses a feature MCP server to track development progress. Features are stored in `.autoforge/features.db` (SQLite). The MCP server is configured in `.mcp.json` and provides these tools:

| Tool | Description |
|------|-------------|
| `feature_get_stats` | Progress statistics (passing/total counts) |
| `feature_get_by_id` | Get a single feature by ID |
| `feature_get_summary` | Minimal info for a single feature (id, name, status, deps) |
| `feature_get_ready` | Features ready to work on (dependencies met) |
| `feature_get_blocked` | Features blocked by unmet dependencies |
| `feature_get_graph` | Full dependency graph |
| `feature_mark_in_progress` | Mark a feature as in progress |
| `feature_mark_passing` | Mark a feature as complete |
| `feature_mark_failing` | Mark a feature as failing |
| `feature_skip` | Move a feature to end of queue |

## Forge Commands

| Command | Description |
|---------|-------------|
| `/forge-init` | Initialize features from the app spec (run once after `/forge-create`) |
| `/forge-build` | Implement the next ready feature(s) |
| `/forge-test` | Run regression tests across completed features |
| `/forge-status` | Show current progress and feature status |
| `/forge-fix` | Fix a failing feature by ID |
| `/forge-expand` | Add new features to the project |

### Typical Workflow

1. `/forge-init` — Creates [FEATURE_COUNT] features in the database from the spec
2. `/forge-build` — Implements the next ready feature (repeat until done)
3. `/forge-test` — Periodically run regression tests to verify nothing broke
4. `/forge-status` — Check progress at any time

## Project Structure

```
.autoforge/
  prompts/
    app_spec.txt           # Project specification (XML)
    coding_prompt.md       # Coding agent prompt
    testing_prompt.md      # Testing agent prompt
  features.db              # Feature database (SQLite)
  .agent.lock              # Lock file (prevents concurrent agents)
  .gitignore               # Ignores runtime files

mcp_server/
  feature_mcp.py           # MCP server for feature tracking
  requirements.txt         # MCP server dependencies

api/
  database.py              # SQLAlchemy models (Feature table)
  dependency_resolver.py   # Cycle detection for feature dependencies

.mcp.json                  # MCP server config (auto-discovered by Claude Code)
CLAUDE.md                  # This file

.claude/
  skills/
    playwright-cli/        # Browser automation for testing
```

## Browser Testing (Playwright CLI)

The Playwright CLI skill is available at `.claude/skills/playwright-cli/` for browser automation testing. Use it to:

- Navigate to pages and verify content renders
- Fill forms and submit data
- Click buttons and verify state changes
- Take screenshots for visual verification
- Test responsive layouts at different viewport sizes

## Coding Conventions

- Follow the technology stack specified in `.autoforge/prompts/app_spec.txt`
- Use real database queries — never use mock data, in-memory stores, or hardcoded arrays
- Every feature must be independently testable via the browser
- Mark features as passing only after verifying they work end-to-end
- Do not modify or delete existing features in the database
- Run `init.sh` to start the development server before testing
