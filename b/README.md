# 阅迹：成员 B 人物与关系模块

提供小说分章预览、人物与关系候选抽取、人工复核、进度查询及有证据的人物合并；带网页界面，可在本机运行，也可用 Docker 部署。

第一次使用可先看 [成员 B 操作指南](成员B_操作指南.md)。

## 快速开始

```powershell
# 进入解压后的 member_b 目录后运行
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python seed.py
Copy-Item .env.example .env    # 填写模型密钥
.\start.ps1
```

打开 http://127.0.0.1:8000 使用界面，API 文档在 `/docs`，健康检查 `/healthz`。原创样例编号为 `demo`；《孤独者》原文可从 `data/guduzhe_wikisource.txt` 导入，来源和校验值见 `data/README.md`。源码包不包含已有数据库，需要在自己的环境中导入或创建示例书目。

不配置模型也可演示动态关系：Windows 下运行 `.\.venv\Scripts\python seed_showcase.py` 后选择 `showcase_dynamic`。在图谱中将进度依次调整到第 1、2、5、6 章，可看到合作、单向怀疑、合作结束以及蒙面人的身份揭示；退回第 5 章可再次看到未合并的人物。人物档案中的示例事实也带原文依据。该示例全部由人工构造，**不是模型抽取结果或质量评测**；重复运行脚本不会覆盖现有同名书目。

## 界面

顶部选择当前书目，标签页依次是：

- **书目**：已有书目与规模，切换当前书目。
- **导入**：上传或粘贴正文，预览并修改章节标题、正文后确认导入；标题前的正文保留为独立前言章节。
- **抽取**：显示模型密钥是否已配置及剩余调用次数，指定章节与阅读进度后调用模型并把候选写入数据库；可查看未通过字段或证据校验的模型输出及原因。密钥状态只检查是否存在，不代表服务商已验证其有效性。
- **复核**：逐条接受/拒绝人物、人物事实与关系候选；人物可新建，也可关联为已有人物的别名。误拒绝后可切换“已拒绝”并移回待复核。人物编号按候选证据章节的已知称谓填写；同名称谓有多个匹配时留空并提示人工确认。展开原文可查看证据段落和同章相邻段落。
- **图谱**：按阅读进度查看人物档案、节点、别名和关系边；可按已知称谓筛选人物及其直接关系，每条事实及关系附原文依据。可在补录区按章节查看原文和段落编号，手动补录人物、事实和关系，并按记录撤回或恢复。
- **合并**：录入证据段落与逐字引文合并人物，或撤销最近的合并。
- **预算**：设置调用次数上限，查看每次调用的状态与用量。

## 模型配置

密钥只放在服务端环境变量或 `.env`（已列入 `.gitignore`），不要写进前端或提交仓库。PLAN 默认百炼 Qwen，可切换 DeepSeek；切换后测试成本和效果需重新验证，正式实验要记录并统一模型。

```ini
YUEJI_MODEL_PROVIDER=deepseek
YUEJI_MODEL=deepseek-flash
DEEPSEEK_API_KEY=你的密钥
```

默认 DeepSeek 模型是 `deepseek-flash`；可用 `YUEJI_MODEL` 更换。恢复 Qwen：`YUEJI_MODEL_PROVIDER=qwen`、设置 `DASHSCOPE_API_KEY`，并清除可能设置的 `YUEJI_MODEL`。`start.ps1` 优先使用当前终端中已有的环境变量，未设置的值再从 `.env` 加载；服务启动时读取这些变量，改完需重启。

## 部署

**本机常驻**：`.\start.ps1` 会读取 `.env` 并监听 `127.0.0.1:8000`。也可以手动：

```powershell
.\.venv\Scripts\python -m uvicorn app:app --host 0.0.0.0 --port 8000
```

**Docker**（本机未安装 Docker，该路径未实际构建验证）：

```powershell
docker compose up -d --build
docker compose logs -f
```

容器把数据库放在挂载卷 `./store/characters.db`，重建容器不丢数据；端口默认只映射到 `127.0.0.1:8000`。

**配置项**

| 变量 | 作用 |
|---|---|
| `YUEJI_MODEL_PROVIDER` / `YUEJI_MODEL` | 模型服务商与模型名 |
| `DEEPSEEK_API_KEY` / `DASHSCOPE_API_KEY` | 对应服务商的密钥，二选一 |
| `YUEJI_DB` | 数据库路径，默认 `characters.db` |
| `YUEJI_TOKEN` | 可选访问令牌；设置后所有页面和接口都要求它 |

