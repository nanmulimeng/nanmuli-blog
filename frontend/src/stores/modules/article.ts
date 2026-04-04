import { defineStore } from 'pinia'
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
import type { PageResult } from '@/types/api'

/**
 * 文章状态管理 Store
 */
export const useArticleStore = defineStore(
  'article',
  () => {
    // State
    const articles = ref<Article[]>([])
    const currentArticle = ref<Article | null>(null)
    const topArticles = ref<Article[]>([])
    const loading = ref(false)
    const pagination = ref({
      current: 1,
      size: 10,
      total: 0,
    })

    // Getters
    const articleList = computed(() => articles.value)
    const hasCurrentArticle = computed(() => currentArticle.value !== null)

    // Actions
    async function fetchArticles(query?: ArticleQuery): Promise<void> {
      loading.value = true
      try {
        const params: ArticleQuery = {
          current: pagination.value.current,
          size: pagination.value.size,
          ...query,
        }
        const result: PageResult<Article> = await getArticleList(params)
        articles.value = result.records
        pagination.value.total = result.total
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

    async function fetchTopArticles(limit = 5): Promise<void> {
      topArticles.value = await getTopArticles(limit)
    }

    async function saveArticle(data: Partial<Article>): Promise<number> {
      if (data.id) {
        await updateArticle(data.id, data)
        return data.id
      }
      return await createArticle(data)
    }

    async function removeArticle(id: number): Promise<void> {
      await deleteArticle(id)
      articles.value = articles.value.filter((a) => a.id !== id)
    }

    function setCurrentArticle(article: Article | null): void {
      currentArticle.value = article
    }

    function updatePagination(current: number, size?: number): void {
      pagination.value.current = current
      if (size) pagination.value.size = size
    }

    function $reset(): void {
      articles.value = []
      currentArticle.value = null
      topArticles.value = []
      pagination.value = { current: 1, size: 10, total: 0 }
    }

    return {
      // State
      articles,
      currentArticle,
      topArticles,
      loading,
      pagination,
      // Getters
      articleList,
      hasCurrentArticle,
      // Actions
      fetchArticles,
      fetchArticleBySlug,
      fetchTopArticles,
      saveArticle,
      removeArticle,
      setCurrentArticle,
      updatePagination,
      $reset,
    }
  }
)
