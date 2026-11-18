# A/B/D 接入约定

逐模块接口与适配方法见下文。可导入样例见 [handoff-examples.json](../integration/handoff-examples.json)。

服务地址默认 `http://127.0.0.1:8000`，交互式接口文档在 `/docs`，机器可读契约在 `/openapi.json`。设置 `APP_TOKEN` 后，所有 `/api/` 请求都带 `Authorization: Bearer <token>`，Swagger 中可点 Authorize。

## 原文与坐标

由 D 上传小说一次，使用 C 返回的 `book_id` 和 `text_version` 作为共享标识。`GET /api/books/{book_id}/chapters?as_of_chapter=N` 给出已读章节和段落 ID；`GET /api/books/{book_id}/paragraphs/{paragraph_id}?as_of_chapter=N` 返回段落正文。

| 字段 | 约定 |
|---|---|
| `book_id` | 上传时由后端生成，同一文本再次上传也得到新 ID |
| `text_version` | 规范化输入的 SHA-256；A/B 导入必须匹配 |
| `chapter_index` | 文件出现顺序从 1 起，与章标题写“第三十章”无关 |
| `paragraph_id` | 如 `ch0001-p0001`，每个非空正文行一段，排除章标题 |
| `start/end` | 去掉段首尾空白后的 Unicode 字符索引，左闭右开；不是字节偏移 |
| `as_of_chapter` | 读到的章节，0 为未读，不能超过总章节数 |

不要让 A/B 用另一套切段方式生成引用。现成分章模块若要替换 `ingest.py`，需要整个团队一起确定版本和段落 ID。中文常用字符偏移在 JS/Python 通常一致，但表情等非 BMP 字符在 JS 是两个 UTF-16 单元；前端高亮可用 `Array.from(text).slice(start,end).join('')` 对齐后端。

## A/B 导入

`POST /api/books/{book_id}/knowledge`，JSON 示例（`text_version` 替换成上传返回值）：

```json
{
  "text_version": "上传时返回的正文哈希",
  "records": [
    {
      "record_id": "relationship-suhe-linzhou",
      "source": "B",
      "kind": "relationship",
      "text": "苏禾与林舟合作核对账册，同时苏禾怀疑林舟会草率下结论；原文没有表明林舟也怀疑苏禾。",
      "known_from_chapter": 2,
      "assertion_type": "narrator",
      "version": "synthetic-v1",
      "evidence_refs": [
        {
          "paragraph_id": "ch0002-p0001",
          "start": 0
        }
      ]
    }
  ]
}
```

该导入示例对应当前 `evaluation/fixtures/灯塔旧账.txt` 的真实记录与坐标，接自己的小说时务必替换证据。`end` 省略表示段尾，单条引用最多 1200 字符。`kind` 可为 `event/character/relationship/alias`；`assertion_type` 可为 `narrator/character_claim/inference`；`source` 为 A 或 B。

`known_from_chapter` 是读者最早能够知道这条**完整结论**的章节。第 8 章回忆三年前的事，获知章节仍是 8；事件发生时间可以保留在 `text`，不能用来放宽问答范围。第 8 章才确认的别名，不能因为它引用了第 2 章的一句话就标成第 2 章可知。

同一逻辑记录用稳定 `record_id`；晚些章节带来新信息时新增 `version`，把 `known_from_chapter` 设成新的获知章节。C 保留旧版本，选取不晚于当前进度的最近版本。相同 ID、相同版本内容不可修改；同一获知章节不接受多个版本，避免顺序歧义。导入完全相同的数据是幂等操作。整个批次原子提交，任何记录冲突则整批失败。

新的版本应是完整快照，不能只写“新增了一条关系”。并存且有方向的关系可分成不同 `record_id`（例如 `suhe-suspects-linzhou`、`suhe-cooperates-linzhou`），避免覆盖。C 不自动做 A/B 的事件抽取或人物图谱构建；只消费符合契约的记录。

## D 调用问答

