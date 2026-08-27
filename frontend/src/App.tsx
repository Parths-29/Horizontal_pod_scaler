/**
 * App.tsx — Root application component
 *
 * Routing structure:
 *   /           → Dashboard overview (summary cards + replica comparison)
 *   /forecast   → Load forecast view (predicted vs actual)
 *   /latency    → Latency comparison (P50/P95/P99)
 *   /benchmark  → Full benchmark results table
 *
 * All route components are lazy-loaded to keep the initial bundle small.
 */

import { BrowserRouter, Routes, Route } from 'react-router-dom'

// ── Placeholder — will be replaced with real components in Phase 7 ───────────
function PlaceholderView({ title }: { title: string }) {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      height: '100vh',
      background: '#0f1117',
      color: '#7c3aed',
      fontFamily: 'Inter, sans-serif',
      fontSize: '1.5rem',
    }}>
      🚧 {title} — Coming in Phase 7
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<PlaceholderView title="Dashboard" />} />
        <Route path="/forecast" element={<PlaceholderView title="Load Forecast" />} />
        <Route path="/latency" element={<PlaceholderView title="Latency Comparison" />} />
        <Route path="/benchmark" element={<PlaceholderView title="Benchmark Results" />} />
      </Routes>
    </BrowserRouter>
  )
}
