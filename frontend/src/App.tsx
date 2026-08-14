import React, { useState, useEffect, useRef, useCallback } from 'react'
import { TestsTab } from './components/TestsTab'
import { RefactorTab } from './components/RefactorTab'
import { DashboardTab, RepositorySummaryData } from './components/DashboardTab'
import { PipelineStatusCard, RepositoryStatusData } from './components/PipelineStatusCard'
import { ExplanationTab } from './components/ExplanationTab'
import { DependencyGraphTab } from './components/DependencyGraphTab'
import { SystemDocsTab } from './components/SystemDocsTab'
import { TestRunData } from './types/test_run'
import { RefactorProposal } from './types/refactor'
import { SafetyScoreData } from './types/safety'
import {
  fetchLatestTestRun,
  fetchRepositories,
  fetchRepositorySummary,
  fetchRepositoryStatus,
  downloadExecutiveReport,
  RepositorySummary,
  triggerGenerateUncovered,
  proposeRefactor,
  fetchSafetyScore,
  uploadRepository,
  importRepository,
  triggerAnalysis,
} from './services/api'

export type TabKey = 'overview' | 'explanations' | 'graph' | 'tests' | 'refactor' | 'docs'

export interface TabConfig {
  key: TabKey
  label: string
  icon: string
  badge?: string
}

const TABS: TabConfig[] = [
  { key: 'overview', label: 'Overview & Architecture', icon: '📊' },
  { key: 'explanations', label: 'Grounded Explanations', icon: '📖' },
  { key: 'graph', label: 'Dependency Graph', icon: '🕸' },
  { key: 'tests', label: 'Generated Tests Lab', icon: '🧪' },
  { key: 'refactor', label: 'Refactor & Safety', icon: '⚡' },
  { key: 'docs', label: 'System Manual & Guide', icon: '📚' },
]

const POLL_INTERVAL_MS = 750
const MAX_POLL_DURATION_MS = 6 * 60 * 1000

