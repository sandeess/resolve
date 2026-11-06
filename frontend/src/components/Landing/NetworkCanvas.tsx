import { useEffect, useRef } from "react"

type Kind = "doc" | "ticket" | "stale"

interface Node {
  kind: Kind
  label?: string
  // Resting position as a fraction of the canvas, drifting a little around it.
  x: number
  y: number
  phase: number
  speed: number
}

interface Pulse {
  from: number
  t: number
}

const CYAN = "56, 225, 255"
const MINT = "94, 234, 212"
const AMBER = "245, 158, 11"

/** Small deterministic PRNG so the layout is identical on every load. */
function mulberry32(seed: number) {
  let a = seed
  return () => {
    a |= 0
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const LABELS: Partial<Record<number, string>> = {
  0: "stylesheet v3",
  3: "T-12 · approved",
  6: "guidelines.pdf",
  9: "T-7 · approved",
  12: "stylesheet v2",
  15: "stylesheet v1",
}

function buildNodes(): Node[] {
  const rand = mulberry32(7)
  const nodes: Node[] = []
  for (let i = 0; i < 28; i++) {
    const kind: Kind = i % 7 === 5 ? "stale" : i % 3 === 0 ? "ticket" : "doc"
    const angle = (i / 28) * Math.PI * 2 + rand() * 0.5
    const radius = 0.22 + rand() * 0.26
    nodes.push({
      kind,
      label: kind === "stale" ? "retired" : LABELS[i],
      x: 0.5 + Math.cos(angle) * radius * 1.25,
      y: 0.5 + Math.sin(angle) * radius,
      phase: rand() * Math.PI * 2,
      speed: 0.25 + rand() * 0.35,
    })
  }
  return nodes
}

/**
 * The hero picture: documents and approved tickets send pulses into one "Ask"
 * node. Retired versions stay dim and never send anything. Pure canvas, paused
 * when off screen or when the user prefers reduced motion (one still frame).
 */
export function NetworkCanvas({ className }: { className?: string }) {
  const ref = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = ref.current
    const ctx = canvas?.getContext("2d")
    if (!canvas || !ctx) return
    const nodes = buildNodes()
    const reduced = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches
    const pulses: Pulse[] = []
    const rings: number[] = []
    let width = 0
    let height = 0
    let raf = 0
    let visible = true
    let last = 0
    let nextPulse = 0

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      width = canvas.clientWidth
      height = canvas.clientHeight
      canvas.width = Math.round(width * dpr)
      canvas.height = Math.round(height * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }

    const hub = () => ({ x: width * 0.5, y: height * 0.5 })
    const pos = (n: Node, time: number) => ({
      x: (n.x + Math.sin(time * n.speed + n.phase) * 0.012) * width,
      y: (n.y + Math.cos(time * n.speed * 0.8 + n.phase) * 0.012) * height,
    })

    const draw = (time: number) => {
      ctx.clearRect(0, 0, width, height)
      const h = hub()
      const live = nodes.map((n) => pos(n, time))

      // edges
      for (const [i, n] of nodes.entries()) {
        const p = live[i]
        ctx.beginPath()
        ctx.moveTo(p.x, p.y)
        ctx.lineTo(h.x, h.y)
        ctx.setLineDash(n.kind === "stale" ? [3, 6] : [])
        ctx.strokeStyle =
          n.kind === "stale" ? `rgba(${AMBER}, 0.12)` : `rgba(${CYAN}, 0.1)`
        ctx.lineWidth = 1
        ctx.stroke()
      }
      ctx.setLineDash([])

      // pulses travelling to the hub
      for (const pulse of pulses) {
        const p = live[pulse.from]
        const x = p.x + (h.x - p.x) * pulse.t
        const y = p.y + (h.y - p.y) * pulse.t
        const tail = Math.max(0, pulse.t - 0.14)
        const gradient = ctx.createLinearGradient(
          p.x + (h.x - p.x) * tail,
          p.y + (h.y - p.y) * tail,
          x,
          y,
        )
        gradient.addColorStop(0, `rgba(${CYAN}, 0)`)
        gradient.addColorStop(1, `rgba(${CYAN}, 0.9)`)
        ctx.beginPath()
        ctx.moveTo(p.x + (h.x - p.x) * tail, p.y + (h.y - p.y) * tail)
        ctx.lineTo(x, y)
        ctx.strokeStyle = gradient
        ctx.lineWidth = 2
        ctx.stroke()
      }

      // nodes
      ctx.font = "11px 'JetBrains Mono Variable', ui-monospace, monospace"
      for (const [i, n] of nodes.entries()) {
        const p = live[i]
        const colour =
          n.kind === "stale" ? AMBER : n.kind === "ticket" ? MINT : CYAN
        const alpha = n.kind === "stale" ? 0.45 : 0.9
        ctx.strokeStyle = `rgba(${colour}, ${alpha})`
        ctx.fillStyle = `rgba(${colour}, ${n.kind === "stale" ? 0.04 : 0.18})`
        ctx.lineWidth = 1.2
        if (n.kind === "ticket") {
          ctx.beginPath()
          ctx.arc(p.x, p.y, 5, 0, Math.PI * 2)
          ctx.fill()
          ctx.stroke()
        } else {
          if (n.kind === "stale") ctx.setLineDash([2, 3])
          ctx.fillRect(p.x - 5, p.y - 5, 10, 10)
          ctx.strokeRect(p.x - 5, p.y - 5, 10, 10)
          ctx.setLineDash([])
        }
        if (n.label) {
          ctx.fillStyle = `rgba(${colour}, ${n.kind === "stale" ? 0.5 : 0.75})`
          ctx.fillText(n.label, p.x + 10, p.y + 4)
        }
      }

      // hub
      for (const age of rings) {
        ctx.beginPath()
        ctx.arc(h.x, h.y, 18 + age * 46, 0, Math.PI * 2)
        ctx.strokeStyle = `rgba(${CYAN}, ${0.5 * (1 - age)})`
        ctx.lineWidth = 1.2
        ctx.stroke()
      }
      ctx.beginPath()
      ctx.arc(h.x, h.y, 18, 0, Math.PI * 2)
      ctx.fillStyle = "rgba(4, 7, 12, 0.9)"
      ctx.fill()
      ctx.strokeStyle = `rgba(${CYAN}, 1)`
      ctx.lineWidth = 1.6
      ctx.stroke()
      ctx.fillStyle = `rgba(${CYAN}, 1)`
      ctx.textAlign = "center"
      ctx.fillText("ASK", h.x, h.y + 4)
      ctx.textAlign = "start"
    }

    const frame = (ms: number) => {
      raf = requestAnimationFrame(frame)
      if (!visible) return
      const time = ms / 1000
      const dt = Math.min(time - last, 0.05)
      last = time
      if (time > nextPulse) {
        const sources = nodes
          .map((n, i) => (n.kind === "stale" ? -1 : i))
          .filter((i) => i >= 0)
        pulses.push({
          from: sources[Math.floor(Math.random() * sources.length)],
          t: 0,
        })
        nextPulse = time + 0.45 + Math.random() * 0.5
      }
      for (let i = pulses.length - 1; i >= 0; i--) {
        pulses[i].t += dt * 0.9
        if (pulses[i].t >= 1) {
          pulses.splice(i, 1)
          rings.push(0)
        }
      }
      for (let i = rings.length - 1; i >= 0; i--) {
        rings[i] += dt * 1.1
        if (rings[i] >= 1) rings.splice(i, 1)
      }
      draw(time)
    }

    resize()
    const observer = new ResizeObserver(() => {
      resize()
      if (reduced) draw(0)
    })
    observer.observe(canvas)
    const onVisibility = () => {
      visible = !document.hidden
    }
    document.addEventListener("visibilitychange", onVisibility)
    const io = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting && !document.hidden
    })
    io.observe(canvas)

    if (reduced) {
      draw(0)
    } else {
      raf = requestAnimationFrame(frame)
    }
    return () => {
      cancelAnimationFrame(raf)
      observer.disconnect()
      io.disconnect()
      document.removeEventListener("visibilitychange", onVisibility)
    }
  }, [])

  return <canvas ref={ref} className={className} />
}
