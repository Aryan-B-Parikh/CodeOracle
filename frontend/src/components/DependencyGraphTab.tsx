import React, { useState, useEffect, useMemo, useRef } from 'react'
import {
  GraphPayload,
  GraphNode,
  fetchRepositoryGraph,
} from '../services/api'

interface DependencyGraphTabProps {
  repositoryId?: string
  loading?: boolean
  onSelectForExplanation?: (entityId: string) => void
  onSelectForRefactor?: (entityId: string) => void
}

interface LayoutNode extends GraphNode {
  x: number
  y: number
  inDegree: number
  outDegree: number
  callers: string[]
  callees: string[]
  isHighRisk: boolean
  isCircular: boolean
}

export function DependencyGraphTab({
  repositoryId,
  loading: globalLoading,
  onSelectForExplanation,
  onSelectForRefactor,
}: DependencyGraphTabProps) {
  const [graphData, setGraphData] = useState<GraphPayload | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [edgeFilter, setEdgeFilter] = useState<'all' | 'call' | 'import' | 'contains'>('all')
  const [nodeFilter, setNodeFilter] = useState<'all' | 'high-risk' | 'circular'>('all')

  // Pan & Zoom state
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [isDragging, setIsDragging] = useState(false)
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 })
  const svgRef = useRef<SVGSVGElement>(null)

  useEffect(() => {
    if (!repositoryId) {
      setGraphData(null)
      setSelectedNodeId(null)
      return
    }

    setLoading(true)
    setError(null)
    fetchRepositoryGraph(repositoryId)
      .then((envelope) => {
        setGraphData(envelope.data)
        if (envelope.data.nodes.length > 0 && !selectedNodeId) {
          setSelectedNodeId(envelope.data.nodes[0].id)
        }
      })
      .catch((err) => {
        setError(`Failed to load dependency graph: ${err.message}`)
      })
      .finally(() => setLoading(false))
  }, [repositoryId])

  // Compute Layout, degrees, and cycles
  const { layoutNodes, layoutEdges, highRiskSet, circularNodeSet } = useMemo(() => {
    if (!graphData || graphData.nodes.length === 0) {
      return { layoutNodes: [], layoutEdges: [], highRiskSet: new Set<string>(), circularNodeSet: new Set<string>() }
    }

    const highRisk = new Set(graphData.meta?.highRiskNodeIds || [])
    const circular = new Set<string>()
    ;(graphData.meta?.circularDependencies || []).forEach((c) => {
      c.cycle?.forEach((id) => circular.add(id))
    })

    const nodeMap = new Map<string, LayoutNode>()
    graphData.nodes.forEach((n) => {
      nodeMap.set(n.id, {
        ...n,
        x: 0,
        y: 0,
        inDegree: 0,
        outDegree: 0,
        callers: [],
        callees: [],
        isHighRisk: highRisk.has(n.id) || (n.complexity >= 10),
        isCircular: circular.has(n.id),
      })
    })

    const filteredEdges = graphData.edges.filter((e) => {
      if (edgeFilter !== 'all' && e.kind !== edgeFilter) return false
      return nodeMap.has(e.source) && nodeMap.has(e.target)
    })

    filteredEdges.forEach((e) => {
      const src = nodeMap.get(e.source)
      const tgt = nodeMap.get(e.target)
      if (src && tgt) {
        src.outDegree += 1
        src.callees.push(tgt.label || tgt.id)
        tgt.inDegree += 1
        tgt.callers.push(src.label || src.id)
      }
    })

    // Grid / Layer layout
    const allNodes = Array.from(nodeMap.values())
    const cols = Math.max(3, Math.ceil(Math.sqrt(allNodes.length * 1.5)))
    const nodeWidth = 220
    const nodeHeight = 110
    const gapX = 80
    const gapY = 80

    allNodes.forEach((node, index) => {
      const col = index % cols
      const row = Math.floor(index / cols)
      node.x = 60 + col * (nodeWidth + gapX)
      node.y = 60 + row * (nodeHeight + gapY)
    })

    return {
      layoutNodes: allNodes,
      layoutEdges: filteredEdges,
      highRiskSet: highRisk,
      circularNodeSet: circular,
    }
  }, [graphData, edgeFilter])

  const visibleNodes = useMemo(() => {
    return layoutNodes.filter((node) => {
      if (nodeFilter === 'high-risk' && !node.isHighRisk) return false
      if (nodeFilter === 'circular' && !node.isCircular) return false
      if (searchQuery) {
        const query = searchQuery.toLowerCase()
        const labelMatch = (node.label || '').toLowerCase().includes(query)
        const fileMatch = (node.file || '').toLowerCase().includes(query)
        const qualMatch = (node.qualifiedName || '').toLowerCase().includes(query)
        if (!labelMatch && !fileMatch && !qualMatch) return false
      }
      return true
    })
  }, [layoutNodes, nodeFilter, searchQuery])

  const visibleNodeIds = useMemo(() => new Set(visibleNodes.map((n) => n.id)), [visibleNodes])

  const visibleEdges = useMemo(() => {
    return layoutEdges.filter((e) => visibleNodeIds.has(e.source) && visibleNodeIds.has(e.target))
  }, [layoutEdges, visibleNodeIds])

  const selectedNode = useMemo(() => {
    return layoutNodes.find((n) => n.id === selectedNodeId) || null
  }, [layoutNodes, selectedNodeId])

  // Mouse drag handlers for canvas
  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return
    setIsDragging(true)
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y })
  }

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return
    setPan({
      x: e.clientX - dragStart.x,
      y: e.clientY - dragStart.y,
    })
  }

  const handleMouseUp = () => setIsDragging(false)

  const resetView = () => {
    setZoom(1)
    setPan({ x: 0, y: 0 })
  }

  if (!repositoryId) {
    return (
      <div style={styles.emptyContainer} data-testid="graph-empty">
        <div style={styles.emptyCard}>
          <h3 style={styles.emptyTitle}>No Repository Selected</h3>
          <p style={styles.emptyText}>
            Select or upload a repository from the header to render the interactive dependency graph.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div style={styles.container} data-testid="graph-workspace">
      {/* Top Controls Toolbar */}
      <div style={styles.toolbar}>
        <div style={styles.toolbarLeft}>
          <input
            type="text"
            placeholder="Search nodes in graph…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={styles.searchInput}
            aria-label="Search graph nodes"
          />

          <div style={styles.filterGroup}>
            <span style={styles.filterLabel}>Edges:</span>
            {(['all', 'call', 'import', 'contains'] as const).map((kind) => (
              <button
                key={kind}
                onClick={() => setEdgeFilter(kind)}
                style={{
                  ...styles.filterBtn,
                  backgroundColor: edgeFilter === kind ? '#0284c7' : '#1e293b',
                  color: edgeFilter === kind ? '#ffffff' : '#94a3b8',
                }}
              >
                {kind === 'all' ? 'All Edges' : kind.toUpperCase()}
              </button>
            ))}
          </div>

          <div style={styles.filterGroup}>
            <span style={styles.filterLabel}>Nodes:</span>
            {(['all', 'high-risk', 'circular'] as const).map((mode) => (
              <button
                key={mode}
                onClick={() => setNodeFilter(mode)}
                style={{
                  ...styles.filterBtn,
                  backgroundColor: nodeFilter === mode ? '#6366f1' : '#1e293b',
                  color: nodeFilter === mode ? '#ffffff' : '#94a3b8',
                }}
              >
                {mode === 'all'
                  ? 'All Nodes'
                  : mode === 'high-risk'
                  ? `⚡ High Risk (${highRiskSet.size})`
                  : `🔄 Circular (${circularNodeSet.size})`}
              </button>
            ))}
          </div>
        </div>

        <div style={styles.toolbarRight}>
          <button onClick={() => setZoom((z) => Math.min(2.5, z + 0.15))} style={styles.zoomBtn} aria-label="Zoom in">+</button>
          <span style={styles.zoomText}>{Math.round(zoom * 100)}%</span>
          <button onClick={() => setZoom((z) => Math.max(0.3, z - 0.15))} style={styles.zoomBtn} aria-label="Zoom out">−</button>
          <button onClick={resetView} style={styles.resetBtn}>Reset</button>
        </div>
      </div>

      {/* Circular Dependencies Alert Banner */}
      {graphData?.meta?.circularDependencies && graphData.meta.circularDependencies.length > 0 && (
        <div style={styles.circularBanner} role="alert">
          <span style={styles.circularIcon}>⚠</span>
          <div style={styles.circularInfo}>
            <strong>Circular Dependencies Detected ({graphData.meta.circularDependencies.length} cycle(s)):</strong>
            <div style={styles.cycleList}>
              {graphData.meta.circularDependencies.map((c, i) => (
                <span key={i} style={styles.cycleItem}>
                  {c.cycle.join(' ➔ ')}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}

      {error && (
        <div style={styles.errorBanner} role="alert">
          <span>{error}</span>
          <button onClick={() => setError(null)} style={styles.closeBtn}>×</button>
        </div>
      )}

      {/* Main Canvas + Detail Drawer */}
      <div style={styles.graphLayout}>
        <div
          style={styles.canvasContainer}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
        >
          {loading || globalLoading ? (
            <div style={styles.loadingOverlay}>
              <div style={styles.spinner} />
              <p>Constructing Dependency Graph &amp; Computing Cycles…</p>
            </div>
          ) : visibleNodes.length === 0 ? (
            <div style={styles.noNodesOverlay}>
              <p>No nodes match current filters.</p>
            </div>
          ) : (
            <svg
              ref={svgRef}
              style={{
                width: '100%',
                height: '100%',
                cursor: isDragging ? 'grabbing' : 'grab',
              }}
            >
              <defs>
                <marker
                  id="arrow-call"
                  viewBox="0 0 10 10"
                  refX="8"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 1 L 10 5 L 0 9 z" fill="#38bdf8" />
                </marker>
                <marker
                  id="arrow-import"
                  viewBox="0 0 10 10"
                  refX="8"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 1 L 10 5 L 0 9 z" fill="#a78bfa" />
                </marker>
                <marker
                  id="arrow-contains"
                  viewBox="0 0 10 10"
                  refX="8"
                  refY="5"
                  markerWidth="6"
                  markerHeight="6"
                  orient="auto-start-reverse"
                >
                  <path d="M 0 1 L 10 5 L 0 9 z" fill="#64748b" />
                </marker>
              </defs>

              <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
                {/* Render Edges */}
                {visibleEdges.map((edge, idx) => {
                  const src = layoutNodes.find((n) => n.id === edge.source)
                  const tgt = layoutNodes.find((n) => n.id === edge.target)
                  if (!src || !tgt) return null

                  const srcX = src.x + 110
                  const srcY = src.y + 55
                  const tgtX = tgt.x + 110
                  const tgtY = tgt.y + 55

                  const isCall = edge.kind === 'call'
                  const isImport = edge.kind === 'import'
                  const strokeColor = isCall ? '#0284c7' : isImport ? '#818cf8' : '#475569'
                  const markerId = isCall ? 'arrow-call' : isImport ? 'arrow-import' : 'arrow-contains'

                  return (
                    <g key={idx}>
                      <line
                        x1={srcX}
                        y1={srcY}
                        x2={tgtX}
                        y2={tgtY}
                        stroke={strokeColor}
                        strokeWidth={isCall ? 2 : 1.5}
                        strokeDasharray={isImport ? '4 2' : 'none'}
                        opacity={0.65}
                        markerEnd={`url(#${markerId})`}
                      />
                    </g>
                  )
                })}

                {/* Render Nodes */}
                {visibleNodes.map((node) => {
                  const isSelected = node.id === selectedNodeId
                  const isHighComplexity = node.complexity >= 10
                  const nodeBg = isSelected
                    ? '#1e3a5f'
                    : node.isHighRisk
                    ? '#2d1515'
                    : '#1e293b'
                  const borderColor = isSelected
                    ? '#38bdf8'
                    : node.isHighRisk
                    ? '#ef4444'
                    : node.isCircular
                    ? '#f59e0b'
                    : '#334155'

                  return (
                    <g
                      key={node.id}
                      transform={`translate(${node.x}, ${node.y})`}
                      onClick={(e) => {
                        e.stopPropagation()
                        setSelectedNodeId(node.id)
                      }}
                      style={{ cursor: 'pointer' }}
                    >
                      {/* Node Box */}
                      <rect
                        width={220}
                        height={100}
                        rx={8}
                        fill={nodeBg}
                        stroke={borderColor}
                        strokeWidth={isSelected ? 2.5 : 1.5}
                        filter="drop-shadow(0 4px 6px rgba(0,0,0,0.3))"
                      />

                      {/* Header bar */}
                      <rect
                        width={220}
                        height={24}
                        rx={8}
                        fill={isSelected ? '#0284c7' : '#0f172a'}
                        opacity={0.8}
                      />

                      {/* Node Type & Complexity */}
                      <text
                        x={10}
                        y={16}
                        fill="#cbd5e1"
                        fontSize={10}
                        fontWeight="700"
                        fontFamily="sans-serif"
                      >
                        {node.type.toUpperCase()}
                      </text>

                      <text
                        x={210}
                        y={16}
                        textAnchor="end"
                        fill={isHighComplexity ? '#f87171' : '#38bdf8'}
                        fontSize={10}
                        fontWeight="700"
                        fontFamily="monospace"
                      >
                        CCN {node.complexity}
                      </text>

                      {/* Node Label */}
                      <text
                        x={10}
                        y={48}
                        fill="#f8fafc"
                        fontSize={13}
                        fontWeight="700"
                        fontFamily="monospace"
                      >
                        {node.label.length > 22 ? `${node.label.slice(0, 20)}…` : node.label}
                      </text>

                      {/* Node File location */}
                      <text
                        x={10}
                        y={70}
                        fill="#94a3b8"
                        fontSize={10}
                        fontFamily="sans-serif"
                      >
                        {node.file ? node.file.split('/').pop() : ''}
                        {node.lineStart ? `: L${node.lineStart}` : ''}
                      </text>

                      {/* Degree indicators */}
                      <text
                        x={10}
                        y={88}
                        fill="#64748b"
                        fontSize={9}
                        fontFamily="sans-serif"
                      >
                        In: {node.inDegree} · Out: {node.outDegree}
                      </text>

                      {node.isHighRisk && (
                        <text
                          x={210}
                          y={88}
                          textAnchor="end"
                          fill="#ef4444"
                          fontSize={9}
                          fontWeight="700"
                        >
                          ⚡ HIGH RISK
                        </text>
                      )}
                    </g>
                  )
                })}
              </g>
            </svg>
          )}
        </div>

        {/* Node Detail Drawer / Inspection Sidebar */}
        <aside style={styles.detailDrawer}>
          <div style={styles.drawerHeader}>
            <h3 style={styles.drawerTitle}>Entity Details</h3>
            {selectedNode && (
              <span style={styles.drawerBadge}>{selectedNode.type}</span>
            )}
          </div>

          {selectedNode ? (
            <div style={styles.drawerBody}>
              <div style={styles.drawerItemNameBox}>
                <span style={styles.drawerItemName}>{selectedNode.label}</span>
                <span
                  style={{
                    ...styles.drawerComplexityPill,
                    backgroundColor: selectedNode.complexity >= 10 ? '#7f1d1d' : '#1e3a5f',
                    color: selectedNode.complexity >= 10 ? '#fca5a5' : '#7dd3fc',
                  }}
                >
                  Complexity: CCN {selectedNode.complexity}
                </span>
              </div>

              <div style={styles.drawerMetaList}>
                <div style={styles.drawerMetaRow}>
                  <span style={styles.drawerMetaLabel}>File:</span>
                  <span style={styles.drawerMetaVal}>{selectedNode.file || 'N/A'}</span>
                </div>
                <div style={styles.drawerMetaRow}>
                  <span style={styles.drawerMetaLabel}>Lines:</span>
                  <span style={styles.drawerMetaVal}>
                    {selectedNode.lineStart && selectedNode.lineEnd
                      ? `L${selectedNode.lineStart} – L${selectedNode.lineEnd}`
                      : 'N/A'}
                  </span>
                </div>
                <div style={styles.drawerMetaRow}>
                  <span style={styles.drawerMetaLabel}>Qualified Name:</span>
                  <span style={styles.drawerMetaVal}>{selectedNode.qualifiedName || selectedNode.id}</span>
                </div>
                <div style={styles.drawerMetaRow}>
                  <span style={styles.drawerMetaLabel}>High Risk Flag:</span>
                  <span style={{ ...styles.drawerMetaVal, color: selectedNode.isHighRisk ? '#f87171' : '#34d399' }}>
                    {selectedNode.isHighRisk ? 'YES (High Complexity/Fan-in)' : 'NO (Normal)'}
                  </span>
                </div>
                <div style={styles.drawerMetaRow}>
                  <span style={styles.drawerMetaLabel}>Circular Dep:</span>
                  <span style={{ ...styles.drawerMetaVal, color: selectedNode.isCircular ? '#fbbf24' : '#34d399' }}>
                    {selectedNode.isCircular ? 'YES (Cycle Participant)' : 'NO'}
                  </span>
                </div>
              </div>

              {/* Action Buttons */}
              <div style={styles.drawerActionGroup}>
                {onSelectForExplanation && (
                  <button
                    onClick={() => {
                      const entityUuid = selectedNode.id.split('::')[0].includes('-')
                        ? selectedNode.id.split('::')[0]
                        : selectedNode.id
                      onSelectForExplanation(entityUuid)
                    }}
                    style={styles.explainActionBtn}
                  >
                    📖 Explain Entity
                  </button>
                )}

                {onSelectForRefactor && (
                  <button
                    onClick={() => {
                      const entityUuid = selectedNode.id.split('::')[0].includes('-')
                        ? selectedNode.id.split('::')[0]
                        : selectedNode.id
                      onSelectForRefactor(entityUuid)
                    }}
                    style={styles.refactorActionBtn}
                  >
                    ⚡ Propose Refactor
                  </button>
                )}
              </div>

              {/* Callers (Fan-in) */}
              {/* Callers (Fan-in) */}
              {(() => {
                const callers = selectedNode.callers || []
                const callees = selectedNode.callees || []
                return (
                  <>
                    <div style={styles.drawerSection}>
                      <h4 style={styles.drawerSectionTitle}>
                        Direct Callers ({callers.length})
                      </h4>
                      {callers.length === 0 ? (
                        <p style={styles.emptyListNotice}>No direct callers found in graph.</p>
                      ) : (
                        <div style={styles.drawerList}>
                          {callers.map((c, i) => (
                            <div key={i} style={styles.drawerListItem}>
                              <span style={styles.callerIcon}>➔</span>
                              <span>{c}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Callees (Fan-out) */}
                    <div style={styles.drawerSection}>
                      <h4 style={styles.drawerSectionTitle}>
                        Direct Dependencies ({callees.length})
                      </h4>
                      {callees.length === 0 ? (
                        <p style={styles.emptyListNotice}>No outgoing dependencies.</p>
                      ) : (
                        <div style={styles.drawerList}>
                          {callees.map((c, i) => (
                            <div key={i} style={styles.drawerListItem}>
                              <span style={styles.calleeIcon}>➔</span>
                              <span>{c}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </>
                )
              })()}
            </div>
          ) : (
            <div style={styles.noSelectionText}>Click a node in the graph to inspect details.</div>
          )}
        </aside>
      </div>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
    minHeight: '80vh',
  },
  emptyContainer: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    padding: '60px 20px',
  },
  emptyCard: {
    backgroundColor: '#1e293b',
    border: '1px solid #334155',
    borderRadius: '12px',
    padding: '40px',
    maxWidth: '540px',
    textAlign: 'center',
  },
  emptyTitle: {
    fontSize: '20px',
    fontWeight: '700',
    color: '#f8fafc',
    marginBottom: '12px',
  },
  emptyText: {
    color: '#94a3b8',
    lineHeight: '1.6',
    fontSize: '14px',
  },
  toolbar: {
    backgroundColor: '#1e293b',
    border: '1px solid #334155',
    borderRadius: '10px',
    padding: '12px 16px',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: '12px',
  },
  toolbarLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    flexWrap: 'wrap',
  },
  toolbarRight: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  searchInput: {
    backgroundColor: '#0f172a',
    border: '1px solid #334155',
    borderRadius: '6px',
    padding: '6px 12px',
    color: '#f8fafc',
    fontSize: '13px',
    outline: 'none',
    width: '200px',
  },
  filterGroup: {
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
  },
  filterLabel: {
    fontSize: '11px',
    fontWeight: '700',
    color: '#64748b',
    textTransform: 'uppercase',
    marginRight: '2px',
  },
  filterBtn: {
    border: '1px solid #334155',
    borderRadius: '4px',
    padding: '4px 8px',
    fontSize: '11px',
    fontWeight: '600',
    cursor: 'pointer',
    transition: 'all 0.15s ease',
  },
  zoomBtn: {
    backgroundColor: '#0f172a',
    border: '1px solid #334155',
    color: '#f8fafc',
    borderRadius: '4px',
    width: '28px',
    height: '28px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: 'pointer',
    fontSize: '16px',
    fontWeight: 'bold',
  },
  zoomText: {
    fontSize: '12px',
    color: '#94a3b8',
    minWidth: '40px',
    textAlign: 'center',
  },
  resetBtn: {
    backgroundColor: '#0f172a',
    border: '1px solid #334155',
    color: '#94a3b8',
    borderRadius: '4px',
    padding: '4px 10px',
    fontSize: '11px',
    fontWeight: '600',
    cursor: 'pointer',
  },
  circularBanner: {
    backgroundColor: '#451a03',
    border: '1px solid #b45309',
    borderRadius: '8px',
    padding: '12px 16px',
    display: 'flex',
    gap: '12px',
    alignItems: 'flex-start',
  },
  circularIcon: {
    fontSize: '20px',
    color: '#fbbf24',
  },
  circularInfo: {
    fontSize: '13px',
    color: '#fef3c7',
  },
  cycleList: {
    marginTop: '6px',
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  cycleItem: {
    fontFamily: 'monospace',
    fontSize: '12px',
    color: '#fde68a',
  },
  errorBanner: {
    backgroundColor: '#7f1d1d',
    border: '1px solid #b91c1c',
    borderRadius: '8px',
    padding: '12px 16px',
    color: '#fecaca',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    fontSize: '13px',
  },
  closeBtn: {
    background: 'none',
    border: 'none',
    color: '#fecaca',
    fontSize: '18px',
    cursor: 'pointer',
  },
  graphLayout: {
    display: 'flex',
    gap: '20px',
    height: 'calc(100vh - 180px)',
    minHeight: '600px',
  },
  canvasContainer: {
    flex: 1,
    backgroundColor: '#090d16',
    border: '1px solid #1e293b',
    borderRadius: '12px',
    position: 'relative',
    overflow: 'hidden',
  },
  loadingOverlay: {
    position: 'absolute',
    inset: 0,
    backgroundColor: 'rgba(9, 13, 22, 0.85)',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    color: '#f8fafc',
    fontSize: '14px',
    gap: '12px',
  },
  spinner: {
    width: '32px',
    height: '32px',
    border: '3px solid #334155',
    borderTopColor: '#38bdf8',
    borderRadius: '50%',
    animation: 'spin 1s linear infinite',
  },
  noNodesOverlay: {
    position: 'absolute',
    inset: 0,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: '#64748b',
    fontSize: '14px',
  },
  detailDrawer: {
    width: '320px',
    flexShrink: 0,
    backgroundColor: '#1e293b',
    border: '1px solid #334155',
    borderRadius: '12px',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  },
  drawerHeader: {
    padding: '16px',
    borderBottom: '1px solid #334155',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  drawerTitle: {
    margin: 0,
    fontSize: '15px',
    fontWeight: '700',
    color: '#f8fafc',
  },
  drawerBadge: {
    fontSize: '10px',
    fontWeight: '700',
    backgroundColor: '#0284c7',
    color: '#ffffff',
    padding: '2px 8px',
    borderRadius: '4px',
    textTransform: 'uppercase',
  },
  drawerBody: {
    padding: '16px',
    overflowY: 'auto',
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  },
  drawerItemNameBox: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  },
  drawerItemName: {
    fontSize: '16px',
    fontWeight: '700',
    color: '#38bdf8',
    fontFamily: 'monospace',
  },
  drawerComplexityPill: {
    fontSize: '11px',
    fontWeight: '700',
    padding: '2px 8px',
    borderRadius: '4px',
    alignSelf: 'flex-start',
  },
  drawerMetaList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
    backgroundColor: '#0f172a',
    padding: '12px',
    borderRadius: '8px',
    border: '1px solid #334155',
  },
  drawerMetaRow: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: '12px',
  },
  drawerMetaLabel: {
    color: '#64748b',
    fontWeight: '600',
  },
  drawerMetaVal: {
    color: '#e2e8f0',
    fontFamily: 'monospace',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    maxWidth: '180px',
  },
  drawerActionGroup: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  explainActionBtn: {
    backgroundColor: '#0284c7',
    color: '#ffffff',
    border: 'none',
    borderRadius: '6px',
    padding: '8px 12px',
    fontSize: '12px',
    fontWeight: '700',
    cursor: 'pointer',
  },
  refactorActionBtn: {
    backgroundColor: '#6366f1',
    color: '#ffffff',
    border: 'none',
    borderRadius: '6px',
    padding: '8px 12px',
    fontSize: '12px',
    fontWeight: '700',
    cursor: 'pointer',
  },
  drawerSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  drawerSectionTitle: {
    margin: 0,
    fontSize: '12px',
    fontWeight: '700',
    color: '#94a3b8',
    textTransform: 'uppercase',
  },
  emptyListNotice: {
    margin: 0,
    fontSize: '12px',
    color: '#64748b',
    fontStyle: 'italic',
  },
  drawerList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  drawerListItem: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    fontSize: '12px',
    color: '#cbd5e1',
    fontFamily: 'monospace',
    backgroundColor: '#0f172a',
    padding: '4px 8px',
    borderRadius: '4px',
  },
  callerIcon: { color: '#38bdf8' },
  calleeIcon: { color: '#818cf8' },
  noSelectionText: {
    padding: '40px 20px',
    textAlign: 'center',
    color: '#64748b',
    fontSize: '13px',
  },
}
