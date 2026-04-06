import type { Article } from './article'
import type { Category } from './category'
import type { Skill } from './skill'
import type { Project } from './project'

export interface HomeAggregated {
  latestArticles: Article[]
  topArticles: Article[]
  hotArticles: Article[]
  categories: Category[]
  skills: Skill[]
  projects: Project[]
  stats: SiteStats
}

export interface SiteStats {
  articleCount: number
  projectCount: number
  dailyLogCount: number
}
