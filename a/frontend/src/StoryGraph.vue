<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { Evidence, Timeline } from './api'
import EventCard from './EventCard.vue'

const EDGE_VERTICAL_OFFSET_PX = 12
const EDGE_TARGET_GAP_PX = 6
const EDGE_LANE_COUNT = 4
const EDGE_LANE_GAP_PX = 5

const props = defineProps<{ timeline: Timeline; characterId: string }>()
defineEmits<{ open: [evidence: Evidence] }>()
const container = ref<HTMLElement>()
const paths = ref<{ id: string; path: string; title: string }[]>([])
const eventMap = computed(() => new Map(props.timeline.events.map(event => [event.id, event])))
const visible = computed(() => new Set(props.timeline.events.filter(event => !props.characterId || event.participants.some(person => person.id === props.characterId)).map(event => event.id)))
const unplacedIds = computed(() => new Set(props.timeline.unplaced_ids))
const simultaneousTitles = computed(() => {
  const labels = new Map<string, string[]>()
  for (const group of props.timeline.simultaneous_groups) {
    for (const eventId of group) {
      labels.set(eventId, group
        .filter(otherId => otherId !== eventId)
        .flatMap(otherId => {
          const title = eventMap.value.get(otherId)?.title
          return title ? [title] : []
        }))
    }
  }
  return labels
})
const layers = computed(() => props.timeline.layers.map(layer => layer
  .filter(id => !unplacedIds.value.has(id))
  .flatMap(id => {
    const event = eventMap.value.get(id)
    return event ? [{
      event,
      isVisible: visible.value.has(id),
      simultaneousTitles: simultaneousTitles.value.get(id) ?? [],
    }] : []
  }))
  .filter(layer => layer.length))
const unplaced = computed(() => props.timeline.events
  .filter(event => unplacedIds.value.has(event.id) && visible.value.has(event.id))
  .map(event => ({ event, simultaneousTitles: simultaneousTitles.value.get(event.id) ?? [] })))
const active = computed(() => props.timeline.constraints.filter(constraint => props.timeline.accepted_ids.includes(constraint.id) && constraint.relation !== 'simultaneous'))
const conflicts = computed(() => props.timeline.conflicts.map(conflict => ({
  reason: conflict.reason,
  constraints: props.timeline.constraints.filter(item => conflict.constraint_ids.includes(item.id)),
})))
let observer: ResizeObserver | undefined
let frame = 0

function layout() {
  const root = container.value
  if (!root) return
  const bounds = root.getBoundingClientRect()
  const nodes = new Map(Array.from(root.querySelectorAll<HTMLElement>('[data-event]')).map(element => [element.dataset.event, element.getBoundingClientRect()]))
  paths.value = active.value.flatMap((constraint, index) => {
    const source = nodes.get(constraint.relation === 'after' ? constraint.target : constraint.source)
    const target = nodes.get(constraint.relation === 'after' ? constraint.source : constraint.target)
    if (!source || !target) return []
    const startX = source.left + source.width / 2 - bounds.left
    const startY = source.bottom - bounds.top
    const endX = target.left + target.width / 2 - bounds.left
    const endY = target.top - bounds.top - EDGE_TARGET_GAP_PX
    const lane = bounds.width - EDGE_LANE_GAP_PX - (index % EDGE_LANE_COUNT) * EDGE_LANE_GAP_PX
    const startTurnY = startY + EDGE_VERTICAL_OFFSET_PX
    const endTurnY = endY - EDGE_VERTICAL_OFFSET_PX
    return [{ id: constraint.id, title: constraint.reason, path: `M ${startX} ${startY} L ${startX} ${startTurnY} L ${lane} ${startTurnY} L ${lane} ${endTurnY} L ${endX} ${endTurnY} L ${endX} ${endY}` }]
  })
}
function schedule() {
  cancelAnimationFrame(frame)
  frame = requestAnimationFrame(layout)
}
watch(() => props.timeline, async () => { await nextTick(); schedule() }, { deep: true })
onMounted(() => {
  observer = new ResizeObserver(schedule)
  if (container.value) observer.observe(container.value)
  schedule()
})
onBeforeUnmount(() => { observer?.disconnect(); cancelAnimationFrame(frame) })
</script>

<template>
  <div class="graph-legend"><span class="legend-line"></span>有原文依据的先后 <span class="graph-count">{{ timeline.events.length }} 个事件</span></div>
  <div ref="container" class="story-graph">
    <svg class="graph-edges" aria-hidden="true">
      <defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" /></marker></defs>
      <path v-for="edge in paths" :key="edge.id" :d="edge.path" marker-end="url(#arrow)"><title>{{ edge.title }}</title></path>
    </svg>
    <div v-for="(layer, index) in layers" :key="index" class="graph-layer">
      <EventCard
        v-for="item in layer"
        :key="item.event.id"
        :event="item.event"
        :muted="!item.isVisible"
        :simultaneous-titles="item.simultaneousTitles"
        @open="$emit('open', $event)"
      />
    </div>
  </div>
  <section v-if="unplaced.length" class="unplaced-section">
    <h3 class="section-label">时间待定</h3>
    <div class="event-grid">
      <EventCard
        v-for="item in unplaced"
        :key="item.event.id"
        :event="item.event"
        :simultaneous-titles="item.simultaneousTitles"
        @open="$emit('open', $event)"
      />
    </div>
  </section>
  <section v-if="timeline.conflicts.length" class="conflict-section">
    <h3 class="section-label">待核对的时间线索</h3>
    <div v-for="(conflict, index) in conflicts" :key="index" class="conflict-item">
      <p>{{ conflict.reason }}</p>
      <div v-for="constraint in conflict.constraints" :key="constraint.id">
        <p>{{ constraint.reason }}</p><EvidenceLinks :evidence="constraint.evidence" @open="$emit('open', $event)" />
      </div>
    </div>
  </section>
</template>
