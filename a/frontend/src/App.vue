<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { Collection, DocumentAdd, Reading, RefreshRight } from '@element-plus/icons-vue'
import type { Book, NovelPreview } from './api'
import { jsonBody, request } from './api'
import PlotPanel from './PlotPanel.vue'
import { useAnalysisTask } from './useAnalysisTask'

const books = ref<Book[]>([])
const selectedBookId = ref('')
const selectedBook = computed(() => books.value.find(book => book.id === selectedBookId.value))
const progress = ref(0)
const refreshKey = ref(0)
const error = ref('')
const preview = ref<NovelPreview>()
const boundaries = ref('')
const file = ref<File>()
const isImportDialogOpen = ref(false)
const isImportBusy = ref(false)
const isProgressUpdating = ref(false)
let progressController: AbortController | undefined
let progressRequestRound = 0
const bookOptions = computed(() => books.value.map(book => ({ label: book.title, value: book.id })))
const analysis = useAnalysisTask(() => selectedBookId.value, () => refreshKey.value++)
const isAnalysisSubmitting = analysis.isSubmitting
const isTaskPolling = analysis.isPolling
const isTaskActive = analysis.isTaskActive
const task = analysis.task
const taskError = analysis.taskError
const isAnalyzing = computed(() => isAnalysisSubmitting.value || isTaskPolling.value)

async function loadBooks() {
  try {
    books.value = (await request<{ books: Book[] }>('/books')).books
    if (!selectedBookId.value && books.value.length) selectBook(books.value[0].id)
  } catch (failure) {
    error.value = failure instanceof Error ? failure.message : String(failure)
    throw failure
  }
}

function refreshBooks() {
  void loadBooks().catch(() => undefined)
}

function selectBook(bookId: string) {
  const book = books.value.find(item => item.id === bookId)
  if (!book) return
  analysis.cancel()
  progressController?.abort()
  progressController = undefined
  progressRequestRound++
  selectedBookId.value = book.id
  progress.value = book.progress
  isProgressUpdating.value = false
  error.value = ''
}

async function updateProgress() {
  const book = selectedBook.value
  if (!book) return
  const bookId = book.id
  const nextProgress = progress.value
  const previousProgress = book.progress
  const requestRound = ++progressRequestRound
  progressController?.abort()
  const controller = new AbortController()
  progressController = controller
  isProgressUpdating.value = true
  error.value = ''
  try {
    const result = await request<Book>(
      `/books/${encodeURIComponent(bookId)}/progress`,
      { ...jsonBody({ chapter: nextProgress }), method: 'PUT' },
      controller.signal,
    )
    if (selectedBookId.value !== bookId || requestRound !== progressRequestRound) return
    Object.assign(book, result)
  } catch (failure) {
    if (requestRound === progressRequestRound && !controller.signal.aborted) {
      progress.value = previousProgress
      error.value = failure instanceof Error ? failure.message : String(failure)
    }
  } finally {
    if (requestRound === progressRequestRound) isProgressUpdating.value = false
  }
}

async function analyze() {
  const book = selectedBook.value
  if (!book) return
  error.value = ''
  await analysis.startAnalysis(book)
}

async function chooseFile(event: Event) {
  const input = event.target as HTMLInputElement
  const chosen = input.files?.[0]
  if (!chosen) return
  file.value = chosen
  const form = new FormData()
  form.append('file', chosen)
  isImportBusy.value = true
  error.value = ''
  try {
    preview.value = await request<NovelPreview>('/books/preview', { method: 'POST', body: form })
    boundaries.value = preview.value.boundaries.map(boundary => `${boundary.line} ${boundary.title}`).join('\n')
    isImportDialogOpen.value = true
  } catch (failure) {
    error.value = failure instanceof Error ? failure.message : String(failure)
  } finally {
    isImportBusy.value = false
    input.value = ''
  }
}

async function importBook() {
  if (!file.value) return
  isImportBusy.value = true
  error.value = ''
  try {
    const parsed = boundaries.value.split('\n').filter(line => line.trim()).map(line => {
      const match = /^(\d+)\s+(.+)$/.exec(line.trim())
      if (!match) throw new Error('每行填写：起始行号 章节标题')
      return { line: Number(match[1]), title: match[2] }
    })
    const form = new FormData()
    form.append('file', file.value)
    form.append('boundaries', JSON.stringify(parsed))
    const book = await request<Book>('/books', { method: 'POST', body: form })
    await loadBooks()
    if (!books.value.some(item => item.id === book.id)) {
      throw new Error('导入成功，但书架尚未加载到这本小说')
    }
    selectBook(book.id)
    isImportDialogOpen.value = false
  } catch (failure) {
    error.value = failure instanceof Error ? failure.message : String(failure)
  } finally {
    isImportBusy.value = false
  }
}

onMounted(() => void loadBooks().catch(() => undefined))
onBeforeUnmount(() => progressController?.abort())
</script>

