/**
 * App.tsx — Root application component
 *
 * Routing structure:
 *   /           → Hero landing page (HeroSection)
 *   /forecast   → Load forecast view (predicted vs actual)
 *   /latency    → Latency comparison (P50/P95/P99)
 *   /benchmark  → Full benchmark results table
 *
 * Phase 7 dashboard views will replace the placeholder routes.
 */

import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { HeroSection } from '@/components/blocks/hero-section-1'

// ── Placeholder — replaced with real components in Phase 7 ───────────────────
function PlaceholderView({ title }: { title: string }) {
  return (
    <div className="flex items-center justify-center h-screen bg-background">
      <div className="text-center">
        <div className="text-5xl mb-4">🚧</div>
        <h2 className="text-2xl font-bold text-foreground mb-2">{title}</h2>
        <p className="text-muted-foreground text-sm">Coming in Phase 7</p>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HeroSection />} />
        <Route path="/forecast" element={<PlaceholderView title="Load Forecast" />} />
        <Route path="/latency" element={<PlaceholderView title="Latency Comparison" />} />
        <Route path="/benchmark" element={<PlaceholderView title="Benchmark Results" />} />
      </Routes>
    </BrowserRouter>
  )
}
