import { useState, useEffect } from 'react'
import { TestsTab } from './components/TestsTab'
import { TestRunData } from './types/test_run'
import { fetchLatestTestRun, triggerGenerateUncovered } from './services/api'

export function App() {
  const [activeTab, setActiveTab] = useState<'overview' | 'architecture' | 'explanations' | 'impact' | 'tests' | 'refactor'>('tests')
  const [repositoryId] = useState<string | null>(null)
  const [testRunData, setTestRunData] = useState<TestRunData | null>(null)
  const [loading, setLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  // Fetch latest test run from backend API on mount or repositoryId change
  useEffect(() => {
    if (!repositoryId) return

    let isMounted = true
    setLoading(true)
    fetchLatestTestRun(repositoryId)
      .then((envelope) => {
        if (isMounted && envelope.data) {
          setTestRunData(envelope.data)
          setErrorMessage(null)
        }
      })
      .catch((err) => {
        if (isMounted) {
          logger_error('Failed to load test run:', err)
        }
      })
      .finally(() => {
        if (isMounted) setLoading(false)
      })

    return () => {
      isMounted = false
    }
  }, [repositoryId])

  const handleGenerateUncovered = async () => {
    if (!repositoryId) {
      // Demo fallback if no active repositoryId is selected
      setLoading(true)
      setTimeout(() => {
        if (testRunData) {
          setTestRunData({
            ...testRunData,
            iteration: testRunData.iteration + 1,
            lineCoverage: Math.min(95.0, testRunData.lineCoverage + 15.0),
            branchCoverage: Math.min(90.0, testRunData.branchCoverage + 12.0),
            uncoveredLines: testRunData.uncoveredLines.slice(1),
            targetReached: true,
            statusLabel: 'PASSED',
          })
        }
        setLoading(false)
      }, 500)
      return
    }

    setLoading(true)
    setErrorMessage(null)
    try {
      const envelope = await triggerGenerateUncovered(repositoryId, 3, 60.0)
      if (envelope.data) {
        setTestRunData(envelope.data)
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setErrorMessage(`Coverage repair failed: ${msg}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={styles.appContainer}>
      {/* Navigation Header */}
      <header style={styles.header}>
        <div style={styles.logoRow}>
          <span style={styles.logoText}>CodeOracle</span>
          <span style={styles.versionBadge}>v0.1.0</span>
        </div>

        <nav style={styles.navTabs}>
          {(['overview', 'architecture', 'explanations', 'impact', 'tests', 'refactor'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              style={{
                ...styles.navButton,
                color: activeTab === tab ? '#38bdf8' : '#94a3b8',
                borderBottom: activeTab === tab ? '2px solid #38bdf8' : '2px solid transparent',
              }}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </nav>
      </header>

      {/* Error Alert (if any) */}
      {errorMessage && (
        <div style={styles.errorBanner}>
          <span>{errorMessage}</span>
          <button onClick={() => setErrorMessage(null)} style={styles.closeBtn}>×</button>
        </div>
      )}

      {/* Main Tab Content */}
      <main style={styles.mainContent}>
        {activeTab === 'tests' && (
          <TestsTab
            repositoryId={repositoryId || undefined}
            testRunData={testRunData}
            loading={loading}
            onGenerateUncovered={handleGenerateUncovered}
          />
        )}

        {activeTab !== 'tests' && (
          <div style={styles.placeholderTab}>
            <h2>{activeTab.charAt(0).toUpperCase() + activeTab.slice(1)} Tab</h2>
            <p>Content for the {activeTab} section of CodeOracle.</p>
          </div>
        )}
      </main>
    </div>
  )
}

function logger_error(msg: string, err: unknown) {
  // Simple error logger helper for frontend
  console.error(msg, err)
}

const styles: Record<string, React.CSSProperties> = {
  appContainer: {
    backgroundColor: '#0f172a',
    minHeight: '100vh',
    color: '#f8fafc',
    fontFamily: 'Inter, system-ui, sans-serif',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '0 24px',
    backgroundColor: '#1e293b',
    borderBottom: '1px solid #334155',
  },
  logoRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
  },
  logoText: {
    fontSize: '20px',
    fontWeight: '800',
    background: 'linear-gradient(to right, #38bdf8, #818cf8)',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
  },
  versionBadge: {
    fontSize: '11px',
    backgroundColor: '#334155',
    color: '#94a3b8',
    padding: '2px 6px',
    borderRadius: '4px',
  },
  navTabs: {
    display: 'flex',
    gap: '8px',
  },
  navButton: {
    backgroundColor: 'transparent',
    border: 'none',
    padding: '16px 12px',
    fontSize: '14px',
    fontWeight: '600',
    cursor: 'pointer',
    transition: 'color 0.2s',
  },
  errorBanner: {
    backgroundColor: '#7f1d1d',
    color: '#fecaca',
    padding: '12px 24px',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    fontSize: '14px',
  },
  closeBtn: {
    backgroundColor: 'transparent',
    border: 'none',
    color: '#fecaca',
    fontSize: '18px',
    cursor: 'pointer',
  },
  mainContent: {
    padding: '0',
  },
  placeholderTab: {
    padding: '40px',
    textAlign: 'center',
    color: '#94a3b8',
  },
}

export default App
