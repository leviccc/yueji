const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

const state = {
  book: localStorage.getItem("yueji.book") || null,
  books: [],
  preview: null,
  characters: [],
  graphData: null,
  visibleProgress: 1,
  jobTimer: null,
  progressWrites: Promise.resolve(),
};

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[ch]);
}

let toastTimer = null;
function toast(message, isError = false) {
  const node = $("#toast");
  node.textContent = message;
  node.classList.toggle("error", isError);
  node.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => node.classList.add("hidden"), 4200);
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const text = await response.text();
  let data = text;
  try { data = JSON.parse(text); } catch { /* 保留纯文本 */ }
  if (!response.ok) {
    const detail = data && data.detail ? (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail)) : response.status;
    throw new Error(detail);
  }
  return data;
}

function showTab(name) {
  $$("#tabs button").forEach((button) => button.classList.toggle("active", button.dataset.tab === name));
  $$(".tab").forEach((section) => section.classList.toggle("active", section.id === `tab-${name}`));
  if (name === "books") loadBooks();
  if (name === "review") loadCandidates();
  if (name === "graph") loadGraph();
  if (name === "merges") loadMerges();
  if (name === "settings") loadSettings();
  if (name === "extract") { loadBudgetLine(); loadJobs(); }
}

function currentBook() {
  if (!state.book) { toast("请先在「书目」里选择一本书", true); return null; }
  return state.book;
}

function chapterCount(bookId = state.book) {
  const book = state.books.find((item) => item.id === bookId);
  return book ? Math.max(book.chapters, 1) : 1;
}

function syncProgressInputs() {
  const max = chapterCount();
  for (const id of ["extract-progress", "extract-chapter", "review-progress", "graph-progress"]) {
    const input = $(`#${id}`);
    if (!input) continue;
    input.max = String(max);
    if (Number(input.value) > max) input.value = String(max);
    if (Number(input.value) < 1) input.value = "1";
  }
  setProgress(Number($("#graph-progress").value));
}

function clearReadingViews() {
  state.characters = [];
  state.graphData = null;
  $("#candidate-list").innerHTML = "";
  $("#graph-svg").innerHTML = "";
  $("#profiles").innerHTML = "";
  $("#relation-summary").innerHTML = "";
  $("#event-context").innerHTML = "";
  $("#order-list").innerHTML = "";
  $("#correction-list").innerHTML = "";
  $("#graph-edges tbody").innerHTML = "";
  $("#merge-table tbody").innerHTML = "";
  $("#extract-result").textContent = "";
  $("#extract-result").classList.add("hidden");
  $("#job-list").innerHTML = "";
  $("#rejections-list").innerHTML = "";
  $("#manual-reading").innerHTML = "";
  for (const field of $$(".manual-entry input:not([type=number])")) field.value = "";
  for (const id of ["order-before", "order-after", "order-paragraph", "order-quote", "correction-id", "correction-paragraph", "correction-quote", "correction-reason", "merge-source", "merge-target", "merge-paragraph", "merge-quote"]) {
    const field = $(`#${id}`);
    if (field) field.value = "";
  }
}

function setProgress(value) {
  const progress = Math.max(1, Math.min(chapterCount(), Number(value) || 1));
  if (state.visibleProgress !== progress) clearReadingViews();
  state.visibleProgress = progress;
  for (const id of ["extract-progress", "review-progress", "graph-progress", "merge-progress"]) {
    const input = $(`#${id}`);
    if (input) input.value = String(progress);
  }
  const label = $("#graph-progress-label");
  if (label) label.textContent = String(progress);
}

async function loadSavedProgress(book) {
  if (!book) return;
  const data = await api(`/books/${encodeURIComponent(book)}/reading-progress`);
  if (state.book === book) setProgress(data.chapter);
}

function persistProgress(book, progress) {
  const write = state.progressWrites.catch(() => {}).then(() => api(`/books/${encodeURIComponent(book)}/reading-progress`,{
    method:"PUT", headers:{"Content-Type":"application/json"}, body:JSON.stringify({chapter:progress})
  }));
  state.progressWrites = write;
  return write;
}

async function changeProgress(value) {
  const book=state.book;
  setProgress(value);
  if (!book) return false;
  const progress=state.visibleProgress;
  try {
    await persistProgress(book,progress);
    return state.book === book && state.visibleProgress === progress;
  } catch(error) {
    if (state.book === book && state.visibleProgress === progress) {
      toast(`保存阅读进度失败：${error.message}`,true);
      try { await loadSavedProgress(book); } catch (_) { /* 保留错误提示 */ }
    }
    return false;
  }
}

/* ---------- 书目 ---------- */

async function loadBooks() {
  try {
    const data = await api("/books");
    state.books = data.books;
    const select = $("#book-select");
    const options = ['<option value="">（未选择）</option>'];
    for (const book of state.books) {
      options.push(`<option value="${esc(book.id)}">${esc(book.title)}（${esc(book.id)}）</option>`);
    }
    select.innerHTML = options.join("");
    if (state.book && state.books.some((book) => book.id === state.book)) {
      select.value = state.book;
    } else {
      state.book = null;
      select.value = "";
    }
    renderBooksTable();
    syncProgressInputs();
    if (state.book) await loadSavedProgress(state.book);
  } catch (error) {
    toast(`加载书目失败：${error.message}`, true);
  }
}

function renderBooksTable() {
  const body = $("#books-table tbody");
  if (!state.books.length) {
    body.innerHTML = '<tr><td colspan="5" class="hint">还没有书目，去「导入」标签页添加。</td></tr>';
    return;
  }
  body.innerHTML = state.books.map((book) => `
    <tr>
      <td><code>${esc(book.id)}</code></td>
      <td>${esc(book.title)}</td>
      <td>${book.chapters}</td>
      <td>${book.paragraphs}</td>
      <td>${book.id === state.book ? '<span class="badge">当前</span>' : `<button data-use="${esc(book.id)}" type="button">设为当前</button>`}</td>
    </tr>`).join("");
  $$("button[data-use]").forEach((button) => {
    button.onclick = async () => {
      clearReadingViews();
      state.book = button.dataset.use;
      $("#graph-progress").value = "1";
      localStorage.setItem("yueji.book", state.book);
      $("#book-select").value = state.book;
      renderBooksTable();
      syncProgressInputs();
      try { await loadSavedProgress(state.book); } catch (error) { toast(`加载阅读进度失败：${error.message}`,true); return; }
      toast(`当前书目：${state.book}`);
    };
  });
}

/* ---------- 导入 ---------- */

