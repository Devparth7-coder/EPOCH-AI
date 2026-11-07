import { Navigate, Route, Routes } from 'react-router-dom'
import AppShell from './components/AppShell'
import Landing from './pages/Landing'
import Dashboard from './pages/Dashboard'
import Workspace from './pages/Workspace'
import EvidenceExplorer from './pages/EvidenceExplorer'
import ReportPage from './pages/ReportPage'
import HistoryPage from './pages/HistoryPage'
import SystemPage from './pages/SystemPage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/app" element={<AppShell />}>
        <Route index element={<Dashboard />} />
        <Route path="workspace" element={<Workspace />} />
        <Route path="workspace/:id" element={<Workspace />} />
        <Route path="evidence" element={<EvidenceExplorer />} />
        <Route path="evidence/:id" element={<EvidenceExplorer />} />
        <Route path="research/:id" element={<ReportPage />} />
        <Route path="history" element={<HistoryPage />} />
        <Route path="system" element={<SystemPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
