<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import type { ChapterInfo, Evidence, Summary, Timeline } from './api'
import { plotClient, statementLabel } from './api'
import EvidenceLinks from './EvidenceLinks.vue'
import SourceDrawer from './SourceDrawer.vue'
import StoryGraph from './StoryGraph.vue'

type ReadChapter = ChapterInfo & { title: string }

const props = defineProps<{ bookId: string; cutoff: number; refreshKey?: number }>()
const selectedTab = ref('recap')
const timeline = ref<Timeline>()
const summary = ref<Summary>()
const recap = ref<Summary>()
const chapters = ref<ReadChapter[]>([])
const summaryChapter = ref(1)
const selectedCharacterId = ref('')
const isLoading = ref(false)
const isLoadingRecap = ref(false)
const error = ref('')
const selectedEvidence = ref<Evidence>()
const isSourceOpen = ref(false)
let plotController: AbortController | undefined
let recapController: AbortController | undefined
let summaryController: AbortController | undefined

const characters = computed(() => Array.from(new Map(
  timeline.value?.events.flatMap(event => event.participants).map(person => [person.id, person]) ?? [],
).values()))
const selectedSummary = computed(() => selectedTab.value === 'recap' ? recap.value : summary.value)

function replaceController(current?: AbortController) {
  current?.abort()
  return new AbortController()
}

function getErrorMessage(failure: unknown) {
  return failure instanceof Error ? failure.message : String(failure)
}

async function loadPlot() {
  plotController = replaceController(plotController)
  recapController = replaceController(recapController)
  summaryController = replaceController(summaryController)
  const { signal } = plotController
  timeline.value = undefined
  summary.value = undefined
  recap.value = undefined
  selectedEvidence.value = undefined
  isSourceOpen.value = false
  selectedCharacterId.value = ''
  error.value = ''
  chapters.value = []
  isLoadingRecap.value = false
  if (!props.cutoff) {
    isLoading.value = false
    return
  }

  isLoading.value = true
  try {
    const client = plotClient(props.bookId, props.cutoff, signal)
    const [eventsResult, chaptersResult] = await Promise.all([client.timeline(), client.chapters()])
    if (signal.aborted) return
    timeline.value = eventsResult.timeline
    chapters.value = chaptersResult.chapters.filter(
      (chapter): chapter is ReadChapter => chapter.number <= props.cutoff && chapter.title !== null,
    )
    summaryChapter.value = props.cutoff
  } catch (failure) {
    if (!signal.aborted) error.value = getErrorMessage(failure)
  } finally {
    if (!signal.aborted) isLoading.value = false
  }
}

async function loadSummary() {
  summaryController = replaceController(summaryController)
  const { signal } = summaryController
  summary.value = undefined
  if (!props.cutoff || !timeline.value) return
  try {
    const result = await plotClient(props.bookId, props.cutoff, signal).summary(summaryChapter.value)
    if (!signal.aborted) summary.value = result.summary
  } catch (failure) {
    if (!signal.aborted) error.value = getErrorMessage(failure)
  }
}

async function loadRecap() {
  recapController = replaceController(recapController)
  const { signal } = recapController
  isLoadingRecap.value = true
  error.value = ''
  try {
    const result = await plotClient(props.bookId, props.cutoff, signal).recap()
    if (!signal.aborted) recap.value = result.recap
  } catch (failure) {
    if (!signal.aborted) error.value = getErrorMessage(failure)
  } finally {
    if (!signal.aborted) isLoadingRecap.value = false
  }
}

function openEvidence(evidence: Evidence) {
  selectedEvidence.value = evidence
  isSourceOpen.value = true
}

watch(() => [props.bookId, props.cutoff, props.refreshKey], loadPlot, { immediate: true })
watch(
  () => [props.bookId, props.cutoff, selectedTab.value, summaryChapter.value, Boolean(timeline.value)],
  ([, cutoff, tab, , hasTimeline]) => {
    if (tab === 'summary' && cutoff && hasTimeline) void loadSummary()
    else summaryController = replaceController(summaryController)
  },
)
watch(selectedTab, () => { error.value = '' })
onBeforeUnmount(() => {
  plotController?.abort()
  recapController?.abort()
  summaryController?.abort()
})
</script>

