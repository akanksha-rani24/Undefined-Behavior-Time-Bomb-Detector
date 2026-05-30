import { useEffect, useRef } from 'react'
import type { CFGData } from '@/lib/types'

interface CFGViewerProps {
  cfg: CFGData
  mode: 'o0' | 'o2'
}

const NODE_W = 120
const NODE_H = 44
const H_GAP = 60
const V_GAP = 30

function layoutNodes(nodes: { id: string; label: string; kind: string }[], edges: { source: string; target: string }[]) {
  // Simple layered layout: BFS from entry
  const layers: Map<string, number> = new Map()
  const byId = new Map(nodes.map(n => [n.id, n]))
  const adjacency = new Map<string, string[]>()
  for (const e of edges) {
    if (!adjacency.has(e.source)) adjacency.set(e.source, [])
    adjacency.get(e.source)!.push(e.target)
  }

  // BFS to assign layers
  const queue: string[] = []
  const entry = nodes.find(n => n.kind === 'entry') ?? nodes[0]
  if (!entry) return []
  queue.push(entry.id)
  layers.set(entry.id, 0)
  while (queue.length > 0) {
    const cur = queue.shift()!
    const curLayer = layers.get(cur) ?? 0
    for (const next of (adjacency.get(cur) ?? [])) {
      if (!layers.has(next)) {
        layers.set(next, curLayer + 1)
        queue.push(next)
      }
    }
  }
  // Assign x within layer
  const layerCounts = new Map<number, number>()
  const positions: { id: string; x: number; y: number; label: string; kind: string }[] = []
  for (const n of nodes) {
    const layer = layers.get(n.id) ?? 0
    const count = layerCounts.get(layer) ?? 0
    positions.push({ id: n.id, x: count * (NODE_W + H_GAP), y: layer * (NODE_H + V_GAP), label: n.label, kind: n.kind })
    layerCounts.set(layer, count + 1)
  }
  return positions
}

const KIND_COLORS: Record<string, { fill: string; stroke: string; text: string }> = {
  entry:     { fill: '#1e3a5f', stroke: '#3b82f6', text: '#93c5fd' },
  exit:      { fill: '#1c3329', stroke: '#22c55e', text: '#86efac' },
  block:     { fill: '#1e1e2e', stroke: '#4b5563', text: '#d1d5db' },
  eliminated:{ fill: '#2d1515', stroke: '#ef4444', text: '#fca5a5' },
}

export default function CFGViewer({ cfg, mode }: CFGViewerProps) {
  const nodes = mode === 'o0' ? cfg.o0_nodes : cfg.o2_nodes
  const edges = mode === 'o0' ? cfg.o0_edges : cfg.o2_edges
  const eliminated = new Set(cfg.eliminated_nodes)

  const enrichedNodes = nodes.map(n => ({
    ...n,
    kind: mode === 'o2' && eliminated.has(n.id) ? 'eliminated' : n.kind,
  }))

  const positions = layoutNodes(enrichedNodes, edges)
  const posMap = new Map(positions.map(p => [p.id, p]))

  const maxX = Math.max(...positions.map(p => p.x), 0) + NODE_W
  const maxY = Math.max(...positions.map(p => p.y), 0) + NODE_H
  const W = maxX + 40
  const H = maxY + 40

  return (
    <div className="w-full h-full overflow-auto bg-[#0b0b14] rounded-lg border border-border p-4">
      {positions.length === 0 ? (
        <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
          No CFG data available
        </div>
      ) : (
        <svg width={W} height={H} className="overflow-visible">
          <defs>
            <marker id="arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
              <path d="M0,0 L0,6 L6,3 z" fill="#6b7280" />
            </marker>
          </defs>

          {/* Edges */}
          {edges.map((e, i) => {
            const src = posMap.get(e.source)
            const tgt = posMap.get(e.target)
            if (!src || !tgt) return null
            const x1 = src.x + NODE_W / 2, y1 = src.y + NODE_H
            const x2 = tgt.x + NODE_W / 2, y2 = tgt.y
            const cy = (y1 + y2) / 2
            return (
              <path
                key={i}
                d={`M${x1},${y1} C${x1},${cy} ${x2},${cy} ${x2},${y2}`}
                fill="none"
                stroke="#4b5563"
                strokeWidth="1.5"
                markerEnd="url(#arrow)"
                opacity={0.7}
              />
            )
          })}

          {/* Nodes */}
          {positions.map(p => {
            const colors = KIND_COLORS[p.kind] ?? KIND_COLORS.block
            const isElim = eliminated.has(p.id) && mode === 'o2'
            return (
              <g key={p.id} transform={`translate(${p.x + 20}, ${p.y + 20})`}>
                <rect
                  width={NODE_W}
                  height={NODE_H}
                  rx={6}
                  fill={colors.fill}
                  stroke={colors.stroke}
                  strokeWidth={isElim ? 2 : 1.5}
                  strokeDasharray={isElim ? '4 2' : undefined}
                  opacity={isElim ? 0.6 : 1}
                />
                {p.label.split('\n').map((line, i) => (
                  <text
                    key={i}
                    x={NODE_W / 2}
                    y={16 + i * 14}
                    textAnchor="middle"
                    fontSize={10}
                    fontFamily="JetBrains Mono, monospace"
                    fill={colors.text}
                    opacity={isElim ? 0.5 : 1}
                  >
                    {line.length > 18 ? line.slice(0, 17) + '…' : line}
                  </text>
                ))}
                {isElim && (
                  <text x={NODE_W / 2} y={NODE_H - 4} textAnchor="middle" fontSize={8} fill="#f87171">
                    eliminated
                  </text>
                )}
              </g>
            )
          })}
        </svg>
      )}
    </div>
  )
}
