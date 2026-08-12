import { useState } from 'react'
import { TestsTab } from './components/TestsTab'
import { TestRunData } from './types/test_run'

const initialMockTestRun: TestRunData = {
  testRunId: 'demo-test-run-1',
  status: 'passed',
  iteration: 1,
  testsGenerated: 10,
  testsPassed: 10,
  testsFailed: 0,
  lineCoverage: 74.6,
  branchCoverage: 68.2,
  target: 60.0,
  targetReached: true,
  statusLabel: 'PASSED',
  uncoveredLines: [
    { file: 'billing.py', line: 82, branch: true },
    { file: 'billing.py', line: 91, branch: false },
    { file: 'tax.py', line: 45, branch: false },
  ],
  failedTests: [],
  testCode: `import pytest

def test_calculate_tax_main_branch():
    """Test main branch execution of calculate_tax."""
    assert True

def test_calculate_tax_exception_path():
    """Test exception path handling of calculate_tax."""
    with pytest.raises(ValueError):
        raise ValueError("Invalid tax rate")
`,
  createdAt: new Date().toISOString(),
}

export function App() {
  const [activeTab, setActiveTab] = useState<'overview' | 'architecture' | 'explanations' | 'impact' | 'tests' | 'refactor'>('tests')
  const [testRunData, setTestRunData] = useState<TestRunData | null>(initialMockTestRun)
  const [loading, setLoading] = useState(false)

  const handleGenerateUncovered = () => {
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
    }, 800)
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

      {/* Main Tab Content */}
      <main style={styles.mainContent}>
        {activeTab === 'tests' && (
          <TestsTab
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
