# CLAUDE.md

See [README.md](README.md) for full project documentation.

CCForge is a Claude Code slash command system for autonomous feature-by-feature application development, built on the AutoForge architecture.

## Key References

- **MCP Server:** `mcp_server/feature_mcp.py` (22 tools)
- **Database:** `api/database.py` (SQLAlchemy models, migrations)
- **Dependency Resolver:** `api/dependency_resolver.py` (topological sort, cycle detection)
- **Commands:** `.claude/commands/forge-*.md` — `forge-create.md` is global (`~/.claude/commands/`), rest are project-local (copied per-project by `/forge-create`)
- **Templates:** `.claude/templates/`
- **Agents:** `.claude/agents/`

## Code Quality

```bash
ruff check .                                    # Lint
mypy .                                          # Type check
python -m pytest test_dependency_resolver.py    # Dependency resolver tests
```

Configuration in `pyproject.toml`:
- **ruff**: Line length 120, Python 3.11 target, select E/F/I/W rules
- **mypy**: Python 3.11, ignore missing imports, warn on return any

## Key Patterns

- All feature operations go through the MCP server with atomic SQL (`BEGIN IMMEDIATE`)
- `UPDATE ... WHERE` guards prevent double-claim races
- Database location: `{project_dir}/.autoforge/features.db`
- Build loop is designed for multi-session execution (claim, implement, verify, commit)
- `depends_on_indices` in bulk create resolves to actual IDs after insertion
- Max 20 dependencies per feature, max depth 50
