# git-weekly-automation

> One command to install. Every git commit is logged automatically. AI writes your weekly report before you leave on Friday.

*English Documentation · [中文文档](README.zh.md)*

## Quick Start

```bash
# 1. Install
npm install -g git-weekly-automation

# 2. Initialize
git-weekly setup

# 3. Set your API key
export OPENAI_API_KEY="sk-your-key-here"
# For third-party APIs like DeepSeek, also set the base URL:
# export OPENAI_BASE_URL="https://api.deepseek.com/v1"

# 4. Generate your first report
git-weekly report
```

After `git-weekly setup`, every `git commit` on this machine is automatically logged.

---

## Commands

| Command | Description |
|------------------------------------|-------------|
| `git-weekly setup` | Install global git hook |
| `git-weekly report` | Generate weekly report |
| `git-weekly collect --scan ~/work` | Bulk-collect commit history from repos |
| `git-weekly schedule add` | Add a scheduled task (interactive) |
| `git-weekly schedule list` | List all scheduled tasks |
| `git-weekly cleanup` | Clean up orphaned installations |

## Command Reference

### git-weekly setup

Installs a global git hook that records every `git commit` to `data/commits/`.

```bash
git-weekly setup                 # Install
git-weekly setup uninstall       # Uninstall (cleans up everything)
git-weekly setup uninstall --yes # Non-interactive (for CI/scripts)
```

### git-weekly report

Reads commit logs and generates a weekly report via AI.

```bash
# Generate a report for the current week
git-weekly report

# Report in Chinese (or set "lang": "zh" in config.json)
git-weekly report --lang zh

# Specify an ISO week number
git-weekly report --week 25

# Include all authors
git-weekly report --all-authors

# Preview the AI prompt without making an API call
git-weekly report --dry-run

# Custom output path or API endpoint
git-weekly report -o my-report.md
git-weekly report --api-base https://api.deepseek.com/v1 --model deepseek-chat
```

### git-weekly collect

Scans directories for git repos (including submodules) and bulk-imports commit history. Useful for backfilling or syncing from multiple machines.

```bash
git-weekly collect --scan ~/work                    # Single directory
git-weekly collect --scan ~/work --scan ~/projects  # Multiple directories
git-weekly collect --scan ~/work --since 2026-01-01 # With date filter
git-weekly collect --scan ~/work --dry-run           # Preview only
```

### git-weekly schedule

Manages macOS launchd scheduled tasks.

```bash
git-weekly schedule add                           # Interactive add (recommended)
git-weekly schedule list                          # List all tasks
git-weekly schedule show -n weekly-report         # Details + recent logs
git-weekly schedule remove -n weekly-report       # Remove a task
git-weekly schedule clear                         # Remove all tasks
```

**Schedule expressions:**

| Expression | Meaning |
|------------|---------|
| `Fri 18:00` | Every Friday at 6 PM |
| `Mon 09:00` | Every Monday at 9 AM |
| `Mon,Wed,Fri 14:00` | Mon, Wed, Fri at 2 PM |
| `weekday 08:00` | Mon–Fri at 8 AM |
| `daily 08:00` | Every day at 8 AM |

### git-weekly cleanup

If the project directory is deleted without running `uninstall`, orphaned entries remain in the registry. This command cleans them up:

```bash
git-weekly cleanup
```

Automatically: unloads residual launchd tasks → deletes plist files → restores git hooksPath → removes registry entries.

---

## Data Files

```
data/
├── commits/
│   ├── 2026-W25.jsonl      # Weekly commit logs (JSONL)
│   └── ...
└── logs/                   # Scheduled task run logs

reports/                    # Generated reports (.md)
~/.git-weekly-automation/
└── registry.json           # Central registry (tracks installations)
```

Old data is automatically purged per the [cleanup configuration](#configuration) — by default: commit logs > 52 weeks, reports > 26 weeks, and logs > 90 days are removed when a report is generated.

Commit record format (one JSON object per line):

```json
{"hash":"abc123...","author":"Zhang San","email":"zhangsan@example.com","timestamp":"2026-06-15T14:30:00+08:00","message":"feat: add auth module","repo":"my-project","repo_path":"/path/to/repo","branch":"main","hostname":"MacBook.local"}
```

---

## Configuration

All settings are resolved with this priority: **CLI flag > environment variable > config.json > built-in default**.

### config.json

Copy the example and edit:

```bash
cp config.example.json config.json
```

Full schema:

```json
{
  "api_key": "sk-your-api-key-here",
  "api_base": "https://api.openai.com/v1",
  "model": "gpt-4o-mini",
  "lang": "en",
  "cleanup": {
    "commits_weeks": 52,
    "reports_weeks": 26,
    "logs_days": 90,
    "on_report": true
  }
}
```

| Key | Default | Description |
|-----|---------|-------------|
| `api_key` | — | API key (also settable via `OPENAI_API_KEY` env var or `--api-key` flag) |
| `api_base` | `https://api.openai.com/v1` | API endpoint (also `OPENAI_BASE_URL` env var or `--api-base` flag) |
| `model` | `gpt-4o-mini` | Model name (also `--model` flag) |
| `lang` | `en` | Report language: `en` (English) or `zh` (Simplified Chinese). Also `--lang` flag |
| `cleanup.commits_weeks` | `52` | Auto-delete commit log files older than N weeks. Set `0` to disable |
| `cleanup.reports_weeks` | `26` | Auto-delete report files older than N weeks. Set `0` to disable |
| `cleanup.logs_days` | `90` | Auto-delete log files older than N days. Set `0` to disable |
| `cleanup.on_report` | `true` | Run cleanup automatically after each report generation |

### Environment variables

```bash
export OPENAI_API_KEY="sk-..."
export OPENAI_BASE_URL="https://api.deepseek.com/v1"
```

### CLI flags

```bash
git-weekly report --api-base https://api.deepseek.com/v1 --model deepseek-chat --lang zh
```

### No configuration

With no API key set, the report command falls back to **dry-run mode** — it prints the AI prompt without making an API call.

Works with any OpenAI-compatible API: OpenAI, DeepSeek, vLLM, Ollama, LiteLLM, etc.

---

## Custom Templates

The template file `templates/weekly-report.md` uses `{{PLACEHOLDER}}` syntax:

| Placeholder | Replaced with |
|-------------|---------------|
| `{{WEEK}}` | ISO week number, e.g. `W25 (2026)` |
| `{{DATE_RANGE}}` | Date range for the week |
| `{{COMMITS}}` | Commits grouped by project |
| `{{COMMIT_COUNT}}` | Total commit count |
| `{{REPO_COUNT}}` | Number of repos |
| `{{GENERATED_AT}}` | Generation timestamp |

```bash
git-weekly report --template my-custom-template.md
```

---

## Uninstall

```bash
# npm users
npm uninstall -g git-weekly-automation

# Manual install
git-weekly setup uninstall        # Interactive — confirms before removing data
git-weekly setup uninstall --yes  # Non-interactive for CI
```

Removes: git hook, all scheduled tasks, and registry entries. Data and reports are removed upon confirmation.

---

## Dependencies

- **Git** — commit collection
- **Python 3.8+** — scripts (stdlib only, no pip dependencies)
- **Node.js / npm** — install tool (skip if cloning manually)
- **macOS** — scheduling uses launchd
- **jq** (optional) — JSON construction in the hook; falls back to Python automatically
- **OpenAI-compatible API** — report generation
