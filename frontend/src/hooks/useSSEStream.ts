import { useState, useEffect, useRef } from 'react'

interface SSEMessage {
  type: 'text' | 'done' | 'error'
  content?: string
}

export function useSSEStream(runId: string | undefined, enabled = true) {
  const [text, setText] = useState('')
  const [done, setDone] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const esRef = useRef<EventSource | null>(null)
  const doneRef = useRef(false)

  useEffect(() => {
    if (!runId || !enabled) return

    setText('')
    setDone(false)
    setError(null)
    doneRef.current = false

    const es = new EventSource(`/api/stream/${runId}`)
    esRef.current = es

    es.onmessage = (e: MessageEvent<string>) => {
      try {
        const data = JSON.parse(e.data) as SSEMessage
        if (data.type === 'text') setText((prev) => prev + (data.content ?? ''))
        else if (data.type === 'done') { doneRef.current = true; setDone(true); es.close() }
        else if (data.type === 'error') { doneRef.current = true; setError(data.content ?? 'Unknown error'); es.close() }
      } catch {
        // ignore malformed SSE frames
      }
    }

    es.onerror = () => {
      if (!doneRef.current) setError('SSE connection error')
      es.close()
    }

    return () => { es.close(); esRef.current = null }
  }, [runId, enabled])

  return { text, done, error }
}