async function previewFrom(body) {
  const data = await api("/books/preview-txt", {
    method: "POST",
    headers: { "Content-Type": "application/octet-stream" },
    body,
  });
  state.preview = data;
  if (data.unassigned_paragraphs.length) {
    data.chapters.unshift({title: "前言", paragraphs: data.unassigned_paragraphs});
  }
  if (!data.chapters.length) data.chapters.push({title: "第一章", paragraphs: []});
  $("#preview-area").classList.remove("hidden");
  $("#preview-status").textContent = `编码 ${data.encoding}，识别 ${data.chapters.length} 章`;
  const warning = $("#needs-review");
  if (data.needs_review) {
    warning.classList.remove("hidden");
    const notes = [];
    if (data.unassigned_paragraphs.length) notes.push(`有 ${data.unassigned_paragraphs.length} 段落在第一个章节标题之前`);
    if (data.chapters.some((chapter) => !chapter.paragraphs.length)) notes.push("存在空章节");
    warning.textContent = `需要人工检查：${notes.join("；") || "章节标题可能是普通数字"}`;
  } else {
    warning.classList.add("hidden");
  }
  renderPreviewChapters();
}

function readPreviewChapters() {
  return state.preview.chapters.map((chapter,index) => ({
    title: $(`input[data-title="${index}"]`).value.trim() || chapter.title,
    paragraphs: $(`textarea[data-paragraphs="${index}"]`).value.split(/\r?\n/).filter((line) => line.trim()),
  }));
}

function renderPreviewChapters() {
  $("#preview-chapters").innerHTML = state.preview.chapters.map((chapter,index) => `
    <div class="chapter-block">
      <div class="chapter-head">
        <span class="badge">第 ${index + 1} 章</span>
        <input data-title="${index}" type="text" value="${esc(chapter.title)}">
        <span class="count">${chapter.paragraphs.length} 段</span>
      </div>
      <label>章节正文（每行一段）<textarea data-paragraphs="${index}" rows="5">${esc(chapter.paragraphs.join("\n"))}</textarea></label>
      <div class="row"><button type="button" data-split="${index}">从光标处分章</button>${index < state.preview.chapters.length - 1 ? `<button type="button" data-merge-next="${index}">与下一章合并</button>` : ""}</div>
    </div>`).join("");
  $$("button[data-split]").forEach((button) => {
    button.onclick = () => {
      const index = Number(button.dataset.split);
      const textarea = $(`textarea[data-paragraphs="${index}"]`);
      const at = textarea.selectionStart;
      const before = textarea.value.slice(0, at);
      const after = textarea.value.slice(at);
      if (!before.trim() || !after.trim()) { toast("请先将光标放到要拆分的位置，保证前后都有正文",true); return; }
      const chapters = readPreviewChapters();
      chapters[index].paragraphs = before.split(/\r?\n/).filter((line) => line.trim());
      chapters.splice(index + 1,0,{title:"新章节",paragraphs:after.split(/\r?\n/).filter((line) => line.trim())});
      state.preview.chapters = chapters;
      renderPreviewChapters();
    };
  });
  $$("button[data-merge-next]").forEach((button) => {
    button.onclick = () => {
      const index = Number(button.dataset.mergeNext);
      const chapters = readPreviewChapters();
      // Retain the following title as text so merging does not silently discard content.
      chapters[index].paragraphs.push(chapters[index + 1].title, ...chapters[index + 1].paragraphs);
      chapters.splice(index + 1,1);
      state.preview.chapters = chapters;
      renderPreviewChapters();
    };
  });
}

async function doPreview() {
  const file = $("#import-file").files[0];
  const text = $("#import-text").value;
  try {
    if (file) {
      await previewFrom(await file.arrayBuffer());
    } else if (text.trim()) {
      await previewFrom(new TextEncoder().encode(text));
    } else {
      toast("请选择文件或粘贴正文", true);
    }
  } catch (error) {
    toast(`预览失败：${error.message}`, true);
  }
}

async function confirmImport() {
  if (!state.preview) { toast("请先预览分章", true); return; }
  const id = $("#import-id").value.trim();
  const title = $("#import-title").value.trim();
  if (!id || !title) { toast("请填写编号和书名", true); return; }
  const chapters = readPreviewChapters();
  try {
    const result = await api("/books/confirmed", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id, title, chapters }),
    });
    toast(`已导入《${title}》：${result.chapter_count} 章`);
    state.book = id;
    localStorage.setItem("yueji.book", id);
    state.preview = null;
    $("#preview-area").classList.add("hidden");
    $("#import-text").value = "";
    $("#import-file").value = "";
    await loadBooks();
    $("#book-select").value = id;
    showTab("extract");
  } catch (error) {
    toast(`导入失败：${error.message}`, true);
  }
}

/* ---------- 抽取 ---------- */

async function loadBudgetLine() {
  try {
    const [data, model] = await Promise.all([api("/settings/call-budget"),api("/settings/model-status")]);
    const configured=model.error || `${model.provider} / ${model.model}：${model.key_configured ? "已检测到密钥（有效性尚未验证）" : "未检测到密钥"}`;
    $("#budget-line").textContent = `${configured}；调用记录：已用 ${data.used_calls} 次，上限 ${data.max_calls} 次，剩余 ${Math.max(0,data.max_calls-data.used_calls)} 次。`;
  } catch (error) {
    $("#budget-line").textContent = `预算信息不可用：${error.message}`;
  }
}

async function runExtract() {
  await createJob(true);
}

async function estimateExtraction() {
  const book = currentBook();
  if (!book) return;
  const start = Number($("#extract-chapter").value), progress = Number($("#extract-progress").value);
  if (!Number.isInteger(start) || start < 1 || start > progress) { toast("起始章节不能超过阅读进度", true); return; }
  const panel = $("#estimate-line");
  panel.textContent = "正在计算分块……";
  try {
    await state.progressWrites;
    const data = await api(`/books/${encodeURIComponent(book)}/extraction-estimate?start_chapter=${start}&progress_chapter=${progress}`);
    if (book !== state.book || start !== Number($("#extract-chapter").value) || progress !== Number($("#extract-progress").value)) { panel.textContent = ""; return; }
    panel.textContent = `第 ${start}—${progress} 章共 ${data.batch_count} 个分块。没有缓存时约需同样次数的请求；缓存可减少请求，失败重试可能增加次数。具体费用以服务商账单为准。`;
  } catch (error) { panel.textContent = ""; toast(`预估失败：${error.message}`, true); }
}

