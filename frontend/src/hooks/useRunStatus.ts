import { useQuery } from '@tanstack/react-query'
import type { RunStatus } from '../types'

export function useRunStatus(runId: string | undefined) {
  return useQuery<RunStatus>({
    queryKey: ['run-status', runId],
    queryFn: () =>
      fetch(`/api/status/${runId}`).then((r) => {
        if (!r.ok) throw new Error('status fetch failed')
        return r.json() as Promise<RunStatus>
      }),
    refetchInterval: (query) => {
      const overall = query.state.data?.overall
      return overall === 'running' || overall === 'pending' ? 2000 : false
    },
    enabled: !!runId,
  })
}
