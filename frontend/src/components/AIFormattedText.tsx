interface AIFormattedTextProps {
  text: string
  emptyText?: string
}

interface Section {
  title: string | null
  lines: string[]
}

const SECTION_TITLES: Record<string, string> = {
  'AI LOG INTERPRETATION': 'AI Log Interpretation',
  WARNINGS: 'Warnings',
  EVENTS: 'Events',
  'RISK SCORES': 'Risk Scores',
  'BOTTLENECK ANALYSIS': 'Bottleneck Analysis',
  SUMMARY: 'Summary',
  IMPACT: 'Impact',
  SUGGESTIONS: 'Suggestions',
  NODES: 'Nodes',
}

function cleanInline(value: string) {
  return value
    .replace(/```(?:json)?/gi, '')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/__([^_]+)__/g, '$1')
    .replace(/\*([^*]+)\*/g, '$1')
    .replace(/^\s*[-*]\s+/, '')
    .replace(/\s+/g, ' ')
    .trim()
}

function sectionTitleFromLine(line: string) {
  const normalized = cleanInline(line)
    .replace(/^#{1,6}\s*/, '')
    .replace(/:$/, '')
    .trim()
    .toUpperCase()

  return SECTION_TITLES[normalized] ?? null
}

function splitSections(text: string): Section[] {
  const sections: Section[] = []
  let current: Section = { title: null, lines: [] }

  text.replace(/\r\n/g, '\n').split('\n').forEach((rawLine) => {
    const line = rawLine.trim()
    if (!line) return

    const title = sectionTitleFromLine(line)
    if (title) {
      if (current.title || current.lines.length) sections.push(current)
      current = { title, lines: [] }
      return
    }

    current.lines.push(line)
  })

  if (current.title || current.lines.length) sections.push(current)
  return sections
}

function renderLines(lines: string[]) {
  const items: JSX.Element[] = []
  let bullets: string[] = []

  const flushBullets = () => {
    if (!bullets.length) return
    const currentBullets = bullets
    bullets = []
    items.push(
      <ul key={`list-${items.length}`} className="ai-list">
        {currentBullets.map((item, index) => (
          <li key={`${item}-${index}`}>{cleanInline(item)}</li>
        ))}
      </ul>,
    )
  }

  lines.forEach((line) => {
    if (/^\s*[-*]\s+/.test(line)) {
      bullets.push(line)
      return
    }

    flushBullets()
    const cleaned = cleanInline(line)
    if (!cleaned) return

    const labelMatch = cleaned.match(/^([A-Za-z][A-Za-z ]{1,24}):\s*(.+)$/)
    if (labelMatch) {
      items.push(
        <p key={`row-${items.length}`} className="ai-definition">
          <span>{labelMatch[1]}:</span> {labelMatch[2]}
        </p>,
      )
      return
    }

    items.push(<p key={`p-${items.length}`}>{cleaned}</p>)
  })

  flushBullets()
  return items
}

export default function AIFormattedText({ text, emptyText = 'Waiting for AI insight...' }: AIFormattedTextProps) {
  const sections = splitSections(text)

  if (!sections.length) {
    return <span className="text-black/40">{emptyText}</span>
  }

  return (
    <div className="ai-formatted">
      {sections.map((section, index) => (
        <section key={`${section.title ?? 'intro'}-${index}`} className="ai-section">
          {section.title && <h3>{section.title}</h3>}
          <div className="ai-section-body">{renderLines(section.lines)}</div>
        </section>
      ))}
    </div>
  )
}
