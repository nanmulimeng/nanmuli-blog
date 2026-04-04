<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()
</script>

<template>
  <component :is="route.meta.layout || 'DefaultLayout'" />
</template>

<style>
#app {
  min-height: 100vh;
}
</style>
