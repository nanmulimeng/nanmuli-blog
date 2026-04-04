import type { Article } from './article'
import type { Category } from './category'
import type { Tag } from './tag'
import type { Skill } from './skill'
import type { Project } from './project'

export interface HomeAggregated {
  latestArticles: Article[]
  topArticles: Article[]
  hotArticles: Article[]
  categories: Category[]
  tags: Tag[]
  skills: Skill[]
  projects: Project[]
  stats: SiteStats
}

export interface SiteStats {
  articleCount: number
  categoryCount: number
  tagCount: number
  dailyLogCount: number
}
