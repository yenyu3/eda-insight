import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { ParserResult } from '../types'

export default function Upload() {
  const [files, setFiles] = useState<File[]>([])
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [starting, setStarting] = useState(false)
  const [parseResult, setParseResult] = useState<ParserResult | null>(null)
  const [runId, setRunId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const resultRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()

  function handleFiles(newFiles: FileList | null) {
    if (!newFiles) return
    const vFiles = Array.from(newFiles).filter((f) => f.name.endsWith('.v'))
    if (!vFiles.length) {
      setError('Please upload at least one .v file.')
      return
    }
    setFiles(vFiles)
    setError(null)
    setParseResult(null)
    setRunId(null)
  }

  async function handleUpload() {
    if (!files.length) return
    setUploading(true)
    setError(null)
    try {
      const form = new FormData()
      files.forEach((f) => form.append('file', f))
      const res = await fetch('/api/upload', { method: 'POST', body: form })
      if (!res.ok) throw new Error(`Upload failed with status ${res.status}`)
      const data = await res.json() as { run_id: string; parser_result: ParserResult }
      setParseResult(data.parser_result)
      setRunId(data.run_id)
      window.requestAnimationFrame(() => {
        resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      })
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setUploading(false)
    }
  }

  async function handleRun() {
    if (!runId || starting) return
    setStarting(true)
    setError(null)
    try {
      const res = await fetch('/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ run_id: runId }),
      })
      if (!res.ok) {
        throw new Error(`Analysis failed to start with status ${res.status}`)
      }
      window.localStorage.setItem('eda-insight:last-run-id', runId)
      navigate(`/analysis/${runId}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setStarting(false)
    }
  }

  const modules = parseResult?.modules ?? []
  const hasParsed = parseResult != null

  return (
    <div className="eda-container eda-narrow">
      <div className="mb-10">
        <span className="section-kicker">Verilog Intake</span>
        <h1 className="page-title">Upload a design and inspect the workflow.</h1>
        <p className="page-subtitle">
          Drop one or more Verilog files, preview parsed modules, then launch the EDA pipeline for
          simulation, synthesis, dependency analysis, and AI-assisted review.
        </p>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept=".v"
        multiple
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />

      {!hasParsed && (
        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => { e.preventDefault(); setDragging(false); handleFiles(e.dataTransfer.files) }}
          onClick={() => inputRef.current?.click()}
          className={`drop-zone ${dragging ? 'dragging' : ''}`}
        >
          <div className="drop-zone-content">
            <div className="drop-icon">.v</div>
            <h2 className="text-xl font-light text-[var(--heading-color)]">Drop Verilog files here</h2>
            <p className="mt-4 text-sm text-black/50">
              Include the design module and testbench when available.
            </p>
            {files.length > 0 && (
              <div className="mt-6">
                <div className="flex flex-wrap justify-center gap-2">
                  {files.map((f) => (
                    <span key={f.name} className="tag">{f.name}</span>
                  ))}
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    handleUpload()
                  }}
                  disabled={uploading}
                  className="btn-primary mt-6 min-w-52"
                >
                  {uploading ? 'Parsing files...' : 'Upload and parse'}
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {error && <p className="mt-4 text-sm text-red-600">{error}</p>}

      {hasParsed && (
        <div ref={resultRef} className="surface-card panel scroll-mt-32">
          <div className="mb-6 flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
            <div>
              <h2 className="panel-title mb-3">Parsed Modules</h2>
              <div className="flex flex-wrap gap-2">
                {files.map((f) => (
                  <span key={f.name} className="tag">{f.name}</span>
                ))}
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className="btn-secondary"
                onClick={() => {
                  setParseResult(null)
                  setRunId(null)
                  inputRef.current?.click()
                }}
              >
                Choose different files
              </button>
              <button onClick={handleRun} disabled={starting} className="btn-primary">
                {starting ? 'Starting...' : 'Start analysis'}
              </button>
            </div>
          </div>

          <div className="space-y-3">
            {modules.map((m) => (
              <div key={m.name} className="rounded-xl border border-black/10 bg-black/[0.02] p-4">
                <div className="mb-2 flex items-center gap-2">
                  <span className="font-mono text-sm font-semibold text-[var(--heading-color)]">{m.name}</span>
                  <span className="tag">{m.logic_type}</span>
                </div>
                <div className="flex flex-wrap gap-4 text-xs text-black/50">
                  <span>{m.ports.length} ports</span>
                  <span>{m.signals.length} signals</span>
                  {m.instantiations.length > 0 && (
                    <span>instances: {m.instantiations.join(', ')}</span>
                  )}
                </div>
              </div>
            ))}
          </div>

          {parseResult.lint_issues?.length > 0 && (
            <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-4">
              <p className="mb-1 text-xs font-medium text-amber-700">Lint Issues</p>
              {parseResult.lint_issues.map((issue, i) => (
                <p key={i} className="text-xs text-amber-600">
                  {issue.type}: {issue.signal} (line {issue.line})
                </p>
              ))}
            </div>
          )}

          <button
            onClick={handleRun}
            disabled={starting}
            className="btn-primary mt-5 w-full md:hidden"
          >
            {starting ? 'Starting...' : 'Start analysis'}
          </button>
        </div>
      )}
    </div>
  )
}