async function loadJobs() {
  clearTimeout(state.jobTimer);
  const book = state.book;
  if (!book || !$("#tab-extract").classList.contains("active")) return;
  const progress = Number($("#extract-progress").value);
  try {
    const data = await api(`/books/${encodeURIComponent(book)}/extraction-jobs?progress_chapter=${progress}`);
    if (book !== state.book || progress !== Number($("#extract-progress").value) || !$("#tab-extract").classList.contains("active")) return;
    const names={queued:"排队中",running:"分析中",completed:"完成",failed:"失败",cancelled:"已停止",interrupted:"服务中断"};
    $("#job-list").innerHTML = data.jobs.length ? data.jobs.map((job) => `<div class="candidate"><strong>第 ${esc(job.start_chapter)}—${esc(job.end_chapter)} 章 · ${esc(names[job.status] || job.status)}</strong><p class="hint">已处理 ${esc(Math.max(0, Math.min(job.end_chapter,job.next_chapter-1)-job.start_chapter+1))} / ${esc(job.end_chapter-job.start_chapter+1)} 章${job.cancel_requested && job.status === "running" ? "（正在停止）" : ""}${job.error ? ` · ${esc(job.error)}` : ""}</p>${["queued","running"].includes(job.status) ? `<button data-job-action="cancel" data-job-id="${esc(job.id)}">停止</button>` : ["failed","cancelled","interrupted"].includes(job.status) && job.next_chapter <= job.end_chapter ? `<button data-job-action="retry" data-job-id="${esc(job.id)}">重试</button>` : ""}</div>`).join("") : '<p class="hint">当前进度没有分析任务。</p>';
    $$("#job-list button[data-job-action]").forEach((button) => { button.onclick = () => changeJob(button.dataset.jobId,button.dataset.jobAction); });
    loadBudgetLine();
    if (data.jobs.some((job) => ["queued","running"].includes(job.status))) state.jobTimer = setTimeout(loadJobs,2000);
  } catch(error) { toast(`加载任务失败：${error.message}`,true); }
}

async function loadRejections() {
  const book=currentBook();
  if (!book) return;
  const progress=Number($("#extract-progress").value);
  const panel=$("#rejections-list");
  panel.textContent="正在加载……";
  try {
    const data=await api(`/books/${encodeURIComponent(book)}/extraction-rejections?progress_chapter=${progress}`);
    if (book !== state.book || progress !== Number($("#extract-progress").value)) return;
    panel.innerHTML=data.rejected.length ? data.rejected.map((item) => `<div class="candidate"><div class="meta">第 ${esc(item.chapter)} 章 · ${esc(item.kind)}</div><div class="warnings">${esc(item.reason)}</div><div class="payload">${esc(JSON.stringify(item.record,null,1))}</div></div>`).join("") : '<p class="hint">当前进度没有记录到未通过项。</p>';
  } catch(error) { panel.textContent=""; toast(`加载未通过项失败：${error.message}`,true); }
}

async function createJob(singleChapter = false) {
  const book=currentBook();
  if (!book) return;
  const start=Number($("#extract-chapter").value), progress=Number($("#extract-progress").value);
  const end=singleChapter ? start : progress;
  if (!Number.isInteger(start) || start<1 || start>progress) { toast("起始章节不能超过阅读进度",true); return; }
  try {
    await state.progressWrites;
    if (state.book !== book || Number($("#extract-progress").value) !== progress) return;
    const created=await api(`/books/${encodeURIComponent(book)}/extraction-jobs`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({start_chapter:start,end_chapter:end,progress_chapter:progress})});
    if (state.book !== book || Number($("#extract-progress").value) < end) {
      await api(`/books/${encodeURIComponent(book)}/extraction-jobs/${encodeURIComponent(created.id)}/cancel?progress_chapter=${progress}`,{method:"POST"}).catch(() => {});
      toast("阅读进度已改变，已请求停止任务");
      return;
    }
    toast("已创建分析任务");
    await loadJobs();
  } catch(error) { toast(`创建任务失败：${error.message}`,true); }
}

async function changeJob(id,action) {
  const book=currentBook();
  if (!book) return;
  const progress=Number($("#extract-progress").value);
  try {
    await api(`/books/${encodeURIComponent(book)}/extraction-jobs/${encodeURIComponent(id)}/${action}?progress_chapter=${progress}`,{method:"POST"});
    toast(action === "cancel" ? "已请求停止" : "已请求重试");
    await loadJobs();
  } catch(error) { toast(`任务操作失败：${error.message}`,true); }
}

/* ---------- 复核 ---------- */

function matchingCharacters(name, people) {
  return people.filter((person) => person.name === name || (person.aliases || []).includes(name));
}

function resolveCharacterId(name, people) {
  const matches = matchingCharacters(name, people);
  return matches.length === 1 ? matches[0].id : "";
}

function candidateDescription(candidate) {
  const p = candidate.payload;
  const field = (label, value) => `<div><strong>${esc(label)}：</strong>${esc(value)}</div>`;
  let details;
  if (candidate.kind === "person") {
    details = field("人物称谓", p.name);
  } else if (candidate.kind === "relation") {
    details = field("关系", `${p.source} ${p.directed ? "→" : "↔"} ${p.target}：${p.relation}`)
      + field("记录性质", p.action === "end" ? "关系结束" : "关系记录")
      + field("方向", p.directed ? "单向" : "双向");
  } else {
    const assertionLabels = {explicit:"原文陈述",claim:"角色声称",inference:"解释性推断"};
    details = field("人物", p.person) + field("类别", p.category) + field("内容", p.content)
      + field("陈述性质", assertionLabels[p.assertion_type] || p.assertion_type);
  }
  return details + field("证据段落", p.paragraph_id) + field("原文引文", p.quote);
}

