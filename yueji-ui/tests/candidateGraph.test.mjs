import { test } from 'node:test'
import assert from 'node:assert/strict'
import { candidateGraph, focusedGraph, relationshipSources } from '../src/candidateGraph.js'

test('preview includes pending evidence without promoting or inventing identities', () => {
  const source = [
    { id: 'p1', chapter: 1, kind: 'person', status: 'pending', payload: { name: '甲', paragraph_id: 'ch0001-p0001', quote: '甲遇到乙。' } },
    { id: 'p2', chapter: 1, kind: 'person', status: 'pending', payload: { name: '乙', paragraph_id: 'ch0001-p0001', quote: '甲遇到乙。' } },
    { id: 'p3', chapter: 1, kind: 'person', status: 'rejected', payload: { name: '丙' } },
    { id: 'r1', chapter: 1, kind: 'relation', status: 'pending', payload: { source: '甲', target: '乙', relation: '相识', paragraph_id: 'ch0001-p0001', quote: '甲遇到乙。' } },
    { id: 'r2', chapter: 1, kind: 'relation', status: 'pending', payload: { source: '甲', target: '丙', relation: '不可靠候选' } },
    { id: 'f1', chapter: 1, kind: 'fact', status: 'pending', payload: { person: '甲', content: '来到港口' } },
  ]
  const before = JSON.stringify(source), reviewed = []
  const graph = candidateGraph(source, reviewed)
  assert.equal(graph.nodes.length, 2)
  assert.equal(graph.edges.length, 1)
  assert.equal(graph.nodes[0].facts[0].pending, true)
  assert.equal(graph.edges[0].quote, '甲遇到乙。')
  assert.equal(JSON.stringify(source), before)
  assert.deepEqual(reviewed, [])
  assert.ok(graph.nodes.every(n => n.pending && n.aliases.length === 0))
})

test('focused graph keeps only selected-person links and does not invent a direction for bundles', () => {
  const nodes = ['甲','乙','丙','丁'].map(id => ({ id }))
  const edges = [
    { id: 1, source_id: '甲', target_id: '乙', directed: true, relation:'信任', records:[{id:11,quote:'甲信任乙'}], record_ids:[11] },
    { id: 2, source_id: '乙', target_id: '甲', directed: true, relation:'怀疑', records:[{id:12,quote:'乙怀疑甲'}], record_ids:[12] },
    { id: 3, source_id: '乙', target_id: '丙', directed: true },
    { id: 4, source_id: '甲', target_id: '丁', directed: true },
  ]
  const graph = focusedGraph(nodes, edges, '甲')
  assert.deepEqual(graph.nodes.map(n => n.id), ['甲','乙','丁'])
  assert.equal(graph.edges.length, 2)
  assert.equal(graph.edges[0].directed, false)
  assert.deepEqual(graph.edges[0].record_ids, [11,12])
  assert.equal(graph.edges[0].relation, '信任 · 怀疑')
  assert.equal(graph.edges[0].relations.length, 2)
  assert.deepEqual(graph.edges[0].relations.flatMap(r=>r.records.map(e=>e.quote)), ['甲信任乙','乙怀疑甲'])
  assert.equal(edges[0].directed, true)
})

test('evidence deduplication preserves both establishment and ending evidence', () => {
  const record = { paragraph_id:'ch0001-p0001', quote:'先合作，后来停止合作。', action:'assert' }
  const sources = relationshipSources({ records:[{...record,id:1},{...record,id:2},{...record,id:3,action:'end'}] })
  assert.deepEqual(sources.map(r=>r.id), [1,3])
})
