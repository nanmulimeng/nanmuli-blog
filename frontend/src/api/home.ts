import { get } from '@/utils/request'
import type { HomeAggregated } from '@/types/home'

export function getHomeAggregated(): Promise<HomeAggregated> {
  return get<HomeAggregated>('/home/aggregated')
}
