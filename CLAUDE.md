# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A git commit logging system that captures every local `git commit` into weekly JSONL files, then feeds the data to an OpenAI-compatible LLM to generate Chinese-language weekly work reports. Includes a macOS launchd-based scheduler.

## Architecture

Three independent data pipelines that share a common data format:

```
git commit ──► hooks/post-commit ──► data/commits/YYYY-WXX.jsonl
                                        │
git repos ─── scripts/collect-commits ──┘         (batch/historical)
                                        │
                     scripts/generate-weekly-report ──► reports/*.md
```

- **Hook** (`hooks/post-commit`): Bash, runs via `git config --global core.hooksPath`. Captures commit metadata with `git log -1 --format=...`, writes one JSON line per commit. Fallback to Python if `jq` is unavailable. Deduplicates by hash via `grep` before writing.
- **Collector** (`scripts/collect-commits`): Python, no external deps. Walks directory trees finding `.git` dirs (regular repos) AND `.git` files (submodules). Runs `git log --author=<email>` for filtering at the git level. Uses a state file (`data/collect-state.json`) to track last-sync per repo.
- **Reporter** (`scripts/generate-weekly-report`): Python, no required deps. Reads weekly JSONL, groups by repo, sends to LLM via OpenAI-compatible `/v1/chat/completions`. Tries `openai` SDK first, falls back to `urllib`.
- **Scheduler** (`scripts/schedule`): Python, manages macOS `~/Library/LaunchAgents/com.git-report.*.plist` files via `launchctl bootstrap`/`bootout`.

## Data format

All scripts read/write the same JSONL format in `data/commits/YYYY-WXX.jsonl` (ISO week). Each line: `{"hash", "author", "email", "timestamp", "message", "repo", "repo_path", "branch", "hostname"}`. Deduplication key: `hash`.

## Common commands

```bash
./scripts/setup                                    # one-time: enable global hook
python3 scripts/collect-commits --scan ~/work      # collect current user, this week
python3 scripts/collect-commits --scan ~/work --all-authors --dry-run
python3 scripts/generate-weekly-report             # current user, current week
python3 scripts/generate-weekly-report --dry-run
./scripts/schedule add --name weekly --schedule "Fri 17:00" \
  --command "python3 $PWD/scripts/generate-weekly-report"
```

## Key defaults (both collector and reporter)

- **Time**: current week (Monday–today). Override with `--week <N>` or `--since YYYY-MM-DD`.
- **Author**: current git user (`git config --global user.email`). Override with `--all-authors` or `--author`.
- The reporter outputs Simplified Chinese.

## Template system

`templates/weekly-report.md` uses `{{PLACEHOLDER}}` syntax. Available variables: `{{WEEK}}`, `{{DATE_RANGE}}`, `{{COMMITS}}`, `{{COMMIT_COUNT}}`, `{{REPO_COUNT}}`, `{{GENERATED_AT}}`. The AI fills all sections but preserves the template's markdown structure.

## Python compatibility

Targets Python 3.8+. Type hints use `Optional[X]` from `typing`, not `X | None` (requires 3.10+).
