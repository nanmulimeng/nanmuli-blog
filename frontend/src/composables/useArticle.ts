import { ref, computed } from 'vue'
import {
  getArticleList,
  getArticleBySlug,
  getTopArticles,
  createArticle,
  updateArticle,
  deleteArticle,
} from '@/api/article'
import type { Article, ArticleQuery } from '@/types/article'

/**
 * 文章数据管理组合式函数
 */
export function useArticle() {
  const loading = ref(false)
  const articles = ref<Article[]>([])
  const currentArticle = ref<Article | null>(null)
  const total = ref(0)

  const articleList = computed(() => articles.value)

  async function fetchArticles(query: ArticleQuery): Promise<void> {
    loading.value = true
    try {
      const res = await getArticleList(query)
      articles.value = res.records
      total.value = res.total
    } finally {
      loading.value = false
    }
  }

  async function fetchArticleBySlug(slug: string): Promise<void> {
    loading.value = true
    try {
      currentArticle.value = await getArticleBySlug(slug)
    } finally {
      loading.value = false
    }
  }

  async function fetchTopArticles(limit = 5): Promise<Article[]> {
    return await getTopArticles(limit)
  }

  async function saveArticle(data: Partial<Article>): Promise<string> {
    if (data.id) {
      await updateArticle(data.id, data)
      return data.id
    }
    return await createArticle(data)
  }

  async function removeArticle(id: string): Promise<void> {
    await deleteArticle(id)
  }

  return {
    loading,
    articles: articleList,
    currentArticle,
    total,
    fetchArticles,
    fetchArticleBySlug,
    fetchTopArticles,
    saveArticle,
    removeArticle,
  }
}
