import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getPublicConfig } from '@/api/config'

export const useConfigStore = defineStore('config', () => {
  const siteName = ref('Nanmuli Blog')
  const siteDescription = ref('记录技术成长，分享学习心得')
  const siteLogo = ref('')
  const siteFavicon = ref('')
  const siteFooter = ref('© 2025 Nanmuli Blog')
  const siteAbout = ref('')
  const siteAvatar = ref('')
  const siteAuthor = ref('')
  const siteEmail = ref('')
  const siteGithub = ref('')
  const siteIcp = ref('')

  async function loadConfig(): Promise<void> {
    try {
      const config = await getPublicConfig()
      siteName.value = config['site.name'] || siteName.value
      siteDescription.value = config['site.description'] || siteDescription.value
      siteLogo.value = config['site.logo'] || siteLogo.value
      siteFavicon.value = config['site.favicon'] || siteFavicon.value
      siteFooter.value = config['site.footer'] || siteFooter.value
      siteAbout.value = config['site.about'] || siteAbout.value
      siteAvatar.value = config['site.avatar'] || siteAvatar.value
      siteAuthor.value = config['site.author'] || siteAuthor.value
      siteEmail.value = config['site.email'] || siteEmail.value
      siteGithub.value = config['site.github'] || siteGithub.value
      siteIcp.value = config['site.icp'] || siteIcp.value
    } catch {
      // 使用默认值
    }
  }

  return {
    siteName,
    siteDescription,
    siteLogo,
    siteFavicon,
    siteFooter,
    siteAbout,
    siteAvatar,
    siteAuthor,
    siteEmail,
    siteGithub,
    siteIcp,
    loadConfig,
  }
})
