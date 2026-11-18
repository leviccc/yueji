import { computed, onBeforeUnmount, ref } from 'vue'
import type { Book, Task } from './api'
import { jsonBody, request } from './api'

export const TASK_POLL_INTERVAL_MS = 1000

export function useAnalysisTask(getSelectedBookId: () => string, onCompleted: () => void) {
  const task = ref<Task>()
  const taskError = ref('')
  const isSubmitting = ref(false)
  const isPolling = ref(false)
  const isTaskActive = computed(
    () => task.value !== undefined && ['queued', 'running'].includes(task.value.status),
  )
  let requestRound = 0
  let controller: AbortController | undefined
  let timer: ReturnType<typeof setTimeout> | undefined

  function isCurrent(bookId: string, round: number) {
    return requestRound === round && getSelectedBookId() === bookId
  }

  function cancel() {
    requestRound++
    controller?.abort()
    controller = undefined
    clearTimeout(timer)
    timer = undefined
    isSubmitting.value = false
    isPolling.value = false
    task.value = undefined
    taskError.value = ''
  }

  async function pollTask(bookId: string, taskId: string, round: number) {
    if (!controller || !isCurrent(bookId, round)) return
    isPolling.value = true
    try {
      const result = await request<Task>(`/tasks/${taskId}`, undefined, controller.signal)
      if (!isCurrent(bookId, round)) return
      task.value = result
      taskError.value = ''
      if (result.status === 'succeeded') {
        isPolling.value = false
        onCompleted()
      } else if (result.status === 'queued' || result.status === 'running') {
        timer = setTimeout(() => void pollTask(bookId, taskId, round), TASK_POLL_INTERVAL_MS)
      } else {
        isPolling.value = false
      }
    } catch (failure) {
      if (isCurrent(bookId, round) && !controller.signal.aborted) {
        isPolling.value = false
        taskError.value = failure instanceof Error ? failure.message : String(failure)
      }
    }
  }

  async function startAnalysis(book: Book) {
    cancel()
    const round = requestRound
    const bookId = book.id
    controller = new AbortController()
    isSubmitting.value = true
    try {
      const result = await request<Task>(
        `/books/${encodeURIComponent(bookId)}/analysis`,
        jsonBody({ cutoff_chapter: book.progress }),
        controller.signal,
      )
      if (!isCurrent(bookId, round)) return
      task.value = result
      await pollTask(bookId, result.id, round)
    } catch (failure) {
      if (isCurrent(bookId, round) && !controller.signal.aborted) {
        taskError.value = failure instanceof Error ? failure.message : String(failure)
      }
    } finally {
      if (isCurrent(bookId, round)) isSubmitting.value = false
    }
  }

  async function resumePolling() {
    const currentTask = task.value
    const bookId = getSelectedBookId()
    if (!currentTask || !isTaskActive.value || !bookId || currentTask.book_id !== bookId) return
    controller?.abort()
    clearTimeout(timer)
    controller = new AbortController()
    requestRound++
    taskError.value = ''
    await pollTask(bookId, currentTask.id, requestRound)
  }

  onBeforeUnmount(cancel)

  return { task, taskError, isSubmitting, isPolling, isTaskActive, cancel, startAnalysis, resumePolling }
}