async function loadCandidates() {
  const book = currentBook();
  if (!book) return;
  const progress = Number($("#review-progress").value);
  const status = $("#review-status").value;
  $("#candidate-list").innerHTML = '<p class="hint">正在加载当前进度的候选。</p>';
  state.characters = [];
  try {
    const [candidateData, characterData, factData] = await Promise.all([
      api(`/books/${encodeURIComponent(book)}/candidates?progress_chapter=${progress}`),
      api(`/books/${encodeURIComponent(book)}/characters?progress_chapter=${progress}`),
      api(`/books/${encodeURIComponent(book)}/profile-candidates?progress_chapter=${progress}`),
    ]);
    if (book !== state.book || progress !== Number($("#review-progress").value) || status !== $("#review-status").value) return;
    state.characters = characterData.characters;
    const pending = [...candidateData.candidates, ...factData.candidates].filter((candidate) => candidate.status === status).sort((a,b) => a.chapter-b.chapter);
    const list = $("#candidate-list");
    if (!pending.length) {
      const statusLabel = {pending:"待复核",accepted:"已接受",rejected:"已拒绝"}[status] || status;
      list.innerHTML = `<p class="hint">进度 ${progress} 下没有${esc(statusLabel)}候选。</p>`;
      return;
    }
    // 按候选证据章节解析身份，而不是使用后面章节才合并的称谓。
    const chapters = [...new Set(pending.map((candidate) => candidate.chapter))];
    const charactersAt = new Map([[progress, characterData.characters]]);
    for (let i = 0; i < chapters.length; i += 8) {
      const group = chapters.slice(i,i+8).filter((chapter) => !charactersAt.has(chapter));
      const snapshots = await Promise.all(group.map((chapter) => api(`/books/${encodeURIComponent(book)}/characters?progress_chapter=${chapter}`)));
      if (book !== state.book || progress !== Number($("#review-progress").value) || status !== $("#review-status").value) return;
      group.forEach((chapter,index) => charactersAt.set(chapter,snapshots[index].characters));
    }
    list.innerHTML = pending.map((candidate) => {
      const payload = candidate.payload;
      const people = charactersAt.get(candidate.chapter) || [];
      const namesToResolve = candidate.kind === "fact" ? [payload.person] : candidate.kind === "relation" ? [payload.source,payload.target] : [];
      const ambiguous = [...new Set(namesToResolve)].filter((name) => matchingCharacters(name,people).length > 1);
      const ambiguityNotice = ambiguous.map((name) => `称谓「${name}」可能指多个人：${matchingCharacters(name,people).map((person) => `${person.name}（${person.id}）`).join("、")}；请核对原文后手动选择编号。`);
      const linkOptions = ['<option value="">选择已有人物</option>']
        .concat(state.characters.map((person) => `<option value="${esc(person.id)}">${esc(person.name)}（${esc(person.id)}）</option>`))
        .join("");
      const actions = status === "accepted" ? '<span class="hint">已接受；可在“图谱”查看实际写入的记录。</span>' : status === "rejected" ? `<button data-act="${candidate.kind === "fact" ? "reopen-fact" : "reopen"}" data-id="${esc(candidate.id)}" type="button">重新复核</button>` : candidate.kind === "person"
        ? `<input data-field="person" placeholder="新人物编号，如 lin">
           <label>更早出现的段落（可选）<input data-field="earlier-paragraph" placeholder="如 ch0001_p0001" title="仅在核对原文后，确认是同一人物时填写"></label>
           <button data-act="accept-person" data-id="${esc(candidate.id)}" type="button">接受为新人物</button>
           <select data-field="link">${linkOptions}</select>
           <input data-field="identity-paragraph" placeholder="身份揭示的段落编号">
           <input data-field="identity-quote" placeholder="身份揭示的逐字引文">
           <button data-act="link-person" data-id="${esc(candidate.id)}" type="button">关联到已有人物</button>
           <button data-act="reject" data-id="${esc(candidate.id)}" type="button" class="danger">拒绝</button>`
        : candidate.kind === "fact" ? `<input data-field="person" placeholder="人物 ID" value="${esc(resolveCharacterId(payload.person,people))}">
           <label>类别 <input data-field="fact-category" value="${esc(payload.category)}"></label>
           <label>内容 <input data-field="fact-content" value="${esc(payload.content)}"></label>
           <label>陈述性质 <select data-field="fact-assertion"><option value="explicit" ${payload.assertion_type === "explicit" ? "selected" : ""}>原文陈述</option><option value="claim" ${payload.assertion_type === "claim" ? "selected" : ""}>角色声称</option><option value="inference" ${payload.assertion_type === "inference" ? "selected" : ""}>解释性推断</option></select></label>
           <button data-act="accept-fact" data-id="${esc(candidate.id)}" type="button">接受人物事实</button>
           <button data-act="reject-fact" data-id="${esc(candidate.id)}" type="button" class="danger">拒绝</button>`
        : `<input data-field="source" placeholder="源人物 ID" value="${esc(resolveCharacterId(payload.source,people))}">
           <input data-field="target" placeholder="目标人物 ID" value="${esc(resolveCharacterId(payload.target,people))}">
           <label>关系名称 <input data-field="relation" value="${esc(payload.relation)}"></label>
           <label>方向 <select data-field="directed"><option value="true" ${payload.directed ? "selected" : ""}>单向</option><option value="false" ${payload.directed ? "" : "selected"}>双向</option></select></label>
           <label>性质 <select data-field="relation-action"><option value="assert" ${payload.action === "assert" ? "selected" : ""}>关系记录</option><option value="end" ${payload.action === "end" ? "selected" : ""}>关系结束</option></select></label>
           <button data-act="accept-relation" data-id="${esc(candidate.id)}" type="button">接受关系</button>
           <button data-act="reject" data-id="${esc(candidate.id)}" type="button" class="danger">拒绝</button>`;
      return `<div class="candidate">
        <div class="meta"><span class="badge ${candidate.kind}">${candidate.kind === "person" ? "人物" : candidate.kind === "fact" ? "人物事实" : "关系"}</span> 第 ${candidate.chapter} 章 · ${esc(candidate.id.slice(0, 8))}</div>
        <div class="payload">${candidateDescription(candidate)}</div>
        ${candidate.warnings.length || ambiguityNotice.length ? `<div class="warnings">${[...candidate.warnings,...ambiguityNotice].map(esc).join("<br>")}</div>` : ""}
        <button data-context="${esc(payload.paragraph_id)}" type="button">查看原文上下文</button>
        <div class="candidate-context hidden"></div>
        <div class="actions">${actions}</div>
      </div>`;
    }).join("");
    $$("#candidate-list button[data-act]").forEach((button) => {
      button.onclick = () => reviewAction(button, progress);
    });
    $$("#candidate-list button[data-context]").forEach((button) => {
      button.onclick = async () => {
        const panel = button.nextElementSibling;
        if (!panel.classList.contains("hidden")) { panel.classList.add("hidden"); button.textContent = "查看原文上下文"; return; }
        button.disabled = true;
        try {
          const data = await api(`/books/${encodeURIComponent(book)}/paragraphs/${encodeURIComponent(button.dataset.context)}/context?progress_chapter=${progress}`);
          if (book !== state.book || progress !== Number($("#review-progress").value) || !button.isConnected) return;
          panel.innerHTML = data.paragraphs.map((p) => `<p${p.id === data.target_id ? ' class="evidence-target"' : ""}><strong>${esc(p.id)}</strong> ${esc(p.text)}</p>`).join("");
          panel.classList.remove("hidden");
          button.textContent = "收起原文上下文";
        } catch (error) { toast(`加载原文失败：${error.message}`, true); }
        finally { button.disabled = false; }
      };
    });
  } catch (error) {
    toast(`加载候选失败：${error.message}`, true);
  }
}

