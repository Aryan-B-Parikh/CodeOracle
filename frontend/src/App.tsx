import React, { useState, useEffect, useRef } from 'react'
import { TestsTab } from './components/TestsTab'
import { RefactorTab } from './components/RefactorTab'
import { TestRunData } from './types/test_run'
import { RefactorProposal } from './types/refactor'
import {
  fetchLatestTestRun,
  fetchRepositories,
  RepositorySummary,
  triggerGenerateUncovered,
  proposeRefactor,
  uploadRepository,
} from './services/api'

type TabKey = 'overview' | 'architecture' | 'explanations' | 'impact' | 'tests' | 'refactor'

const TABS: TabKey[] = ['overview', 'architecture', 'explanations', 'impact', 'tests', 'refactor']

export function App() {
  const [activeTab, setActiveTab] = useState<TabKey>('tests')
  const [repositoryId, setRepositoryId] = useState<string | null>(null)
  const [repositories, setRepositories] = useState<RepositorySummary[]>([])
  const [testRunData, setTestRunData] = useState<TestRunData | null>(null)
  const [refactorProposal, setRefactorProposal] = useState<RefactorProposal | null>(null)
  const [loading, setLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    fetchRepositories()
      .then((envelope) => setRepositories(envelope.data ?? []))
      .catch((err) => console.error('Failed to load repositories:', err))
  }, [])

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
          console.error('Failed to load test run:', err)
          setTestRunData(null)
        }
      })
      .finally(() => {
        if (isMounted) setLoading(false)
      })

    return () => {
      isMounted = false
    }
  }, [repositoryId])

  const selectRepository = (id: string) => {
    if (!id) return
    setRepositoryId(id)
    setRefactorProposal(null)
  }

  const handleUpload = async (file: File | null) => {
    if (!file) return
    setLoading(true)
    setErrorMessage(null)
    try {
      const repo = await uploadRepository(file)
      setRepositories((prev) => [repo, ...prev])
      selectRepository(repo.id)
      setActiveTab('tests')
      if (fileInputRef.current) fileInputRef.current.value = ''
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setErrorMessage(`Upload failed: ${msg}`)
    } finally {
      setLoading(false)
    }
  }

  const handleGenerateUncovered = async () => {
    if (!repositoryId) return

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

  const handleProposeRefactor = async (entityId: string) => {
    if (!repositoryId) return
    setLoading(true)
    setErrorMessage(null)
    setRefactorProposal(null)
    try {
      const envelope = await proposeRefactor(repositoryId, entityId)
      if (envelope.data) {
        setRefactorProposal(envelope.data)
      } else if (envelope.error) {
        setErrorMessage(`Refactor proposal failed: ${envelope.error.message}`)
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setErrorMessage(`Refactor proposal failed: ${msg}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={styles.appContainer}>
      <header style={styles.header}>
        <div style={styles.logoRow}>
          <span style={styles.logoText}>CodeOracle</span>
          <span style={styles.versionBadge}>v0.1.0</span>
        </div>

        <div style={styles.repoControls}>
          <select
            value={repositoryId ?? ''}
            onChange={(e) => selectRepository(e.target.value)}
            style={styles.repoSelect}
            aria-label="Select repository"
          >
            <option value="">Select repository…</option>
            {repositories.map((repo) => (
              <option key={repo.id} value={repo.id}>
                {repo.name} ({repo.status})
              </option>
            ))}
          </select>
          <input
            ref={fileInputRef}
            type="file"
            accept=".zip"
            style={{ display: 'none' }}
            onChange={(e) => handleUpload(e.target.files?.[0] ?? null)}
            data-testid="upload-input"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={loading}
            style={styles.uploadButton}
            data-testid="upload-btn"
          >
            {loading ? 'Uploading…' : 'Upload ZIP'}
          </button>
        </div>

        <nav style={styles.navTabs}>
          {TABS.map((tab) => (
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

      {errorMessage && (
        <div style={styles.errorBanner} role="alert">
          <span>{errorMessage}</span>
          <button onClick={() => setErrorMessage(null)} style={styles.closeBtn} aria-label="Dismiss error">
            ×
          </button>
        </div>
      )}

      <main style={styles.mainContent}>
        {activeTab === 'tests' && (
          <TestsTab
            repositoryId={repositoryId || undefined}
            testRunData={testRunData}
            loading={loading}
            onGenerateUncovered={repositoryId ? handleGenerateUncovered : undefined}
          />
        )}

        {activeTab === 'refactor' && (
          <RefactorTab
            repositoryId={repositoryId || undefined}
            proposal={refactorProposal}
            loading={loading}
            onPropose={repositoryId ? handleProposeRefactor : undefined}
          />
        )}

        {activeTab !== 'tests' && activeTab !== 'refactor' && (
          <div style={styles.placeholderTab}>
            <h2>{activeTab.charAt(0).toUpperCase() + activeTab.slice(1)} Tab</h2>
            <p>
              Not implemented yet (scoped out: processing pipeline/dashboard/report-export UI).
            </p>
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
    gap: '16px',
    padding: '0 24px',
    backgroundColor: '#1e293b',
    borderBottom: '1px solid #334155',
  },
  logoRow: { display: 'flex', alignItems: 'center', gap: '10px' },
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
  repoControls: { display: 'flex', alignItems: 'center', gap: '8px', flex: 1 },
  repoSelect: {
    flex: 1,
    maxWidth: '360px',
    backgroundColor: '#0f172a',
    border: '1px solid #334155',
    borderRadius: '8px',
    padding: '8px 10px',
    color: '#f8fafc',
    fontSize: '13px',
    outline: 'none',
  },
  uploadButton: {
    backgroundColor: '#2563eb',
    color: '#fff',
    border: 'none',
    borderRadius: '8px',
    padding: '8px 14px',
    fontSize: '13px',
    fontWeight: '600',
    cursor: 'pointer',
    whiteSpace: 'nowrap',
  },
  navTabs: { display: 'flex', gap: '4px' },
  navButton: {
    backgroundColor: 'transparent',
    border: 'none',
    padding: '16px 10px',
    fontSize: '13px',
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
  closeBtn: { backgroundColor: 'transparent', border: 'none', color: '#fecaca', fontSize: '18px', cursor: 'pointer' },
  mainContent: { padding: '0' },
  placeholderTab: { padding: '40px', textAlign: 'center', color: '#94a3b8' },
}

export default App