**安全与运维**

- 设置 `YUEJI_TOKEN` 后，第一次用 `http://地址:8000/?token=令牌` 打开，会写入 HttpOnly Cookie，之后正常访问；接口也接受 `X-API-Token` 头。未设置时没有任何鉴权，**只应在本机或可信内网使用**。
- 对外暴露时建议放在反向代理后并启用 HTTPS；直接把 8000 端口开到公网不合适。
- 调用预算是硬上限（`/settings/call-budget`），生产环境建议设小值；`call_log` 记录每次调用。
- 备份：停服后复制 `characters.db`；WAL 模式运行时还会生成 `-wal`/`-shm`，更稳的做法是停服或用 `sqlite3 characters.db ".backup 备份.db"`。
- SQLite + WAL 适合单机读写；任务执行器当前仅支持一个服务进程。不要以多个 worker 或实例共享数据库运行，否则启动时的中断恢复会影响其他实例的任务。
- 监控看 `/healthz`；排障看 uvicorn 访问日志和 `call_log` 表。


## 使用流程

1. `POST /books/preview-txt` 接收原始 UTF-8 或 GB18030 文件字节，核对分章。单独汉字数字节号会标记为需检查。修改预览后用 `POST /books/confirmed` 导入。
2. 首次调用前通过 `PUT /settings/call-budget` 设置调用次数上限（如 `{"max_calls": 5}`），默认为 0。`GET` 可查看调用记录。缓存命中不占次数，失败和超时请求也计入。上限是全数据库累计次数，不是金额；请结合服务商实际账单和预算控制。`POST /books/{book_id}/extract` 指定 `chapter` 和 `progress_chapter`；仅发送指定且已读章节，按段落切为约 2000 字一批。调用外部服务有费用。
3. `GET /books/{book_id}/candidates` 查看候选。复核接口接受或拒绝；先接受人物并指定人物 ID，若候选其实是已有人的另一称谓，用 `link_to_person_id` 及 `identity_paragraph_id`、`identity_quote` 录入身份揭示证据；揭示前仍保留独立人物；再接受关系并指定已知人物 ID。
4. `GET /books/{book_id}/characters`、`/relationships` 和 `/relationships/history` 返回当前进度可见的人物和关系断言。关系历史按获知章节展示，不表示故事发生顺序或当前状态。
5. `POST /books/{book_id}/person-merges` 接受两个人物 ID、证据段落和逐字引文，创建从该证据章节开始生效的人工合并；`GET` 可查看历史。合并需按证据章节顺序录入，系统校验引文存在但不能判定是否证明同一身份。

每一成功批次按小说、章节、模型、提示词和原文内容缓存；重复请求可复用，已成功批次不会重复生成候选，失败后重试会从缓存继续。缓存用量是原请求的数据，不代表缓存命中产生新费用。抽取结果需人工复核，模型可能遗漏或误判；候选引文存在并不证明关系成立。超过 2000 字的单段会按标点优先拆分并保留少量重叠；所有片段保留原段落编号，完全相同的重叠候选在一次抽取中复用。边界可能仍影响抽取效果。

## 验证与限制

在安装依赖的环境中执行 `python -m unittest -v test_app`（当前 61 个用例，含进度隔离、任务取消、候选复核、事件时序和十万字导入读取等）。容量测试覆盖分章、入库、按进度读取与分块，不包含十万字的真实模型调用或整书处理耗时。测试主要使用原创小样例与模拟服务。《孤独者》的开发集评测见 `evaluation_guduzhe.md`：其中映射及规则针对该书调整，不能代表其他小说或人工复核后图谱的实际准确率。事件时序接口尚未与成员 A 的真实系统联调。可通过 `POST /books/{book_id}/person-merges/{merge_id}/withdraw` 填写理由撤销最近的合并；撤销作为纠错影响所有查询视图，并保留记录。暂不支持直接修改原始候选或撤销接受操作、金额预算上限和完整审计版本；已接受的人物、关系和人物事实可按证据撤回。新版本产生的候选复核操作可通过 `GET /books/{book_id}/candidate-review-history?progress_chapter=...` 查看，旧版本的历史操作不会自动补齐。图谱查询的 `knowledge_version` 是当前人物与关系可见内容的哈希，不覆盖独立时间约束或候选状态。网页和本机部署已有原型，正式独立评测与组内联调尚未完成。

## 关系评测

