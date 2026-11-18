<script setup lang="ts">
import type { Evidence, Event } from './api'
import { statementLabel } from './api'
import EvidenceLinks from './EvidenceLinks.vue'

withDefaults(defineProps<{
  event: Event
  simultaneousTitles?: string[]
  muted?: boolean
}>(), {
  simultaneousTitles: () => [],
  muted: false,
})

defineEmits<{ open: [evidence: Evidence] }>()
</script>

<template>
  <article :data-event="event.id" class="event-card" :class="{ muted }">
    <div class="event-meta">
      <span>第 {{ event.known_from }} 章揭示</span>
      <el-tag v-if="event.statement !== 'fact'" size="small" type="info">
        {{ statementLabel[event.statement] }}
      </el-tag>
      <el-tag v-if="event.retrospective" size="small" type="warning">回忆</el-tag>
    </div>
    <h3>{{ event.title }}</h3>
    <p v-if="event.time_expression" class="event-time">{{ event.time_expression }}</p>
    <p v-if="event.time_bounds" class="event-time">
      {{ event.time_bounds.earliest }} — {{ event.time_bounds.latest }}
    </p>
    <p v-if="event.participants.length" class="event-people">
      {{ event.participants.map(person => person.name).join(' · ') }}
    </p>
    <p v-if="simultaneousTitles.length" class="event-time">
      同时开始：{{ simultaneousTitles.join('、') }}
    </p>
    <EvidenceLinks :evidence="event.evidence" @open="$emit('open', $event)" />
  </article>
</template>
