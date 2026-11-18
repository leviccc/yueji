import { expect, test, type Page, type Route } from '@playwright/test'

const bookA = { id: 'book-a', title: '审阅书籍 A', chapter_count: 2, progress: 1 }
const bookB = { id: 'book-b', title: '审阅书籍 B', chapter_count: 2, progress: 1 }
const emptyTimeline = {
  events: [],
  constraints: [],
  accepted_ids: [],
  pending_ids: [],
  simultaneous_groups: [],
  layers: [],
  unplaced_ids: [],
  predecessors: {},
  conflicts: [],
}
const task = {
  id: 'task-a',
  book_id: 'book-a',
  cutoff: 1,
  profile: 'test:plot-v1',
  status: 'running',
  stage: 'A 书任务正在运行',
  completed: 0,
  total: 3,
  error: null,
  created_at: '',
  updated_at: '',
}
const summary = {
  items: [{ text: '章节摘要内容', event_ids: ['event-1'], statement: 'fact', evidence: [] }],
  unresolved_questions: [],
}

type MockOptions = {
  books?: typeof bookA[]
  timeline?: unknown
  intercept?: (route: Route) => Promise<boolean>
}

async function installApi(page: Page, options: MockOptions = {}) {
  const books = options.books ?? [bookA]
  const timeline = options.timeline ?? emptyTimeline
  await page.route('**/api/**', async route => {
    if (await options.intercept?.(route)) return
    const request = route.request()
    const url = new URL(request.url())
    const cutoff = Number(url.searchParams.get('cutoff') ?? 1)
    const book = books.find(item => url.pathname.includes(item.id)) ?? books[0]
    let body: unknown

    if (url.pathname === '/api/books' && request.method() === 'GET') {
      body = { books }
    } else if (url.pathname.endsWith('/timeline')) {
      body = { scope: { book_id: book.id, cutoff_chapter: cutoff }, timeline }
    } else if (url.pathname.endsWith('/chapters')) {
      body = {
        scope: { book_id: book.id, cutoff_chapter: cutoff },
        chapters: [
          { id: 'chapter-1', number: 1, title: '第一章' },
          { id: 'chapter-2', number: 2, title: cutoff >= 2 ? '第二章' : null },
        ],
      }
    } else if (url.pathname.endsWith('/progress')) {
      body = { ...book, progress: request.postDataJSON().chapter }
    } else if (url.pathname.includes('/summaries/')) {
      body = { summary: { ...summary, items: [{ ...summary.items[0], text: `${url.pathname.split('/').at(-1)}章摘要` }] } }
    } else if (url.pathname.endsWith('/analysis') || url.pathname.startsWith('/api/tasks/')) {
      body = task
    } else if (url.pathname.endsWith('/recap')) {
      body = { recap: summary }
    } else if (url.pathname.endsWith('/source')) {
      body = { chapter: { number: 1, title: '第一章', paragraphs: [] } }
    } else {
      throw new Error(`Unexpected API request: ${url.pathname}`)
    }
    await route.fulfill({ json: body })
  })
}

async function openApp(page: Page) {
  await page.goto('/')
  await expect(page.locator('.book-title')).toHaveText(bookA.title)
  await expect(page.locator('.el-skeleton')).toHaveCount(0)
}

test('late analysis response cannot replace the selected book task', async ({ page }) => {
  let markStarted!: () => void
  let release!: () => void
  const started = new Promise<void>(resolve => { markStarted = resolve })
  const responseReady = new Promise<void>(resolve => { release = resolve })
  await installApi(page, {
    books: [bookA, bookB],
    intercept: async route => {
      if (new URL(route.request().url()).pathname !== '/api/books/book-a/analysis') return false
      markStarted()
      await responseReady
      try {
        await route.fulfill({ json: task })
      } catch {
        // The selected-book change cancels this request.
      }
      return true
    },
  })
  await openApp(page)
  await page.getByRole('button', { name: '分析已读章节', exact: true }).click()
  await started
  await page.locator('.book-sidebar .el-select').click()
  await page.getByRole('option', { name: bookB.title, exact: true }).click()
  await expect(page.locator('.book-title')).toHaveText(bookB.title)
  await page.locator('.book-sidebar .el-select').click()
  await page.getByRole('option', { name: bookA.title, exact: true }).click()
  await expect(page.locator('.book-title')).toHaveText(bookA.title)
  release()
  await expect(page.locator('.task-section')).toHaveCount(0)
  expect(await page.locator('.analyze-button').isDisabled()).toBeFalsy()
})

