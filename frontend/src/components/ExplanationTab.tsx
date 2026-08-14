import React, { useState, useEffect } from 'react'
import {
  EntityItem,
  ExplanationData,
  ImpactData,
  fetchRepositoryEntities,
  fetchEntityExplanation,
  fetchEntityImpact,
  fetchEntitySource,
} from '../services/api'

interface ExplanationTabProps {
  repositoryId?: string
  loading?: boolean
  onSelectForRefactor?: (entityId: string) => void
}

export function ExplanationTab({
  repositoryId,
  loading: globalLoading,
  onSelectForRefactor,
}: ExplanationTabProps) {
  const [entities, setEntities] = useState<EntityItem[]>([])
  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState<'all' | 'function' | 'method' | 'class'>('all')
  const [explanation, setExplanation] = useState<ExplanationData | null>(null)
  const [impact, setImpact] = useState<ImpactData | null>(null)
  const [sourceData, setSourceData] = useState<{ file: string; lineStart: number; lineEnd: number; code: string } | null>(null)
  const [loadingExplanation, setLoadingExplanation] = useState(false)
  const [loadingEntities, setLoadingEntities] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeCitationIndex, setActiveCitationIndex] = useState<number | null>(null)

  useEffect(() => {
    if (!repositoryId) {
      setEntities([])
      setSelectedEntityId(null)
      setExplanation(null)
      setImpact(null)
      setSourceData(null)
      return
    }

    setLoadingEntities(true)
    fetchRepositoryEntities(repositoryId)
      .then((items) => {
        setEntities(items)
        if (items.length > 0 && !selectedEntityId) {
          setSelectedEntityId(items[0].id)
        }
      })
      .catch((err) => {
        setError(`Failed to load entities: ${err.message}`)
      })
      .finally(() => setLoadingEntities(false))
  }, [repositoryId])

  useEffect(() => {
    if (!repositoryId || !selectedEntityId) {
      setExplanation(null)
      setImpact(null)
      setSourceData(null)
      return
    }

    setLoadingExplanation(true)
    setError(null)
    setActiveCitationIndex(null)

    Promise.all([
      fetchEntityExplanation(repositoryId, selectedEntityId).catch(() => null),
      fetchEntityImpact(repositoryId, selectedEntityId).catch(() => null),
      fetchEntitySource(repositoryId, selectedEntityId).catch(() => null),
    ])
      .then(([expEnv, impEnv, srcData]) => {
        if (expEnv?.data) setExplanation(expEnv.data)
        if (impEnv?.data) setImpact(impEnv.data)
        if (srcData) setSourceData(srcData)
      })
      .catch((err) => setError(`Failed to load entity details: ${err.message}`))
      .finally(() => setLoadingExplanation(false))
  }, [repositoryId, selectedEntityId])

  const filteredEntities = entities.filter((e) => {
    const matchesSearch =
      e.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      e.file.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesType = typeFilter === 'all' || e.type === typeFilter
    return matchesSearch && matchesType
  })

  const currentEntity = entities.find((e) => e.id === selectedEntityId)

  if (!repositoryId) {
    return (
      <div style={styles.emptyContainer} data-testid="explanation-empty">
        <div style={styles.emptyCard}>
          <h3 style={styles.emptyTitle}>No Repository Selected</h3>
          <p style={styles.emptyText}>
            Select or upload a repository from the header to explore AI-grounded code explanations and blast radius impact analysis.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div style={styles.container} data-testid="explanation-workspace">
      {/* Sidebar / Entity List */}
      <aside style={styles.sidebar}>
        <div style={styles.sidebarHeader}>
          <h3 style={styles.sidebarTitle}>Discovered Entities</h3>
          <span style={styles.badge}>{entities.length} total</span>
        </div>

        <div style={styles.filterBox}>
          <input
            type="text"
            placeholder="Search functions & classes…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={styles.searchInput}
            aria-label="Search entities"
          />
          <div style={styles.typeToggleGroup} role="radiogroup" aria-label="Entity type filter">
            {(['all', 'function', 'class'] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTypeFilter(t)}
                style={{
                  ...styles.typeToggleButton,
                  backgroundColor: typeFilter === t ? '#0284c7' : 'transparent',
                  color: typeFilter === t ? '#ffffff' : '#94a3b8',
                }}
              >
                {t === 'all' ? 'All' : t.charAt(0).toUpperCase() + t.slice(1)}
              </button>
            ))}
          </div>
        </div>

        <div style={styles.entityList}>
          {loadingEntities ? (
            <div style={styles.loadingState}>Loading entities…</div>
          ) : filteredEntities.length === 0 ? (
            <div style={styles.noResultsState}>No matching entities found</div>
          ) : (
            filteredEntities.map((e) => {
              const isSelected = e.id === selectedEntityId
              const isHighComplexity = e.complexity >= 10
              return (
                <button
                  key={e.id}
                  onClick={() => setSelectedEntityId(e.id)}
                  style={{
                    ...styles.entityItem,
                    backgroundColor: isSelected ? '#1e293b' : 'transparent',
                    borderColor: isSelected ? '#38bdf8' : '#334155',
                  }}
                  data-testid={`entity-item-${e.name}`}
                >
                  <div style={styles.entityItemHeader}>
                    <span style={styles.entityItemName}>{e.name}</span>
                    <span
                      style={{
                        ...styles.complexityPill,
                        backgroundColor: isHighComplexity ? '#7f1d1d' : '#1e3a5f',
                        color: isHighComplexity ? '#fca5a5' : '#7dd3fc',
                      }}
                    >
                      CCN {e.complexity}
                    </span>
                  </div>
                  <div style={styles.entityItemMeta}>
                    <span style={styles.entityTypeBadge}>{e.type}</span>
                    <span style={styles.entityFilePath}>{e.file.split('/').pop()}</span>
                    <span style={styles.entityLineRange}>L{e.lineStart}–L{e.lineEnd}</span>
                  </div>
                </button>
              )
            })
          )}
        </div>
      </aside>

      {/* Main Content Area */}
      <main style={styles.mainContent}>
        {error && (
          <div style={styles.errorBanner} role="alert">
            <span>{error}</span>
            <button onClick={() => setError(null)} style={styles.closeBtn}>×</button>
          </div>
        )}

        {loadingExplanation || globalLoading ? (
          <div style={styles.loadingHero}>
            <div style={styles.spinner} />
            <h3>Analyzing AST Facts & Generating Evidence-Cited Explanation…</h3>
            <p style={styles.loadingSubtext}>
              Grounding purpose, business rules, control flow, and safety boundaries with static facts.
            </p>
          </div>
        ) : currentEntity ? (
          <div style={styles.detailsContainer}>
            {/* Entity Header Banner */}
            <div style={styles.entityBanner}>
              <div style={styles.entityBannerInfo}>
                <div style={styles.entityBannerTagRow}>
                  <span style={styles.typeTag}>{currentEntity.type.toUpperCase()}</span>
                  <span style={styles.langTag}>{currentEntity.language || 'Python'}</span>
                  {currentEntity.complexity >= 10 && (
                    <span style={styles.riskTag}>HIGH COMPLEXITY</span>
                  )}
                  {explanation?.provider && (
                    <span style={styles.providerTag}>Provider: {explanation.provider}</span>
                  )}
                </div>
                <h2 style={styles.entityNameTitle}>{currentEntity.name}</h2>
                <div style={styles.signatureBox}>
                  <code>{currentEntity.signature || `def ${currentEntity.name}(...)`}</code>
                </div>
                <div style={styles.fileLocationRow}>
                  <span><strong>File:</strong> {currentEntity.file}</span>
                  <span><strong>Lines:</strong> {currentEntity.lineStart} – {currentEntity.lineEnd} ({currentEntity.lineEnd - currentEntity.lineStart + 1} LOC)</span>
                  <span><strong>Cyclomatic Complexity:</strong> {currentEntity.complexity}</span>
                </div>
              </div>

              {onSelectForRefactor && (
                <div style={styles.bannerActions}>
                  <button
                    onClick={() => onSelectForRefactor(currentEntity.id)}
                    style={styles.refactorActionBtn}
                    data-testid="propose-refactor-btn"
                  >
                    ⚡ Propose Refactor
                  </button>
                </div>
              )}
            </div>

            {/* Structured 10-Field Explanation Grid */}
            {explanation?.explanation && (
              <section style={styles.sectionCard} aria-labelledby="explanation-title">
                <div style={styles.sectionHeader}>
                  <h3 id="explanation-title" style={styles.sectionTitle}>
                    10-Field Grounded Explanation
                  </h3>
                  <span style={styles.verifiedBadge}>✓ AST Grounded</span>
                </div>

                <div style={styles.fieldsGrid}>
                  <div style={{ ...styles.fieldBox, gridColumn: 'span 2' }}>
                    <span style={styles.fieldLabel}>Core Purpose</span>
                    <p style={styles.fieldValue}>{explanation.explanation.purpose}</p>
                  </div>

                  <div style={{ ...styles.fieldBox, gridColumn: 'span 2' }}>
                    <span style={styles.fieldLabel}>Business Rules &amp; Invariants</span>
                    <p style={styles.fieldValue}>{explanation.explanation.businessRules || 'Standard business execution logic.'}</p>
                  </div>

                  <div style={styles.fieldBox}>
                    <span style={styles.fieldLabel}>Inputs &amp; Arguments</span>
                    <p style={styles.fieldValue}>{explanation.explanation.inputs || 'None'}</p>
                  </div>

                  <div style={styles.fieldBox}>
                    <span style={styles.fieldLabel}>Outputs &amp; Return Type</span>
                    <p style={styles.fieldValue}>{explanation.explanation.outputs || 'None'}</p>
                  </div>

                  <div style={styles.fieldBox}>
                    <span style={styles.fieldLabel}>Control Flow</span>
                    <p style={styles.fieldValue}>{explanation.explanation.controlFlow || 'Linear execution path.'}</p>
                  </div>

                  <div style={styles.fieldBox}>
                    <span style={styles.fieldLabel}>Dependencies</span>
                    <p style={styles.fieldValue}>{explanation.explanation.dependencies || 'None'}</p>
                  </div>

                  <div style={styles.fieldBox}>
                    <span style={styles.fieldLabel}>Error Handling</span>
                    <p style={styles.fieldValue}>{explanation.explanation.errorHandling || 'Standard exception propagation.'}</p>
                  </div>

                  <div style={styles.fieldBox}>
                    <span style={styles.fieldLabel}>Side Effects</span>
                    <p style={styles.fieldValue}>{explanation.explanation.sideEffects || 'None detected (pure calculation).'}</p>
                  </div>

                  <div style={{ ...styles.fieldBox, gridColumn: 'span 2', borderColor: '#7f1d1d' }}>
                    <span style={{ ...styles.fieldLabel, color: '#f87171' }}>Risks &amp; Modernization Hazards</span>
                    <p style={{ ...styles.fieldValue, color: '#fca5a5' }}>{explanation.explanation.risks || 'No severe modernization hazards detected.'}</p>
                  </div>
                </div>
              </section>
            )}

            {/* Evidence Citations Table */}
            {explanation?.evidence && explanation.evidence.length > 0 && (
              <section style={styles.sectionCard} aria-labelledby="evidence-title">
                <div style={styles.sectionHeader}>
                  <h3 id="evidence-title" style={styles.sectionTitle}>
                    Static Evidence Citations ({explanation.evidence.length})
                  </h3>
                  <span style={styles.evidenceSubtitle}>
                    Click any citation to inspect code bounds
                  </span>
                </div>

                <div style={styles.citationList}>
                  {explanation.evidence.map((item, idx) => (
                    <div
                      key={idx}
                      onClick={() => setActiveCitationIndex(activeCitationIndex === idx ? null : idx)}
                      style={{
                        ...styles.citationCard,
                        borderColor: activeCitationIndex === idx ? '#38bdf8' : '#334155',
                      }}
                    >
                      <div style={styles.citationHeader}>
                        <span style={styles.citationClaim}><strong>Claim:</strong> {item.claim}</span>
                        <span style={styles.citationLocBadge}>
                          {item.file}: L{item.lineStart}–L{item.lineEnd}
                        </span>
                      </div>
                      {item.code && (
                        <pre style={styles.citationCodeSnippet}>
                          <code>{item.code}</code>
                        </pre>
                      )}
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Impact & Blast Radius Card */}
            {impact && (
              <section style={styles.sectionCard} aria-labelledby="impact-title">
                <div style={styles.sectionHeader}>
                  <h3 id="impact-title" style={styles.sectionTitle}>
                    Impact Analysis &amp; Blast Radius
                  </h3>
                  <span
                    style={{
                      ...styles.impactBadge,
                      backgroundColor:
                        impact.impact.toLowerCase() === 'high'
                          ? '#7f1d1d'
                          : impact.impact.toLowerCase() === 'medium'
                          ? '#78350f'
                          : '#14532d',
                      color:
                        impact.impact.toLowerCase() === 'high'
                          ? '#fca5a5'
                          : impact.impact.toLowerCase() === 'medium'
                          ? '#fde68a'
                          : '#86efac',
                    }}
                  >
                    {impact.impact.toUpperCase()} IMPACT
                  </span>
                </div>

                <p style={styles.impactReasonText}>{impact.impactReason}</p>

                <div style={styles.impactColumns}>
                  {/* Callers (Fan-in) */}
                  <div style={styles.impactColumn}>
                    <h4 style={styles.columnHeading}>
                      Callers (Fan-In: {impact.callers.length})
                    </h4>
                    {impact.callers.length === 0 ? (
                      <div style={styles.emptyListNotice}>No internal callers found (potential entry point)</div>
                    ) : (
                      <div style={styles.impactList}>
                        {impact.callers.map((c, i) => (
                          <div key={i} style={styles.impactListItem}>
                            <span style={styles.impactCallerName}>{c.caller}</span>
                            <span style={styles.impactLocation}>{c.file}:L{c.callLine}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Callees (Fan-out) */}
                  <div style={styles.impactColumn}>
                    <h4 style={styles.columnHeading}>
                      Callees (Fan-Out: {impact.callees.length})
                    </h4>
                    {impact.callees.length === 0 ? (
                      <div style={styles.emptyListNotice}>Leaf function (no downstream calls)</div>
                    ) : (
                      <div style={styles.impactList}>
                        {impact.callees.map((c, i) => (
                          <div key={i} style={styles.impactListItem}>
                            <span style={styles.impactCalleeName}>{c.callee}</span>
                            <span style={styles.impactLocation}>{c.file}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </section>
            )}

            {/* Source Code Viewer */}
            {sourceData && (
              <section style={styles.sectionCard} aria-labelledby="source-title">
                <div style={styles.sectionHeader}>
                  <h3 id="source-title" style={styles.sectionTitle}>
                    Source Code: {sourceData.file}
                  </h3>
                  <span style={styles.lineCountBadge}>
                    Lines {sourceData.lineStart} – {sourceData.lineEnd}
                  </span>
                </div>

                <div style={styles.sourceCodeContainer}>
                  <pre style={styles.sourceCodePre}>
                    <code>{sourceData.code || '# Source code not available'}</code>
                  </pre>
                </div>
              </section>
            )}
          </div>
        ) : (
          <div style={styles.noSelectionState}>Select an entity from the list to view explanation.</div>
        )}
      </main>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex',
    gap: '20px',
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
  sidebar: {
    width: '320px',
    flexShrink: 0,
    backgroundColor: '#1e293b',
    borderRadius: '12px',
    border: '1px solid #334155',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
    height: 'calc(100vh - 120px)',
    position: 'sticky',
    top: '20px',
  },
  sidebarHeader: {
    padding: '16px',
    borderBottom: '1px solid #334155',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  sidebarTitle: {
    margin: 0,
    fontSize: '15px',
    fontWeight: '700',
    color: '#f8fafc',
  },
  badge: {
    fontSize: '11px',
    backgroundColor: '#0f172a',
    color: '#38bdf8',
    padding: '2px 8px',
    borderRadius: '12px',
    fontWeight: '600',
  },
  filterBox: {
    padding: '12px 16px',
    borderBottom: '1px solid #334155',
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  searchInput: {
    backgroundColor: '#0f172a',
    border: '1px solid #334155',
    borderRadius: '6px',
    padding: '8px 12px',
    color: '#f8fafc',
    fontSize: '13px',
    outline: 'none',
  },
  typeToggleGroup: {
    display: 'flex',
    gap: '4px',
    backgroundColor: '#0f172a',
    padding: '2px',
    borderRadius: '6px',
  },
  typeToggleButton: {
    flex: 1,
    padding: '4px 8px',
    fontSize: '11px',
    fontWeight: '600',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    transition: 'all 0.15s ease',
  },
  entityList: {
    flex: 1,
    overflowY: 'auto',
    padding: '8px',
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  },
  loadingState: {
    padding: '24px',
    textAlign: 'center',
    color: '#94a3b8',
    fontSize: '13px',
  },
  noResultsState: {
    padding: '24px',
    textAlign: 'center',
    color: '#64748b',
    fontSize: '13px',
  },
  entityItem: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    padding: '10px 12px',
    borderRadius: '8px',
    border: '1px solid #334155',
    textAlign: 'left',
    cursor: 'pointer',
    transition: 'all 0.15s ease',
    color: '#f8fafc',
  },
  entityItemHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  entityItemName: {
    fontSize: '13px',
    fontWeight: '600',
    color: '#38bdf8',
    fontFamily: 'JetBrains Mono, monospace',
  },
  complexityPill: {
    fontSize: '10px',
    fontWeight: '700',
    padding: '1px 6px',
    borderRadius: '4px',
  },
  entityItemMeta: {
    display: 'flex',
    gap: '8px',
    fontSize: '11px',
    color: '#94a3b8',
    alignItems: 'center',
  },
  entityTypeBadge: {
    textTransform: 'uppercase',
    fontSize: '9px',
    fontWeight: '700',
    letterSpacing: '0.05em',
    color: '#cbd5e1',
  },
  entityFilePath: {
    color: '#64748b',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    maxWidth: '120px',
  },
  entityLineRange: {
    color: '#64748b',
    marginLeft: 'auto',
  },
  mainContent: {
    flex: 1,
    minWidth: 0,
    display: 'flex',
    flexDirection: 'column',
    gap: '20px',
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
  loadingHero: {
    backgroundColor: '#1e293b',
    borderRadius: '12px',
    border: '1px solid #334155',
    padding: '60px 20px',
    textAlign: 'center',
    color: '#f8fafc',
  },
  spinner: {
    width: '32px',
    height: '32px',
    border: '3px solid #334155',
    borderTopColor: '#38bdf8',
    borderRadius: '50%',
    margin: '0 auto 16px',
    animation: 'spin 1s linear infinite',
  },
  loadingSubtext: {
    color: '#94a3b8',
    fontSize: '13px',
    maxWidth: '480px',
    margin: '8px auto 0',
  },
  detailsContainer: {
    display: 'flex',
    flexDirection: 'column',
    gap: '20px',
  },
  entityBanner: {
    backgroundColor: '#1e293b',
    border: '1px solid #334155',
    borderRadius: '12px',
    padding: '24px',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: '20px',
  },
  entityBannerInfo: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
    flex: 1,
  },
  entityBannerTagRow: {
    display: 'flex',
    gap: '8px',
    alignItems: 'center',
  },
  typeTag: {
    backgroundColor: '#0284c7',
    color: '#ffffff',
    fontSize: '10px',
    fontWeight: '700',
    padding: '2px 8px',
    borderRadius: '4px',
    letterSpacing: '0.05em',
  },
  langTag: {
    backgroundColor: '#334155',
    color: '#cbd5e1',
    fontSize: '10px',
    fontWeight: '600',
    padding: '2px 8px',
    borderRadius: '4px',
  },
  riskTag: {
    backgroundColor: '#7f1d1d',
    color: '#fca5a5',
    fontSize: '10px',
    fontWeight: '700',
    padding: '2px 8px',
    borderRadius: '4px',
  },
  providerTag: {
    fontSize: '11px',
    color: '#64748b',
    marginLeft: 'auto',
  },
  entityNameTitle: {
    margin: 0,
    fontSize: '24px',
    fontWeight: '800',
    color: '#f8fafc',
    fontFamily: 'JetBrains Mono, monospace',
  },
  signatureBox: {
    backgroundColor: '#0f172a',
    border: '1px solid #334155',
    borderRadius: '6px',
    padding: '8px 12px',
    color: '#7dd3fc',
    fontSize: '13px',
    fontFamily: 'JetBrains Mono, monospace',
    overflowX: 'auto',
  },
  fileLocationRow: {
    display: 'flex',
    gap: '20px',
    fontSize: '12px',
    color: '#94a3b8',
    marginTop: '4px',
  },
  bannerActions: {
    display: 'flex',
    alignItems: 'center',
  },
  refactorActionBtn: {
    backgroundColor: '#6366f1',
    color: '#ffffff',
    border: 'none',
    borderRadius: '8px',
    padding: '10px 18px',
    fontSize: '13px',
    fontWeight: '700',
    cursor: 'pointer',
    boxShadow: '0 4px 14px rgba(99, 102, 241, 0.4)',
    transition: 'all 0.15s ease',
  },
  sectionCard: {
    backgroundColor: '#1e293b',
    border: '1px solid #334155',
    borderRadius: '12px',
    padding: '24px',
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  },
  sectionHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderBottom: '1px solid #334155',
    paddingBottom: '12px',
  },
  sectionTitle: {
    margin: 0,
    fontSize: '16px',
    fontWeight: '700',
    color: '#f8fafc',
  },
  verifiedBadge: {
    fontSize: '11px',
    color: '#34d399',
    backgroundColor: 'rgba(52, 211, 153, 0.1)',
    border: '1px solid #059669',
    borderRadius: '12px',
    padding: '2px 8px',
    fontWeight: '600',
  },
  fieldsGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '16px',
  },
  fieldBox: {
    backgroundColor: '#0f172a',
    border: '1px solid #334155',
    borderRadius: '8px',
    padding: '14px',
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  },
  fieldLabel: {
    fontSize: '11px',
    fontWeight: '700',
    color: '#38bdf8',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
  },
  fieldValue: {
    margin: 0,
    fontSize: '13px',
    color: '#e2e8f0',
    lineHeight: '1.6',
  },
  evidenceSubtitle: {
    fontSize: '12px',
    color: '#94a3b8',
  },
  citationList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '10px',
  },
  citationCard: {
    backgroundColor: '#0f172a',
    border: '1px solid #334155',
    borderRadius: '8px',
    padding: '12px',
    cursor: 'pointer',
    transition: 'border-color 0.15s ease',
  },
  citationHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: '12px',
  },
  citationClaim: {
    fontSize: '13px',
    color: '#f8fafc',
  },
  citationLocBadge: {
    fontSize: '11px',
    backgroundColor: '#1e293b',
    color: '#38bdf8',
    padding: '2px 8px',
    borderRadius: '4px',
    fontFamily: 'JetBrains Mono, monospace',
    flexShrink: 0,
  },
  citationCodeSnippet: {
    marginTop: '10px',
    backgroundColor: '#020617',
    border: '1px solid #1e293b',
    borderRadius: '6px',
    padding: '10px',
    fontSize: '12px',
    color: '#a5f3fc',
    fontFamily: 'JetBrains Mono, monospace',
    overflowX: 'auto',
  },
  impactBadge: {
    fontSize: '11px',
    fontWeight: '700',
    padding: '3px 10px',
    borderRadius: '6px',
    letterSpacing: '0.05em',
  },
  impactReasonText: {
    margin: 0,
    fontSize: '13px',
    color: '#cbd5e1',
    lineHeight: '1.6',
  },
  impactColumns: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '20px',
    marginTop: '8px',
  },
  impactColumn: {
    backgroundColor: '#0f172a',
    border: '1px solid #334155',
    borderRadius: '8px',
    padding: '16px',
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
  },
  columnHeading: {
    margin: 0,
    fontSize: '13px',
    fontWeight: '700',
    color: '#f8fafc',
  },
  emptyListNotice: {
    fontSize: '12px',
    color: '#64748b',
    fontStyle: 'italic',
  },
  impactList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  },
  impactListItem: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '6px 10px',
    backgroundColor: '#1e293b',
    borderRadius: '4px',
    fontSize: '12px',
  },
  impactCallerName: {
    color: '#38bdf8',
    fontFamily: 'JetBrains Mono, monospace',
    fontWeight: '600',
  },
  impactCalleeName: {
    color: '#a78bfa',
    fontFamily: 'JetBrains Mono, monospace',
    fontWeight: '600',
  },
  impactLocation: {
    color: '#94a3b8',
    fontSize: '11px',
  },
  lineCountBadge: {
    fontSize: '12px',
    color: '#94a3b8',
  },
  sourceCodeContainer: {
    backgroundColor: '#020617',
    border: '1px solid #1e293b',
    borderRadius: '8px',
    overflow: 'hidden',
  },
  sourceCodePre: {
    margin: 0,
    padding: '16px',
    fontSize: '13px',
    lineHeight: '1.6',
    color: '#e2e8f0',
    fontFamily: 'JetBrains Mono, Consolas, monospace',
    overflowX: 'auto',
  },
  noSelectionState: {
    backgroundColor: '#1e293b',
    borderRadius: '12px',
    border: '1px solid #334155',
    padding: '60px 20px',
    textAlign: 'center',
    color: '#94a3b8',
    fontSize: '14px',
  },
}
