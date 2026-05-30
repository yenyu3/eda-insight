import Plot from 'react-plotly.js'
import type { PlotData, Layout } from 'plotly.js'
import type { WaveformData } from '../types'

const SIG_COLORS: Record<string, string> = { clk: '#378ADD', reset: '#1D9E75' }
const DEFAULT_COLOR = '#EF9F27'

interface WaveformChartProps {
  waveform?: WaveformData | null
}

export default function WaveformChart({ waveform }: WaveformChartProps) {
  if (!waveform?.signals || !waveform?.timeline) {
    return <p className="text-sm text-gray-400">No waveform data.</p>
  }

  const traces = waveform.signals.map((sig) => {
    const tl = waveform.timeline[sig] ?? {}
    return {
      x: tl.times ?? [],
      y: tl.values ?? [],
      name: sig,
      type: 'scatter' as const,
      mode: 'lines' as const,
      line: { shape: 'hv' as const, color: SIG_COLORS[sig] ?? DEFAULT_COLOR, width: 1.5 },
    }
  })

  const layout = {
    autosize: true,
    height: 260,
    margin: { t: 10, b: 40, l: 50, r: 10 },
    paper_bgcolor: 'transparent',
    plot_bgcolor: '#f9fafb',
    font: { size: 11, color: '#6b7280' },
    xaxis: { title: 'Time (ns)', gridcolor: '#e5e7eb' },
    yaxis: { gridcolor: '#e5e7eb' },
    legend: { orientation: 'h' as const, y: -0.2 },
    showlegend: true,
  }

  return (
    <div className="waveform-chart">
      <Plot
        data={traces as Partial<PlotData>[]}
        layout={layout as Partial<Layout>}
        config={{ displayModeBar: false, responsive: true }}
        useResizeHandler
        style={{ width: '100%', height: '260px' }}
      />
    </div>
  )
}
