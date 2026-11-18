import { test } from 'node:test'
import assert from 'node:assert/strict'
import { chapterAnalysisStatus as status } from '../src/analysisStatus.js'
const workspace = () => ({ book: { id: 'book' }, scope: { cutoff_chapter: 5 },
  plot: { summaries: { 1: { items: [{ text: '第一章提要' }] }, 5: null }, timeline: { events: [] } },
  graph: { nodes: [], edges: [] }, analysis: { people_completed_through: 1 }, candidates: [] })
const job = (overrides = {}) => ({ book_id: 'book', cutoff: 1, kind: 'all', status: 'completed', stage: '分析完成', completed: 2, total: 2, ...overrides })

test('switching from analysed to unanalysed chapter does not reuse an old completion', () => {
  const ws = workspace()
  assert.equal(status(ws, 1, 'plot', job()).state, 'completed')
  assert.equal(status(ws, 5, 'plot', job()).label, '当前章节还未分析')
  assert.equal(status(ws, 1, 'plot', job()).state, 'completed')
})
test('people-only completion cannot mark plot as complete', () => {
  const ws = workspace(); ws.analysis.people_completed_through = 5
  assert.equal(status(ws, 5, 'plot', job({ cutoff: 5, kind: 'people' })).state, 'unanalysed')
  assert.equal(status(ws, 5, 'people', job({ cutoff: 5, kind: 'people' })).state, 'completed')
})
test('existing chapter results survive a newer task from another module', () => {
  assert.equal(status(workspace(), 1, 'people', job({ cutoff: 5, kind: 'plot' })).state, 'completed')
})
test('partial events with missing summary are not described as completed', () => {
  const ws = workspace(); ws.plot.timeline.events.push({ known_from: 5, evidence: [] })
  assert.equal(status(ws, 5, 'plot', job({ cutoff: 5, kind: 'people' })).state, 'partial')
})
test('progress bar belongs only to an active task covering the current chapter and module', () => {
  const running = job({ cutoff: 5, status: 'running', stage: '正在分析第五章' })
  assert.equal(status(workspace(), 5, 'plot', running).state, 'running')
  assert.equal(status(workspace(), 5, 'plot', { ...running, cutoff: 1 }).state, 'unanalysed')
  assert.equal(status(workspace(), 5, 'plot', { ...running, kind: 'people' }).state, 'unanalysed')
  assert.equal(status(workspace(), 5, 'plot', { ...running, book_id: 'other' }).state, 'unanalysed')
  const early = workspace(); early.scope.cutoff_chapter = 1
  assert.equal(status(early, 1, 'plot', running).state, 'completed')
})
test('retry is offered only for a relevant failed scope; chat has no analysis status', () => {
  const failed = job({ cutoff: 5, status: 'partial', error: '摘要未完成' })
  assert.equal(status(workspace(), 5, 'plot', failed).job, failed)
  assert.equal(status(workspace(), 5, 'plot', { ...failed, kind: 'people' }).job, null)
  assert.equal(status(workspace(), 1, 'chat', failed), null)
})

test('saved internal validation drafts never reach reader notices and modules stay separate', () => {
  const failed = job({ cutoff: 5, status: 'partial',
    error: '人物分析：已达到调用次数上限；请先调整预算；情节分析：摘要不能将计划、角色声称或推断写为已发生事实。错误条目：内部原文；关联事件的性质：secret-id' })
  const plot = status(workspace(), 5, 'plot', failed)
  assert.equal(plot.notice, '分析尚未完成，已有结果已保存，可继续分析。')
  assert.ok(!plot.notice.includes('secret-id') && !plot.notice.includes('内部原文'))
  assert.match(status(workspace(), 5, 'people', failed).notice, /服务调用额度已用完/)
})