async function reviewAction(button, progress) {
  const book = currentBook();
  if (!book) return;
  const kind = button.dataset.act;
  const candidateId = button.dataset.id;
  const card = button.closest(".candidate");
  if (kind === "reopen" || kind === "reopen-fact") {
    button.disabled = true;
    try {
      const path=kind === "reopen-fact" ? "profile-candidates" : "candidates";
      await api(`/books/${encodeURIComponent(book)}/${path}/${encodeURIComponent(candidateId)}/reopen?progress_chapter=${progress}`,{method:"POST"});
      toast("已移回待复核");
      await loadCandidates();
    } catch (error) { toast(`重新复核失败：${error.message}`,true); button.disabled=false; }
    return;
  }
  const body = { action: kind === "reject" || kind === "reject-fact" ? "reject" : "accept" };
  if (kind === "accept-fact") {
    body.person_id = card.querySelector('[data-field="person"]').value.trim();
    if (!body.person_id) { toast("请填写人物 ID", true); return; }
    body.category = card.querySelector('[data-field="fact-category"]').value.trim();
    body.content = card.querySelector('[data-field="fact-content"]').value.trim();
    body.assertion_type = card.querySelector('[data-field="fact-assertion"]').value;
    if (!body.category || !body.content) { toast("请填写人物事实的类别和内容", true); return; }
  }
  if (kind === "accept-person") {
    body.person_id = card.querySelector('[data-field="person"]').value.trim();
    if (!body.person_id) { toast("请填写新人物编号", true); return; }
    const earlier = card.querySelector('[data-field="earlier-paragraph"]').value.trim();
    if (earlier) body.earlier_paragraph_id = earlier;
  }
  if (kind === "link-person") {
    body.link_to_person_id = card.querySelector('[data-field="link"]').value;
    if (!body.link_to_person_id) { toast("请选择要关联的人物", true); return; }
    body.identity_paragraph_id = card.querySelector('[data-field="identity-paragraph"]').value.trim();
    body.identity_quote = card.querySelector('[data-field="identity-quote"]').value.trim();
    if (!body.identity_paragraph_id || !body.identity_quote) { toast("请填写身份揭示的证据段落和引文",true); return; }
  }
  if (kind === "accept-relation") {
    body.source_id = card.querySelector('[data-field="source"]').value.trim();
    body.target_id = card.querySelector('[data-field="target"]').value.trim();
    if (!body.source_id || !body.target_id) { toast("请填写关系双方的人物 ID", true); return; }
    body.relation = card.querySelector('[data-field="relation"]').value.trim();
    body.directed = card.querySelector('[data-field="directed"]').value === "true";
    body.relation_action = card.querySelector('[data-field="relation-action"]').value;
    if (!body.relation) { toast("请填写关系名称", true); return; }
  }
  button.disabled = true;
  try {
    const candidateType = kind === "accept-fact" || kind === "reject-fact" ? "profile-candidates" : "candidates";
    await api(`/books/${encodeURIComponent(book)}/${candidateType}/${encodeURIComponent(candidateId)}/review?progress_chapter=${progress}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    toast(body.action === "reject" ? "已拒绝" : "已接受");
    loadCandidates();
  } catch (error) {
    toast(`复核失败：${error.message}`, true);
    button.disabled = false;
  }
}

/* ---------- 图谱 ---------- */

async function loadGraph() {
  const book = currentBook();
  if (!book) return;
  const progress = Number($("#graph-progress").value);
  $("#graph-progress-label").textContent = progress;
  $("#graph-svg").innerHTML = "";
  $("#profiles").innerHTML = "";
  $("#relation-summary").innerHTML = "";
  $("#event-context").innerHTML = "";
  $("#order-list").innerHTML = "";
  $("#correction-list").innerHTML = "";
  $("#graph-edges tbody").innerHTML = "";
  try {
    const [data, summary, orders, corrections, eventContext, integrationCorrections, personCorrections] = await Promise.all([
      api(`/books/${encodeURIComponent(book)}/characters?progress_chapter=${progress}`),
      api(`/books/${encodeURIComponent(book)}/relationships/summary?progress_chapter=${progress}`),
      api(`/books/${encodeURIComponent(book)}/relationship-orders?progress_chapter=${progress}`),
      api(`/books/${encodeURIComponent(book)}/record-corrections?progress_chapter=${progress}`),
      api(`/books/${encodeURIComponent(book)}/event-context?progress_chapter=${progress}`),
      api(`/books/${encodeURIComponent(book)}/integration-corrections?progress_chapter=${progress}`),
      api(`/books/${encodeURIComponent(book)}/person-corrections?progress_chapter=${progress}`),
    ]);
    if (book !== state.book || progress !== Number($("#graph-progress").value)) return;
    state.graphData = data;
    renderGraph(data);
    renderProfiles(data.characters);
    renderRelationSummary(summary.states, data.characters, orders.constraints);
    renderCorrections([...corrections.corrections,...integrationCorrections.corrections,...personCorrections.corrections].sort((a,b) => a.known_chapter-b.known_chapter));
    renderEventContext(eventContext);
  } catch (error) {
    toast(`加载图谱失败：${error.message}`, true);
  }
}

function renderGraph(data) {
  const svg = $("#graph-svg");
  const query = $("#graph-filter").value.trim().toLocaleLowerCase();
  const selected = new Set(data.characters.filter((node) => [node.name,...(node.aliases || [])].some((name) => name.toLocaleLowerCase().includes(query))).map((node) => node.id));
  const shown = new Set(selected);
  if (query) for (const edge of data.edges) {
    if (selected.has(edge.source_id) || selected.has(edge.target_id)) { shown.add(edge.source_id); shown.add(edge.target_id); }
  }
  const nodes = query ? data.characters.filter((node) => shown.has(node.id)) : data.characters;
  const edges = query ? data.edges.filter((edge) => selected.has(edge.source_id) || selected.has(edge.target_id)) : data.edges;
  $("#graph-filter-info").textContent = query ? `匹配 ${selected.size} 人；图中显示 ${nodes.length} 人、${edges.length} 条直接关系。人物档案和关系状态仍显示全部。` : "筛选图谱及关系表，保留直接相连的人物。";
  $("#graph-empty").textContent = query ? "没有匹配的人物，请尝试其他姓名或称谓。" : "当前进度还没有人物，先抽取并复核候选。";
  $("#graph-empty").classList.toggle("hidden", nodes.length > 0);
  const width = 900, height = 520;
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  if (!nodes.length) { svg.innerHTML = ""; renderEdgeTable([], nodes); return; }
  const cx = width / 2, cy = height / 2;
  const radius = Math.max(120, Math.min(width, height) / 2 - 80);
  const positions = {};
  nodes.forEach((node, index) => {
    const angle = -Math.PI / 2 + (index * 2 * Math.PI) / nodes.length;
    positions[node.id] = { x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle) };
  });
  let markup = `<defs><marker id="arrow" viewBox="0 0 10 10" refX="32" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8"></path></marker></defs>`;
  const pairGroups = new Map();
  const pairKey = (edge) => JSON.stringify([edge.source_id,edge.target_id].sort());
  for (const edge of edges) {
    const key = pairKey(edge);
    if (!pairGroups.has(key)) pairGroups.set(key,[]);
    pairGroups.get(key).push(edge);
  }
  for (const edge of edges) {
    const from = positions[edge.source_id], to = positions[edge.target_id];
    if (!from || !to) continue;
    const group=pairGroups.get(pairKey(edge)), index=group.indexOf(edge);
    const marker=edge.directed ? 'marker-end="url(#arrow)"' : "";
    let path, labelX, labelY;
    if (edge.source_id === edge.target_id) {
      const rise=65+index*28;
      path=`M ${from.x-18} ${from.y-19} C ${from.x-80} ${from.y-rise}, ${from.x+80} ${from.y-rise}, ${from.x+18} ${from.y-19}`;
      labelX=from.x; labelY=from.y-rise*0.72-6;
    } else {
      const dx=to.x-from.x, dy=to.y-from.y, length=Math.hypot(dx,dy) || 1;
      const direction=edge.source_id < edge.target_id ? 1 : -1;
      const offset=(index-(group.length-1)/2)*44*direction;
      const mx=(from.x+to.x)/2, my=(from.y+to.y)/2;
      const controlX=mx-dy/length*offset, controlY=my+dx/length*offset;
      path=`M ${from.x} ${from.y} Q ${controlX} ${controlY} ${to.x} ${to.y}`;
      const t=Math.max(0.15,Math.min(0.85,0.5+(index-(group.length-1)/2)*0.095*direction));
      labelX=(1-t)*(1-t)*from.x+2*(1-t)*t*controlX+t*t*to.x;
      labelY=(1-t)*(1-t)*from.y+2*(1-t)*t*controlY+t*t*to.y-6;
    }
    markup += `<path d="${path}" fill="none" stroke="#94a3b8" stroke-width="1.4" ${marker}></path>`;
    markup += `<text x="${labelX}" y="${labelY}" text-anchor="middle" font-size="12" fill="#475569" stroke="white" stroke-width="3" paint-order="stroke">${esc(edge.relation)}${edge.action === "end" ? "（结束）" : ""}</text>`;
  }
  for (const node of nodes) {
    const point = positions[node.id];
    const aliases = (node.aliases || []).length ? `<tspan x="${point.x}" dy="15" font-size="11" fill="#64748b">${esc(node.aliases.join(" / "))}</tspan>` : "";
    markup += `<g class="node">
      <circle cx="${point.x}" cy="${point.y}" r="27" fill="#eaf1ff" stroke="#2f6fed" stroke-width="1.6"></circle>
      <text x="${point.x}" y="${point.y + 5}" text-anchor="middle" font-size="13" fill="#1f2430">${esc(node.name)}${aliases}</text>
    </g>`;
  }
  svg.innerHTML = markup;
  renderEdgeTable(edges, nodes);
}

function renderEdgeTable(edges, nodes) {
  const body = $("#graph-edges tbody");
  if (!edges.length) {
    body.innerHTML = '<tr><td colspan="7" class="hint">暂无关系。</td></tr>';
    return;
  }
  const nameOf = (id) => (nodes.find((node) => node.id === id) || { name: id }).name;
  body.innerHTML = edges.map((edge) => `
    <tr>
      <td>${esc(edge.id)}</td>
      <td>${esc(nameOf(edge.source_id))}</td>
      <td>${esc(edge.relation)}（${edge.action === "end" ? "结束" : "记录"}）</td>
      <td>${esc(nameOf(edge.target_id))}</td>
      <td>${edge.directed ? "有向" : "无向"}${edge.direction_warning ? `<br><span class="hint">${esc(edge.direction_warning)}</span>` : ""}</td>
      <td>${edge.known_chapter}</td>
      <td class="hint">${esc(edge.paragraph_id)}${edge.quote ? `<br>引文：${esc(edge.quote)}` : `<br>旧记录未保存单独引文<br><input data-evidence-quote="${esc(edge.id)}" placeholder="核对后填写逐字引文"><button type="button" data-evidence-submit="${esc(edge.id)}">补充引文</button>`}<br>${esc(edge.evidence_text || "")}</td>
    </tr>`).join("");
  $$("#graph-edges button[data-evidence-submit]").forEach((button) => {
    button.onclick=async () => {
      const book=currentBook();
      if (!book) return;
      const id=button.dataset.evidenceSubmit;
      const quote=button.parentElement.querySelector("input[data-evidence-quote]").value.trim();
      const progress=Number($("#graph-progress").value);
      if (!quote) { toast("请填写并核对逐字引文",true); return; }
      button.disabled=true;
      try {
        await state.progressWrites;
        if (book !== state.book || progress !== Number($("#graph-progress").value)) return;
        await api(`/books/${encodeURIComponent(book)}/relationships/${encodeURIComponent(id)}/evidence?progress_chapter=${progress}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({quote})});
        toast("已补充引文");
        await loadGraph();
      } catch(error) { toast(`补充引文失败：${error.message}`,true); }
      finally { button.disabled=false; }
    };
  });
}

function renderProfiles(nodes) {
  const labels = {explicit:"原文陈述",claim:"角色声称",inference:"解释性推断"};
  $("#profiles").innerHTML = nodes.length ? nodes.map((node) => {
    const names=(node.name_evidence || []).map((item) => `<p>称谓「${esc(item.name)}」· 第 ${esc(item.known_chapter)} 章 · ${esc(item.paragraph_id)}<br>${esc(item.evidence_text)}${item.identity_quote ? `<br>身份关联引文：${esc(item.identity_quote)}` : ""}</p>`).join("");
    const identities=(node.identity_evidence || []).map((item) => `<p>身份关联 ${esc(item.source_id)} → ${esc(item.target_id)} · 第 ${esc(item.known_chapter)} 章 · ${esc(item.paragraph_id)}<br>引文：${esc(item.quote)}</p>`).join("");
    const evidence=`<details class="hint"><summary>查看称谓与身份依据</summary><p>称谓出现本身不证明两个称谓是同一人；身份关联依据需要人工核对。</p>${names}${identities || "<p>暂无通过人物合并记录保存的身份关联依据。</p>"}</details>`;
    const facts=(node.facts || []).length ? (node.facts || []).map((fact) => `<p>${esc(fact.category)}：${esc(fact.content)} <span class="hint">[${esc(labels[fact.assertion_type] || fact.assertion_type)} · 第 ${esc(fact.known_chapter)} 章 · ${esc(fact.paragraph_id)} · 记录 ${esc(fact.id)}]</span><br><span class="hint">依据：${esc(fact.quote)}</span></p>`).join("") : '<p class="hint">暂无已复核的人物事实。</p>';
    return `<div class="candidate"><strong>${esc(node.name)}</strong> <span class="hint">编号：${esc(node.id)}</span>${node.aliases.length ? `（称谓：${esc(node.aliases.join("、"))}）` : ""}${evidence}${facts}</div>`;
  }).join("") : '<p class="hint">暂无人物档案。</p>';
}

async function submitManual(kind) {
  const book = currentBook();
  if (!book) return;
  const value = (id) => $(`#manual-${id}`).value.trim();
  const progress = Number($("#graph-progress").value);
  let endpoint, payload;
  if (kind === "person") {
    endpoint = "characters";
    payload = {id:value("person-id"),name:value("person-name"),paragraph_id:value("person-paragraph")};
  } else if (kind === "fact") {
    endpoint = "profile-facts";
    payload = {person_id:value("fact-person"),category:value("fact-category"),content:value("fact-content"),assertion_type:value("fact-type"),paragraph_id:value("fact-paragraph"),quote:value("fact-quote"),progress_chapter:progress};
  } else {
    endpoint = "relationships";
    payload = {source_id:value("relation-source"),target_id:value("relation-target"),relation:value("relation-label"),directed:value("relation-directed") === "true",action:value("relation-action"),paragraph_id:value("relation-paragraph"),quote:value("relation-quote")};
  }
  if (Object.values(payload).some((v) => v === "")) { toast("请填写该条记录的所有字段", true); return; }
  const button = $(`#manual-${kind}-submit`);
  button.disabled = true;
  try {
    await state.progressWrites;
    if (book !== state.book || progress !== Number($("#graph-progress").value)) return;
    await api(`/books/${encodeURIComponent(book)}/${endpoint}?progress_chapter=${progress}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
    toast("补录成功");
    await loadGraph();
  } catch (error) { toast(`补录失败：${error.message}`,true); }
  finally { button.disabled = false; }
}

async function loadManualReading() {
  const book = currentBook();
  if (!book) return;
  const progress = Number($("#graph-progress").value);
  const chapter = Number($("#manual-read-chapter").value);
  if (!Number.isInteger(chapter) || chapter < 1 || chapter > progress) { toast("请选择当前阅读进度内的章节",true); return; }
  const panel = $("#manual-reading");
  panel.textContent = "正在加载正文……";
  try {
    await state.progressWrites;
    const data = await api(`/books/${encodeURIComponent(book)}/chapters/${chapter}/paragraphs?progress_chapter=${progress}`);
    if (book !== state.book || progress !== Number($("#graph-progress").value) || chapter !== Number($("#manual-read-chapter").value)) return;
    panel.innerHTML = `<strong>${esc(data.title)}</strong>` + data.paragraphs.map((p) => `<p><code>${esc(p.id)}</code> ${esc(p.text)}</p>`).join("");
  } catch (error) { panel.textContent = ""; toast(`加载正文失败：${error.message}`,true); }
}

function renderEventContext(context) {
  const events = context.events.map((e) => `<p class="hint">事件 ${esc(e.event_id)}：${esc(e.summary)} · 第 ${esc(e.known_chapter)} 章 · 来源 ${esc(e.source)} · ${esc(e.quote)}</p>`);
  const orders = context.orders.map((o) => `<p class="hint">事件 ${esc(o.before_event_id)} 早于 ${esc(o.after_event_id)}（时序编号 ${esc(o.id)}） · 第 ${esc(o.known_chapter)} 章 · 来源 ${esc(o.source)} · ${esc(o.quote)}</p>`);
  const links = context.links.map((l) => `<p class="hint">关系记录 ${esc(l.relation_id)} 关联事件 ${esc(l.event_id)}（关联编号 ${esc(l.id)}） · 第 ${esc(l.known_chapter)} 章 · 来源 ${esc(l.source)} · ${esc(l.quote)}</p>`);
  $("#event-context").innerHTML = [...events,...orders,...links].join("") || '<p class="hint">暂无事件时序依据。</p>';
}

function renderCorrections(items) {
  const kindLabels={person:"人物",fact:"人物事实",relation:"关系",event:"事件",event_order:"事件时序",event_link:"事件关联",relation_order:"关系时序"};
  $("#correction-list").innerHTML = items.length ? items.map((item) => `<p class="hint">第 ${esc(item.known_chapter)} 章 · ${esc(kindLabels[item.target_kind] || item.target_kind)} ${esc(item.target_id)} · ${item.action === "retract" ? "撤回" : "恢复"}：${esc(item.reason)}（${esc(item.quote)}）</p>`).join("") : '<p class="hint">暂无修订记录。</p>';
}

async function submitRecordCorrection() {
  const book=currentBook();
  if (!book) return;
  const payload={target_kind:$("#correction-kind").value,target_id:$("#correction-id").value.trim(),action:$("#correction-action").value,paragraph_id:$("#correction-paragraph").value.trim(),quote:$("#correction-quote").value.trim(),reason:$("#correction-reason").value.trim(),progress_chapter:Number($("#graph-progress").value)};
  if (!payload.target_id || !payload.paragraph_id || !payload.quote || !payload.reason) { toast("请填写记录编号、依据和说明",true); return; }
  try {
    const endpoint = payload.target_kind === "person" ? "person-corrections" : ["relation","fact"].includes(payload.target_kind) ? "record-corrections" : "integration-corrections";
    const requestBody = payload.target_kind === "person" ? {person_id:payload.target_id,action:payload.action,paragraph_id:payload.paragraph_id,quote:payload.quote,reason:payload.reason,progress_chapter:payload.progress_chapter} : payload;
    await api(`/books/${encodeURIComponent(book)}/${endpoint}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(requestBody)});
    toast("已保存修订");
    await loadGraph();
  } catch(error) { toast(`保存失败：${error.message}`,true); }
}

function renderRelationSummary(states, nodes, constraints) {
  const nameOf = (id) => (nodes.find((node) => node.id === id) || {name:id}).name;
  const labels = {assert_evidence:"最近可排序证据为关系存在", end_evidence:"最近可排序证据为关系结束", unresolved:"先后未定或时间约束冲突"};
  $("#relation-summary").innerHTML = states.length ? states.map((state) => `<p>${esc(nameOf(state.source_id))} ${state.directed ? "→" : "—"} ${esc(nameOf(state.target_id))} · ${esc(state.relation)}：<strong>${esc(labels[state.status])}</strong>（记录 ${esc(state.record_ids.join("、"))}）</p>`).join("") : '<p class="hint">暂无关系记录。</p>';
  $("#order-list").innerHTML = constraints.length ? constraints.map((item) => `<p class="hint">记录 ${esc(item.before_id)} 早于 ${esc(item.after_id)}（时序编号 ${esc(item.id)}） · 第 ${esc(item.known_chapter)} 章 · ${esc(item.quote)}</p>`).join("") : '<p class="hint">暂无先后约束。</p>';
}

async function addRelationOrder() {
  const book = currentBook();
  if (!book) return;
  const payload = {before_id:Number($("#order-before").value), after_id:Number($("#order-after").value), paragraph_id:$("#order-paragraph").value.trim(), quote:$("#order-quote").value.trim(), progress_chapter:Number($("#graph-progress").value)};
  if (!payload.before_id || !payload.after_id || !payload.paragraph_id || !payload.quote) { toast("请填写关系编号和证据",true); return; }
  try {
    await api(`/books/${encodeURIComponent(book)}/relationship-orders`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
    toast("已保存时间依据");
    await loadGraph();
  } catch(error) { toast(`保存失败：${error.message}`,true); }
}

/* ---------- 合并 ---------- */

async function loadMerges() {
  const book = currentBook();
  if (!book) return;
  const progress = Number($("#merge-progress").value);
  $("#merge-table tbody").innerHTML = "";
  try {
    const data = await api(`/books/${encodeURIComponent(book)}/person-merges?progress_chapter=${progress}`);
    if (book !== state.book || progress !== Number($("#merge-progress").value)) return;
    const body = $("#merge-table tbody");
    if (!data.merges.length) {
      body.innerHTML = '<tr><td colspan="6" class="hint">还没有合并记录。</td></tr>';
      return;
    }
    body.innerHTML = data.merges.map((merge) => `
      <tr>
        <td><code>${esc(merge.source_id)}</code></td>
        <td><code>${esc(merge.target_id)}</code></td>
        <td>${merge.known_chapter}</td>
        <td class="hint">${esc(merge.quote)}</td>
        <td>${merge.withdrawal_reason ? `已撤销：${esc(merge.withdrawal_reason)}` : "有效"}</td>
        <td>${merge.withdrawal_reason ? "" : `<button data-withdraw="${esc(merge.id)}" type="button" class="danger">撤销</button>`}</td>
      </tr>`).join("");
    $$("button[data-withdraw]").forEach((button) => {
      button.onclick = () => withdrawMerge(button.dataset.withdraw);
    });
  } catch (error) {
    toast(`加载合并记录失败：${error.message}`, true);
  }
}

async function createMerge() {
  const book = currentBook();
  if (!book) return;
  const payload = {
    source_id: $("#merge-source").value.trim(),
    target_id: $("#merge-target").value.trim(),
    paragraph_id: $("#merge-paragraph").value.trim(),
    quote: $("#merge-quote").value.trim(),
    progress_chapter: Number($("#merge-progress").value),
  };
  if (Object.values(payload).some((value) => !value)) { toast("请填写完整", true); return; }
  try {
    await api(`/books/${encodeURIComponent(book)}/person-merges`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    toast("已添加合并");
    loadMerges();
  } catch (error) {
    toast(`合并失败：${error.message}`, true);
  }
}

async function withdrawMerge(mergeId) {
  const book = currentBook();
  if (!book) return;
  const reason = prompt("撤销理由（1-500 字）：");
  if (!reason) return;
  try {
    await api(`/books/${encodeURIComponent(book)}/person-merges/${encodeURIComponent(mergeId)}/withdraw`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason }),
    });
    toast("已撤销合并");
    loadMerges();
  } catch (error) {
    toast(`撤销失败：${error.message}`, true);
  }
}

/* ---------- 预算 ---------- */

async function loadSettings() {
  try {
    const data = await api("/settings/call-budget");
    $("#budget-input").value = data.max_calls;
    const body = $("#call-table tbody");
    if (!data.calls.length) {
      body.innerHTML = '<tr><td colspan="6" class="hint">还没有调用记录。</td></tr>';
      return;
    }
    body.innerHTML = data.calls.slice().reverse().map((call) => `
      <tr>
        <td>${esc(call.created_at)}</td>
        <td>${esc(call.book_id)}</td>
        <td>${call.chapter}</td>
        <td>${esc(call.provider)} / ${esc(call.model)}</td>
        <td>${esc(call.status)}</td>
        <td class="hint">${call.usage ? esc(JSON.stringify(call.usage)) : ""}</td>
      </tr>`).join("");
  } catch (error) {
    toast(`加载预算失败：${error.message}`, true);
  }
}

async function saveBudget() {
  const maxCalls = Number($("#budget-input").value);
  try {
    await api("/settings/call-budget", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ max_calls: maxCalls }),
    });
    toast(`上限已设为 ${maxCalls} 次`);
    loadSettings();
    loadBudgetLine();
  } catch (error) {
    toast(`保存失败：${error.message}`, true);
  }
}

/* ---------- 初始化 ---------- */

$("#book-select").onchange = async (event) => {
  clearReadingViews();
  state.book = event.target.value || null;
  $("#graph-progress").value = "1";
  localStorage.setItem("yueji.book", state.book || "");
  syncProgressInputs();
  if (state.book) {
    try { await loadSavedProgress(state.book); } catch(error) { toast(`加载阅读进度失败：${error.message}`,true); return; }
  }
  if ($("#tab-review").classList.contains("active")) loadCandidates();
  if ($("#tab-graph").classList.contains("active")) loadGraph();
  if ($("#tab-merges").classList.contains("active")) loadMerges();
};
$$("#tabs button").forEach((button) => { button.onclick = () => showTab(button.dataset.tab); });
$("#refresh-books").onclick = loadBooks;
$("#preview-btn").onclick = doPreview;
$("#confirm-import").onclick = confirmImport;
$("#extract-btn").onclick = runExtract;
$("#extract-job-btn").onclick = () => createJob(false);
$("#estimate-btn").onclick = estimateExtraction;
for (const id of ["book-select", "extract-chapter", "extract-progress"]) {
  $(`#${id}`).addEventListener("input", () => { $("#estimate-line").textContent = ""; });
}
$("#rejections-refresh").onclick = loadRejections;
$("#review-refresh").onclick = loadCandidates;
$("#review-status").onchange = loadCandidates;
$("#graph-refresh").onclick = loadGraph;
$("#graph-filter").oninput = () => { if (state.graphData) renderGraph(state.graphData); };
for (const kind of ["person", "fact", "relation"]) $(`#manual-${kind}-submit`).onclick = () => submitManual(kind);
$("#manual-read-button").onclick = loadManualReading;
$("#order-submit").onclick = addRelationOrder;
$("#correction-submit").onclick = submitRecordCorrection;
for (const id of ["extract-progress", "review-progress", "graph-progress", "merge-progress"]) {
  $(`#${id}`).onchange = async (event) => {
    if (!await changeProgress(event.target.value)) return;
    if (id === "graph-progress") loadGraph();
    if (id === "review-progress") loadCandidates();
    if (id === "merge-progress") loadMerges();
    if (id === "extract-progress") loadJobs();
  };
}
$("#graph-progress").oninput = (event) => { changeProgress(event.target.value); };
$("#merge-btn").onclick = createMerge;
$("#budget-save").onclick = saveBudget;

loadBooks().then(() => {
  syncProgressInputs();
  if (state.book) loadGraph();
});
