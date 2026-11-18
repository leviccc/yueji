import { test } from 'node:test'
import assert from 'node:assert/strict'
import { api } from '../src/api.js'

test('proxy HTML errors are reported as a temporary service issue', async () => {
  const original = globalThis.fetch
  try {
    globalThis.fetch = async () => new Response('<html>Bad Gateway</html>', { status: 502 })
    await assert.rejects(api('/books/test/workspace'), e => e.status === 502 && e.message.includes('服务暂时繁忙') && !e.message.includes('格式异常'))
  } finally { globalThis.fetch = original }
})

test('malformed successful responses cannot masquerade as a workspace', async () => {
  const original = globalThis.fetch
  try {
    globalThis.fetch = async () => new Response('not json', { status: 200 })
    await assert.rejects(api('/books/test/workspace'), /内容暂时未能加载/)
  } finally { globalThis.fetch = original }
})
