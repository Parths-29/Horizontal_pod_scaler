import React from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, ChevronRight, Menu, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { AnimatedGroup } from '@/components/ui/animated-group'
import { cn } from '@/lib/utils'

// ── Transition presets ────────────────────────────────────────────────────────
const transitionVariants = {
  item: {
    hidden: {
      opacity: 0,
      filter: 'blur(12px)',
      y: 12,
    },
    visible: {
      opacity: 1,
      filter: 'blur(0px)',
      y: 0,
      transition: {
        type: 'spring' as const,
        bounce: 0.3,
        duration: 1.5,
      },
    },
  },
}

// ── Main hero export ──────────────────────────────────────────────────────────
export function HeroSection() {
  return (
    <>
      <HeroHeader />
      <main className="overflow-hidden">
        {/* Decorative elements removed for monochrome theme */}

        {/* ── Hero section ──────────────────────────────────────────────────── */}
        <section>
          <div className="relative pt-24 md:pt-36">
            {/* Subtle background noise/grid (monochrome) */}
            <div className="absolute inset-0 -z-20 bg-[linear-gradient(to_right,#80808012_1px,transparent_1px),linear-gradient(to_bottom,#80808012_1px,transparent_1px)] bg-[size:24px_24px]">
              <div className="absolute left-0 right-0 top-0 -z-10 m-auto h-[310px] w-[310px] rounded-full bg-white opacity-[0.05] blur-[100px]"></div>
            </div>

            {/* Headline + CTA */}
            <div className="mx-auto max-w-7xl px-6">
              <div className="text-center sm:mx-auto lg:mr-auto lg:mt-0">
                <AnimatedGroup variants={transitionVariants}>
                  {/* Announcement pill */}
                  <Link
                    to="#"
                    className="hover:bg-background dark:hover:border-t-border bg-muted group mx-auto flex w-fit items-center gap-4 rounded-full border p-1 pl-4 shadow-md shadow-black/5 transition-all duration-300 dark:border-t-white/5 dark:shadow-zinc-950">
                    <span className="text-foreground text-sm">Predictive Kubernetes Autoscaling — Now Open Source</span>
                    <span className="dark:border-background block h-4 w-0.5 border-l bg-white/20 dark:bg-zinc-700" />
                    <div className="bg-background group-hover:bg-muted size-6 overflow-hidden rounded-full duration-500">
                      <div className="flex w-12 -translate-x-1/2 duration-500 ease-in-out group-hover:translate-x-0">
                        <span className="flex size-6">
                          <ArrowRight className="m-auto size-3" />
                        </span>
                        <span className="flex size-6">
                          <ArrowRight className="m-auto size-3" />
                        </span>
                      </div>
                    </div>
                  </Link>

                  {/* Main headline */}
                  <h1 className="mt-8 max-w-4xl mx-auto text-balance text-6xl md:text-7xl lg:mt-16 xl:text-[5.25rem] font-bold tracking-tight">
                    Stop Reacting.<br />
                    <span className="text-foreground">
                      Start Predicting.
                    </span>
                  </h1>

                  <p className="mx-auto mt-8 max-w-2xl text-balance text-lg text-muted-foreground">
                    ML-powered Kubernetes autoscaling that provisions pods <em>before</em> traffic spikes hit —
                    benchmarked against standard HPA in a live AWS EKS environment.
                  </p>
                </AnimatedGroup>

                {/* CTA buttons */}
                <AnimatedGroup
                  variants={{
                    container: {
                      visible: {
                        transition: { staggerChildren: 0.05, delayChildren: 0.75 },
                      },
                    },
                    ...transitionVariants,
                  }}
                  className="mt-12 flex flex-col items-center justify-center gap-2 md:flex-row">
                  <div className="bg-foreground/10 rounded-[14px] border p-0.5">
                    <Button asChild size="lg" className="rounded-xl px-5 text-base">
                      <Link to="/benchmark">
                        <span className="text-nowrap">View Benchmark Results</span>
                      </Link>
                    </Button>
                  </div>
                  <Button
                    asChild
                    size="lg"
                    variant="ghost"
                    className="rounded-xl px-5">
                    <Link to="/forecast">
                      <span className="text-nowrap">Live Forecast →</span>
                    </Link>
                  </Button>
                </AnimatedGroup>
              </div>
            </div>

            {/* Hero dashboard screenshot */}
            <AnimatedGroup
              variants={{
                container: {
                  visible: {
                    transition: { staggerChildren: 0.05, delayChildren: 0.75 },
                  },
                },
                ...transitionVariants,
              }}>
              <div className="relative mt-8 overflow-hidden px-2 sm:mt-12 md:mt-20">
                <div
                  aria-hidden
                  className="bg-gradient-to-b to-background absolute inset-0 z-10 from-transparent from-35%"
                />
                <div className="bg-black/40 backdrop-blur-xl relative mx-auto max-w-6xl overflow-hidden rounded-2xl border border-white/10 p-4 shadow-2xl shadow-white/5 ring-1 ring-white/5">
                  {/* Grafana-style dashboard mockup */}
                  <DashboardPreview />
                </div>
              </div>
            </AnimatedGroup>
          </div>
        </section>

        {/* ── Technology / trust logos ──────────────────────────────────────── */}
        <section className="bg-background pb-16 pt-16 md:pb-32">
          <div className="group relative m-auto max-w-5xl px-6">
            <p className="text-center text-sm text-muted-foreground mb-10 tracking-widest uppercase">
              Built on battle-tested open-source infrastructure
            </p>
            <div className="mx-auto mt-4 grid max-w-3xl grid-cols-4 gap-x-12 gap-y-8 sm:gap-x-16 sm:gap-y-14 items-center">
              {techLogos.map((logo) => (
                <div key={logo.alt} className="flex justify-center">
                  <img
                    className="mx-auto h-6 w-fit opacity-60 hover:opacity-100 transition-opacity duration-300 dark:invert"
                    src={logo.src}
                    alt={logo.alt}
                    height="24"
                    width="auto"
                  />
                </div>
              ))}
            </div>

            {/* "Meet Our Customers" hover CTA */}
            <div className="absolute inset-0 z-10 flex scale-95 items-center justify-center opacity-0 duration-500 group-hover:scale-100 group-hover:opacity-100 pointer-events-none group-hover:pointer-events-auto">
              <a
                href="https://github.com/Parths-29/Horizontal_pod_scaler"
                target="_blank"
                rel="noopener noreferrer"
                className="block text-sm duration-150 hover:opacity-75 bg-background/80 backdrop-blur px-4 py-2 rounded-full border">
                <span>View on GitHub</span>
                <ChevronRight className="ml-1 inline-block size-3" />
              </a>
            </div>
          </div>
        </section>
      </main>
    </>
  )
}

