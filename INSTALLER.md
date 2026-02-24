# Forge Global Installer

Registers only `/forge-create` globally so it works from any directory in Claude Code. All other commands are copied into each project during `/forge-create`, keeping projects self-contained.

## Quick Start

```bash
python ccforge/install_forge.py
```

That's it. Open Claude Code anywhere and run `/forge-create my-app` to start a project.

## What It Does

The installer copies forge's core files to `~/.forge/` and registers `/forge-create` in `~/.claude/commands/` where Claude Code auto-discovers it. All other commands are staged in `~/.forge/commands/` and copied into each project by `/forge-create`.

```
~/.forge/                          # Global installation
  mcp_server/                      # MCP feature server (copied to each project)
  api/                             # Database models (copied to each project)
  templates/                       # Prompt templates
  skills/                          # playwright-cli, frontend-design
  agents/                          # coder, code-review, deep-dive
  commands/                        # Project-local commands (staged here, copied per-project)
    forge-init.md
    forge-build.md
    forge-parallel.md
    forge-status.md
    forge-test.md
    forge-fix.md
    forge-expand.md
    forge-regression.md
    checkpoint.md
    check-code.md
    review-pr.md
  venv/                            # Python 3.11+ venv (mcp, sqlalchemy, pydantic)
  version.json                     # Install metadata

~/.claude/commands/                # Global slash commands (only forge-create)
  forge-create.md                  # Adapted with absolute ~/.forge/ paths
```

## Commands

```bash
python install_forge.py                        # Install or update
python install_forge.py --check                # Verify installation health
python install_forge.py --uninstall            # Remove everything
python install_forge.py --update-project PATH  # Update an existing project
```

## Requirements

- Python 3.11+
- Claude Code CLI

## How It Works After Installation

1. Open Claude Code in **any directory**
2. `/forge-create my-app` — creates project with spec wizard, copies files from `~/.forge/` (including commands and agents into the project's `.claude/`)
3. `cd my-app` — project now has `mcp_server/`, `api/`, `.mcp.json`, templates, skills, commands, agents
4. `.mcp.json` points to `~/.forge/venv/python` so MCP deps are always available
5. `/forge-init` — reads spec, populates feature database (command is project-local)
6. `/forge-build` — implements features one by one, or `/forge-parallel` for parallel builds

## Design Decisions

**MCP server is copied per-project.** Each project needs its own `features.db` with its own `PROJECT_DIR`. Copying makes projects self-contained and portable.

**Venv is global.** A single `~/.forge/venv/` avoids installing mcp/sqlalchemy/pydantic per-project. Each project's `.mcp.json` references this shared venv's python.

**Only `forge-create.md` is global.** All other commands are project-local — copied into each project's `.claude/commands/` during `/forge-create`. This avoids polluting the global namespace and makes projects self-contained.

**Only `forge-create.md` is adapted.** All other commands work through MCP tools that are already in the project after creation. One file modified = minimal surface area for bugs.

**Forward-slash paths everywhere.** Claude Code uses bash on Windows. Python's `Path.as_posix()` produces forward slashes that work on both platforms.

## Re-runs Are Safe

- Core files are replaced cleanly (old dirs removed before copy)
- Venv is skipped if a marker file matches the current requirements hash + Python version
- Commands are overwritten in place

## Updating Existing Projects

When CCForge is updated (bug fixes, new tools, improved commands), existing projects don't get the changes automatically — they were scaffolded at creation time. Use `--update-project` to bring them up to date:

```bash
python install_forge.py --update-project /path/to/my-app
```

This replaces the following files from `~/.forge/` into the project:

- `mcp_server/` — full directory replacement
- `api/` — full directory replacement
- `.claude/commands/` — the 11 project-local command files
- `.claude/agents/` — coder.md, code-review.md, deep-dive.md
- `.claude/skills/playwright-cli/` — full directory replacement

**Not touched:** `.autoforge/features.db`, `.autoforge/prompts/`, `CLAUDE.md`, `.mcp.json`. Your feature database, specs, prompts, and project-specific config are preserved.

The command writes `.autoforge/version.json` to track which version the project is on. If the project is already at the current version, it exits early.

**Workflow:** Run the global installer first to update `~/.forge/`, then update each project:

```bash
python install_forge.py                          # Update global install
python install_forge.py --update-project my-app  # Update project
```

## Uninstall

```bash
python install_forge.py --uninstall
```

Removes `~/.forge/` and `forge-create.md` from `~/.claude/commands/`. Also cleans up any legacy global commands from older installs. Does not touch any project-local files.
