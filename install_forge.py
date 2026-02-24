#!/usr/bin/env python3
"""Forge Global Installer — Install forge commands globally for Claude Code.

Usage:
    python install_forge.py             # Install or update (idempotent)
    python install_forge.py --uninstall # Remove ~/.forge/ and commands from ~/.claude/commands/
    python install_forge.py --check     # Verify installation health
"""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

FORGE_HOME = Path.home() / ".forge"
CLAUDE_COMMANDS = Path.home() / ".claude" / "commands"
SOURCE_DIR = Path(__file__).resolve().parent  # The ccforge/ directory containing this script

PROJECT_LOCAL_COMMANDS = [
    "forge-init.md", "forge-build.md", "forge-parallel.md", "forge-status.md", "forge-test.md",
    "forge-fix.md", "forge-expand.md", "forge-regression.md", "checkpoint.md", "check-code.md", "review-pr.md",
]
GLOBAL_COMMAND = "forge-create.md"


def check_python_version() -> None:
    if sys.version_info < (3, 11):
        print(f"Error: Python 3.11+ required (found {sys.version_info.major}.{sys.version_info.minor})")
        sys.exit(1)


def venv_python() -> Path:
    venv = FORGE_HOME / "venv"
    return venv / "Scripts" / "python.exe" if sys.platform == "win32" else venv / "bin" / "python"


def venv_pip() -> Path:
    venv = FORGE_HOME / "venv"
    return venv / "Scripts" / "pip.exe" if sys.platform == "win32" else venv / "bin" / "pip"


def requirements_hash() -> str:
    req = FORGE_HOME / "mcp_server" / "requirements.txt"
    return hashlib.sha256(req.read_bytes()).hexdigest()[:16]


# ── Step 1: Copy core files ──────────────────────────────────────────────────


def copy_core_files() -> None:
    copies = {
        "mcp_server": SOURCE_DIR / "mcp_server",
        "api": SOURCE_DIR / "api",
        "templates": SOURCE_DIR / ".claude" / "templates",
        "skills": SOURCE_DIR / ".claude" / "skills",
        "agents": SOURCE_DIR / ".claude" / "agents",
    }
    for name, src in copies.items():
        dst = FORGE_HOME / name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))
        print(f"  Copied {name}/")

    # Copy project-local commands (individual files, excluding forge-create.md)
    commands_dst = FORGE_HOME / "commands"
    commands_dst.mkdir(parents=True, exist_ok=True)
    commands_src = SOURCE_DIR / ".claude" / "commands"
    for cmd in PROJECT_LOCAL_COMMANDS:
        src = commands_src / cmd
        if src.exists():
            shutil.copy2(src, commands_dst / cmd)
    print(f"  Copied commands/ ({len(PROJECT_LOCAL_COMMANDS)} project-local commands)")


# ── Step 2: Create venv ──────────────────────────────────────────────────────