`python normalize.py [输出文件]` 是《孤独者》开发集专用的评测导出脚本，内部固定了该书的人物和关系映射；它会尝试判定引语说话人、归一标签、去重并过滤「其他」类预测，也包含未复核候选。它不改变网页中人工复核的图谱，不能直接用于任意新小说。通用关系候选导出见 `export_relations.py --help`。`python evaluate.py gold.json predictions.json` 对标注和预测 JSON 数组计算 Precision、Recall 和 F1。每条需包含 `book_id`、整数 `progress_chapter`、`source`、`target`、`relation`、布尔 `directed` 和 `action`；双向关系对调双方视为一致，单向关系方向相反不一致。空分母输出 null。评测前应人工统一人物编号和标签，单独记录历史状态错误与证据支持情况；该脚本本身不生成或验证标注。样例见 `gold_guduzhe.json`、`predictions_guduzhe.json`，结果与错误分析见 `evaluation_guduzhe.md`。

## 人物出现位置和指代复核

候选查询对代词人物或引文中没有直接出现关系双方称谓的记录显示提醒。提醒只是复核线索：包含两个名称也不能证明语义关系，不包含也不一定有错。接受人物候选时可选 `earlier_paragraph_id`，在人工确认人物身份后，将其出现章节绑定到不晚于候选且包含相同称谓的原文段落。相同称谓并不自动证明是同一人物，应结合上下文判断。章节级过滤并不保证段落顺序；同一章节内更早段落的关系不会因为人物候选出现在同章后段而被拒绝。

界面中的抽取、复核、图谱和合并共享每本书保存在服务端的阅读进度；首次使用默认为第一章，刷新页面或切换书目后会恢复上次保存的进度。图谱展示带“记录”或“结束”标记的关系历史，不推断真实故事时间下的当前状态。

接入方可用 `GET /books/{book_id}/reading-progress` 获取进度，用 `PUT /books/{book_id}/reading-progress` 和请求体 `{"chapter": 2}` 更新进度。查询时仍需传入 `progress_chapter`，且不能超过服务端保存的进度；写入请求中所带的进度和证据段落也会检查。抽取接口和任务另有进度检查。回退进度时，服务端会取消超出范围的排队任务，并请求停止正在执行的任务。其他已打开的页面不会自动收到推送，需要刷新或重新选择书目以同步；已经开始处理的普通请求与进度回退并发时，不能保证被中途撤回。

## 关系变化与故事时间

图谱展示每条已复核关系的证据记录编号，并可填写两个编号及一段原文引文，建立“较早 → 较晚”的人工时间约束。`POST /books/{book_id}/relationship-orders` 需要 `before_id`、`after_id`、`paragraph_id`、`quote` 和 `progress_chapter`；`GET` 按阅读进度返回已知约束。`GET /books/{book_id}/relationships/summary` 根据可见约束计算每一关系的最新可排序记录；相反记录先后不明或存在冲突时返回 `unresolved`。没有时间依据时不会把叙述顺序当作故事顺序。

系统验证引文存在、证据和关系在进度内，以及新增约束是否与当前可见约束直接或间接构成环；引文是否真正支持先后关系仍需人工判断。时间约束可通过下文的修订接口撤回或恢复，但不能直接编辑，也未与成员 A 的事件时序系统实际联调；不能把汇总当作对所有故事时刻的完整状态证明。

## 人物事实

模型可输出 `facts`：人物称谓、类别、内容、陈述性质（`explicit` 原文陈述、`claim` 角色声称、`inference` 解释性推断）和逐字引文。事实候选经 `GET /books/{book_id}/profile-candidates?progress_chapter=...` 查询；复核使用 `POST /books/{book_id}/profile-candidates/{id}/review?progress_chapter=...`，接受时给出已录入人物的 `person_id`。也可用 `POST /books/{book_id}/profile-facts` 手动添加。查询人物档案时只返回已读范围内的事实及证据，人物合并只在揭示章节后影响档案。模型或人工录入的性质、内容及引文与人物的对应关系必须人工核查。

新提示词会改变模型缓存键，因此历史缓存不会自动产生人物事实；重新分析会消耗 API 次数和费用，未配置密钥时仍可手工录入。

身份候选复核的“关联到已有人物”必须提供揭示身份的原文段落及逐字引文，证据章节不能早于候选出现或超出当前进度。人工仍须确认引文确实能证明同一身份。早期已按旧逻辑直接写入的别名不会自动恢复独立身份，应逐条复核已有数据。

