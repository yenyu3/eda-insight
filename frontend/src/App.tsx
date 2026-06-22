import { BrowserRouter, Navigate, Routes, Route } from 'react-router-dom'
import Navbar from './components/Navbar'
import Upload from './pages/Upload'
import Analysis from './pages/Analysis'
import History from './pages/History'
import Compare from './pages/Compare'

function AnalysisRedirect() {
  const lastRunId = window.localStorage.getItem('veriflow-insight:last-run-id')
  return <Navigate to={lastRunId ? `/analysis/${lastRunId}` : '/history'} replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-shell">
        <Navbar />
        <main className="app-main">
          <Routes>
            <Route path="/" element={<Upload />} />
            <Route path="/analysis" element={<AnalysisRedirect />} />
            <Route path="/analysis/:runId" element={<Analysis />} />
            <Route path="/history" element={<History />} />
            <Route path="/compare" element={<Compare />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
