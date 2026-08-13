import React from 'react'
import { SafetyScoreData } from '../types/safety'

export interface SafetyScoreCardProps {
  safetyData: SafetyScoreData | null
  loading?: boolean
}

export const SafetyScoreCard: React.FC<SafetyScoreCardProps> = ({
  safetyData,
  loading = false,
}) => {
  if (loading) {
    return (
      <div style={styles.card} data-testid="safety-score-loading">
        <p style={{ color: '#38bdf8' }}>⟳ Computing Refactor Safety Score...</p>
      </div>
    )
  }

  if (!safetyData) {
    return null
  }

  const badgeColor =
    safetyData.riskLevel === 'low'
      ? '#059669'
      : safetyData.riskLevel === 'medium'
        ? '#d97706'
        : '#dc2626'

  return (
    <div style={styles.card} data-testid="safety-score-card">
      {/* Top Header & Score Gauge */}
      <div style={styles.headerRow}>
        <div>
          <h4 style={styles.cardTitle}>Refactor Safety Score</h4>
          <p style={styles.cardSubtitle}>
            0–100 score derived from API compatibility, test compatibility, dependency impact, and
            behavioral risk.
          </p>
        </div>

        <div style={styles.scoreContainer}>
          <div style={styles.scoreCircle} data-testid="total-safety-score">
            <span style={styles.scoreNumber}>{safetyData.total}</span>
            <span style={styles.scoreMax}>/100</span>
          </div>

          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', justifyContent: 'center' }}>
            <span
              style={{
                ...styles.riskBadge,
                backgroundColor: badgeColor,
              }}
              data-testid="risk-level-badge"
            >
              {safetyData.riskLevel.toUpperCase()} RISK
            </span>

            {safetyData.confidenceScore !== undefined && (
              <span
                style={{
                  ...styles.riskBadge,
                  backgroundColor: '#0284c7',
                }}
                data-testid="confidence-badge"
              >
                CONFIDENCE: {safetyData.confidenceScore}%
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Sub-scores Grid */}
      <div style={styles.subScoresGrid}>
        <SubScoreBar
          label="API Compatibility"
          score={safetyData.apiCompatibility}
          testId="api-compat-score"
        />
        <SubScoreBar
          label="Test Compatibility"
          score={safetyData.testCompatibility}
          testId="test-compat-score"
        />
        <SubScoreBar
          label="Dependency Impact"
          score={safetyData.dependencyImpact}
          testId="dep-impact-score"
        />
        <SubScoreBar
          label="Behavioral Risk"
          score={safetyData.behavioralRisk}
          testId="beh-risk-score"
        />
      </div>

      {/* Breaking Changes (T-18) */}
      {safetyData.breakingChanges.length > 0 && (
        <div style={styles.section}>
          <h5 style={styles.sectionTitle}>
            Breaking Changes Detected ({safetyData.breakingChanges.length})
          </h5>
          <div style={styles.bcList}>
            {safetyData.breakingChanges.map((bc, idx) => {
              const impactColor =
                bc.impact === 'HIGH' ? '#dc2626' : bc.impact === 'MEDIUM' ? '#d97706' : '#2563eb'
              return (
                <div key={idx} style={styles.bcItem} data-testid={`breaking-change-${idx}`}>
                  <div style={styles.bcHeader}>
                    <span
                      style={{
                        ...styles.impactBadge,
                        backgroundColor: impactColor,
                      }}
                    >
                      {bc.impact}
                    </span>
                    <span style={styles.bcEntity}>{bc.entity}</span>
                  </div>
                  <p style={styles.bcReason}>{bc.reason}</p>
                  {bc.affectedCallers.length > 0 && (
                    <div style={styles.callersRow}>
                      <span style={styles.callersLabel}>Impacted callers:</span>
                      {bc.affectedCallers.map((c, i) => (
                        <code key={i} style={styles.callerCode}>
                          {c}
                        </code>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Recommendations */}
      {safetyData.recommendations.length > 0 && (
        <div style={styles.section}>
          <h5 style={styles.sectionTitle}>Safety Recommendations</h5>
          <ul style={styles.recList}>
            {safetyData.recommendations.map((rec, i) => (
              <li key={i} style={styles.recItem}>
                <span style={styles.recBullet}>✓</span>
                {rec}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

interface SubScoreBarProps {
  label: string
  score: number
  testId?: string
}

const SubScoreBar: React.FC<SubScoreBarProps> = ({ label, score, testId }) => {
  const barColor = score >= 80 ? '#10b981' : score >= 50 ? '#f59e0b' : '#ef4444'

  return (
    <div style={styles.subScoreItem} data-testid={testId}>
      <div style={styles.subScoreHeader}>
        <span style={styles.subScoreLabel}>{label}</span>
        <span style={{ ...styles.subScoreVal, color: barColor }}>{score}%</span>
      </div>
      <div style={styles.subScoreTrack}>
        <div
          style={{
            ...styles.subScoreBar,
            width: `${Math.min(100, Math.max(0, score))}%`,
            backgroundColor: barColor,
          }}
        />
      </div>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  card: {
    backgroundColor: '#1e293b',
    border: '1px solid #334155',
    borderRadius: '12px',
    padding: '24px',
    marginBottom: '24px',
  },
  headerRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '20px',
  },
  cardTitle: {
    margin: '0 0 4px 0',
    fontSize: '18px',
    fontWeight: '700',
  },
  cardSubtitle: {
    margin: 0,
    fontSize: '13px',
    color: '#94a3b8',
  },
  scoreContainer: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '6px',
  },
  scoreCircle: {
    display: 'flex',
    alignItems: 'baseline',
    backgroundColor: '#0f172a',
    border: '2px solid #38bdf8',
    borderRadius: '12px',
    padding: '8px 16px',
  },
  scoreNumber: {
    fontSize: '28px',
    fontWeight: '800',
    color: '#38bdf8',
  },
  scoreMax: {
    fontSize: '14px',
    color: '#64748b',
    marginLeft: '2px',
  },
  riskBadge: {
    fontSize: '11px',
    fontWeight: '700',
    color: '#ffffff',
    padding: '3px 10px',
    borderRadius: '12px',
    letterSpacing: '0.05em',
  },
  subScoresGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '16px',
    marginBottom: '20px',
  },
  subScoreItem: {
    backgroundColor: '#0f172a',
    border: '1px solid #334155',
    borderRadius: '8px',
    padding: '12px 16px',
  },
  subScoreHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    marginBottom: '6px',
  },
  subScoreLabel: {
    fontSize: '12px',
    color: '#94a3b8',
    fontWeight: '600',
  },
  subScoreVal: {
    fontSize: '13px',
    fontWeight: '700',
  },
  subScoreTrack: {
    height: '6px',
    backgroundColor: '#1e293b',
    borderRadius: '3px',
    overflow: 'hidden',
  },
  subScoreBar: {
    height: '100%',
    borderRadius: '3px',
    transition: 'width 0.4s ease',
  },
  section: {
    marginTop: '20px',
    paddingTop: '16px',
    borderTop: '1px solid #334155',
  },
  sectionTitle: {
    margin: '0 0 12px 0',
    fontSize: '13px',
    fontWeight: '700',
    color: '#94a3b8',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
  },
  bcList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '10px',
  },
  bcItem: {
    backgroundColor: '#0f172a',
    border: '1px solid #334155',
    borderRadius: '8px',
    padding: '12px',
  },
  bcHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    marginBottom: '4px',
  },
  impactBadge: {
    fontSize: '10px',
    fontWeight: '700',
    color: '#ffffff',
    padding: '2px 6px',
    borderRadius: '4px',
  },
  bcEntity: {
    fontSize: '13px',
    fontWeight: '700',
    color: '#f8fafc',
  },
  bcReason: {
    margin: '0 0 6px 0',
    fontSize: '13px',
    color: '#cbd5e1',
  },
  callersRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    flexWrap: 'wrap',
  },
  callersLabel: {
    fontSize: '11px',
    color: '#94a3b8',
  },
  callerCode: {
    fontSize: '11px',
    backgroundColor: '#1e293b',
    color: '#38bdf8',
    padding: '2px 6px',
    borderRadius: '4px',
  },
  recList: {
    margin: 0,
    padding: 0,
    listStyle: 'none',
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  },
  recItem: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    fontSize: '13px',
    color: '#e2e8f0',
  },
  recBullet: {
    color: '#10b981',
    fontWeight: '700',
  },
}
