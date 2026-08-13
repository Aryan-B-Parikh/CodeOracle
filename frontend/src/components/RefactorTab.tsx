import React, { useState } from 'react'
import { RefactorProposal } from '../types/refactor'
import { SafetyScoreData } from '../types/safety'
import { DiffViewer } from './DiffViewer'
import { SafetyScoreCard } from './SafetyScoreCard'

export interface RefactorTabProps {
  repositoryId?: string
  proposal: RefactorProposal | null
  safetyData?: SafetyScoreData | null
  loading?: boolean
  onPropose?: (entityId: string) => void
}

export const RefactorTab: React.FC<RefactorTabProps> = ({
  repositoryId,
  proposal,
  safetyData = null,
  loading = false,
  onPropose,
}) => {
  const [entityIdInput, setEntityIdInput] = useState('')

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

  return (
    <div style={styles.container} data-testid="refactor-tab">
      {/* Proposal Controls */}
      <div style={styles.controlCard}>
        <h3 style={styles.cardTitle}>Refactor Proposal</h3>
        <p style={styles.cardSubtitle}>
          Enter an entity ID to generate a modernization proposal with original vs. proposed
          diff and a WHY list. Original repository files are never modified.
        </p>
        <div style={styles.inputRow}>
          <input
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
            {loading ? 'Generating Proposal...' : 'Propose Refactor'}
          </button>
        </div>
      </div>

      {/* No proposal yet */}
      {!proposal && !loading && (
        <div style={styles.emptyProposal}>
          <p>Enter an entity ID above and click "Propose Refactor" to generate a diff.</p>
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div style={styles.emptyProposal}>
          <p style={{ color: '#38bdf8' }}>⟳ Generating refactor proposal via LLM...</p>
        </div>
      )}

      {/* Proposal Result */}
      {proposal && !loading && (
        <>
          {/* Metadata header */}
          <div style={styles.proposalHeader}>
            <div>
              <span style={styles.entityName}>{proposal.entityName}</span>
              <span style={styles.filePath}>{proposal.filePath}</span>
            </div>
            <div style={styles.checksumRow}>
              <span style={styles.checksumLabel}>Original checksum (repo unchanged):</span>
              <code style={styles.checksum}>{proposal.originalChecksum.slice(0, 16)}…</code>
            </div>
          </div>

          {/* Safety Score Card (T-19 & T-18) */}
          <SafetyScoreCard safetyData={safetyData} loading={loading} />

          {/* Diff view */}
          <div style={styles.section}>
            <h4 style={styles.sectionTitle}>Code Diff</h4>
            <DiffViewer
              original={proposal.original}
              proposed={proposal.proposed}
              entityName={proposal.entityName}
            />
          </div>

          {/* WHY list */}
          <div style={styles.twoCol}>
            <div style={styles.panel}>
              <h4 style={styles.sectionTitle}>Why This Refactor</h4>
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
                  No behavioral differences — refactor preserves observable behavior.
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
        </>
      )}
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    padding: '24px',
    backgroundColor: '#0f172a',
    color: '#f8fafc',
    minHeight: '100vh',
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
  },
  cardTitle: {
    margin: '0 0 6px 0',
    fontSize: '18px',
    fontWeight: '700',
  },
  cardSubtitle: {
    margin: '0 0 16px 0',
    fontSize: '13px',
    color: '#94a3b8',
  },
  inputRow: {
    display: 'flex',
    gap: '12px',
  },
  entityInput: {
    flex: 1,
    backgroundColor: '#0f172a',
    border: '1px solid #334155',
    borderRadius: '8px',
    padding: '10px 14px',
    color: '#f8fafc',
    fontSize: '14px',
    outline: 'none',
  },
  proposeButton: {
    backgroundColor: '#7c3aed',
    color: '#ffffff',
    border: 'none',
    borderRadius: '8px',
    padding: '10px 20px',
    fontSize: '14px',
    fontWeight: '600',
    cursor: 'pointer',
    whiteSpace: 'nowrap',
  },
  emptyProposal: {
    backgroundColor: '#1e293b',
    border: '1px solid #334155',
    borderRadius: '12px',
    padding: '32px',
    textAlign: 'center',
    color: '#64748b',
    fontSize: '14px',
  },
  proposalHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: '#1e293b',
    border: '1px solid #334155',
    borderRadius: '12px',
    padding: '16px 20px',
    marginBottom: '20px',
  },
  entityName: {
    display: 'block',
    fontSize: '18px',
    fontWeight: '700',
    color: '#38bdf8',
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
  },
  section: {
    marginBottom: '20px',
  },
  sectionTitle: {
    fontSize: '14px',
    fontWeight: '700',
    color: '#94a3b8',
    margin: '0 0 10px 0',
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
    fontSize: '14px',
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
    backgroundColor: '#052e16',
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
    backgroundColor: '#1c0a0a',
    border: '1px solid #7f1d1d',
    borderRadius: '12px',
    padding: '20px',
    marginTop: '20px',
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
    margin: '0 0 16px 0',
    fontSize: '12px',
    color: '#b91c1c',
  },
  changesList: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: '12px',
  },
  changeItem: {
    backgroundColor: '#2a0a0a',
    border: '1px solid #7f1d1d',
    borderRadius: '8px',
    padding: '14px',
  },
  changeHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    marginBottom: '6px',
  },
  impactBadge: {
    fontSize: '11px',
    fontWeight: '800',
    padding: '2px 8px',
    borderRadius: '4px',
    letterSpacing: '0.06em',
    flexShrink: 0,
  },
  impactHigh: {
    backgroundColor: '#7f1d1d',
    color: '#fecaca',
  },
  impactMedium: {
    backgroundColor: '#78350f',
    color: '#fde68a',
  },
  impactLow: {
    backgroundColor: '#1e3a5f',
    color: '#bae6fd',
  },
  changeEntity: {
    fontSize: '14px',
    fontWeight: '600',
    color: '#f8fafc',
  },
  changeReason: {
    margin: '0 0 10px 0',
    fontSize: '13px',
    color: '#fca5a5',
    lineHeight: '1.5',
  },
  callersBox: {
    backgroundColor: '#0f172a',
    borderRadius: '6px',
    padding: '10px',
  },
  callersLabel: {
    display: 'block',
    fontSize: '11px',
    fontWeight: '600',
    color: '#64748b',
    marginBottom: '6px',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.05em',
  },
  callersList: {
    display: 'flex',
    flexDirection: 'column' as const,
    gap: '4px',
  },
  callerLink: {
    fontSize: '12px',
    color: '#38bdf8',
    backgroundColor: '#0c1829',
    padding: '2px 6px',
    borderRadius: '4px',
    fontFamily: 'monospace',
  },
  noBreakingChangesBox: {
    backgroundColor: '#052e16',
    color: '#86efac',
    borderRadius: '8px',
    padding: '12px 16px',
    fontSize: '13px',
    marginTop: '20px',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
}
