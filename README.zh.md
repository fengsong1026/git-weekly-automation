# git-weekly-automation

> 一条命令安装，自动记录每一次 git commit，周五下班前 AI 帮你写好中文周报。

> *中文文档 · [English Documentation](README.md)*

## 3 分钟上手

```bash
# 1. 安装
npm install -g git-weekly-automation

# 2. 初始化
git-weekly setup

# 3. 配置 API Key
export OPENAI_API_KEY="sk-your-key-here"
# 如果用 DeepSeek 等第三方 API，还需指定地址：
# export OPENAI_BASE_URL="https://api.deepseek.com/v1"

# 4. 立即试试
git-weekly report
```

执行 `git-weekly setup` 之后，本机所有 Git 仓库的每次 `git commit` 都会自动记录。

---

## 常用命令


| 命令                                 | 说明            |
| ---------------------------------- | ------------- |
| `git-weekly setup`                 | 安装全局 git hook |
| `git-weekly report`                | 生成本周周报        |
| `git-weekly collect --scan ~/work` | 从现有仓库批量采集历史提交 |
| `git-weekly schedule add`          | 添加定时任务（交互式引导） |
| `git-weekly schedule list`         | 查看所有定时任务      |
| `git-weekly cleanup`               | 清理残留的孤儿安装     |


## 命令详解

### git-weekly setup

安装全局 git hook，之后本机每次 `git commit` 自动记录到 `data/commits/`。

```bash
git-weekly setup            # 安装
git-weekly setup uninstall  # 卸载（自动清理所有产物）
git-weekly setup uninstall --yes  # 非交互卸载（CI/脚本用）
```

### git-weekly report

读取本周提交记录，调用 AI 生成中文周报。

```bash
# 前置：配置 API Key
export OPENAI_API_KEY="sk-..."

# 基础用法
git-weekly report                        # 本周、当前用户
git-weekly report --week 25              # 指定 ISO 周号
git-weekly report --all-authors          # 所有作者
git-weekly report --dry-run              # 只看 prompt，不调 API
git-weekly report -o my-report.md        # 指定输出路径
git-weekly report --api-base https://api.deepseek.com/v1  # 自定义 API
```

### git-weekly collect

扫描目录下所有 Git 仓库（含 submodule），批量拉取提交记录。用于导入历史记录或从多台机器同步。

```bash
git-weekly collect --scan ~/work                    # 扫描单个目录
git-weekly collect --scan ~/work --scan ~/projects  # 扫描多个
git-weekly collect --scan ~/work --since 2026-01-01 # 指定起始日期
git-weekly collect --scan ~/work --dry-run           # 预览不写入
```

### git-weekly schedule

管理 macOS launchd 定时任务。

```bash
git-weekly schedule add     # 交互式添加（推荐）
git-weekly schedule list    # 查看所有任务
git-weekly schedule show -n weekly-report  # 任务详情 + 最近日志
git-weekly schedule remove -n weekly-report  # 删除任务
git-weekly schedule clear   # 清空全部
```

**Schedule 表达式：**


| 表达式                 | 含义           |
| ------------------- | ------------ |
| `Fri 18:00`         | 每周五下午 6 点    |
| `Mon 09:00`         | 每周一早上 9 点    |
| `Mon,Wed,Fri 14:00` | 周一、三、五下午 2 点 |
| `weekday 08:00`     | 周一至周五早上 8 点  |
| `daily 08:00`       | 每天早上 8 点     |


### git-weekly cleanup

如果项目目录被意外删除（没先跑 uninstall），注册表中会留下孤儿条目。此命令扫描并清理：

```bash
git-weekly cleanup
```

自动执行：卸载残留 launchd 任务 → 删除 plist 文件 → 恢复 git hooksPath → 移除注册表条目。

---

## 数据文件位置

```
data/
├── commits/
│   ├── 2026-W25.jsonl      # 每周提交记录（JSONL）
│   └── ...
└── logs/                   # 定时任务运行日志

reports/                    # 生成的周报（.md）
```

提交记录格式（一行一条 JSON）：

```json
{"hash":"abc123...","author":"Zhang San","email":"zhangsan@example.com","timestamp":"2026-06-15T14:30:00+08:00","message":"feat: add auth module","repo":"my-project","repo_path":"/path/to/repo","branch":"main","hostname":"MacBook.local"}
```

---

## API 配置

四种方式，优先级从高到低：

```bash
# 1. 命令行参数（最高优先级）
git-weekly report --api-base https://api.deepseek.com/v1 --model deepseek-chat

# 2. 环境变量
export OPENAI_API_KEY="sk-..."
export OPENAI_BASE_URL="https://api.deepseek.com/v1"

# 3. 项目根目录 config.json（复制 config.example.json 后修改）
cp config.example.json config.json
# 编辑 config.json：
#   "api_key":  API 密钥
#   "api_base": API 地址（可选，默认 api.openai.com/v1）
#   "model":    模型名（可选，默认 gpt-4o-mini）

# 4. 什么都不配 → 走 dry-run 模式预览 prompt
```

支持任何 OpenAI 兼容 API：OpenAI、DeepSeek、vLLM、Ollama、LiteLLM 等。

---

## 自定义模板

模板文件 `templates/weekly-report.md`，使用 `{{PLACEHOLDER}}` 占位符：


| 占位符                | 替换为                   |
| ------------------ | --------------------- |
| `{{WEEK}}`         | ISO 周号，如 `W25 (2026)` |
| `{{DATE_RANGE}}`   | 本周日期范围                |
| `{{COMMITS}}`      | 按项目分组的提交列表            |
| `{{COMMIT_COUNT}}` | 提交总数                  |
| `{{REPO_COUNT}}`   | 涉及项目数                 |
| `{{GENERATED_AT}}` | 生成时间                  |


```bash
git-weekly report --template my-custom-template.md
```

---

## 卸载

```bash
# npm 用户
npm uninstall -g git-weekly-automation

# 或手动
git-weekly setup uninstall     # 交互式，会确认是否删除数据
git-weekly setup uninstall --yes  # 非交互，CI 中直接全清
```

卸载会移除：git hook、所有定时任务、注册表条目。数据和报告按提示确认。

---

## 依赖

- **Git** — 提交记录采集
- **Python 3.8+** — 脚本运行（仅标准库，无需 pip）
- **Node.js / npm** — 安装工具（手动克隆可跳过）
- **macOS** — 定时任务依赖 launchd
- **jq**（可选）— hook 中 JSON 构造，缺失自动回退 Python
- **OpenAI 兼容 API** — 周报生成