// ── Internal: Dashboard preview card ─────────────────────────────────────────

function DashboardPreview() {
  return (
    <div className="aspect-[15/8] relative rounded-2xl overflow-hidden bg-[#0d1117] border border-white/5 p-6">
      {/* Header bar */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="size-3 rounded-full bg-red-500/70" />
          <div className="size-3 rounded-full bg-yellow-500/70" />
          <div className="size-3 rounded-full bg-green-500/70" />
          <span className="ml-2 text-xs text-zinc-500 font-mono">HPA Benchmark Dashboard — Live</span>
        </div>
        <span className="text-xs text-emerald-400 font-mono flex items-center gap-1">
          <span className="size-1.5 rounded-full bg-emerald-400 inline-block animate-pulse" />
          LIVE
        </span>
      </div>

      {/* Metric cards row */}
      <div className="grid grid-cols-4 gap-3 mb-6">
        {metrics.map((m) => (
          <div key={m.label} className="bg-white/[0.03] border border-white/5 rounded-xl p-3">
            <div className={`text-xs font-mono ${m.color} mb-1`}>{m.label}</div>
            <div className="text-xl font-bold text-white font-mono">{m.value}</div>
            <div className={`text-xs ${m.delta.startsWith('+') ? 'text-emerald-400' : 'text-red-400'}`}>{m.delta}</div>
          </div>
        ))}
      </div>

      {/* Chart area */}
      <div className="grid grid-cols-3 gap-3 h-28">
        {/* Replica count sparkline */}
        <div className="col-span-2 bg-white/[0.03] border border-white/5 rounded-xl p-3 overflow-hidden">
          <div className="text-xs text-zinc-500 mb-2 font-mono">Replica Count — HPA vs KEDA</div>
          <svg viewBox="0 0 300 60" className="w-full h-full" preserveAspectRatio="none">
            {/* HPA (reactive) — orange */}
            <polyline
              points="0,50 30,50 60,50 70,10 80,10 110,10 130,40 160,40 190,40 200,10 210,10 240,40 270,40 300,40"
              fill="none"
              stroke="#f97316"
              strokeWidth="1.5"
              opacity="0.8"
            />
            {/* KEDA (predictive) — violet */}
            <polyline
              points="0,45 30,40 60,25 70,15 80,15 110,15 130,35 160,35 190,30 200,15 210,15 240,35 270,35 300,35"
              fill="none"
              stroke="#8b5cf6"
              strokeWidth="1.5"
              opacity="0.9"
            />
            {/* Legend */}
            <rect x="10" y="2" width="8" height="2" rx="1" fill="#f97316" />
            <text x="22" y="5" className="text-[5px]" fill="#9ca3af" fontSize="5">HPA</text>
            <rect x="50" y="2" width="8" height="2" rx="1" fill="#8b5cf6" />
            <text x="62" y="5" className="text-[5px]" fill="#9ca3af" fontSize="5">KEDA</text>
          </svg>
        </div>

        {/* Latency card */}
        <div className="bg-white/[0.03] border border-white/5 rounded-xl p-3">
          <div className="text-xs text-zinc-500 mb-2 font-mono">P99 Latency (ms)</div>
          <div className="space-y-1.5">
            <div className="flex justify-between items-center">
              <span className="text-[10px] text-orange-400 font-mono">HPA</span>
              <div className="flex-1 mx-2 bg-white/5 rounded-full h-1">
                <div className="bg-orange-400 h-1 rounded-full" style={{ width: '72%' }} />
              </div>
              <span className="text-[10px] text-zinc-400 font-mono">487ms</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-[10px] text-violet-400 font-mono">KEDA</span>
              <div className="flex-1 mx-2 bg-white/5 rounded-full h-1">
                <div className="bg-violet-400 h-1 rounded-full" style={{ width: '46%' }} />
              </div>
              <span className="text-[10px] text-zinc-400 font-mono">312ms</span>
            </div>
          </div>
          <div className="mt-2 text-center text-emerald-400 text-xs font-mono font-bold">
            −35.9% latency
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Data ──────────────────────────────────────────────────────────────────────

const metrics = [
  { label: 'Cost Savings', value: '18.7%', delta: '+18.7% vs HPA', color: 'text-emerald-400' },
  { label: 'Scale Speed', value: '3.75×', delta: '+275% faster', color: 'text-violet-400' },
  { label: 'SLO Violations', value: '4', delta: '−83% vs HPA (23)', color: 'text-cyan-400' },
  { label: 'Time to Scale', value: '12s', delta: '−73% vs 45s HPA', color: 'text-blue-400' },
]

const techLogos = [
  { src: 'https://html.tailus.io/blocks/customers/nvidia.svg', alt: 'Kubernetes' },
  { src: 'https://html.tailus.io/blocks/customers/github.svg', alt: 'GitHub' },
  { src: 'https://html.tailus.io/blocks/customers/openai.svg', alt: 'AWS' },
  { src: 'https://html.tailus.io/blocks/customers/nvidia.svg', alt: 'Prometheus' },
  { src: 'https://html.tailus.io/blocks/customers/laravel.svg', alt: 'Grafana' },
  { src: 'https://html.tailus.io/blocks/customers/column.svg', alt: 'XGBoost' },
  { src: 'https://html.tailus.io/blocks/customers/lilly.svg', alt: 'Jenkins' },
  { src: 'https://html.tailus.io/blocks/customers/nike.svg', alt: 'Terraform' },
]

// ── Navigation ────────────────────────────────────────────────────────────────

const menuItems = [
  { name: 'Forecast', href: '/forecast' },
  { name: 'Benchmark', href: '/benchmark' },
  { name: 'Latency', href: '/latency' },
  { name: 'Architecture', href: '#architecture' },
]

const HeroHeader = () => {
  const [menuState, setMenuState] = React.useState(false)
  const [isScrolled, setIsScrolled] = React.useState(false)

  React.useEffect(() => {
    const handleScroll = () => setIsScrolled(window.scrollY > 50)
    window.addEventListener('scroll', handleScroll)
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])

  return (
    <header>
      <nav
        data-state={menuState ? 'active' : undefined}
        className="fixed z-20 w-full px-2 group">
        <div
          className={cn(
            'mx-auto mt-2 max-w-6xl px-6 transition-all duration-300 lg:px-12',
            isScrolled && 'bg-background/70 max-w-4xl rounded-2xl border backdrop-blur-lg lg:px-5',
          )}>
          <div className="relative flex flex-wrap items-center justify-between gap-6 py-3 lg:gap-0 lg:py-4">
            {/* Logo */}
            <div className="flex w-full justify-between lg:w-auto">
              <Link to="/" aria-label="home" className="flex items-center space-x-2">
                <ProjectLogo />
              </Link>
              {/* Mobile menu toggle */}
              <button
                onClick={() => setMenuState(!menuState)}
                aria-label={menuState ? 'Close Menu' : 'Open Menu'}
                className="relative z-20 -m-2.5 -mr-4 block cursor-pointer p-2.5 lg:hidden">
                <Menu className="group-data-[state=active]:scale-0 group-data-[state=active]:opacity-0 m-auto size-6 duration-200" />
                <X className="group-data-[state=active]:rotate-0 group-data-[state=active]:scale-100 group-data-[state=active]:opacity-100 absolute inset-0 m-auto size-6 -rotate-180 scale-0 opacity-0 duration-200" />
              </button>
            </div>

            {/* Desktop nav links (centred) */}
            <div className="absolute inset-0 m-auto hidden size-fit lg:block">
              <ul className="flex gap-8 text-sm">
                {menuItems.map((item) => (
                  <li key={item.name}>
                    <Link
                      to={item.href}
                      className="text-muted-foreground hover:text-foreground block duration-150">
                      {item.name}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>

            {/* Actions */}
            <div className="bg-background group-data-[state=active]:block lg:group-data-[state=active]:flex mb-6 hidden w-full flex-wrap items-center justify-end space-y-8 rounded-3xl border p-6 shadow-2xl shadow-zinc-300/20 md:flex-nowrap lg:m-0 lg:flex lg:w-fit lg:gap-6 lg:space-y-0 lg:border-transparent lg:bg-transparent lg:p-0 lg:shadow-none dark:shadow-none">
              {/* Mobile nav links */}
              <div className="lg:hidden">
                <ul className="space-y-6 text-base">
                  {menuItems.map((item) => (
                    <li key={item.name}>
                      <Link
                        to={item.href}
                        className="text-muted-foreground hover:text-foreground block duration-150"
                        onClick={() => setMenuState(false)}>
                        {item.name}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="flex w-full flex-col space-y-3 sm:flex-row sm:gap-3 sm:space-y-0 md:w-fit">
                <Button
                  asChild
                  variant="outline"
                  size="sm"
                  className={cn(isScrolled && 'lg:hidden')}>
                  <a href="https://github.com/Parths-29/Horizontal_pod_scaler" target="_blank" rel="noopener noreferrer">
                    GitHub
                  </a>
                </Button>
                <Button
                  asChild
                  size="sm"
                  className={cn(isScrolled && 'lg:hidden')}>
                  <Link to="/benchmark">
                    View Results
                  </Link>
                </Button>
                <Button
                  asChild
                  size="sm"
                  className={cn(isScrolled ? 'lg:inline-flex' : 'hidden')}>
                  <Link to="/benchmark">
                    Get Started
                  </Link>
                </Button>
              </div>
            </div>
          </div>
        </div>
      </nav>
    </header>
  )
}

// ── Logo ──────────────────────────────────────────────────────────────────────

const ProjectLogo = ({ className }: { className?: string }) => (
  <div className={cn('flex items-center gap-2', className)}>
    <div className="size-7 rounded-lg bg-white flex items-center justify-center">
      <svg viewBox="0 0 24 24" fill="none" className="size-4 text-black" stroke="currentColor" strokeWidth={2.5}>
        <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
      </svg>
    </div>
    <span className="font-bold text-sm tracking-tight">
      <span className="text-foreground">Predictive</span>
      <span className="text-muted-foreground font-medium">HPA</span>
    </span>
  </div>
)