## 关系和人物事实修订

`POST /books/{book_id}/person-corrections` 接收 `person_id`、`action`、`paragraph_id`、`quote`、`reason` 和 `progress_chapter`；图谱页也可操作。撤回从证据章节生效，该人物原始记录保留，相关关系和事实不再显示、涉及该人物的合并暂不应用；恢复后重新计算。`GET /books/{book_id}/person-corrections?progress_chapter=...` 查看进度内修订历史。引文是否支持撤回或恢复仍须人工核对。

新接受的关系候选会保存逐字引文和候选编号；网页手动补录关系时也需填写逐字引文，后端校验引文位于所选段落。人物关系接口和知识快照同时返回段落编号、全文及可用的引文。旧关系没有保存独立引文时返回 `null`，页面明确显示该情况；可以核对原段后手动补充，但不会自动推测历史引文或候选来源，已保存的引文不能直接覆盖。API 为兼容旧调用仍允许手动关系不提交引文。

`POST /books/{book_id}/record-corrections` 提交 `target_kind`（`relation` 或 `fact`）、`target_id`、`action`（`retract` 或 `restore`）、`paragraph_id`、逐字 `quote`、`reason` 和 `progress_chapter`。修订章节取自证据，不能早于原记录或晚于阅读进度；引文和记录归属均会校验。修订历史通过 `GET /books/{book_id}/record-corrections?progress_chapter=...` 查询，早期视图不显示后文修订。原记录保留，需修改内容时先撤回原记录，再录入有依据的新记录。系统无法自动判定引文是否支持修订，仍须人工核对。

## 与事件时序模块联调（待组内确认契约）

此模块提供独立的交换接口；目前只用模拟事件数据验证，成员 A 的实际格式和服务尚未对接。传入的书号、段落编号必须与本模块一致，`source` 用于注明上游版本或来源。

成员 C、D 可用 `GET /books/{book_id}/knowledge-snapshot?progress_chapter=1` 一次获取当前进度的人物档案、关系、关系状态、时序约束、事件及修订记录。响应的 `knowledge_version` 是该快照内容的 SHA-256；内容变化时可用于识别不同版本。请求不能超过服务端已保存的阅读进度。读取期间若发现其他事务提交，接口会重新读取；多次冲突则返回 409，调用方可重试。该接口已做模拟数据验证，并不表示已经与其他成员的真实服务联调。

人物档案的 `name_evidence` 记录称谓出现的章节、段落与原文；`identity_evidence` 记录当前生效的人物合并及其引文。称谓出现在同一段落本身不证明身份相同；直接挂在原人物上的旧别名未必具有独立合并证据，需要人工复核。

直接添加人物称谓的 `POST /books/{book_id}/characters/{person_id}/names` 需提供 `name`、`paragraph_id` 和逐字 `identity_quote`。引文随称谓显示在 `name_evidence` 中；模型和系统无法自动判断它是否证明同一身份，仍需人工核对。此接口从证据章节开始关联称谓；若称谓此前已作为独立人物出现，请使用人物合并功能，保留揭示前的独立身份。旧记录不会自动补造引文。

- `POST /books/{book_id}/events`：`event_id`、`summary`、`source`、`paragraph_id`、`quote`、`progress_chapter`。事件获知章节取自证据段落。
- `POST /books/{book_id}/event-orders`：`before_event_id`、`after_event_id`，以及 `source`、`paragraph_id`、`quote`、`progress_chapter`。表示两个事件的故事发生先后。
- `POST /books/{book_id}/relation-event-links`：`relation_id`、`event_id`，以及 `source`、`paragraph_id`、`quote`、`progress_chapter`。关联对应关系断言与事件。
- `GET /books/{book_id}/event-context?progress_chapter=...` 返回该进度可见事件、时序和关联及其证据。关系汇总会使用已读且单一对应的事件，沿已知时序进行传递推导；一个关系关联多个事件时，暂不据此推导顺序。

系统校验证据逐字存在、书籍归属、可知章节及可见约束冲突，不能判断事件摘要和先后关系的语义是否得到支持。上游需先核对，不能把后文信息写进早期事件摘要。事件、事件时序、关系与事件的关联，以及关系时序可通过修订接口撤回或恢复；实际联调前仍需与成员 A 确定数据版本及同步协议。

