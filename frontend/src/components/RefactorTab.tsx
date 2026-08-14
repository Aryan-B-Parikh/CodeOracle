import React, { useState, useEffect } from 'react'
import { RefactorProposal } from '../types/refactor'
import { SafetyScoreData } from '../types/safety'
import { EntityItem, fetchRepositoryEntities } from '../services/api'
import { DiffViewer } from './DiffViewer'
import { SafetyScoreCard } from './SafetyScoreCard'

export interface RefactorTabProps {
  repositoryId?: string
  proposal: RefactorProposal | null
  safetyData?: SafetyScoreData | null
  loading?: boolean
  initialEntityId?: string
  onPropose?: (entityId: string) => void
}

export const RefactorTab: React.FC<RefactorTabProps> = ({
  repositoryId,
  proposal,
  safetyData = null,
  loading = false,
  initialEntityId,
  onPropose,
}) => {
  const [entityIdInput, setEntityIdInput] = useState(initialEntityId || '')
  const [entities, setEntities] = useState<EntityItem[]>([])

  useEffect(() => {
    if (initialEntityId) {
      setEntityIdInput(initialEntityId)
    }
  }, [initialEntityId])

  useEffect(() => {
    if (!repositoryId) {
      setEntities([])
      return
    }

    fetchRepositoryEntities(repositoryId)
      .then((items) => {
        setEntities(items)
        if (items.length > 0 && !entityIdInput) {
          // Pre-select highest complexity entity
          const sorted = [...items].sort((a, b) => b.complexity - a.complexity)
          setEntityIdInput(sorted[0].id)
        }
      })
      .catch(() => {})
  }, [repositoryId, entityIdInput])

  const handlePropose = () => {
    const id = entityIdInput.trim()
    if (id && onPropose) {
      onPropose(id)
    }
  }

  // Empty state — no repository selected
  if (!repositoryId) {
    return (
      <div style={styles.container}>
        <div style={styles.emptyState}>
          <div style={styles.emptyIcon}>⟳</div>
          <h3 style={styles.emptyTitle}>No Repository Selected</h3>
          <p style={styles.emptySubtitle}>
            Upload or select a repository to generate refactor proposals.
          </p>
        </div>
      </div>
    )
  }

  const selectedEntity = entities.find((e) => e.id === entityIdInput)

  return (
    <div style={styles.container} data-testid="refactor-tab">
      {/* Proposal Controls */}
      <div style={styles.controlCard}>
        <div style={styles.cardHeaderRow}>
          <div>
            <h3 style={styles.cardTitle}>Refactor &amp; Modernization Workspace</h3>
            <p style={styles.cardSubtitle}>
              Select an entity to generate a safe modernization proposal with side-by-side diffs, AST-grounded rationale, breaking change alerts, and behavioral equivalence verification.
            </p>
          </div>
          <span style={styles.safetyBadge}>Zero-Modification Guarantee</span>
        </div>

        {/* Entity Selection Controls */}
        <div style={styles.selectorRow}>
          <div style={styles.dropdownCol}>
            <label style={styles.inputLabel} htmlFor="entity-select">
              Select Discovered Entity ({entities.length} available):
            </label>
            <select
              id="entity-select"
              value={entityIdInput}
              onChange={(e) => setEntityIdInput(e.target.value)}
              style={styles.entitySelect}
              aria-label="Select entity for refactor"
            >
              <option value="">Choose an entity…</option>
              {entities.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.name} ({e.file.split('/').pop()}: L{e.lineStart}–L{e.lineEnd}) · CCN {e.complexity}
                  {e.complexity >= 10 ? ' [HIGH RISK]' : ''}
                </option>
              ))}
            </select>
          </div>

          <div style={styles.manualInputCol}>
            <label style={styles.inputLabel} htmlFor="entity-id-input">
              Or specify Entity UUID:
            </label>
            <div style={styles.inputRow}>
              <input
                id="entity-id-input"
                style={styles.entityInput}
                type="text"
                placeholder="Entity UUID (e.g. 3f8a1b2c-...)"
                value={entityIdInput}
                onChange={(e) => setEntityIdInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handlePropose()}
                data-testid="entity-id-input"
              />
              <button
                onClick={handlePropose}
                disabled={loading || !entityIdInput.trim()}
                style={{
                  ...styles.proposeButton,
                  opacity: loading || !entityIdInput.trim() ? 0.5 : 1,
                }}
                data-testid="propose-btn"
              >
                {loading ? 'Generating Proposal…' : '⚡ Propose Refactor'}
              </button>
            </div>
          </div>
        </div>

        {selectedEntity && (
          <div style={styles.entityPreviewBadgeRow}>
            <span style={styles.previewTag}>Entity: {selectedEntity.name}</span>
            <span style={styles.previewTag}>File: {selectedEntity.file}</span>
            <span style={styles.previewTag}>Complexity: CCN {selectedEntity.complexity}</span>
            <span style={styles.previewTag}>Type: {selectedEntity.type}</span>
          </div>
        )}
      </div>

      {/* No proposal yet */}
      {!proposal && !loading && (
        <div style={styles.emptyProposal}>
          <p>Select a function or class above and click "Propose Refactor" to generate an AST-grounded diff.</p>
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div style={styles.loadingHero}>
          <div style={styles.spinner} />
          <h3>Generating Modernization Proposal via AI Gateway…</h3>
          <p style={styles.loadingSubtext}>
            Preserving public signatures, computing behavioral equivalence, verifying syntax, and calculating 4-pillar safety score.
          </p>
        </div>
      )}

      {/* Proposal Result */}
      {proposal && !loading && (
        <div style={styles.proposalResultsContainer}>
          {/* Metadata header */}
          <div style={styles.proposalHeader}>
            <div>
              <span style={styles.entityName}>{proposal.entityName}</span>
              <span style={styles.filePath}>{proposal.filePath}</span>
            </div>
            <div style={styles.checksumRow}>
              <span style={styles.checksumLabel}>Original Checksum (Guaranteed Unchanged):</span>
              <code style={styles.checksum}>{proposal.originalChecksum.slice(0, 16)}…</code>
            </div>
          </div>

          {/* Behavioral Verification Banner */}
          {safetyData && (
            <div
              style={{
                ...styles.behaviorBanner,
                backgroundColor:
                  safetyData.behaviorStatus === 'BEHAVIOR_PRESERVED'
                    ? 'rgba(16, 185, 129, 0.1)'
                    : safetyData.behaviorStatus === 'BEHAVIOR_MUTATED'
                    ? 'rgba(239, 68, 68, 0.1)'
                    : 'rgba(245, 158, 11, 0.1)',
                borderColor:
                  safetyData.behaviorStatus === 'BEHAVIOR_PRESERVED'
                    ? '#059669'
                    : safetyData.behaviorStatus === 'BEHAVIOR_MUTATED'
                    ? '#dc2626'
                    : '#d97706',
              }}
              data-testid="behavior-status-banner"
            >
              <div style={styles.behaviorIcon}>
                {safetyData.behaviorStatus === 'BEHAVIOR_PRESERVED'
                  ? '✓'
                  : safetyData.behaviorStatus === 'BEHAVIOR_MUTATED'
                  ? '✕'
                  : '⚠'}
              </div>
              <div style={styles.behaviorTextContent}>
                <div style={styles.behaviorTitleRow}>
                  <strong style={styles.behaviorTitle}>
                    {safetyData.behaviorStatus === 'BEHAVIOR_PRESERVED'
                      ? 'BEHAVIOR PRESERVED (Verified via Sandbox)'
                      : safetyData.behaviorStatus === 'BEHAVIOR_MUTATED'
                      ? 'BEHAVIOR MUTATED (Test Failure Detected)'
                      : 'BEHAVIOR UNVERIFIED (No Proposal Sandbox Run Exists)'}
                  </strong>
                  <span style={styles.confidenceBadge}>
                    Confidence: {(safetyData.confidenceLevel || 'medium').toUpperCase()}
                  </span>
                </div>
                <p style={styles.behaviorDescription}>
                  {safetyData.behaviorStatus === 'BEHAVIOR_PRESERVED'
                    ? 'All unit test assertions passed inside the Docker container against the proposed refactor code.'
                    : safetyData.behaviorStatus === 'BEHAVIOR_MUTATED'
                    ? 'One or more unit tests failed when executing against the proposed refactor code. Review breaking changes.'
                    : 'Absence of evidence policy: No proposal-bound test run was recorded yet. Confidence is marked LOW (35%) until test verification runs.'}
                </p>
              </div>
            </div>
          )}

          {/* Safety Score Card (T-19 & T-18) */}
          <SafetyScoreCard safetyData={safetyData} loading={loading} />

          {/* Breaking Changes Section */}
          {proposal.breakingChanges && proposal.breakingChanges.detected && (
            <div style={styles.breakingChangesSection}>
              <h4 style={styles.breakingChangesTitle}>
                <span style={styles.breakingChangesIcon}>⚠</span>
                Potential Breaking Changes Detected ({proposal.breakingChanges.changes.length})
              </h4>
              <p style={styles.breakingChangesSubtitle}>
                Review callers and dependencies that may be affected by signature changes:
              </p>
              <div style={styles.changesList}>
                {proposal.breakingChanges.changes.map((ch, idx) => (
                  <div key={idx} style={styles.changeItem}>
                    <div style={styles.changeHeader}>
                      <span
                        style={{
                          ...styles.impactBadge,
                          ...(ch.impact === 'HIGH'
                            ? styles.impactHigh
                            : ch.impact === 'MEDIUM'
                            ? styles.impactMedium
                            : styles.impactLow),
                        }}
                      >
                        {ch.impact} IMPACT
                      </span>
                      <span style={styles.changeEntity}>{ch.entity}</span>
                    </div>
                    <p style={styles.changeReason}>{ch.reason}</p>
                    {ch.affectedCallers.length > 0 && (
                      <div style={styles.callersBox}>
                        <span style={styles.callersLabel}>Affected Callers:</span>
                        <div style={styles.callersList}>
                          {ch.affectedCallers.map((c, i) => (
                            <span key={i} style={styles.callerLink}>{c}</span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Diff view */}
          <div style={styles.section}>
            <h4 style={styles.sectionTitle}>Side-by-Side Code Diff</h4>
            <DiffViewer
              original={proposal.original}
              proposed={proposal.proposed}
              entityName={proposal.entityName}
            />
          </div>

          {/* WHY list */}
          <div style={styles.twoCol}>
            <div style={styles.panel}>
              <h4 style={styles.sectionTitle}>Why This Refactor (Rationale)</h4>
              {proposal.rationale.length === 0 ? (
                <p style={styles.emptyText}>No rationale provided.</p>
              ) : (
                <ul style={styles.whyList}>
                  {proposal.rationale.map((r, i) => (
                    <li key={i} style={styles.whyItem} data-testid={`rationale-${i}`}>
                      <span style={styles.whyBullet}>→</span>
                      {r}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div style={styles.panel}>
              <h4 style={styles.sectionTitle}>Behavioral Differences</h4>
              {proposal.behavioralDifferences.length === 0 ? (
                <div style={styles.noChangesBox}>
                  ✓ No behavioral differences — refactor preserves observable semantics.
                </div>
              ) : (
                <ul style={styles.whyList}>
                  {proposal.behavioralDifferences.map((d, i) => (
                    <li key={i} style={styles.whyItem}>
                      <span style={{ ...styles.whyBullet, color: '#f59e0b' }}>⚠</span>
                      {d}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    padding: '0 0 40px 0',
    backgroundColor: 'transparent',
    color: '#f8fafc',
    fontFamily: 'Inter, system-ui, sans-serif',
  },
  emptyState: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '50vh',
    textAlign: 'center',
    gap: '12px',
  },
  emptyIcon: {
    fontSize: '48px',
    color: '#334155',
  },
  emptyTitle: {
    fontSize: '22px',
    fontWeight: '700',
    color: '#94a3b8',
    margin: 0,
  },
  emptySubtitle: {
    fontSize: '15px',
    color: '#64748b',
    maxWidth: '400px',
    margin: 0,
  },
  controlCard: {
    backgroundColor: '#1e293b',
    border: '1px solid #334155',
    borderRadius: '12px',
    padding: '24px',
    marginBottom: '24px',
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  },
  cardHeaderRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: '16px',
  },
  cardTitle: {
    margin: '0 0 6px 0',
    fontSize: '18px',
    fontWeight: '700',
  },
  cardSubtitle: {
    margin: 0,
    fontSize: '13px',
    color: '#94a3b8',
    lineHeight: '1.5',
    maxWidth: '680px',
  },
  safetyBadge: {
    backgroundColor: 'rgba(52, 211, 153, 0.1)',
    color: '#34d399',
    border: '1px solid #059669',
    borderRadius: '12px',
    padding: '4px 10px',
    fontSize: '11px',
    fontWeight: '700',
    whiteSpace: 'nowrap',
  },
  selectorRow: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '16px',
  },
  dropdownCol: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  },
  manualInputCol: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  },
  inputLabel: {
    fontSize: '12px',
    fontWeight: '600',
    color: '#94a3b8',
  },
  entitySelect: {
    backgroundColor: '#0f172a',
    border: '1px solid #334155',
    borderRadius: '8px',
    padding: '10px 12px',
    color: '#f8fafc',
    fontSize: '13px',
    outline: 'none',
    width: '100%',
  },
  inputRow: {
    display: 'flex',
    gap: '10px',
  },
  entityInput: {
    flex: 1,
    backgroundColor: '#0f172a',
    border: '1px solid #334155',
    borderRadius: '8px',
    padding: '10px 14px',
    color: '#f8fafc',
    fontSize: '13px',
    outline: 'none',
  },
  proposeButton: {
    backgroundColor: '#6366f1',
    color: '#ffffff',
    border: 'none',
    borderRadius: '8px',
    padding: '10px 18px',
    fontSize: '13px',
    fontWeight: '700',
    cursor: 'pointer',
    whiteSpace: 'nowrap',
    boxShadow: '0 4px 14px rgba(99, 102, 241, 0.35)',
    transition: 'all 0.15s ease',
  },
  entityPreviewBadgeRow: {
    display: 'flex',
    gap: '10px',
    flexWrap: 'wrap',
    marginTop: '4px',
  },
  previewTag: {
    backgroundColor: '#0f172a',
    border: '1px solid #334155',
    color: '#7dd3fc',
    fontSize: '11px',
    padding: '2px 8px',
    borderRadius: '4px',
    fontFamily: 'monospace',
  },
  emptyProposal: {
    backgroundColor: '#1e293b',
    border: '1px solid #334155',
    borderRadius: '12px',
    padding: '40px',
    textAlign: 'center',
    color: '#64748b',
    fontSize: '14px',
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
    borderTopColor: '#6366f1',
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
  proposalResultsContainer: {
    display: 'flex',
    flexDirection: 'column',
    gap: '20px',
  },
  proposalHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: '#1e293b',
    border: '1px solid #334155',
    borderRadius: '12px',
    padding: '16px 20px',
  },
  entityName: {
    display: 'block',
    fontSize: '18px',
    fontWeight: '700',
    color: '#38bdf8',
    fontFamily: 'monospace',
  },
  filePath: {
    display: 'block',
    fontSize: '12px',
    color: '#94a3b8',
    marginTop: '2px',
  },
  checksumRow: {
    textAlign: 'right',
  },
  checksumLabel: {
    display: 'block',
    fontSize: '11px',
    color: '#64748b',
    marginBottom: '2px',
  },
  checksum: {
    fontSize: '11px',
    color: '#22c55e',
    backgroundColor: '#052e16',
    padding: '2px 6px',
    borderRadius: '4px',
    fontFamily: 'monospace',
  },
  behaviorBanner: {
    border: '1px solid',
    borderRadius: '10px',
    padding: '16px 20px',
    display: 'flex',
    gap: '16px',
    alignItems: 'flex-start',
  },
  behaviorIcon: {
    fontSize: '24px',
    lineHeight: '1',
  },
  behaviorTextContent: {
    flex: 1,
  },
  behaviorTitleRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '4px',
  },
  behaviorTitle: {
    fontSize: '14px',
    color: '#f8fafc',
  },
  confidenceBadge: {
    fontSize: '11px',
    fontWeight: '700',
    backgroundColor: '#0f172a',
    padding: '2px 8px',
    borderRadius: '4px',
    color: '#94a3b8',
  },
  behaviorDescription: {
    margin: 0,
    fontSize: '13px',
    color: '#cbd5e1',
    lineHeight: '1.5',
  },
  section: {
    backgroundColor: '#1e293b',
    border: '1px solid #334155',
    borderRadius: '12px',
    padding: '20px',
  },
  sectionTitle: {
    fontSize: '14px',
    fontWeight: '700',
    color: '#94a3b8',
    margin: '0 0 14px 0',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
  },
  twoCol: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '20px',
  },
  panel: {
    backgroundColor: '#1e293b',
    border: '1px solid #334155',
    borderRadius: '12px',
    padding: '20px',
  },
  whyList: {
    margin: 0,
    padding: 0,
    listStyle: 'none',
    display: 'flex',
    flexDirection: 'column',
    gap: '10px',
  },
  whyItem: {
    display: 'flex',
    gap: '10px',
    fontSize: '13px',
    color: '#e2e8f0',
    lineHeight: '1.5',
  },
  whyBullet: {
    color: '#818cf8',
    fontWeight: '700',
    flexShrink: 0,
    marginTop: '1px',
  },
  noChangesBox: {
    backgroundColor: 'rgba(16, 185, 129, 0.1)',
    border: '1px solid #059669',
    color: '#86efac',
    borderRadius: '8px',
    padding: '12px',
    fontSize: '13px',
  },
  emptyText: {
    color: '#64748b',
    fontSize: '13px',
  },
  breakingChangesSection: {
    backgroundColor: 'rgba(127, 29, 29, 0.25)',
    border: '1px solid #7f1d1d',
    borderRadius: '12px',
    padding: '20px',
  },
  breakingChangesTitle: {
    margin: '0 0 6px 0',
    fontSize: '15px',
    fontWeight: '700',
    color: '#fca5a5',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  breakingChangesIcon: {
    fontSize: '18px',
    color: '#ef4444',
  },
  breakingChangesSubtitle: {
    margin: '0 0 14px 0',
    fontSize: '12px',
    color: '#f87171',
  },
  changesList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '10px',
  },
  changeItem: {
    backgroundColor: '#1c0a0a',
    border: '1px solid #991b1b',
    borderRadius: '8px',
    padding: '12px',
  },
  changeHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    marginBottom: '6px',
  },
  impactBadge: {
    fontSize: '10px',
    fontWeight: '800',
    padding: '2px 6px',
    borderRadius: '4px',
    letterSpacing: '0.05em',
  },
  impactHigh: { backgroundColor: '#7f1d1d', color: '#fecaca' },
  impactMedium: { backgroundColor: '#78350f', color: '#fde68a' },
  impactLow: { backgroundColor: '#1e3a5f', color: '#bae6fd' },
  changeEntity: {
    fontSize: '13px',
    fontWeight: '700',
    color: '#f8fafc',
    fontFamily: 'monospace',
  },
  changeReason: {
    margin: '0 0 8px 0',
    fontSize: '12px',
    color: '#fca5a5',
    lineHeight: '1.4',
  },
  callersBox: {
    backgroundColor: '#0f172a',
    borderRadius: '4px',
    padding: '8px',
  },
  callersLabel: {
    display: 'block',
    fontSize: '10px',
    fontWeight: '700',
    color: '#94a3b8',
    marginBottom: '4px',
    textTransform: 'uppercase',
  },
  callersList: {
    display: 'flex',
    gap: '6px',
    flexWrap: 'wrap',
  },
  callerLink: {
    fontSize: '11px',
    color: '#38bdf8',
    backgroundColor: '#1e293b',
    padding: '2px 6px',
    borderRadius: '4px',
    fontFamily: 'monospace',
  },
}
