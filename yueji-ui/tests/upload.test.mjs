import { test } from 'node:test'
import assert from 'node:assert/strict'
import { uploadForm, MAX_UPLOAD_PREFIX_BYTES } from '../src/upload.js'

test('large files upload only a bounded prefix with original filename and a truncation flag', async () => {
  const bytes=new Uint8Array(MAX_UPLOAD_PREFIX_BYTES+10).fill(65)
  const file=new File([bytes],'long.txt')
  const data=uploadForm(file)
  assert.equal(data.get('file').name,'long.txt')
  assert.equal(data.get('file').size,MAX_UPLOAD_PREFIX_BYTES)
  assert.equal(data.get('prefix_truncated'),'true')
})
test('small files are uploaded unchanged without a truncation flag', async () => {
  const data=uploadForm(new File(['第一章 开始\n正文。'],'novel.txt'))
  assert.equal(await data.get('file').text(),'第一章 开始\n正文。')
  assert.equal(data.get('prefix_truncated'),'false')
})
