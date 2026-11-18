<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import type { Evidence, Source } from './api'
import { plotClient } from './api'

const props = defineProps<{ bookId: string; cutoff: number; evidence?: Evidence }>()
const isOpen = defineModel<boolean>({ required: true })
const source = ref<Source>()
const error = ref('')
let controller: AbortController | undefined

const highlighted = computed(() => {
  const citation = props.evidence
  const paragraph = source.value?.chapter.paragraphs.find(
    item => item.id === citation?.paragraph_id,
  )
  if (!citation || !paragraph) return undefined
  const characters = Array.from(paragraph.text)
  return {
    paragraphId: paragraph.id,
    before: characters.slice(0, citation.start).join(''),
    quote: characters.slice(citation.start, citation.end).join(''),
    after: characters.slice(citation.end).join(''),
  }
})

async function loadSource() {
  controller?.abort()
  source.value = undefined
  error.value = ''
  if (!isOpen.value || !props.evidence) return
  const requestController = new AbortController()
  controller = requestController
  try {
    const result = await plotClient(props.bookId, props.cutoff, requestController.signal)
      .source(props.evidence.chapter)
    if (requestController.signal.aborted) return
    source.value = result
    await new Promise<void>(resolve => requestAnimationFrame(() => resolve()))
    if (!requestController.signal.aborted) {
      document.getElementById(`paragraph-${props.evidence.paragraph_id}`)
        ?.scrollIntoView({ block: 'center' })
    }
  } catch (failure) {
    if (!requestController.signal.aborted) {
      error.value = failure instanceof Error ? failure.message : String(failure)
    }
  }
}

watch(
  () => [props.bookId, props.cutoff, props.evidence?.id, isOpen.value],
  () => void loadSource(),
  { immediate: true },
)
onBeforeUnmount(() => controller?.abort())
</script>

<template>
  <el-drawer v-model="isOpen" title="回到原文" size="min(640px, 100vw)" destroy-on-close>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <article v-if="source" class="source-reader">
      <p class="eyebrow">第 {{ source.chapter.number }} 章</p>
      <h2>{{ source.chapter.title }}</h2>
      <p
        v-for="paragraph in source.chapter.paragraphs"
        :id="`paragraph-${paragraph.id}`"
        :key="paragraph.id"
      >
        <template v-if="paragraph.id === highlighted?.paragraphId">
          {{ highlighted.before }}<mark>{{ highlighted.quote }}</mark>{{ highlighted.after }}
        </template>
        <template v-else>{{ paragraph.text }}</template>
      </p>
    </article>
    <el-skeleton v-else-if="!error" :rows="10" animated />
  </el-drawer>
</template>
