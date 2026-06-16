# git-report

> 自动收集 Git 提交记录 → AI 生成周报 → 定时自动执行

## 功能概览

| 组件 | 说明 |
|------|------|
| **全局 Git Hook** | 每次 `git commit` 后自动将提交信息记录到本项目 |
| **目录扫描采集器** | 扫描指定目录下所有 Git 仓库，批量拉取提交记录 |
| **AI 周报生成器** | 读取提交日志 + 周报模板 → 投喂给 AI（OpenAI 兼容 API）→ 生成真实周报 |
| **任务调度器** | 管理 macOS launchd 定时任务，如每周五下午 5 点自动生成周报 |

## 项目结构

```
git-report/
├── hooks/
│   └── post-commit              # 全局 Git 钩子脚本
├── data/
│   ├── commits/                 # 提交日志 (YYYY-WXX.jsonl)
│   └── logs/                    # 定时任务日志
├── reports/                     # 生成的周报输出
├── templates/
│   └── weekly-report.md         # 周报模板
├── scripts/
│   ├── setup                    # 一次性安装脚本
│   ├── collect-commits          # 目录扫描采集器
│   ├── generate-weekly-report   # AI 周报生成器
│   └── schedule                 # 任务调度器
├── requirements.txt
└── README.md
```

## 快速开始

### 1. 安装全局 Git Hook

```bash
cd ~/development/lifecycle/git-report
./scripts/setup
```

执行后，本机上所有 Git 仓库的提交都会被记录到 `data/commits/` 目录下。

### 2. 从现有仓库批量采集提交（补充方式）

如果你有大量旧仓库需要一次性导入历史提交，或者想定期从特定目录同步（作为 Hook 的补充）：

```bash
# 扫描 ~/work（默认：本周一至今、当前用户、如有状态文件则增量）
python3 scripts/collect-commits --scan ~/work

# 扫描多个目录
python3 scripts/collect-commits --scan ~/work --scan ~/projects

# 采集所有作者的提交（关闭默认过滤）
python3 scripts/collect-commits --scan ~/work --all-authors

# 只采集指定作者的提交
python3 scripts/collect-commits --scan ~/work --author "someone@example.com"

# 指定日期范围
python3 scripts/collect-commits --scan ~/work --since 2026-01-01
python3 scripts/collect-commits --scan ~/work --since 2026-01-01 --until 2026-06-01

# 预览（不实际写入）
python3 scripts/collect-commits --scan ~/work --dry-run

# 调整扫描深度（默认 10 层，基本覆盖所有嵌套目录）
python3 scripts/collect-commits --scan ~/ --max-depth 20

# 重置同步状态，重新采集
python3 scripts/collect-commits --scan ~/work --reset-state
```

**与 Hook 的关系：** 两种方式互不冲突——采集器通过 commit hash 去重，Hook 已记录的提交不会重复写入。可以同时使用：
- Hook 负责实时采集（每次 commit 自动触发）
- 采集器负责批量导入和定期巡检（如每天凌晨定时跑一次，确保没有遗漏）

### 3. 生成周报

```bash
# 设置 API Key（二选一）
export OPENAI_API_KEY="your-api-key"
# 或传入参数: --api-key your-key

# 使用自定义 API 端点（兼容 OpenAI、DeepSeek、vLLM、Ollama 等）
export OPENAI_BASE_URL="https://api.deepseek.com/v1"
# 或传入参数: --api-base https://your-endpoint/v1

# 生成本周周报（默认：本周一～今天、当前 git 用户）
python3 scripts/generate-weekly-report

# 包含所有作者的提交
python3 scripts/generate-weekly-report --all-authors

# 只包含指定作者的提交
python3 scripts/generate-weekly-report --author "someone@example.com"

# 查看将要发送给 AI 的 prompt（不调用 API）
python3 scripts/generate-weekly-report --dry-run

# 指定周数
python3 scripts/generate-weekly-report --week 24

# 使用自定义模板
python3 scripts/generate-weekly-report --template my-template.md

# 指定输出路径
python3 scripts/generate-weekly-report --output reports/custom-name.md
```

### 4. 设置定时自动生成（每周五下午 5 点）

```bash
# 添加定时任务（每周五下午 5 点自动生成周报）
./scripts/schedule add \
  --name weekly-report \
  --schedule "Fri 17:00" \
  --command "python3 $PWD/scripts/generate-weekly-report" \
  --api-key "your-api-key"

# 查看所有定时任务
./scripts/schedule list

# 查看任务详情和最近日志
./scripts/schedule show --name weekly-report

# 删除定时任务
./scripts/schedule remove --name weekly-report
```

## 提交日志格式

每条提交记录存储为一行 JSON（JSONL 格式）：

```json
{
  "hash": "abc123def456...",
  "author": "Zhang San",
  "email": "zhangsan@example.com",
  "timestamp": "2026-06-15T14:30:00+08:00",
  "message": "feat: add user authentication module",
  "repo": "my-project",
  "repo_path": "/Users/dabo/work/my-project",
  "branch": "feature/auth",
  "hostname": "MacBook-Pro.local"
}
```

按周存储（ISO 周号）：`data/commits/2026-W25.jsonl`

## Schedule 表达式参考

| 表达式 | 含义 |
|--------|------|
| `Mon 09:00` | 每周一早上 9 点 |
| `Fri 17:00` | 每周五下午 5 点 |
| `Mon,Wed,Fri 14:00` | 每周一、三、五下午 2 点 |
| `weekday 08:00` | 每个工作日早上 8 点 |
| `daily 08:00` | 每天早上 8 点 |
| `Mon-Fri 18:00` | 周一至周五下午 6 点 |

## 自定义周报模板

模板使用 `{{PLACEHOLDER}}` 占位符，可用变量：

| 占位符 | 说明 |
|--------|------|
| `{{WEEK}}` | ISO 周号，如 `W24 (2026)` |
| `{{DATE_RANGE}}` | 日期范围，如 `2026-06-08 → 2026-06-14` |
| `{{COMMITS}}` | 按项目分组的提交列表 |
| `{{COMMIT_COUNT}}` | 提交总数 |
| `{{REPO_COUNT}}` | 涉及项目数 |
| `{{GENERATED_AT}}` | 生成时间 |

## 卸载

```bash
# 恢复 Git 默认 hooks
git config --global --unset core.hooksPath

# 删除所有定时任务
./scripts/schedule list | tail -n +3 | awk '{print $1}' | xargs -I{} ./scripts/schedule remove --name {}
```

## 依赖

- **Git** — 提交记录采集
- **Python 3.8+** — 脚本运行（仅标准库，无需 pip 安装额外依赖）
- **jq**（可选）— hook 脚本中更可靠的 JSON 构造，缺失时会回退到 Python
- **OpenAI 兼容 API** — 用于 AI 生成周报（支持 OpenAI、DeepSeek、vLLM、Ollama、LiteLLM 等）
- **macOS** — 定时任务功能依赖 launchd（Linux 可用 cron 代替）