export function App() {
  const [activeTab, setActiveTab] = useState<TabKey>('overview')
  const [repositoryId, setRepositoryId] = useState<string | null>(null)
  const [repositories, setRepositories] = useState<RepositorySummary[]>([])
  const [testRunData, setTestRunData] = useState<TestRunData | null>(null)
  const [refactorProposal, setRefactorProposal] = useState<RefactorProposal | null>(null)
  const [safetyData, setSafetyData] = useState<SafetyScoreData | null>(null)
  const [summaryData, setSummaryData] = useState<RepositorySummaryData | null>(null)
  const [pipelineStatus, setPipelineStatus] = useState<RepositoryStatusData | null>(null)
  const [loading, setLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [sourceMode, setSourceMode] = useState<'zip' | 'github'>('zip')
  const [githubUrl, setGithubUrl] = useState('')
  const [selectedEntityForRefactor, setSelectedEntityForRefactor] = useState<string | undefined>()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const pollingRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const activeRepositoryRef = useRef<string | null>(null)

  const stopLivePolling = useCallback(() => {
    if (pollingRef.current) {
      clearTimeout(pollingRef.current)
      pollingRef.current = null
    }
  }, [])

  const loadRepositoryData = useCallback(async (id: string) => {
    try {
      const [testEnv, sumEnv, statusEnv] = await Promise.all([
        fetchLatestTestRun(id).catch(() => null),
        fetchRepositorySummary(id).catch(() => null),
        fetchRepositoryStatus(id).catch(() => null),
      ])
      if (activeRepositoryRef.current !== id) return
      if (testEnv?.data) setTestRunData(testEnv.data)
      if (sumEnv?.data) setSummaryData(sumEnv.data)
      if (statusEnv?.data) setPipelineStatus(statusEnv.data)
    } catch {
      // Handled silently
    }
  }, [])

  const startLivePolling = useCallback((id: string) => {
    stopLivePolling()
    activeRepositoryRef.current = id
    const startedAt = Date.now()

    const poll = async () => {
      if (activeRepositoryRef.current !== id) return
      if (Date.now() - startedAt >= MAX_POLL_DURATION_MS) {
        pollingRef.current = null
        setErrorMessage('Analysis is taking longer than expected. You can continue working; refresh status to check progress.')
        return
      }

      try {
        const statusEnv = await fetchRepositoryStatus(id)
        if (activeRepositoryRef.current !== id) return
        if (statusEnv?.data) {
          setPipelineStatus(statusEnv.data)
          const isDone =
            statusEnv.data.analysisStatus === 'completed' ||
            statusEnv.data.analysisStatus === 'failed' ||
            statusEnv.data.currentStage === 'completed'
          if (isDone) {
            pollingRef.current = null
            await loadRepositoryData(id)
            if (activeRepositoryRef.current !== id) return
            const repoList = await fetchRepositories()
            if (activeRepositoryRef.current === id) {
              setRepositories(repoList.data ?? [])
            }
            return
          }
        }
      } catch {
        // Retry next tick while the selected repository remains active.
      }

      if (activeRepositoryRef.current === id) {
        pollingRef.current = setTimeout(poll, POLL_INTERVAL_MS)
      }
    }

    void poll()
  }, [loadRepositoryData, stopLivePolling])

  useEffect(() => {
    fetchRepositories()
      .then((envelope) => {
        const repos = envelope.data ?? []
        setRepositories(repos)
        if (repos.length > 0 && !activeRepositoryRef.current) {
          activeRepositoryRef.current = repos[0].id
          setRepositoryId(repos[0].id)
        }
      })
      .catch((err) => console.error('Failed to load repositories:', err))

    return () => {
      stopLivePolling()
      activeRepositoryRef.current = null
    }
  }, [stopLivePolling])

  useEffect(() => {
    if (!repositoryId) return
    activeRepositoryRef.current = repositoryId
    void loadRepositoryData(repositoryId)
  }, [repositoryId, loadRepositoryData])

  const selectRepository = (id: string) => {
    stopLivePolling()
    activeRepositoryRef.current = id || null
    setRepositoryId(id || null)
    setTestRunData(null)
    setSummaryData(null)
    setPipelineStatus(null)
    setRefactorProposal(null)
    setSafetyData(null)
    setSelectedEntityForRefactor(undefined)
    setErrorMessage(null)
    setSuccessMessage(null)
  }

  const handleUpload = async (file: File | null) => {
    if (!file) return
    setLoading(true)
    setErrorMessage(null)
    setSuccessMessage(null)
    try {
      const repo = await uploadRepository(file)
      if (repo?.id) {
        activeRepositoryRef.current = repo.id
        setRepositoryId(repo.id)
        setRepositories((prev) => [repo, ...prev.filter((r) => r.id !== repo.id)])
        setSuccessMessage(`Repository '${repo.name}' uploaded!`)
        await triggerAnalysis(repo.id)
        setSuccessMessage(`Repository '${repo.name}' uploaded. Live analysis started.`)
        startLivePolling(repo.id)
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setErrorMessage(`Upload failed: ${msg}`)
    } finally {
      setLoading(false)
    }
  }

  const handleImport = async () => {
    const url = githubUrl.trim()
    if (!url) {
      setErrorMessage('Enter a GitHub repository URL (e.g. https://github.com/owner/repo).')
      return
    }
    setLoading(true)
    setErrorMessage(null)
    setSuccessMessage(null)
    try {
      const repo = await importRepository(url)
      if (repo?.id) {
        activeRepositoryRef.current = repo.id
        setRepositoryId(repo.id)
        setRepositories((prev) => [repo, ...prev.filter((r) => r.id !== repo.id)])
        setGithubUrl('')
        await triggerAnalysis(repo.id)
        setSuccessMessage(`Repository '${repo.name}' imported from GitHub. Live analysis started.`)
        startLivePolling(repo.id)
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setErrorMessage(`GitHub import failed: ${msg}`)
    } finally {
      setLoading(false)
    }
  }

  const handleTriggerAnalysis = async () => {
    const id = repositoryId
    if (!id) return
    setLoading(true)
    setErrorMessage(null)
    try {
      await triggerAnalysis(id)
      setSuccessMessage('Analysis pipeline queued!')
      startLivePolling(id)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      setErrorMessage(`Failed to trigger analysis: ${msg}`)
    } finally {
      setLoading(false)
    }
  }

  const handleGenerateUncovered = async () => {
    const id = repositoryId
    if (!id) {
      setErrorMessage('Select or upload a repository before generating tests.')
      return
    }

    setLoading(true)
    setErrorMessage(null)
    try {
      const envelope = await triggerGenerateUncovered(id, 3, 60.0)
      if (activeRepositoryRef.current !== id) return
      if (envelope.data) {
        setTestRunData(envelope.data)
        setSuccessMessage('Coverage repair cycle completed!')
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      if (activeRepositoryRef.current === id) setErrorMessage(`Coverage repair failed: ${msg}`)
    } finally {
      if (activeRepositoryRef.current === id) setLoading(false)
    }
  }

  const handleProposeRefactor = async (entityId: string) => {
    const id = repositoryId
    if (!id) return
    setLoading(true)
    setErrorMessage(null)
    setRefactorProposal(null)
    setSafetyData(null)
    try {
      const envelope = await proposeRefactor(id, entityId)
      if (activeRepositoryRef.current !== id) return
      if (envelope.data) {
        setRefactorProposal(envelope.data)
        try {
          const safetyEnv = await fetchSafetyScore(id, envelope.data.proposalId)
          if (activeRepositoryRef.current === id && safetyEnv.data) {
            setSafetyData(safetyEnv.data)
          }
        } catch {
          // Safety score retrieval error
        }
      } else if (envelope.error) {
        setErrorMessage(`Refactor proposal failed: ${envelope.error.message}`)
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err)
      if (activeRepositoryRef.current === id) setErrorMessage(`Refactor proposal failed: ${msg}`)
    } finally {
      if (activeRepositoryRef.current === id) setLoading(false)
    }
  }

  const navigateToRefactor = (entityId: string) => {
    setSelectedEntityForRefactor(entityId)
    setActiveTab('refactor')
    void handleProposeRefactor(entityId)
  }

  const navigateToExplanation = () => {
    setActiveTab('explanations')
  }

  return (
    <div style={styles.appContainer}>
      <header style={styles.header}>
        <div style={styles.headerLeft}>
          <div style={styles.brandRow}>
            <span style={styles.brandLogo}>⚡</span>
            <span style={styles.logoText}>CodeOracle</span>
          </div>
          <div style={styles.repoPickerContainer}>
            <select
              value={repositoryId ?? ''}
              onChange={(e) => selectRepository(e.target.value)}
              style={styles.repoSelect}
              aria-label="Select active repository"
            >
              <option value="">Select repository…</option>
              {repositories.map((repo) => (
                <option key={repo.id} value={repo.id}>
                  {repo.name} ({repo.status} · {repo.sourceType === 'github' ? 'GitHub' : 'ZIP'})
                </option>
              ))}
            </select>
          </div>
        </div>

        <div style={styles.headerRight}>
          <div style={styles.sourceToggle} role="tablist" aria-label="Ingestion method">
            <button
              onClick={() => setSourceMode('zip')}
              style={{
                ...styles.toggleButton,
                backgroundColor: sourceMode === 'zip' ? '#0284c7' : 'transparent',
                color: sourceMode === 'zip' ? '#ffffff' : '#94a3b8',
              }}
              data-testid="source-zip"
            >
              ZIP Upload
            </button>
            <button
              onClick={() => setSourceMode('github')}
              style={{
                ...styles.toggleButton,
                backgroundColor: sourceMode === 'github' ? '#0284c7' : 'transparent',
                color: sourceMode === 'github' ? '#ffffff' : '#94a3b8',
              }}
              data-testid="source-github"
            >
              GitHub Import
            </button>
          </div>

          {sourceMode === 'github' ? (
            <div style={styles.githubForm}>
              <input
                type="url"
                placeholder="https://github.com/owner/repo"
                value={githubUrl}
                onChange={(e) => setGithubUrl(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    void handleImport()
                  }
                }}
                style={styles.urlInput}
                aria-label="GitHub repository URL"
                data-testid="github-url-input"
              />
              <button
                onClick={() => void handleImport()}
                disabled={loading || !githubUrl.trim()}
                style={styles.uploadButton}
                data-testid="import-btn"
              >
                {loading ? 'Importing…' : 'Import Repo'}
              </button>
            </div>
          ) : (
            <>
              <input
                ref={fileInputRef}
                type="file"
                accept=".zip"
                style={{ display: 'none' }}
                onChange={(e) => void handleUpload(e.target.files?.[0] ?? null)}
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
            </>
          )}

          {repositoryId && (
            <button
              onClick={() => void handleTriggerAnalysis()}
              disabled={loading || pipelineStatus?.analysisStatus === 'running'}
              style={styles.reanalyzeBtn}
              title="Re-run AST facts, Graph & Semantic Index pipeline"
            >
              {pipelineStatus?.analysisStatus === 'running' ? 'Analyzing…' : '🔄 Re-Analyze'}
            </button>
          )}
        </div>
      </header>

      <nav style={styles.navBar} aria-label="Main Navigation">
        <div style={styles.navTabsContainer}>
          {TABS.map((tab) => {
            const isActive = activeTab === tab.key
            return (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                style={{
                  ...styles.navButton,
                  color: isActive ? '#38bdf8' : '#94a3b8',
                  borderBottom: isActive ? '3px solid #38bdf8' : '3px solid transparent',
                  backgroundColor: isActive ? 'rgba(56, 189, 248, 0.08)' : 'transparent',
                }}
                aria-current={isActive ? 'page' : undefined}
                data-testid={`tab-${tab.key}`}
              >
                <span style={styles.navIcon}>{tab.icon}</span>
                <span>{tab.label}</span>
              </button>
            )
          })}
        </div>
      </nav>

      {errorMessage && (
        <div style={styles.errorBanner} role="alert">
          <span style={styles.alertIcon}>✕</span>
          <span style={{ flex: 1 }}>{errorMessage}</span>
          <button onClick={() => setErrorMessage(null)} style={styles.closeBtn} aria-label="Dismiss error">×</button>
        </div>
      )}

      {successMessage && (
        <div style={styles.successBanner} role="status">
          <span style={styles.alertIcon}>✓</span>
          <span style={{ flex: 1 }}>{successMessage}</span>
          <button onClick={() => setSuccessMessage(null)} style={styles.closeBtn} aria-label="Dismiss message">×</button>
        </div>
      )}

      <main style={styles.mainContent}>
        {pipelineStatus && pipelineStatus.analysisStatus === 'running' && (
          <div style={styles.pipelineLiveContainer}>
            <PipelineStatusCard
              pipelineState={pipelineStatus.pipelineState}
              currentStage={pipelineStatus.currentStage}
              analysisStatus={pipelineStatus.analysisStatus}
            />
          </div>
        )}

        {activeTab === 'overview' && (
          <div style={styles.tabContentContainer}>
            {pipelineStatus && pipelineStatus.analysisStatus !== 'running' && (
              <PipelineStatusCard
                pipelineState={pipelineStatus.pipelineState}
                currentStage={pipelineStatus.currentStage}
                analysisStatus={pipelineStatus.analysisStatus}
              />
            )}
            <DashboardTab
              repositoryId={repositoryId || undefined}
              repositoryName={repositories.find((r) => r.id === repositoryId)?.name}
              summaryData={summaryData}
              loading={loading}
              onDownloadReport={
                repositoryId
                  ? () => downloadExecutiveReport(repositoryId, repositories.find((r) => r.id === repositoryId)?.name)
                  : undefined
              }
            />
          </div>
        )}

        {activeTab === 'explanations' && (
          <div style={styles.tabContentContainer}>
            <ExplanationTab
              repositoryId={repositoryId || undefined}
              loading={loading}
              onSelectForRefactor={navigateToRefactor}
            />
          </div>
        )}

        {activeTab === 'graph' && (
          <div style={styles.tabContentContainer}>
            <DependencyGraphTab
              repositoryId={repositoryId || undefined}
              loading={loading}
              onSelectForExplanation={navigateToExplanation}
              onSelectForRefactor={navigateToRefactor}
            />
          </div>
        )}

        {activeTab === 'tests' && (
          <div style={styles.tabContentContainer}>
            <TestsTab
              repositoryId={repositoryId || undefined}
              testRunData={testRunData}
              loading={loading}
              onGenerateUncovered={repositoryId ? () => void handleGenerateUncovered() : undefined}
            />
          </div>
        )}

        {activeTab === 'refactor' && (
          <div style={styles.tabContentContainer}>
            <RefactorTab
              repositoryId={repositoryId || undefined}
              proposal={refactorProposal}
              safetyData={safetyData}
              loading={loading}
              initialEntityId={selectedEntityForRefactor}
              onPropose={repositoryId ? handleProposeRefactor : undefined}
            />
          </div>
        )}

        {activeTab === 'docs' && (
          <div style={styles.tabContentContainer}>
            <SystemDocsTab onNavigateTab={(tab) => setActiveTab(tab)} />
          </div>
        )}
      </main>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  appContainer: {
    backgroundColor: '#090d16',
    minHeight: '100vh',
    color: '#f8fafc',
    fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '12px 24px',
    backgroundColor: '#0f172a',
    borderBottom: '1px solid #1e293b',
    gap: '20px',
    flexWrap: 'wrap',
  },
  headerLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: '16px',
    flexWrap: 'wrap',
  },
  brandRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  brandLogo: {
    fontSize: '20px',
  },
  logoText: {
    fontSize: '20px',
    fontWeight: '800',
    background: 'linear-gradient(135deg, #38bdf8 0%, #818cf8 100%)',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
    letterSpacing: '-0.02em',
  },
  versionBadge: {
    fontSize: '10px',
    fontWeight: '700',
    backgroundColor: '#1e293b',
    color: '#38bdf8',
    border: '1px solid #334155',
    padding: '2px 8px',
    borderRadius: '12px',
    textTransform: 'uppercase',
  },
  repoPickerContainer: {
    display: 'flex',
    alignItems: 'center',
  },
  repoSelect: {
    backgroundColor: '#1e293b',
    border: '1px solid #334155',
    color: '#f8fafc',
    padding: '8px 12px',
    borderRadius: '8px',
    fontSize: '13px',
    outline: 'none',
    fontWeight: '500',
    minWidth: '220px',
  },
  headerRight: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    flexWrap: 'wrap',
  },
  sourceToggle: {
    display: 'flex',
    backgroundColor: '#1e293b',
    borderRadius: '8px',
    padding: '2px',
    border: '1px solid #334155',
  },
  toggleButton: {
    border: 'none',
    borderRadius: '6px',
    padding: '6px 12px',
    fontSize: '12px',
    fontWeight: '600',
    cursor: 'pointer',
    transition: 'all 0.15s ease',
  },
  githubForm: {
    display: 'flex',
    gap: '8px',
    alignItems: 'center',
  },
  urlInput: {
    backgroundColor: '#1e293b',
    border: '1px solid #334155',
    borderRadius: '8px',
    padding: '8px 12px',
    color: '#f8fafc',
    fontSize: '13px',
    outline: 'none',
    width: '240px',
  },
  uploadButton: {
    backgroundColor: '#0284c7',
    color: '#ffffff',
    border: 'none',
    borderRadius: '8px',
    padding: '8px 16px',
    fontSize: '13px',
    fontWeight: '700',
    cursor: 'pointer',
    boxShadow: '0 2px 8px rgba(2, 132, 199, 0.35)',
    transition: 'all 0.15s ease',
  },
  reanalyzeBtn: {
    backgroundColor: '#1e293b',
    color: '#cbd5e1',
    border: '1px solid #334155',
    borderRadius: '8px',
    padding: '8px 14px',
    fontSize: '12px',
    fontWeight: '600',
    cursor: 'pointer',
  },
  navBar: {
    backgroundColor: '#0f172a',
    borderBottom: '1px solid #1e293b',
    padding: '0 24px',
  },
  navTabsContainer: {
    display: 'flex',
    gap: '4px',
    overflowX: 'auto',
  },
  navButton: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '12px 18px',
    fontSize: '13px',
    fontWeight: '600',
    border: 'none',
    cursor: 'pointer',
    transition: 'all 0.15s ease',
    borderRadius: '6px 6px 0 0',
  },
  navIcon: {
    fontSize: '15px',
  },
  errorBanner: {
    margin: '16px 24px 0',
    backgroundColor: '#7f1d1d',
    border: '1px solid #b91c1c',
    borderRadius: '8px',
    padding: '12px 16px',
    color: '#fecaca',
    display: 'flex',
    gap: '12px',
    alignItems: 'center',
    fontSize: '13px',
  },
  successBanner: {
    margin: '16px 24px 0',
    backgroundColor: '#064e3b',
    border: '1px solid #059669',
    borderRadius: '8px',
    padding: '12px 16px',
    color: '#a7f3d0',
    display: 'flex',
    gap: '12px',
    alignItems: 'center',
    fontSize: '13px',
  },
  alertIcon: {
    fontWeight: 'bold',
    fontSize: '16px',
  },
  closeBtn: {
    background: 'none',
    border: 'none',
    color: 'inherit',
    fontSize: '18px',
    cursor: 'pointer',
  },
  mainContent: {
    padding: '24px',
    maxWidth: '1600px',
    margin: '0 auto',
  },
  pipelineLiveContainer: {
    marginBottom: '20px',
  },
  tabContentContainer: {
    display: 'flex',
    flexDirection: 'column',
    gap: '20px',
  },
}

export default App