<template>
  <section class="plot-panel" aria-label="情节梳理与故事时间线">
    <div class="panel-heading"><div><p class="eyebrow">故事读到这里</p><h1>拾起故事的线索</h1></div><span v-if="cutoff" class="scope-pill">已读至第 {{ cutoff }} 章</span></div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
    <el-tabs v-model="selectedTab">
      <el-tab-pane label="前情回顾" name="recap" />
      <el-tab-pane label="故事时间线" name="timeline" />
      <el-tab-pane label="章节摘要" name="summary" />
      <el-tab-pane label="人物剧情线" name="character" />
    </el-tabs>
    <div v-if="!cutoff" class="empty-state"><h2>从已读的一章开始</h2><p>设置阅读进度，整理已经读过的故事。</p></div>
    <el-skeleton v-else-if="isLoading" :rows="6" animated />
    <template v-else-if="timeline">
      <template v-if="selectedTab === 'recap' || selectedTab === 'summary'">
        <div class="panel-toolbar">
          <div><h2>{{ selectedTab === 'recap' ? '前情，重新连起来' : '这一章发生了什么' }}</h2><p>{{ selectedTab === 'recap' ? `从开篇到第 ${cutoff} 章` : '循着关键变化，回到故事中' }}</p></div>
          <el-select v-if="selectedTab === 'summary'" v-model="summaryChapter" aria-label="选择摘要章节" class="chapter-select"><el-option v-for="item in chapters" :key="item.number" :value="item.number" :label="item.title" /></el-select>
          <el-button v-else type="primary" :loading="isLoadingRecap" @click="loadRecap">{{ recap ? '重新查看回顾' : '生成前情回顾' }}</el-button>
        </div>
        <template v-if="selectedSummary">
          <div class="summary-prose">
            <article v-for="(item, index) in selectedSummary.items" :key="index" class="summary-item">
              <el-tag v-if="item.statement !== 'fact'" type="info" size="small">{{ statementLabel[item.statement] }}</el-tag>
              <p>{{ item.text }}</p><EvidenceLinks :evidence="item.evidence" @open="openEvidence" />
            </article>
          </div>
          <section v-if="selectedSummary.unresolved_questions.length" class="questions-section"><h3>还悬着的线索</h3><article v-for="(item, index) in selectedSummary.unresolved_questions" :key="index"><p>{{ item.text }}</p><EvidenceLinks :evidence="item.evidence" @open="openEvidence" /></article></section>
        </template>
        <div v-else-if="selectedTab === 'recap' && !isLoadingRecap" class="recap-intro"><span class="large-quote" aria-hidden="true">“</span><p>隔了一段时间，<br />也能接着读下去。</p><span>回顾已读的情节与尚未解开的线索。</span></div>
        <el-skeleton v-if="isLoadingRecap" :rows="5" animated />
      </template>
      <template v-else>
        <div class="panel-toolbar"><div><h2>{{ selectedTab === 'character' ? '沿着一个人的足迹' : '故事发生的顺序' }}</h2><p>{{ selectedTab === 'character' ? '回看人物经历与被揭示的章节' : '从叙述中，找回事情的来龙去脉' }}</p></div><el-select v-if="selectedTab === 'character'" v-model="selectedCharacterId" clearable placeholder="选择人物" aria-label="选择人物" class="chapter-select"><el-option v-for="person in characters" :key="person.id" :value="person.id" :label="person.name" /></el-select></div>
        <StoryGraph v-if="timeline.events.length" :timeline="timeline" :character-id="selectedTab === 'character' ? selectedCharacterId : ''" @open="openEvidence" />
        <el-empty v-else description="分析已读章节后，查看关键事件" />
      </template>
    </template>
    <SourceDrawer v-model="isSourceOpen" :book-id="bookId" :cutoff="cutoff" :evidence="selectedEvidence" />
  </section>
</template>
