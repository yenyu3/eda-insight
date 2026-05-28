import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Navbar from './components/Navbar'
import Upload from './pages/Upload'
import Analysis from './pages/Analysis'
import History from './pages/History'
import Compare from './pages/Compare'

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-shell">
        <Navbar />
        <main className="app-main">
          <Routes>
            <Route path="/" element={<Upload />} />
            <Route path="/analysis/:runId" element={<Analysis />} />
            <Route path="/history" element={<History />} />
            <Route path="/compare" element={<Compare />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
