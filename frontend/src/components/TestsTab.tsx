import React, { useState } from 'react'
import { TestRunData, UncoveredLineItem } from '../types/test_run'

export interface TestsTabProps {
  repositoryId?: string
  testRunData: TestRunData | null
  loading?: boolean
  onGenerateUncovered?: () => void
}

export const TestsTab: React.FC<TestsTabProps> = ({
  repositoryId,
  testRunData,
  loading = false,
  onGenerateUncovered,
}) => {
  const [selectedLine, setSelectedLine] = useState<UncoveredLineItem | null>(null)

  if (!testRunData) {
    const hasRepository = Boolean(repositoryId)
    return (
      <div style={styles.container}>
        <div style={styles.emptyCard} data-testid="tests-empty-state">
          <div style={styles.emptyIcon}>{hasRepository ? '◌' : '↑'}</div>
          <h3>{hasRepository ? 'No Test Run Available' : 'Select a Repository'}</h3>
          <p>
            {hasRepository
              ? 'No coverage run exists for this repository yet. Generate the initial test suite to measure real coverage.'
              : 'Upload or select a repository to generate tests, execute them in the sandbox, and inspect real coverage results.'}
          </p>
          {hasRepository && onGenerateUncovered && (
            <button
              onClick={onGenerateUncovered}
              disabled={loading}
              style={styles.primaryButton}
              data-testid="generate-initial-tests-btn"
            >
              {loading ? 'Generating...' : 'Generate Initial Tests'}
            </button>
          )}
        </div>
      </div>
    )
  }

  const isPassed = testRunData.targetReached || testRunData.statusLabel === 'PASSED'
  const linePercent = Math.min(100, Math.max(0, testRunData.lineCoverage))
  const branchPercent = Math.min(100, Math.max(0, testRunData.branchCoverage))

  return (
    <div style={styles.container} data-testid="tests-tab">
      <div style={styles.summaryCard}>
        <div style={styles.headerRow}>
          <div>
            <span style={styles.title}>Test Execution & Coverage</span>
            <span style={styles.iterationBadge}>Iteration #{testRunData.iteration}</span>
          </div>
          <div style={styles.headerRight}>
            <span
              style={{ ...styles.statusBadge, backgroundColor: isPassed ? '#059669' : '#dc2626' }}
              data-testid="status-badge"
            >
              {isPassed ? 'PASSED' : 'FAILED'} (Target: {testRunData.target}%)
            </span>
            {onGenerateUncovered && (
              <button
                onClick={onGenerateUncovered}
                disabled={loading}
                style={styles.primaryButton}
                data-testid="generate-uncovered-btn"
              >
                {loading ? 'Running Repair Loop...' : 'Generate Tests for Uncovered Code'}
              </button>
            )}
          </div>
        </div>

        <div style={styles.metricsGrid}>
          <div style={styles.metricItem}><span style={styles.metricLabel}>Tests Generated</span><span style={styles.metricValue}>{testRunData.testsGenerated}</span></div>
          <div style={styles.metricItem}><span style={styles.metricLabel}>Passed</span><span style={{ ...styles.metricValue, color: '#10b981' }}>{testRunData.testsPassed}</span></div>
          <div style={styles.metricItem}><span style={styles.metricLabel}>Failed</span><span style={{ ...styles.metricValue, color: testRunData.testsFailed > 0 ? '#ef4444' : '#9ca3af' }}>{testRunData.testsFailed}</span></div>
          <div style={styles.metricItem}><span style={styles.metricLabel}>Line Coverage</span><span style={{ ...styles.metricValue, color: linePercent >= testRunData.target ? '#10b981' : '#f59e0b' }} data-testid="line-coverage-value">{testRunData.lineCoverage}%</span></div>
          <div style={styles.metricItem}><span style={styles.metricLabel}>Branch Coverage</span><span style={styles.metricValue} data-testid="branch-coverage-value">{testRunData.branchCoverage}%</span></div>
        </div>

        <div style={styles.progressSection}>
          <div style={styles.progressRow}>
            <span style={styles.progressLabel}>Line Coverage ({linePercent}% / {testRunData.target}% target)</span>
            <div style={styles.progressTrack}><div style={{ ...styles.progressBar, width: `${linePercent}%`, backgroundColor: linePercent >= testRunData.target ? '#10b981' : '#f59e0b' }} /></div>
          </div>
          <div style={styles.progressRow}>
            <span style={styles.progressLabel}>Branch Coverage ({branchPercent}%)</span>
            <div style={styles.progressTrack}><div style={{ ...styles.progressBar, width: `${branchPercent}%`, backgroundColor: '#3b82f6' }} /></div>
          </div>
        </div>
      </div>

      <div style={styles.contentGrid}>
        <div style={styles.panel}>
          <h4 style={styles.panelTitle}>Uncovered Lines ({testRunData.uncoveredLines.length})</h4>
          <p style={styles.panelSubtitle}>Click an uncovered line to inspect location context.</p>
          {testRunData.uncoveredLines.length === 0 ? (
            <div style={styles.successBox}>All target code lines and branches are fully covered!</div>
          ) : (
            <div style={styles.uncoveredList}>
              {testRunData.uncoveredLines.map((item, idx) => {
                const isSelected = selectedLine?.file === item.file && selectedLine?.line === item.line
                return (
                  <div key={`${item.file}-${item.line}-${idx}`} onClick={() => setSelectedLine(item)} style={{ ...styles.uncoveredItem, backgroundColor: isSelected ? '#1e293b' : '#0f172a', borderColor: isSelected ? '#38bdf8' : '#334155' }} data-testid={`uncovered-line-${idx}`}>
                    <span style={styles.uncoveredFile}>{item.file}</span>
                    <span style={styles.uncoveredLineNum}>Line {item.line}</span>
                    {item.branch && <span style={styles.branchBadge}>Branch</span>}
                  </div>
                )
              })}
            </div>
          )}
          {selectedLine && <div style={styles.selectedLineDetail} data-testid="selected-line-detail"><strong>Selected Location:</strong> {selectedLine.file}:L{selectedLine.line} {selectedLine.branch ? '(Uncovered Branch)' : '(Uncovered Line)'}</div>}
        </div>

        <div style={styles.panel}>
          <h4 style={styles.panelTitle}>Generated Test Suite</h4>
          <p style={styles.panelSubtitle}>AST-grounded runnable pytest / JUnit test code</p>
          <pre style={styles.codeBlock} data-testid="test-code-block"><code>{testRunData.testCode || '// No test code available.'}</code></pre>
        </div>
      </div>

      {testRunData.failedTests.length > 0 && (
        <div style={styles.failedSection}>
          <h4 style={{ ...styles.panelTitle, color: '#f87171' }}>Failed Test Cases ({testRunData.failedTests.length})</h4>
          {testRunData.failedTests.map((failed, idx) => (
            <div key={idx} style={styles.failedCard}>
              <span style={styles.failedName}>{failed.name}</span>
              {failed.targetEntity && <span style={styles.failedEntity}>Target: {failed.targetEntity}</span>}
              <div style={styles.failedMsg}>{failed.message}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  container: { padding: '24px', backgroundColor: '#0f172a', color: '#f8fafc', fontFamily: 'Inter, system-ui, sans-serif', minHeight: '100vh' },
  emptyCard: { backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '12px', padding: '40px', textAlign: 'center', maxWidth: '720px', margin: '80px auto' },
  emptyIcon: { fontSize: '36px', color: '#38bdf8', marginBottom: '12px' },
  summaryCard: { backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '12px', padding: '24px', marginBottom: '24px' },
  headerRow: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' },
  title: { fontSize: '20px', fontWeight: '700', marginRight: '12px' },
  iterationBadge: { fontSize: '12px', fontWeight: '600', backgroundColor: '#334155', color: '#94a3b8', padding: '4px 8px', borderRadius: '6px' },
  headerRight: { display: 'flex', alignItems: 'center', gap: '12px' },
  statusBadge: { fontSize: '13px', fontWeight: '700', color: '#fff', padding: '6px 14px', borderRadius: '20px' },
  primaryButton: { backgroundColor: '#2563eb', color: '#fff', border: 'none', borderRadius: '8px', padding: '10px 18px', fontSize: '14px', fontWeight: '600', cursor: 'pointer' },
  metricsGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '16px', marginBottom: '20px' },
  metricItem: { backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: '8px', padding: '14px', textAlign: 'center' },
  metricLabel: { display: 'block', fontSize: '12px', color: '#94a3b8', marginBottom: '4px' },
  metricValue: { fontSize: '22px', fontWeight: '700' },
  progressSection: { display: 'flex', flexDirection: 'column', gap: '12px' },
  progressRow: { display: 'flex', flexDirection: 'column', gap: '6px' },
  progressLabel: { fontSize: '13px', color: '#cbd5e1' },
  progressTrack: { height: '10px', backgroundColor: '#0f172a', borderRadius: '5px', overflow: 'hidden' },
  progressBar: { height: '100%', borderRadius: '5px', transition: 'width 0.4s ease-in-out' },
  contentGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', marginBottom: '24px' },
  panel: { backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '12px', padding: '20px' },
  panelTitle: { margin: '0 0 4px 0', fontSize: '16px', fontWeight: '700' },
  panelSubtitle: { margin: '0 0 16px 0', fontSize: '13px', color: '#94a3b8' },
  uncoveredList: { display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '340px', overflowY: 'auto' },
  uncoveredItem: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 14px', border: '1px solid #334155', borderRadius: '8px', cursor: 'pointer' },
  uncoveredFile: { fontSize: '13px', fontWeight: '600', color: '#38bdf8' },
  uncoveredLineNum: { fontSize: '12px', color: '#cbd5e1' },
  branchBadge: { fontSize: '11px', backgroundColor: '#7c3aed', color: '#fff', padding: '2px 6px', borderRadius: '4px' },
  selectedLineDetail: { marginTop: '16px', padding: '12px', backgroundColor: '#0284c7', color: '#fff', borderRadius: '8px', fontSize: '13px' },
  successBox: { padding: '16px', backgroundColor: '#065f46', color: '#a7f3d0', borderRadius: '8px', fontSize: '14px' },
  codeBlock: { backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: '8px', padding: '16px', fontSize: '13px', color: '#e2e8f0', maxHeight: '400px', overflowY: 'auto', whiteSpace: 'pre-wrap', margin: 0 },
  failedSection: { backgroundColor: '#1e293b', border: '1px solid #991b1b', borderRadius: '12px', padding: '20px' },
  failedCard: { backgroundColor: '#0f172a', border: '1px solid #7f1d1d', borderRadius: '8px', padding: '12px', marginTop: '12px' },
  failedName: { fontSize: '14px', fontWeight: '700', color: '#f87171', display: 'block' },
  failedEntity: { fontSize: '12px', color: '#9ca3af' },
  failedMsg: { fontSize: '13px', color: '#fca5a5', marginTop: '6px' },
}
