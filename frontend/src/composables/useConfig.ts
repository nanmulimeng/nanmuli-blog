import { computed } from 'vue'
import { useConfigStore } from '@/stores/modules/config'

/**
 * 站点配置组合式函数
 */
export function useConfig() {
  const configStore = useConfigStore()

  const siteName = computed(() => configStore.siteName)
  const siteDescription = computed(() => configStore.siteDescription)
  const siteLogo = computed(() => configStore.siteLogo)
  const siteFavicon = computed(() => configStore.siteFavicon)
  const siteFooter = computed(() => configStore.siteFooter)
  const siteAbout = computed(() => configStore.siteAbout)
  const siteAvatar = computed(() => configStore.siteAvatar)
  const siteEmail = computed(() => configStore.siteEmail)
  const siteGithub = computed(() => configStore.siteGithub)

  async function loadConfig(): Promise<void> {
    await configStore.loadConfig()
  }

  return {
    siteName,
    siteDescription,
    siteLogo,
    siteFavicon,
    siteFooter,
    siteAbout,
    siteAvatar,
    siteEmail,
    siteGithub,
    loadConfig,
  }
}