def create_venv() -> None:
    venv_dir = FORGE_HOME / "venv"
    marker = venv_dir / ".forge_marker"
    expected = f"{requirements_hash()}|{sys.version}"

    if marker.exists() and marker.read_text().strip() == expected:
        print("  Venv up to date (skipped)")
        return

    if venv_dir.exists():
        shutil.rmtree(venv_dir)

    print("  Creating venv...")
    subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)

    print("  Installing dependencies...")
    req = FORGE_HOME / "mcp_server" / "requirements.txt"
    result = subprocess.run(
        [str(venv_pip()), "install", "-r", str(req)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  pip install failed:\n{result.stderr}")
        sys.exit(1)

    marker.write_text(expected)
    print("  Venv ready")


# ── Step 3: Copy commands ────────────────────────────────────────────────────


def adapt_forge_create() -> str:
    """Read forge-create.md and replace relative paths with absolute ~/.forge/ paths."""
    src = SOURCE_DIR / ".claude" / "commands" / GLOBAL_COMMAND
    content = src.read_text(encoding="utf-8")

    home = FORGE_HOME.as_posix()
    python = venv_python().as_posix()
    pip = venv_pip().as_posix()

    replacements = [
        # Template references
        (".claude/templates/initializer_prompt.template.md",
         f"{home}/templates/initializer_prompt.template.md"),
        (".claude/templates/coding_prompt.template.md",
         f"{home}/templates/coding_prompt.template.md"),
        (".claude/templates/testing_prompt.template.md",
         f"{home}/templates/testing_prompt.template.md"),
        (".claude/templates/project-claude.template.md",
         f"{home}/templates/project-claude.template.md"),
        # Source directory copy instructions
        ("Copy `mcp_server/` directory",
         f"Copy `{home}/mcp_server/` directory"),
        ("Copy `api/` directory",
         f"Copy `{home}/api/` directory"),
        # Playwright skill copy
        ("cp -r .claude/skills/playwright-cli",
         f"cp -r {home}/skills/playwright-cli"),
        # Project-local commands copy
        ("cp .claude/commands/$cmd",
         f"cp {home}/commands/$cmd"),
        # Project-local agents copy
        ("cp .claude/agents/$agent",
         f"cp {home}/agents/$agent"),
        # pip install (replace full line — deps pre-installed in global venv)
        ("cd $ARGUMENTS && pip install -r mcp_server/requirements.txt",
         f"{pip} install -r $ARGUMENTS/mcp_server/requirements.txt"),
        # MCP server python command in .mcp.json template
        ('"command": "python"',
         f'"command": "{python}"'),
    ]

    for old, new in replacements:
        content = content.replace(old, new)

    return content


def copy_commands() -> None:
    CLAUDE_COMMANDS.mkdir(parents=True, exist_ok=True)

    # Only install forge-create.md globally (adapted with absolute paths)
    adapted = adapt_forge_create()
    (CLAUDE_COMMANDS / GLOBAL_COMMAND).write_text(adapted, encoding="utf-8")
    print(f"  Adapted {GLOBAL_COMMAND}")

    # Clean up legacy global commands from previous installations
    removed = 0
    for cmd in PROJECT_LOCAL_COMMANDS:
        p = CLAUDE_COMMANDS / cmd
        if p.exists():
            p.unlink()
            removed += 1
    if removed:
        print(f"  Removed {removed} legacy global command(s)")


# ── Step 4: Metadata ─────────────────────────────────────────────────────────


def write_version() -> None:
    info = {
        "installed_at": datetime.now(timezone.utc).isoformat(),
        "source_path": SOURCE_DIR.as_posix(),
        "python_version": sys.version,
        "platform": sys.platform,
    }
    (FORGE_HOME / "version.json").write_text(json.dumps(info, indent=2))
    print("  Wrote version.json")


# ── Step 5: Verify ───────────────────────────────────────────────────────────


def verify() -> list[str]:
    errors: list[str] = []

    # Check directories
    for name in ["mcp_server", "api", "templates", "skills", "agents", "commands"]:
        if not (FORGE_HOME / name).is_dir():
            errors.append(f"Missing: ~/.forge/{name}/")

    # Check all project-local commands exist in ~/.forge/commands/
    for cmd in PROJECT_LOCAL_COMMANDS:
        if not (FORGE_HOME / "commands" / cmd).exists():
            errors.append(f"Missing project-local command: ~/.forge/commands/{cmd}")

    # Check venv python and imports
    python = venv_python()
    if not python.exists():
        errors.append(f"Missing venv python: {python}")
    else:
        r = subprocess.run(
            [str(python), "-c", "import mcp; import sqlalchemy; import pydantic"],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            errors.append(f"Import check failed: {r.stderr.strip()}")

    # Check forge-create.md has absolute paths, no leftover relative paths
    fc = CLAUDE_COMMANDS / GLOBAL_COMMAND
    if fc.exists():
        text = fc.read_text(encoding="utf-8")
        if FORGE_HOME.as_posix() not in text:
            errors.append("forge-create.md missing absolute paths")
        if ".claude/templates/" in text:
            errors.append("forge-create.md has leftover relative template paths")
        if ".claude/commands/$cmd" in text:
            errors.append("forge-create.md has leftover relative command paths")
        if ".claude/agents/$agent" in text:
            errors.append("forge-create.md has leftover relative agent paths")
    else:
        errors.append("Missing forge-create.md in ~/.claude/commands/")

    # Warn if legacy global commands still present
    for cmd in PROJECT_LOCAL_COMMANDS:
        if (CLAUDE_COMMANDS / cmd).exists():
            errors.append(f"Legacy global command still present: ~/.claude/commands/{cmd}")

    return errors


# ── CLI actions ───────────────────────────────────────────────────────────────


def install() -> None:
    print(f"Installing Forge to {FORGE_HOME}\n")
    FORGE_HOME.mkdir(parents=True, exist_ok=True)

    print("[1/5] Copying core files...")
    copy_core_files()

    print("\n[2/5] Setting up Python venv...")
    create_venv()

    print("\n[3/5] Installing global command (forge-create)...")
    copy_commands()

    print("\n[4/5] Writing metadata...")
    write_version()

    print("\n[5/5] Verifying...")
    errors = verify()

    if errors:
        print("\nCompleted with errors:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)

    print("\nInstallation complete. All checks passed.")
    print(f"\n  Forge home:      {FORGE_HOME}")
    print(f"  Global command:  {CLAUDE_COMMANDS / GLOBAL_COMMAND}")
    print("\nOpen Claude Code anywhere and run /forge-create to get started.")


def uninstall() -> None:
    if FORGE_HOME.exists():
        shutil.rmtree(FORGE_HOME)
        print(f"Removed {FORGE_HOME}")
    else:
        print(f"{FORGE_HOME} not found")

    # Remove forge-create.md from global commands
    fc = CLAUDE_COMMANDS / GLOBAL_COMMAND
    if fc.exists():
        fc.unlink()
        print(f"Removed {GLOBAL_COMMAND} from {CLAUDE_COMMANDS}")

    # Also clean up any legacy global commands from older installs
    removed = 0
    for cmd in PROJECT_LOCAL_COMMANDS:
        p = CLAUDE_COMMANDS / cmd
        if p.exists():
            p.unlink()
            removed += 1
    if removed:
        print(f"Removed {removed} legacy global command(s) from {CLAUDE_COMMANDS}")

    print("\nUninstall complete.")


def check() -> None:
    print("Checking Forge installation...\n")
    if not FORGE_HOME.exists():
        print("Not installed. Run: python install_forge.py")
        sys.exit(1)

    errors = verify()
    if errors:
        print("Issues found:")
        for e in errors:
            print(f"  - {e}")
        print("\nRe-run: python install_forge.py")
        sys.exit(1)

    print("Installation is healthy.")
    vf = FORGE_HOME / "version.json"
    if vf.exists():
        info = json.loads(vf.read_text())
        print(f"\n  Installed: {info.get('installed_at', '?')}")
        print(f"  Source:    {info.get('source_path', '?')}")
        print(f"  Python:    {info.get('python_version', '?').split()[0]}")


# ── Entry point ───────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Forge Global Installer")
    parser.add_argument("--uninstall", action="store_true", help="Remove installation")
    parser.add_argument("--check", action="store_true", help="Verify installation health")
    args = parser.parse_args()

    check_python_version()

    if args.uninstall:
        uninstall()
    elif args.check:
        check()
    else:
        install()


if __name__ == "__main__":
    main()
