import React from 'react'

export interface ArchLayer {
  name: string
  fileCount: number
  moduleCount: number
  modules: string[]
}

export interface ArchIssue {
  severity: 'high' | 'medium' | 'low'
  type: string
  description: string
  affectedItems: string[]
}

export interface HighRiskEntity {
  name: string
  filePath: string
  complexity: number
  fanIn: number
  riskReasons: string[]
}

export interface RepositorySummaryData {
  repositoryId: string
  architecturePattern: string
  layers: ArchLayer[]
  architecturalIssues: ArchIssue[]
  highRiskEntities: HighRiskEntity[]
}

export interface DashboardTabProps {
  repositoryId?: string
  repositoryName?: string
  summaryData: RepositorySummaryData | null
  loading?: boolean
  onDownloadReport?: () => void
}

export const DashboardTab: React.FC<DashboardTabProps> = ({
  repositoryId,
  repositoryName = 'Repository',
  summaryData,
  loading = false,
  onDownloadReport,
}) => {
  if (!repositoryId) {
    return (
      <div style={styles.container}>
        <div style={styles.emptyState}>
          <div style={styles.emptyIcon}>📊</div>
          <h3 style={styles.emptyTitle}>No Repository Selected</h3>
          <p style={styles.emptySubtitle}>
            Select or upload a repository to view architectural analytics and export reports.
          </p>
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div style={styles.container}>
        <div style={styles.emptyState}>
          <p style={{ color: '#38bdf8' }}>⟳ Loading repository analytics...</p>
        </div>
      </div>
    )
  }

  return (
    <div style={styles.container} data-testid="dashboard-tab">
      {/* Top Banner */}
      <div style={styles.topBanner}>
        <div>
          <h3 style={styles.bannerTitle}>{repositoryName} Dashboard</h3>
          <p style={styles.bannerSubtitle}>
            Architectural summary, layer breakdown, risk warnings, and executive report export.
          </p>
        </div>
        <button
          onClick={onDownloadReport}
          style={styles.exportButton}
          data-testid="export-report-btn"
        >
          📥 Export Executive Report (.md)
        </button>
      </div>

      {summaryData && (() => {
        const layers = summaryData.layers || []
        const architecturalIssues = summaryData.architecturalIssues || []
        const highRiskEntities = summaryData.highRiskEntities || []

        return (
        <>
          {/* Architecture Pattern Banner */}
          <div style={styles.patternBox} data-testid="arch-pattern">
            <span style={styles.patternLabel}>Inferred Architecture Pattern:</span>
            <span style={styles.patternVal}>{summaryData.architecturePattern || 'Modular / Layered'}</span>
          </div>

          {/* Architectural Layers */}
          <div style={styles.section}>
            <h4 style={styles.sectionTitle}>Architectural Layers</h4>
            <div style={styles.layersGrid}>
              {layers.length === 0 ? (
                <div style={styles.noIssuesBox}>Layers are being organized from discovered modules...</div>
              ) : (
                layers.map((layer, idx) => {
                  const modules = layer.modules || []
                  return (
                    <div key={idx} style={styles.layerCard} data-testid={`layer-${idx}`}>
                      <div style={styles.layerHeader}>
                        <span style={styles.layerName}>{layer.name}</span>
                        <span style={styles.layerCount}>{layer.fileCount || 0} files</span>
                      </div>
                      <p style={styles.layerModules}>
                        Modules: {modules.slice(0, 5).join(', ')}
                        {modules.length > 5 ? '…' : ''}
                      </p>
                    </div>
                  )
                })
              )}
            </div>
          </div>

          {/* Architectural Issues & Warnings */}
          <div style={styles.section}>
            <h4 style={styles.sectionTitle}>
              Architectural Issues &amp; Warnings ({architecturalIssues.length})
            </h4>
            {architecturalIssues.length === 0 ? (
              <div style={styles.noIssuesBox}>
                ✓ No high-risk architectural issues detected in this repository.
              </div>
            ) : (
              <div style={styles.issuesList}>
                {architecturalIssues.map((issue, idx) => {
                  const badgeColor =
                    issue.severity === 'high'
                      ? '#dc2626'
                      : issue.severity === 'medium'
                      ? '#d97706'
                      : '#2563eb'
                  const affected = issue.affectedItems || []

                  return (
                    <div key={idx} style={styles.issueItem} data-testid={`issue-${idx}`}>
                      <div style={styles.issueHeader}>
                        <span style={{ ...styles.sevBadge, backgroundColor: badgeColor }}>
                          {(issue.severity || 'info').toUpperCase()}
                        </span>
                        <span style={styles.issueType}>{issue.type}</span>
                      </div>
                      <p style={styles.issueDesc}>{issue.description}</p>
                      {affected.length > 0 && (
                        <div style={styles.affectedRow}>
                          <span style={styles.affectedLabel}>Affected:</span>
                          {affected.map((item, i) => (
                            <code key={i} style={styles.itemCode}>
                              {item}
                            </code>
                          ))}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          {/* High-Risk Entities */}
          {highRiskEntities.length > 0 && (
            <div style={styles.section}>
              <h4 style={styles.sectionTitle}>High-Risk Code Entities ({highRiskEntities.length})</h4>
              <div style={styles.tableCard}>
                <table style={styles.table}>
                  <thead>
                    <tr>
                      <th style={styles.th}>Entity</th>
                      <th style={styles.th}>File Path</th>
                      <th style={styles.th}>CCN</th>
                      <th style={styles.th}>Fan-In</th>
                      <th style={styles.th}>Risk Reasons</th>
                    </tr>
                  </thead>
                  <tbody>
                    {highRiskEntities.map((entity, idx) => {
                      const reasons = entity.riskReasons || []
                      return (
                        <tr key={idx} style={styles.tr}>
                          <td style={styles.tdBold}>{entity.name}</td>
                          <td style={styles.tdCode}>{entity.filePath}</td>
                          <td style={styles.tdCenter}>{entity.complexity}</td>
                          <td style={styles.tdCenter}>{entity.fanIn}</td>
                          <td style={styles.tdMuted}>{reasons.join(', ')}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
        )
      })()}
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
  emptyIcon: { fontSize: '48px', color: '#334155' },
  emptyTitle: { fontSize: '22px', fontWeight: '700', color: '#94a3b8', margin: 0 },
  emptySubtitle: { fontSize: '15px', color: '#64748b', maxWidth: '400px', margin: 0 },
  topBanner: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: '#1e293b',
    border: '1px solid #334155',
    borderRadius: '12px',
    padding: '24px',
    marginBottom: '24px',
  },
  bannerTitle: { margin: '0 0 4px 0', fontSize: '20px', fontWeight: '800' },
  bannerSubtitle: { margin: 0, fontSize: '13px', color: '#94a3b8' },
  exportButton: {
    backgroundColor: '#059669',
    color: '#ffffff',
    border: 'none',
    borderRadius: '8px',
    padding: '10px 18px',
    fontSize: '13px',
    fontWeight: '700',
    cursor: 'pointer',
    whiteSpace: 'nowrap',
  },
  patternBox: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    backgroundColor: '#1e293b',
    border: '1px solid #334155',
    borderRadius: '8px',
    padding: '14px 20px',
    marginBottom: '24px',
  },
  patternLabel: { fontSize: '13px', color: '#94a3b8', fontWeight: '600' },
  patternVal: { fontSize: '15px', color: '#38bdf8', fontWeight: '700' },
  section: { marginBottom: '24px' },
  sectionTitle: {
    fontSize: '14px',
    fontWeight: '700',
    color: '#94a3b8',
    margin: '0 0 12px 0',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
  },
  layersGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' },
  layerCard: {
    backgroundColor: '#1e293b',
    border: '1px solid #334155',
    borderRadius: '8px',
    padding: '16px',
  },
  layerHeader: { display: 'flex', justifyContent: 'space-between', marginBottom: '6px' },
  layerName: { fontSize: '15px', fontWeight: '700', color: '#f8fafc' },
  layerCount: { fontSize: '12px', color: '#38bdf8', fontWeight: '600' },
  layerModules: { margin: 0, fontSize: '12px', color: '#94a3b8' },
  noIssuesBox: {
    backgroundColor: '#052e16',
    color: '#86efac',
    borderRadius: '8px',
    padding: '14px',
    fontSize: '13px',
  },
  issuesList: { display: 'flex', flexDirection: 'column', gap: '10px' },
  issueItem: {
    backgroundColor: '#1e293b',
    border: '1px solid #334155',
    borderRadius: '8px',
    padding: '14px',
  },
  issueHeader: { display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' },
  sevBadge: {
    fontSize: '10px',
    fontWeight: '700',
    color: '#ffffff',
    padding: '2px 6px',
    borderRadius: '4px',
  },
  issueType: { fontSize: '14px', fontWeight: '700', color: '#f8fafc' },
  issueDesc: { margin: '0 0 6px 0', fontSize: '13px', color: '#cbd5e1' },
  affectedRow: { display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' },
  affectedLabel: { fontSize: '11px', color: '#94a3b8' },
  itemCode: {
    fontSize: '11px',
    backgroundColor: '#0f172a',
    color: '#38bdf8',
    padding: '2px 6px',
    borderRadius: '4px',
  },
  tableCard: {
    backgroundColor: '#1e293b',
    border: '1px solid #334155',
    borderRadius: '8px',
    overflow: 'hidden',
  },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: '13px' },
  th: {
    backgroundColor: '#0f172a',
    color: '#94a3b8',
    textAlign: 'left',
    padding: '10px 14px',
    fontWeight: '600',
    borderBottom: '1px solid #334155',
  },
  tr: { borderBottom: '1px solid #334155' },
  tdBold: { padding: '10px 14px', fontWeight: '700', color: '#f8fafc' },
  tdCode: { padding: '10px 14px', fontFamily: 'monospace', color: '#38bdf8' },
  tdCenter: { padding: '10px 14px', textAlign: 'center', fontWeight: '700' },
  tdMuted: { padding: '10px 14px', color: '#94a3b8', fontSize: '12px' },
}