`POST /books/{book_id}/integration-corrections` 支持 `target_kind` 为 `event`、`event_order`、`event_link` 或 `relation_order`，其余字段与记录修订接口一致。`GET /books/{book_id}/integration-corrections?progress_chapter=...` 返回当前进度内的修订历史；被撤回的事件及其关联不会用于关系推导。图谱页面可查看编号并提交修订。恢复只恢复记录的可见性，不代表语义已自动核验。

## 进度隔离回归

`data/synthetic_progress_pair.json` 是两版原创八章故事及 60 条程序检查，见 `data/README.md`。`python -m unittest -v test_app.SyntheticIsolationTests` 在临时数据库验证全书导入后的回退、身份揭示、关系状态和两版前五章输入一致性；不调用付费模型。检查结果不作为模型 Precision / Recall 或独立人工标注评测。

## 通用关系候选导出

`export_relations.py` 用于在不同书籍上导出模型关系候选，不依赖《孤独者》的人名表：

```powershell
python export_relations.py --book 小说编号 --progress 已读章节 --output 预测.json --issues 待核对项.json --status all
python evaluate.py 金标准.json 预测.json
```

可用 `--labels` 指定事先冻结的原始标签到目标标签的 JSON 映射；未知标签保留原值并记录待核对项，不会直接删掉。人物仅用候选出现章节的人物档案解析，未找到或有歧义时保留占位符并记录待核对项。`--status all` 包含接受、拒绝及待复核的候选；也可指定其他状态，实验中必须固定口径。输出是以已复核人物档案为条件的关系候选评测，不是人物识别端到端指标；姓名映射本身由人工提供，不能宣称全自动。多个相同七元组在 `evaluate.py` 按集合计为一条，不能检验同章多次独立事件。

独立测试正文 `data/aq_test_wikisource.txt` 已固定来源和校验值，见 `data/README.md`。目前只有助手起草、未复核且不完整的标注；第一章已进行探索性真实模型抽取，不能再用作未接触的盲测，详情见 `data/README.md`。在正式标注和实验方案冻结前，不应根据测试结果调参。

## 抽取时的人物上下文

模型请求包含该章及以前已复核的人物称谓分组，但不发送人物编号、人物事实或后文章节。称谓仅作指代参考，不能代替当前请求段落中的证据；所有候选仍需引文校验与人工复核。为控制输入大小，称谓上下文按稳定顺序限制在 8000 字符内，响应的 `known_people_count` 和 `context_truncated` 表示实际发送数量及是否截断。称谓上下文变化会改变缓存键，触发新的付费调用；运行前检查预算上限。

上下文变化后重抽时，同一本书、同一章节中字段和引文完全相同的候选会复用已有候选及其复核状态；描述或证据不同的候选仍需分别核对。已有历史重复记录不会自动删除。本轮尚未用真实模型验证新增上下文的效果，不能从模拟测试推断抽取质量。

独立测试的局部标注草稿、格式校验与暂存配置清单位于 `data/`，详情见 `data/README.md`。草稿不等同于人工核验的金标准；需补全并复核后才能用于正式评测。

## 分析任务与恢复

在抽取页可提交单章任务或从当前章节分析至阅读进度。`POST /books/{book_id}/extraction-jobs` 需要 `start_chapter`、`end_chapter` 和 `progress_chapter`；结束章节不能超过阅读进度。`GET /books/{book_id}/extraction-jobs?progress_chapter=...` 只显示范围不超过该进度的任务。可以用任务的 `/cancel` 和 `/retry` 操作停止或从未完成章节重试。服务重启会将未完成任务标为中断，需手动重试。

任务串行处理章节，已成功批次的缓存可在重试时复用；各次调用仍受全库调用次数上限限制。单条模型输出字段错误或证据不匹配时，同批有效候选仍会保留，任务会显示受影响章节及拒绝数量；抽取接口的批次结果包含被拒绝项及原因。需要核对原文并补录，不能视为模型已完整抽取。顶层结果格式错误仍会使批次失败。同一服务进程内，同一本书的直接抽取与后台任务互斥：已有抽取在运行时，新的调用返回 409，稍后可重试并复用缓存。人物上下文或提示词等发生变化时会生成新缓存键，仍可能调用模型。服务端保存的进度回退时，会请求停止超出新进度的任务；直接抽取和后台任务都会在分块之间检查保存的进度。已经发送的模型请求不能撤回，也可能产生费用；检查进度和发送请求之间仍存在短暂竞态。任务执行器和互斥保护运行于单个服务进程，不支持多进程或多实例共享任务队列。
