# 阅迹 · 成员 C：带证据的小说问答

本项目实现原文检索、按阅读进度限制知识、模型问答与支持性复核、A/B 版本化数据接入、FastAPI 接口、Vue 接入组件和评测脚本。适合四人两周项目中的 C 模块，可独立运行。

默认 `extractive` 模式不调用聊天模型，返回候选原文，`claims` 为空。设置模型服务后切换到 `llm` 模式，才能生成事实/推断答案并执行支持性复核。检索相关性不等于答案正确性；模型复核也不能保证绝对不剧透。

## 启动

项目代码在 `C:\vscode111\nlp\nlp`。上一级的 `nlp.code-workspace` 可用 VS Code 打开。

```powershell
cd C:\vscode111\nlp\nlp
# 当前交付环境已安装依赖；新电脑需先运行以下两步（Python 3.11+）。
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
# 不需要激活虚拟环境。
.\.venv\Scripts\python.exe -m yueji_qa
```

打开 http://127.0.0.1:8000/docs 。也可在上一级运行 `powershell -ExecutionPolicy Bypass -File .\start.ps1`。默认仅监听本机，SQLite 数据保存在 `data/yueji.sqlite3`，重启保留小说、A/B 快照、向量缓存、问答缓存和调用计数。

在 Swagger 中按以下步骤操作：

1. `POST /api/books/upload`，上传 `evaluation/fixtures/灯塔旧账.txt`，选择 UTF-8。
2. 复制返回的 `book_id`；`POST /api/books/{book_id}/qa` 提交 `{"question":"渡口维修账册锁在哪里？","as_of_chapter":1,"experiment":"Q1"}`。
3. 查看 `evidence` 中的原文、章节和段落坐标。`paragraph_url` 可读取完整段落。
4. 同一问题分别设置较早和较晚进度，观察可见证据变化。模型模式还可观察拒答与解答变化。

## 配置生成式问答

把 `.env.example` 复制为 `.env`，填入自己已有的服务信息，再重启后端：

```dotenv
QA_MODE=llm
LLM_BASE_URL=https://你的服务地址/兼容接口前缀
LLM_API_KEY=你的密钥
LLM_MODEL=你的模型名称
DAILY_CHAT_CALL_LIMIT=100
```

服务需要支持 `/chat/completions`、`response_format: json_object`、`temperature` 和 `max_tokens`。地址中应包含服务商要求的前缀（例如 `/v1`），程序只追加 `/chat/completions`。没有硬编码供应商或付费模型，也不会自动下载模型。

一个有候选证据、未命中缓存的问题通常调用两次聊天 API：生成一次、复核一次。生成明确拒答或全部引用无效时可只调用一次。每日上限按 UTC 记录尝试调用次数，不代表人民币金额；服务商的费用限制仍需自行设置以满足总预算 200 元。无自动重试。`GET /api/config` 可查看当前模式和当日调用计数，不返回密钥。

需要语义检索时完整填写 `EMBEDDING_BASE_URL/API_KEY/MODEL`；该服务须支持 `/embeddings`。程序先限制章节，再批量嵌入可见片段；片段向量持久缓存，问题向量按次计算。失败会明确提示并回退 BM25。首次读取较多章节的嵌入调用更多；先用 BM25 跑通再开启。

## 已实现行为

| 环节 | 实现 |
|---|---|
| TXT 导入 | 最多 100000 字符；UTF-8/GB18030；章标题独占一行；每个非空正文行成为一个段落 |
| 章节坐标 | 以文件中的出现顺序从 1 编号；`as_of_chapter=0` 表示未读；不使用故事发生时间做权限过滤 |
| 分块 | 约 600 字符、100 字符重叠，不跨章节，保留段落字符起止位置 |
| 检索 | 中文分词 BM25（正值 IDF 适配少量已读章节）；可选向量检索；两路候选 RRF 融合；先按书和进度过滤再排名 |
| 生成 | 每条断言标注事实/推断、叙述/角色声称/推断，附证据 ID |
| 复核 | 校验真实引用 ID；第二次模型请求检查完整支持、回答相关性和归属，移除未通过断言 |
| A/B 接入 | 保留同一记录的历史版本，按 `known_from_chapter` 取当前可见版本，最终仍引用原文 |
| 缓存 | 书、正文版本、进度、问题、模型、提示词、Q0/Q1、可见 A/B 数据共同决定键 |
| 故障 | 向量/A/B 不可用退回原文检索；模型超时、非法 JSON、存储异常作为 HTTP 技术错误 |
| 集成 | OpenAPI/Swagger、CORS、可选 Bearer 令牌、Vue 3 组件，进度回退时清除旧答案和未完成请求 |

单轮问答；不接收历史对话，避免把较晚进度的答案带回较早进度。上传新文本会生成新 `book_id` 和正文版本。章节元数据接口也只返回已读章节标题。

## 给 A、B、D 的交接

模块接入和示例见 [整合接口](docs/integration.md)，实验范围见 [问答对照](evaluation/README.md)。