<template>
  <header class="app-header">
    <a class="brand" href="/" aria-label="阅迹首页">
      <span class="brand-mark"><el-icon :size="27"><Reading /></el-icon></span>
      <span>阅迹</span>
    </a>
    <span class="brand-motto">让故事有迹可循</span>
    <span class="header-context"><span class="status-dot"></span> 阅读工作台</span>
    <el-button :icon="Collection" text @click="refreshBooks">我的书架</el-button>
  </header>
  <div class="app-layout">
    <aside class="book-sidebar">
      <div class="sidebar-title">
        <span>我的书架</span>
        <label
          class="upload-button"
          tabindex="0"
          role="button"
          @keydown.enter="($refs.upload as HTMLInputElement).click()"
        >
          <el-icon><DocumentAdd /></el-icon>
          <span class="sr-only">导入小说</span>
          <input ref="upload" type="file" accept=".txt,text/plain" hidden @change="chooseFile" />
        </label>
      </div>
      <el-select
        :model-value="selectedBookId"
        placeholder="选择一本小说"
        aria-label="选择小说"
        @change="selectBook"
      >
        <el-option
          v-for="option in bookOptions"
          :key="option.value"
          :value="option.value"
          :label="option.label"
        />
      </el-select>
      <template v-if="selectedBook">
        <div class="book-cover" aria-hidden="true">
          <div class="cover-rule"></div>
          <span class="cover-imprint">阅迹书房</span>
          <span class="cover-name">{{ selectedBook.title.split(' · ')[0] }}</span>
          <div class="cover-circle"></div>
          <span class="cover-caption">故事里的每一次回望</span>
        </div>
        <h2 class="book-title">{{ selectedBook.title }}</h2>
        <p class="book-subtitle">{{ selectedBook.chapter_count }} 章 · 中文小说</p>
        <section class="progress-section">
          <div class="progress-label">
            <span>我的阅读进度</span>
            <strong>{{ selectedBook.progress }} <small>/ {{ selectedBook.chapter_count }} 章</small></strong>
          </div>
          <el-progress
            :percentage="Math.round(selectedBook.progress / selectedBook.chapter_count * 100)"
            :show-text="false"
            :stroke-width="4"
          />
          <div class="progress-control">
            <el-input-number
              v-model="progress"
              :min="0"
              :max="selectedBook.chapter_count"
              size="small"
              controls-position="right"
              aria-label="阅读截止章节"
            />
            <el-button size="small" :loading="isProgressUpdating" @click="updateProgress">
              更新进度
            </el-button>
          </div>
        </section>
        <el-button
          class="analyze-button"
          type="primary"
          :icon="RefreshRight"
          :loading="isAnalyzing"
          :disabled="!selectedBook.progress || isTaskActive"
          @click="analyze"
        >
          分析已读章节
        </el-button>
        <section v-if="task" class="task-section" aria-live="polite">
          <p>{{ task.stage }}</p>
          <el-progress
            v-if="task.total"
            :percentage="Math.round(task.completed / task.total * 100)"
            :stroke-width="4"
            :status="task.status === 'failed' ? 'exception' : undefined"
          />
          <p v-if="task.error" class="error-text">{{ task.error }}</p>
          <p v-if="taskError" class="error-text">{{ taskError }}</p>
          <el-button
            v-if="isTaskActive && !isTaskPolling && !isAnalysisSubmitting"
            size="small"
            @click="analysis.resumePolling"
          >
            重新查询状态
          </el-button>
          <el-button
            v-if="task.status === 'failed' || task.status === 'paused'"
            size="small"
            @click="analyze"
          >
            继续分析
          </el-button>
        </section>
        <div class="sidebar-note">
          <el-icon><Reading /></el-icon>
          <p>故事的来龙去脉，<br />都藏在字里行间。</p>
        </div>
      </template>
      <p v-else class="book-subtitle">导入一本 TXT，开始整理故事。</p>
    </aside>
    <main class="main-content">
      <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
      <el-alert v-if="taskError && !task" :title="taskError" type="error" :closable="false" show-icon />
      <PlotPanel
        v-if="selectedBook"
        :book-id="selectedBook.id"
        :cutoff="selectedBook.progress"
        :refresh-key="refreshKey"
      />
      <div v-else class="welcome-state">
        <el-icon :size="48"><Reading /></el-icon>
        <h1>在故事里，留下足迹</h1>
        <p>从书架导入一本有章节的中文小说。</p>
      </div>
    </main>
  </div>
  <el-dialog v-model="isImportDialogOpen" title="确认章节" width="min(900px, 96vw)">
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <p class="import-hint">每行填写“起始行号 章节标题”，可直接修改识别结果。</p>
    <div class="import-columns">
      <el-input v-model="boundaries" type="textarea" :rows="15" aria-label="章节起始行与标题" />
      <div class="source-preview">
        <p v-for="line in preview?.lines" :key="line.line">
          <span>{{ line.line }}</span>{{ line.text }}
        </p>
      </div>
    </div>
    <template #footer>
      <el-button @click="isImportDialogOpen = false">取消</el-button>
      <el-button type="primary" :loading="isImportBusy" @click="importBook">确认导入</el-button>
    </template>
  </el-dialog>
</template>
