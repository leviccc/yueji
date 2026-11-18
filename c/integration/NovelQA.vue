<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'

type Evidence = {
  evidence_id: string; chapter_index: number; chapter_title: string
  paragraph_id: string; start: number; end: number; quote: string; paragraph_url: string
}
type Answer = {
  status: 'answered' | 'partial' | 'insufficient_evidence' | 'clarification_needed'
  mode: 'extractive' | 'llm'; as_of_chapter: number; book_id: string
  claims: { text: string; kind: string; assertion_type: string; evidence_ids: string[] }[]
  evidence: Evidence[]; limitations: string[]; cached: boolean
}
const props = withDefaults(defineProps<{
  bookId: string; asOfChapter: number; apiBase?: string; token?: string
}>(), { apiBase: 'http://127.0.0.1:8000', token: '' })
const emit = defineEmits<{ (e: 'open-evidence', evidence: Evidence): void }>()
const question = ref('')
const answer = ref<Answer | null>(null)
const error = ref('')
const busy = ref(false)
let controller: AbortController | undefined
let requestVersion = 0
const labels = {
  answered: '回答', partial: '部分回答 / 候选原文',
  insufficient_evidence: '当前证据不足', clarification_needed: '请补充问题中的人物或事件',
}

function clearResult() {
  ++requestVersion
  controller?.abort()
  answer.value = null
  error.value = ''
  busy.value = false
}
watch(() => [props.bookId, props.asOfChapter, props.apiBase, props.token], clearResult, { flush: 'sync' })
onBeforeUnmount(clearResult)

async function ask() {
  if (!props.bookId || question.value.trim().length < 2 || busy.value) return
  clearResult()
  const version = requestVersion
  controller = new AbortController()
  busy.value = true
  try {
    const response = await fetch(`${props.apiBase.replace(/\/$/, '')}/api/books/${encodeURIComponent(props.bookId)}/qa`, {
      method: 'POST', signal: controller.signal,
      headers: { 'Content-Type': 'application/json', ...(props.token ? { Authorization: `Bearer ${props.token}` } : {}) },
      body: JSON.stringify({ question: question.value.trim(), as_of_chapter: props.asOfChapter, experiment: 'Q1' }),
    })
    const body = await response.json()
    if (version !== requestVersion) return
    if (!response.ok) throw new Error(body.error?.message ?? '问答请求失败，请稍后重试。')
    if (body.book_id !== props.bookId || body.as_of_chapter !== props.asOfChapter) return
    answer.value = body
  } catch (err) {
    if (version === requestVersion && !(err instanceof DOMException && err.name === 'AbortError'))
      error.value = err instanceof Error ? err.message : '网络连接失败。'
  } finally {
    if (version === requestVersion) busy.value = false
  }
}
</script>

<template>
  <section class="novel-qa" aria-label="小说问答">
    <p>回答范围：第 1 至 {{ asOfChapter }} 章</p>
    <form @submit.prevent="ask">
      <label for="novel-question">关于已读内容，你想了解什么？</label>
      <textarea id="novel-question" v-model="question" :maxlength="500" rows="3"
        placeholder="例如：林舟为什么开始怀疑青禾？" />
      <button :disabled="busy || !bookId || question.trim().length < 2 || asOfChapter < 1">
        {{ busy ? '正在检索与核对…' : '提问' }}
      </button>
    </form>
    <p v-if="error" role="alert">{{ error }}</p>
    <article v-if="answer" aria-live="polite">
      <p><strong>{{ labels[answer.status] }}</strong></p>
      <p v-if="answer.mode === 'extractive'">当前展示检索原文，尚未生成解释性答案。</p>
      <p v-for="(claim, i) in answer.claims" :key="i">
        <span v-if="claim.kind === 'inference'">【推断】</span>
        <span v-else-if="claim.assertion_type === 'character_claim'">【角色声称】</span>
        {{ claim.text }}
        <span class="citation">[{{ claim.evidence_ids.join(', ') }}]</span>
      </p>
      <details v-for="evidence in answer.evidence" :key="evidence.evidence_id">
        <summary>{{ evidence.evidence_id }} · {{ evidence.chapter_title }} · {{ evidence.paragraph_id }}</summary>
        <blockquote>{{ evidence.quote }}</blockquote>
        <button type="button" @click="emit('open-evidence', evidence)">定位原文</button>
      </details>
      <ul><li v-for="note in answer.limitations" :key="note">{{ note }}</li></ul>
    </article>
  </section>
</template>

<style scoped>
.novel-qa { max-width: 52rem; color: #182b31; line-height: 1.7; }
form { display: grid; gap: .75rem; }
textarea { box-sizing: border-box; width: 100%; padding: .75rem; border: 1px solid #8c9b9c; border-radius: .4rem; font: inherit; }
button { cursor: pointer; justify-self: start; border: 0; border-radius: .4rem; padding: .55rem 1rem; color: #fff; background: #216b63; }
button:disabled { opacity: .5; cursor: default; }
details { padding: .75rem; background: #f1f6f4; margin: .75rem 0; border-radius: .4rem; }
summary { cursor: pointer; }
blockquote { margin: .8rem 0; white-space: pre-wrap; }
.citation { color: #216b63; }
[role='alert'] { color: #a32929; }
</style>