详细字段和示例见 [docs/integration.md](docs/integration.md)。A/B 通过 `POST /api/books/{book_id}/knowledge` 提交事件、人物、别名、关系记录，必须带 `text_version`、获知章节和原文引用。D 可直接复制 [integration/NovelQA.vue](integration/NovelQA.vue) 到 Vue 3 项目。

Q0 使用原文；Q1 使用原文加当前可见的 A/B 候选记录。两者共享 6000 字符的证据/结构文本上限、最多 64 条证据、相同检索参数和同一生成模型；Q1 有可见 A/B 数据时最多先收录 48 条原文证据，保留位置给结构记录的引用。模型仅接收证据编号、章节和原文，完整定位元数据留在 API 响应中。未导入 A/B 数据时，Q1 与 Q0 的证据来源基本相同。

## 测试与评测

```powershell
.\.venv\Scripts\python.exe -m pytest -q
# 后端启动后，另开终端运行开发题评测；具体参数见 --help。
.\.venv\Scripts\python.exe scripts/evaluate.py --help
# 无需密钥的 Q0/Q1 实验，输出目录请使用未占用名称。
.\.venv\Scripts\python.exe scripts/evaluate.py --in-process --mode both --output evaluation/results/my-run
# 真实本机 HTTP 验证，脚本自动启停临时服务。
.\.venv\Scripts\python.exe scripts/smoke_http.py
```

当前 142 项自动测试通过（最终记录见 `evaluation/results/expanded-verification-20261113/tests-final.xml`）。测试包括进度回退、未知别名、同书后文变化、跨书隔离、无效证据、虚假前提的复核结果处理、A/B 历史版本、服务故障、调用上限、缓存、脱敏 Token 记录和逐题检查点。模型接口用模拟响应验证控制逻辑，不能据此宣称真实模型准确率。

`evaluation/fixtures` 提供原创六章小说、20 条开发问题和示例 A/B 数据。它们用于联调；另已新增四部小说前五回的 120 条样本，按书划分开发/留出，助手标注仍待人工校验。评测说明见 [evaluation/README.md](evaluation/README.md)。

已完成离线联调和 DeepSeek 真实模型实验：

- [2026-11-13 扩展实验记录](docs/扩展实验记录-2026-11-13.md)：新增 240 份离线结果、260 份真实问答结果，391 次调用、1,121,580 Token；包含 90 条按书留出题和 8 条合成压力题。已导出人工盲评表，语义评分待完成。Q1 使用参考记录且部分复用答案标注，不能作为自动 A/B 的端到端成绩。留出集发现关键句截断与回答不完整，未证明复核增益。

- [2026-11-12 真实模型实验记录](docs/真实模型实验记录-2026-11-12.md)：使用官方 `deepseek-flash`，20 题 × Q0/Q1，共 40 份有效响应；每组 14 道可答题均有回答、6 道不可答题均拒答。引用坐标和章节边界检查均未发现错误。这些结果不等于语义准确率或独立测试集成绩。
- [2026-10-29 离线实验记录](docs/实验记录-2026-10-29.md)：原文检索模式的流程验证，不产生生成式答案。

真实模型原始响应、统计、逐题检查点与用量保存在 `evaluation/results/deepseek-20261112/`；另有两题预检目录 `deepseek-pilot-20261112/`。完整实验调用模型 68 次，使用 80,323 Token；包含预检合计 76 次、85,307 Token。没有微调，也没有额外调用模型评分。关键词覆盖 Q0 为 14/14、Q1 为 12/14，差异是同义改写；本批数据未证明 A/B 增益。

复现实验时使用隐藏输入，密钥仅传入本次进程，不写项目文件：

```powershell
.\.venv\Scripts\python.exe scripts/run_deepseek_experiment.py --output evaluation/results/my-deepseek-run
```

脚本默认 `deepseek-flash` 非思考模式，采用 BM25，保存每题结果和 API 返回的 Token 用量；可先加 `--limit 2` 做小样本预检。详细规则见 [评测说明](evaluation/README.md)。

## 边界与部署

解析器要求章节清晰；章前文字会忽略并返回提醒，空章节拒绝导入。段落坐标针对去除首尾空白、统一换行后的正文，使用 Python Unicode 字符偏移（左闭右开），不是原始 TXT 字节偏移。超长段落会分块保留局部位置。

API 依赖调用者正确传入当前进度；它不是防止用户主动查看自己上传全文的权限系统。LLM 仍可能利用预训练记忆，语义复核亦可能漏检；必须用真实模型和留出小说评估后文泄露率。A/B 的获知章节由生产模块负责正确标注，C 能校验证据章节和版本，不能自动证明标注语义正确。

服务器部署设置 `HOST=0.0.0.0` 和 `APP_TOKEN`，使用 HTTPS 反向代理；只开放必要端口，前端域名填入 `CORS_ORIGINS`。这是单账号模块，令牌只放自己的前端会话/配置，不把模型密钥发到浏览器。默认一个进程、一个问答并发，配合每日调用上限控制预算。已完成本地 DeepSeek 真实模型开发实验；尚未购买服务器或部署公网。

开源借鉴与许可证记录见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
