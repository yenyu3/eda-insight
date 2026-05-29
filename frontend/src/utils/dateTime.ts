const TAIPEI_TIME_ZONE = 'Asia/Taipei'

function parseApiTimestamp(timestamp: string) {
  const hasTimeZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(timestamp)
  const normalized = timestamp.includes('T') ? timestamp : timestamp.replace(' ', 'T')

  return new Date(hasTimeZone ? normalized : `${normalized}Z`)
}

export function formatTaipeiDateTime(timestamp: string) {
  return new Intl.DateTimeFormat('zh-TW', {
    dateStyle: 'short',
    timeStyle: 'medium',
    timeZone: TAIPEI_TIME_ZONE,
  }).format(parseApiTimestamp(timestamp))
}
