<script setup lang="ts">
import type { Evidence } from './api'
defineProps<{ evidence: Evidence[] }>()
defineEmits<{ open: [evidence: Evidence] }>()
</script>

<template>
  <div class="evidence-links">
    <button v-for="item in evidence" :key="item.id" type="button" @click="$emit('open', item)">
      第 {{ item.chapter }} 章 · 原文 <span aria-hidden="true">↗</span>
    </button>
  </div>
</template>
