/**
 * API 相关常量
 */

// HTTP 状态码
export const HTTP_STATUS = {
  OK: 200,
  BAD_REQUEST: 400,
  UNAUTHORIZED: 401,
  FORBIDDEN: 403,
  NOT_FOUND: 404,
  UNPROCESSABLE_ENTITY: 422,
  INTERNAL_SERVER_ERROR: 500,
} as const

// 业务状态码
export const BUSINESS_CODE = {
  SUCCESS: 200,
  ERROR: 500,
  PARAM_ERROR: 400,
  UNAUTHORIZED: 401,
  FORBIDDEN: 403,
  NOT_FOUND: 404,
  BUSINESS_ERROR: 422,
} as const

// API 前缀
export const API_PREFIX = '/api'
export const ADMIN_API_PREFIX = '/api/admin'

// 请求超时时间（毫秒）
export const REQUEST_TIMEOUT = 30000

// 请求重试次数
export const REQUEST_RETRY_COUNT = 3

/** 分页大小常量 */
export const PAGE_SIZE = {
  DEFAULT: 10,
  ARTICLE_FRONT: 12,
  ARTICLE_ADMIN: 10,
  DAILY_LOG_FRONT: 20,
  DAILY_LOG_ADMIN: 10,
  DIGEST: 10,
  COLLECTOR: 10,
  HOME_ARTICLES: 6,
  RELATED_ARTICLES: 4,
} as const

/** 轮询间隔常量（毫秒） */
export const POLLING_INTERVAL = {
  TASK_STATUS: 5000,
  DIGEST_STATUS: 5000,
  AUTO_SAVE: 30000,
} as const

/** 延迟常量（毫秒） */
export const DELAY = {
  UV_RECORD: 5000,
  DIGEST_REFRESH: 3000,
  LOADING_THRESHOLD: 100,
} as const
