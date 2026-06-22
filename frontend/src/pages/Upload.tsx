import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import LoadingState from '../components/LoadingState'
import type { ParserResult } from '../types'

type UploadStep = 1 | 2 | 3

const GOALS = [
  { id: 'simulate', label: 'Simulation', description: 'Run the testbench and inspect waveform behavior.' },
  { id: 'synthesize', label: 'Synthesis', description: 'Estimate cells, timing, slack, and resource cost.' },
  { id: 'dependency', label: 'Dependency graph', description: 'Map module relationships and possible bottlenecks.' },
  { id: 'lint', label: 'Lint checks', description: 'Keep parser warnings and structural checks in the report.' },
]

const UPLOAD_STEPS = [
  {
    label: 'Drop file',
    title: 'Choose Verilog files',
    description: 'Upload the design module and any related testbench files.',
  },
  {
    label: 'Preview & parse',
    title: 'Review parsed modules',
    description: 'Confirm the file preview, module names, ports, and lint findings before continuing.',
  },
  {
    label: 'Set goals & run',
    title: 'Select analysis goals',
    description: 'All goals are enabled by default. Turn off anything you do not need for this run.',
  },
]

export default function Upload() {
  const [step, setStep] = useState<UploadStep>(1)
  const [files, setFiles] = useState<File[]>([])
  const [preview, setPreview] = useState('')
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [starting, setStarting] = useState(false)
  const [parseResult, setParseResult] = useState<ParserResult | null>(null)
  const [runId, setRunId] = useState<string | null>(null)
  const [selectedGoals, setSelectedGoals] = useState<string[]>(() => GOALS.map((goal) => goal.id))
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()

  // Track the latest pending runId and whether the pipeline was started,
  // so we can clean up abandoned uploads on unmount or Re-select.
  const pendingRunIdRef = useRef<string | null>(null)
  const pipelineStartedRef = useRef(false)

  useEffect(() => {
    if (!pipelineStartedRef.current) {
      pendingRunIdRef.current = runId
    }
  }, [runId])

  useEffect(() => {
    return () => {
      if (pendingRunIdRef.current) {
        fetch(`/api/run/${pendingRunIdRef.current}`, { method: 'DELETE' }).catch(() => {})
      }
    }
  }, [])

  async function handleFiles(newFiles: FileList | null) {
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
    setPreview((await vFiles[0].text()).split('\n').slice(0, 12).join('\n'))
    await uploadFiles(vFiles)
  }

  async function uploadFiles(vFiles = files) {
    if (!vFiles.length) return
    setUploading(true)
    setError(null)
    try {
      const form = new FormData()
      vFiles.forEach((f) => form.append('file', f))
      const res = await fetch('/api/upload', { method: 'POST', body: form })
      if (!res.ok) throw new Error(`Upload failed with status ${res.status}`)
      const data = await res.json() as { run_id: string; parser_result: ParserResult; preview?: string }
      setParseResult(data.parser_result)
      setRunId(data.run_id)
      if (data.preview) setPreview(data.preview)
      setStep(2)
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
        body: JSON.stringify({ run_id: runId, goals: selectedGoals }),
      })
      if (!res.ok) throw new Error(`Analysis failed to start with status ${res.status}`)
      pipelineStartedRef.current = true
      pendingRunIdRef.current = null
      window.localStorage.setItem('veriflow-insight:last-run-id', runId)
      navigate(`/analysis/${runId}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setStarting(false)
    }
  }

  function resetSelection() {
    if (runId) {
      fetch(`/api/run/${runId}`, { method: 'DELETE' }).catch(() => {})
      pendingRunIdRef.current = null
    }
    setStep(1)
    setFiles([])
    setPreview('')
    setParseResult(null)
    setRunId(null)
    inputRef.current?.click()
  }

  function toggleGoal(goal: string) {
    setSelectedGoals((current) => {
      return current.includes(goal) ? current.filter((g) => g !== goal) : [...current, goal]
    })
  }

  const modules = parseResult?.modules ?? []
  return (
    <div className="eda-container">
      <div className="upload-hero">
        <div>
          <span className="section-kicker">Verilog Intake</span>
          <h1 className="page-title">Upload a design and inspect the workflow.</h1>
          <p className="page-subtitle">
            Drop one or more Verilog files, preview parsed modules, choose analysis goals, then launch the EDA pipeline.
          </p>
        </div>

        <div className="upload-progress">
          <div className="upload-stepper" aria-label="Upload progress">
            {UPLOAD_STEPS.map((item, index) => {
              const stepNumber = index + 1
              const status = stepNumber < step ? 'complete' : stepNumber === step ? 'current' : 'upcoming'
              return (
                <div key={item.label} className={`upload-step ${status}`}>
                  <span className="upload-step-mark">
                    <span>{stepNumber}</span>
                  </span>
                  <span className="upload-step-label">{item.label}</span>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept=".v"
        multiple
        className="hidden"
        onChange={(e) => void handleFiles(e.target.files)}
      />

      {step === 1 && (
        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => { e.preventDefault(); setDragging(false); void handleFiles(e.dataTransfer.files) }}
          onClick={() => inputRef.current?.click()}
          className={`drop-zone ${dragging ? 'dragging' : ''}`}
        >
          <div className="drop-zone-content">
            <div className={`drop-icon ${uploading ? 'loading' : ''}`}>.v</div>
            <h2 className="text-xl font-light text-[var(--heading-color)]">
              {uploading ? 'Parsing files...' : 'Drop Verilog files here'}
            </h2>
            <p className="mt-4 text-sm text-black/50">
              {uploading
                ? 'Uploading Verilog and extracting modules, ports, and lint findings.'
                : 'Include the design module and testbench when available.'}
            </p>
          </div>
        </div>
      )}

      {step === 2 && parseResult && (
        <div className="surface-card panel upload-panel">
          <div className="upload-panel-head">
            <div>
              <h2 className="panel-title mb-3">File Preview</h2>
              <div className="flex flex-wrap gap-2">
                {files.map((f) => <span key={f.name} className="tag">{f.name}</span>)}
              </div>
            </div>
            <div className="upload-actions">
              <button className="btn-secondary" type="button" onClick={resetSelection}>Re-select</button>
              <button className="btn-primary" type="button" onClick={() => setStep(3)}>Continue</button>
            </div>
          </div>

          <pre className="upload-code-preview">
            {preview || 'No preview available.'}
          </pre>

          <h2 className="panel-title">Parse Preview</h2>
          <div className="space-y-3">
            {modules.map((m) => (
              <div key={m.name} className="rounded-xl border border-black/10 bg-black/[0.02] p-4">
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <span className="font-mono text-sm font-semibold text-[var(--heading-color)]">{m.name}</span>
                  <span className="tag">{m.logic_type}</span>
                  <span className="tag">{m.ports.length} ports</span>
                </div>
                <div className="text-xs text-black/50">
                  {m.instantiations.length ? `instances: ${m.instantiations.join(', ')}` : 'single-module or leaf module'}
                </div>
              </div>
            ))}
          </div>

          {parseResult.lint_issues?.length > 0 && (
            <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-4">
              <p className="mb-1 text-xs font-medium text-amber-700">Lint Issues</p>
              {parseResult.lint_issues.map((issue, i) => (
                <p key={i} className="text-xs text-amber-600">
                  {issue.type}: {issue.signal} (line {issue.line ?? 'N/A'})
                </p>
              ))}
            </div>
          )}
        </div>
      )}

      {step === 3 && (
        <div className="surface-card panel upload-panel">
          <div className="upload-panel-head">
            <div>
              <h2 className="panel-title mb-3">Analysis Goals</h2>
              <p className="text-sm leading-relaxed text-black/55">
                Select the pipeline work to run. Simulation and synthesis are recommended for most designs.
              </p>
            </div>
            <div className="upload-actions">
              <button className="btn-secondary" type="button" onClick={() => setStep(2)}>Back</button>
              <button className="btn-primary" type="button" disabled={starting || selectedGoals.length === 0} onClick={handleRun}>
                <span className={`run-icon ${starting ? 'running' : ''}`} aria-hidden="true" />
                {starting ? 'Starting...' : 'Run analysis'}
              </button>
            </div>
          </div>

          <div className="goal-grid">
            {GOALS.map((goal) => {
              const active = selectedGoals.includes(goal.id)
              return (
                <button
                  key={goal.id}
                  type="button"
                  onClick={() => toggleGoal(goal.id)}
                  className={`goal-option ${active ? 'active' : ''}`}
                  aria-pressed={active}
                >
                  <span className="goal-check" aria-hidden="true" />
                  <span className="goal-copy">
                    <span className="goal-label">{goal.label}</span>
                    <span className="goal-description">{goal.description}</span>
                  </span>
                </button>
              )
            })}
          </div>

          {starting && (
            <LoadingState
              className="mt-5"
              title="Starting EDA pipeline"
              description="Creating the run plan and handing the selected goals to the backend."
            />
          )}
        </div>
      )}

      {error && <p className="mt-4 text-sm text-red-600">{error}</p>}
    </div>
  )
}