test('polling failure preserves a task and permits a status retry', async ({ page }) => {
  let pollCount = 0
  await installApi(page, {
    intercept: async route => {
      if (!new URL(route.request().url()).pathname.startsWith('/api/tasks/')) return false
      pollCount++
      if (pollCount === 1) {
        await route.fulfill({ status: 503, json: { detail: '状态查询暂时失败' } })
      } else {
        await route.fulfill({ json: { ...task, status: 'succeeded', stage: '分析完成' } })
      }
      return true
    },
  })
  await openApp(page)
  await page.getByRole('button', { name: '分析已读章节', exact: true }).click()
  await expect(page.locator('.task-section')).toContainText('状态查询')
  await expect(page.getByRole('button', { name: '重新查询状态' })).toBeVisible()
  await page.getByRole('button', { name: '重新查询状态' }).click()
  await expect(page.locator('.task-section')).toContainText('分析完成')
  expect(pollCount).toBe(2)
})

test('progress changes request the matching chapter summary once', async ({ page }) => {
  const summaryRequests: string[] = []
  await installApi(page, {
    intercept: async route => {
      const url = new URL(route.request().url())
      if (!url.pathname.includes('/summaries/')) return false
      summaryRequests.push(url.pathname)
      return false
    },
  })
  await openApp(page)
  await page.getByRole('tab', { name: '章节摘要', exact: true }).click()
  await expect(page.locator('.summary-prose')).toContainText('1章摘要')
  summaryRequests.length = 0
  await page.getByRole('spinbutton').fill('2')
  await page.getByRole('button', { name: '更新进度', exact: true }).click()
  await expect(page.getByText('已读至第 2 章')).toBeVisible()
  await expect(page.locator('.summary-prose')).toContainText('2章摘要')
  expect(summaryRequests.filter(path => path.endsWith('/summaries/2'))).toHaveLength(1)
})

test('unplaced simultaneous events retain their shared time and flashback details', async ({ page }) => {
  const evidence = (id: string) => ({
    id: `quote-${id}`,
    paragraph_id: `paragraph-${id}`,
    chapter: 1,
    paragraph_number: 1,
    start: 0,
    end: 4,
    quote: '同时出发',
  })
  const events = ['甲', '乙'].map((name, index) => ({
    id: `event-${index}`,
    title: `${name}出发`,
    participants: [{ id: name, name }],
    action: '出发',
    location: '長安',
    time_expression: '七年前清晨',
    time_bounds: null,
    result: null,
    statement: 'fact',
    speaker: null,
    importance: 'key',
    retrospective: true,
    known_from: 1,
    last_mentioned: 1,
    evidence: [evidence(name)],
  }))
  const timeline = {
    ...emptyTimeline,
    events,
    constraints: [{ id: 'simultaneous', source: 'event-0', target: 'event-1', relation: 'simultaneous', evidence_type: 'explicit', known_from: 1, reason: '同时出发', evidence: [evidence('甲')] }],
    accepted_ids: ['simultaneous'],
    simultaneous_groups: [['event-0', 'event-1']],
    layers: [['event-0', 'event-1']],
    unplaced_ids: ['event-0', 'event-1'],
    predecessors: { 'event-0': [], 'event-1': [] },
  }
  await installApi(page, { timeline })
  await openApp(page)
  await page.getByRole('tab', { name: '故事时间线', exact: true }).click()
  const unplaced = page.locator('.unplaced-section')
  await expect(unplaced).toContainText('甲出发')
  await expect(unplaced).toContainText('乙出发')
  await expect(unplaced).toContainText('同时开始：乙出发')
  await expect(unplaced).toContainText('七年前清晨')
  await expect(unplaced).toContainText('回忆')
})

test('HTML service errors display a normalized HTTP message', async ({ page }) => {
  await page.route('**/api/books', route => route.fulfill({
    status: 503,
    contentType: 'text/html',
    body: '<html><body>upstream failure</body></html>',
  }))
  await page.goto('/')
  await expect(page.locator('.el-alert')).toContainText('HTTP 503')
})
