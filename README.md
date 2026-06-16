# git-report

> 自动收集 Git 提交记录 → AI 生成中文周报 → 定时自动执行

## 功能概览

| 组件 | 说明 |
|------|------|
| **全局 Git Hook** | 每次 `git commit` 后自动将提交信息记录到本项目 |
| **目录扫描采集器** | 扫描指定目录下所有 Git 仓库（含 submodule），批量拉取提交记录 |
| **AI 周报生成器** | 读取提交日志 + 周报模板 → 投喂给 AI（OpenAI 兼容 API）→ 生成中文周报 |
| **任务调度器** | 管理 macOS launchd 定时任务，如每周五下午 5 点自动生成周报 |

## 项目结构

```
git-report/
├── hooks/
│   └── post-commit              # 全局 Git 钩子脚本 (bash)
├── data/
│   ├── commits/                 # 提交日志 (YYYY-WXX.jsonl，ISO 周号)
│   ├── logs/                    # 定时任务日志
│   └── collect-state.json       # 采集器同步状态
├── reports/                     # 生成的周报输出
├── templates/
│   └── weekly-report.md         # 周报模板（中文，支持 {{占位符}}）
├── scripts/
│   ├── setup                    # 一次性安装脚本
│   ├── collect-commits          # 目录扫描采集器 (Python)
│   ├── generate-weekly-report   # AI 周报生成器 (Python)
│   └── schedule                 # 任务调度器 (Python)
├── requirements.txt
└── README.md
```

## 快速开始

### 1. 安装全局 Git Hook

```bash
cd ~/development/lifecycle/git-report
./scripts/setup
```

执行后，本机上所有 Git 仓库的每次提交都会自动记录到 `data/commits/YYYY-WXX.jsonl`。

### 2. 从现有仓库批量采集提交

Hook 只捕获安装之后的提交。如需导入历史记录，或定期从特定目录同步：

```bash
# 默认：当前 git 用户、本周一至今
python3 scripts/collect-commits --scan ~/work

# 扫描多个目录
python3 scripts/collect-commits --scan ~/work --scan ~/projects

# 采集所有作者（关闭默认过滤）
python3 scripts/collect-commits --scan ~/work --all-authors

# 指定作者或日期范围
python3 scripts/collect-commits --scan ~/work --author "someone@example.com"
python3 scripts/collect-commits --scan ~/work --since 2026-01-01

# 预览（不写入）
python3 scripts/collect-commits --scan ~/work --dry-run

# 调整扫描深度（默认 10 层）
python3 scripts/collect-commits --scan ~/work --max-depth 20

# 重置同步状态，重新采集
python3 scripts/collect-commits --scan ~/work --reset-state
```

**采集器特性：** 支持 submodule（`.git` 文件）、commit hash 去重、增量同步（状态文件）。

### 3. 生成周报

```bash
# 方式一：配置文件（推荐，gitignored）
cp config.example.json config.json
# 编辑 config.json

# 方式二：环境变量
export OPENAI_API_KEY="your-api-key"
export OPENAI_BASE_URL="https://api.deepseek.com/v1"

# 方式三：命令行参数（仅 api-base）
python3 scripts/generate-weekly-report --api-base https://...

# 默认：当前用户、本周一～今天、中文输出
python3 scripts/generate-weekly-report

# 所有作者
python3 scripts/generate-weekly-report --all-authors

# 查看 prompt（不调用 API）
python3 scripts/generate-weekly-report --dry-run

# 指定周数 / 自定义模板 / 指定输出
python3 scripts/generate-weekly-report --week 24
python3 scripts/generate-weekly-report --template my-template.md
python3 scripts/generate-weekly-report --output reports/custom-name.md
```

### 4. 定时自动执行

```bash
# API Key 通过 config.json 或环境变量自动获取
cp config.example.json config.json
# 编辑 config.json 填入实际 key

# 交互式添加（推荐 — 逐步引导输入，避免 shell 转义问题）
./scripts/schedule add

# 或一行命令添加
./scripts/schedule add -n weekly-report -s "Fri 17:00" -c "python3 $PWD/scripts/generate-weekly-report"

# 管理任务
./scripts/schedule list                        # 查看所有
./scripts/schedule show --name weekly-report    # 详情 + 日志
./scripts/schedule remove --name weekly-report  # 删除
```

## 两种采集方式的配合

| 方式 | 触发时机 | 适用场景 |
|------|----------|----------|
| Hook | 每次 `git commit` 实时触发 | 日常开发，安装后自动运行 |
| 采集器 | 手动 / 定时执行 | 历史导入、多仓库巡检、补漏 |

两者通过 commit hash 去重，互不冲突，可同时使用。

## 提交日志格式

每条提交一行 JSON（JSONL），按 ISO 周号存储：

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

## Schedule 表达式

| 表达式 | 含义 |
|--------|------|
| `Mon 09:00` | 每周一早上 9 点 |
| `Fri 17:00` | 每周五下午 5 点 |
| `Mon,Wed,Fri 14:00` | 每周一、三、五下午 2 点 |
| `weekday 08:00` | 周一至周五早上 8 点 |
| `daily 08:00` | 每天早上 8 点 |

## 自定义模板

模板使用 `{{PLACEHOLDER}}` 占位符：

| 占位符 | 说明 |
|--------|------|
| `{{WEEK}}` | ISO 周号，如 `W25 (2026)` |
| `{{DATE_RANGE}}` | 日期范围 |
| `{{COMMITS}}` | 按项目分组的提交列表 |
| `{{COMMIT_COUNT}}` | 提交总数 |
| `{{REPO_COUNT}}` | 涉及项目数 |
| `{{GENERATED_AT}}` | 生成时间 |

## 卸载

```bash
git config --global --unset core.hooksPath
./scripts/schedule list | tail -n +3 | awk '{print $1}' | xargs -I{} ./scripts/schedule remove --name {}
```

## 依赖

- **Git** — 提交记录采集
- **Python 3.8+** — 脚本运行（仅标准库，无需 pip 安装额外依赖）
- **jq**（可选）— hook 中更可靠的 JSON 构造，缺失时回退到 Python
- **OpenAI 兼容 API** — AI 周报生成（支持 OpenAI、DeepSeek、vLLM、Ollama、LiteLLM 等）
- **macOS** — 定时任务依赖 launchd（Linux 可用 cron 代替）
