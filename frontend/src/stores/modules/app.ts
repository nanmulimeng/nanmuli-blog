import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAppStore = defineStore('app', () => {
  const sidebarCollapsed = ref(false)
  const isMobile = ref(false)

  function toggleSidebar(): void {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  function setMobile(value: boolean): void {
    isMobile.value = value
  }

  return {
    sidebarCollapsed,
    isMobile,
    toggleSidebar,
    setMobile,
  }
})