```http
POST /api/books/{book_id}/qa
Content-Type: application/json

{"question":"苏禾与林舟合作时是否还有怀疑？","as_of_chapter":2,"experiment":"Q1"}
```

建议实际提问时用姓名代替“他”。每个请求是单轮，不附加历史消息。

```json
{
  "book_id": "...", "text_version": "...", "as_of_chapter": 2,
  "experiment": "Q1", "mode": "llm", "status": "answered",
  "claims": [{
    "text": "苏禾仍怀疑林舟会草率下结论；这种怀疑没有阻止她与林舟合作。",
    "kind": "fact", "assertion_type": "narrator",
    "evidence_ids": ["E1"], "verification": "model_supported"
  }],
  "evidence": [{
    "evidence_id": "E1", "book_id": "...", "text_version": "...",
    "chapter_index": 2, "chapter_title": "第二章 同行与疑心", "paragraph_id": "ch0002-p0001",
    "start": 0, "end": 31,
    "quote": "示意：实际内容由后端从原文切片填入，不由模型编写",
    "paragraph_url": "/api/books/.../paragraphs/ch0002-p0001?as_of_chapter=2"
  }],
  "limitations": ["支持性复核由模型完成，仍可能判断错误；请结合原文核对。"],
  "retrieval_method": "bm25", "used_knowledge_ids": ["B:relationship-suhe-linzhou:synthetic-v1"],
  "cached": false, "latency_ms": 1200
}
```

这是字段示例，非实际模型输出或测得的延迟。引用 ID 只在当前回答内有效，不应作为全局主键。稳定定位使用 `book_id/text_version/paragraph_id/start/end`。

| 状态 | 前端含义 |
|---|---|
| `answered` | 系统标记为已回答；仍需核对完整性和正确性 |
| `partial` | 仅解决部分问题；或处于原文检索模式，应展示模式提示 |
| `insufficient_evidence` | 没有足够证据，不能显示成“全书不存在” |
| `clarification_needed` | 需要补充具体人物、事件或范围 |

技术错误使用非 2xx HTTP 状态和 `{"error":{"code":"...","message":"..."}}`，不伪装成证据不足。422 表示参数/文本不符合要求；409 表示正文或知识版本冲突；429 表示并发/本地调用上限；502/504 表示模型服务失败/超时；503 表示存储异常。

`claims[].kind=inference` 显示“推断”；`assertion_type=character_claim` 显示“角色声称”。`verification=model_supported` 仅表示模型复核通过，不是人工验证。原文模式不生成断言，`claims=[]`；此时可展示 `evidence` 作为搜索结果。

## Vue 组件

复制 `integration/NovelQA.vue` 到 D 的 Vue 3 工程：

```vue
<NovelQA
  :book-id="selectedBookId"
  :as-of-chapter="readingChapter"
  api-base="http://127.0.0.1:8000"
  :token="sessionToken"
  @open-evidence="locateParagraph"
/>
```

`locateParagraph(evidence)` 使用相同 Authorization 请求 `evidence.paragraph_url`，拿到完整段落后按字符区间高亮。组件会在换书、进度变化、服务地址或令牌变化时清空答案并取消旧请求，且忽略迟到响应；D 自己的历史聊天区也必须遵守同样规则。不要用 `v-html` 渲染原文或模型输出。

## 研究对照与缓存

Q0/Q1 通过请求的 `experiment` 切换；同一个模型、同一进度、同一问题下比较。两种模式均限制候选原文与结构文本合计最多 6000 字符，提示词和元数据开销另计，因此这是字符预算匹配，不是精确 token 相等。新增 A/B 可见记录自动改变缓存键；晚于当前进度的记录不会进入该进度上下文。A/B 加载或向量检索发生降级时不缓存本次结果，以便服务恢复后重新尝试。

公共 knowledge 接口每批 records 为 1–500 条；空列表不发送请求。未知扩展字段会被拒绝，A/B 的事件图、置信度、实体布局等保留在自身数据中。接口没有删除或撤回知识记录的操作；错误数据修订需另行设计，不得用未来版本掩盖早期错误。
