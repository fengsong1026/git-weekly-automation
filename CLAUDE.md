# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A git commit logging system that captures every local `git commit` into weekly JSONL files, then feeds the data to an OpenAI-compatible LLM to generate weekly work reports (English by default, Chinese via `--lang zh`). Includes a macOS launchd-based scheduler and a central registry for lifecycle management.

## Architecture

```
git commit ──► hooks/post-commit ──► data/commits/YYYY-WXX.jsonl
                                        │
git repos ─── scripts/collect-commits ──┘         (batch/historical)
                                        │
                     scripts/generate-weekly-report ──► reports/*.md
```

- **Hook** (`hooks/post-commit`): Bash, runs via `git config --global core.hooksPath`. Captures commit metadata, writes one JSON line per commit. Fallback to Python if `jq` is unavailable. Deduplicates by hash via Python JSON parsing.
- **Collector** (`scripts/collect-commits`): Python, no external deps. Walks directory trees finding `.git` dirs (regular repos) AND `.git` files (submodules). Runs `git log` with a single batch call per repo (null-delimited output). Deduplicates against all existing hashes.
- **Reporter** (`scripts/generate-weekly-report`): Python, no required deps. Reads weekly JSONL, groups by repo, sends to LLM via OpenAI-compatible `/v1/chat/completions`. Tries `openai` SDK first, falls back to `urllib` with retry.
- **Scheduler** (`scripts/schedule`): Python, manages macOS `~/Library/LaunchAgents/com.git-weekly-automation.*.plist` files via `launchctl bootstrap`/`bootout`. Tasks self-destruct if the project directory is deleted.
- **Registry** (`scripts/registry.py`): Central registry at `~/.git-weekly-automation/registry.json`. Tracks all installations, hooks, and scheduled tasks. Uses `fcntl.flock` for concurrency safety. Survives project deletion.
- **CLI** (`scripts/cli`): Unified entry point (`git-weekly`). Dispatches subcommands to sibling scripts, detecting the correct interpreter from each script's shebang. Does NOT define per-command flags — all args pass through to inner scripts.
- **Common** (`scripts/common.py`): Shared utilities: config loading, git email detection, ISO week validation, data retention purge.

## Data format

All scripts read/write the same JSONL format in `data/commits/YYYY-WXX.jsonl` (ISO week). Each line: `{"hash", "author", "email", "timestamp", "message", "repo", "repo_path", "branch", "hostname"}`. Deduplication key: `hash`.

## Common commands

```bash
./scripts/setup                                    # one-time: enable global hook
python3 scripts/collect-commits --scan ~/work      # collect current user, this week
python3 scripts/collect-commits --scan ~/work --all-authors --dry-run
python3 scripts/generate-weekly-report             # current user, current week (English)
python3 scripts/generate-weekly-report --lang zh   # Chinese report
python3 scripts/generate-weekly-report --dry-run
./scripts/schedule add --name weekly --schedule "Fri 17:00" \
  --command "python3 $PWD/scripts/generate-weekly-report"
python3 tests/run_all.py                           # run all tests
```

## Key defaults

- **Language**: English by default. Override with `--lang zh` or `config.json` `"lang": "zh"`.
- **Time**: current week (Monday–today). Override with `--week <N>` or `--since YYYY-MM-DD`.
- **Author**: current git user (`git config --global user.email`). Override with `--all-authors` or `--author`.

## Template system

`templates/weekly-report.md` uses `{{PLACEHOLDER}}` syntax. Available variables: `{{WEEK}}`, `{{DATE_RANGE}}`, `{{COMMITS}}`, `{{COMMIT_COUNT}}`, `{{REPO_COUNT}}`, `{{GENERATED_AT}}`. The AI fills all sections but preserves the template's markdown structure.

Chinese template available at `templates/weekly-report.zh.md`.

## Configuration

`config.example.json` documents all keys. Copy to `config.json` to use. Priority: **CLI flag > env var > config.json > built-in default**.

## Python compatibility

Targets Python 3.8+. Type hints use `Optional[X]` from `typing`, not `X | None` (requires 3.10+).

## README synchronization

**IMPORTANT**: Whenever `README.md` is updated, `README.zh.md` MUST be updated with the equivalent Chinese translation in the same commit. The two files share the same structure — changes to sections, commands, tables, or configuration docs must be mirrored.

## Tests

87 tests in `tests/`, zero dependencies (stdlib `unittest`). Run with `python3 tests/run_all.py`. Files without `.py` extensions in `scripts/` must be loaded via `importlib.machinery.SourceFileLoader` in tests.
