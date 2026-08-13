import React from 'react'

export interface PipelineStageInfo {
  status: 'completed' | 'running' | 'pending' | 'failed'
  progress: number
  filesProcessed?: number
  totalFiles?: number
  entityCount?: number
  durationSeconds?: number
}

export interface RepositoryStatusData {
  repositoryStatus?: string
  analysisStatus?: string | null
  currentStage?: string | null
  pipelineState?: Record<string, PipelineStageInfo>
}

export interface PipelineStatusCardProps {
  pipelineState?: Record<string, PipelineStageInfo> | null
  currentStage?: string | null
  analysisStatus?: string | null
}

const STAGES = [
  { id: 'stage_1_scan', name: 'Scan Repository', desc: 'Discovering files & measuring LOC' },
  { id: 'stage_2_parse', name: 'AST & Tree-Sitter Parsing', desc: 'Extracting entities, signatures & facts' },
  { id: 'stage_3_graph', name: 'Dependency Graph', desc: 'Building call & inheritance edges' },
  { id: 'stage_4_index', name: 'Semantic Indexing', desc: 'Generating chunk embeddings & HNSW index' },
  { id: 'stage_5_summary', name: 'Architecture & Risk Analysis', desc: 'Classifying layers & detecting high risk' },
]

export const PipelineStatusCard: React.FC<PipelineStatusCardProps> = ({
  pipelineState = {},
  currentStage = null,
  analysisStatus = null,
}) => {
  return (
    <div style={styles.card} data-testid="pipeline-status-card">
      <div style={styles.header}>
        <div>
          <h4 style={styles.title}>Live Analysis Pipeline</h4>
          <p style={styles.subtitle}>
            Real-time multi-stage analysis pipeline monitoring file parsing, dependency graphs, and vector indexing.
          </p>
        </div>
        {analysisStatus && (
          <span
            style={{
              ...styles.statusBadge,
              backgroundColor:
                analysisStatus === 'completed'
                  ? '#059669'
                  : analysisStatus === 'running'
                  ? '#0284c7'
                  : '#475569',
            }}
            data-testid="analysis-status-badge"
          >
            {analysisStatus.toUpperCase()}
          </span>
        )}
      </div>

      <div style={styles.stageList}>
        {STAGES.map((st, idx) => {
          const info = pipelineState?.[st.id]
          const isCurrent = currentStage === st.id
          const isDone = info?.status === 'completed' || (!info && analysisStatus === 'completed')
          const isRunning = info?.status === 'running' || (isCurrent && analysisStatus === 'running')
          const isFailed = info?.status === 'failed'

          const icon = isDone ? '✓' : isRunning ? '⟳' : isFailed ? '✕' : '○'
          const iconColor = isDone ? '#10b981' : isRunning ? '#38bdf8' : isFailed ? '#ef4444' : '#64748b'

          return (
            <div key={st.id} style={styles.stageItem} data-testid={`stage-${idx + 1}`}>
              <div style={{ ...styles.iconCircle, color: iconColor, borderColor: iconColor }}>
                {icon}
              </div>
              <div style={styles.stageContent}>
                <div style={styles.stageNameRow}>
                  <span style={styles.stageName}>{st.name}</span>
                  {info?.durationSeconds !== undefined && (
                    <span style={styles.duration}>{info.durationSeconds.toFixed(1)}s</span>
                  )}
                </div>
                <p style={styles.stageDesc}>{st.desc}</p>
                {info && (info.filesProcessed !== undefined || info.totalFiles !== undefined) && (
                  <div style={styles.metrics}>
                    <span>Files: {info.filesProcessed ?? 0} / {info.totalFiles ?? 0}</span>
                    {info.entityCount !== undefined && <span> • Entities: {info.entityCount}</span>}
                  </div>
                )}
              </div>
            </div>
          )
        })}
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
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '20px',
  },
  title: { margin: '0 0 4px 0', fontSize: '18px', fontWeight: '700' },
  subtitle: { margin: 0, fontSize: '13px', color: '#94a3b8' },
  statusBadge: {
    fontSize: '11px',
    fontWeight: '700',
    color: '#ffffff',
    padding: '4px 12px',
    borderRadius: '12px',
    letterSpacing: '0.05em',
  },
  stageList: { display: 'flex', flexDirection: 'column', gap: '16px' },
  stageItem: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: '14px',
    backgroundColor: '#0f172a',
    border: '1px solid #334155',
    borderRadius: '8px',
    padding: '14px 18px',
  },
  iconCircle: {
    width: '28px',
    height: '28px',
    borderRadius: '50%',
    border: '2px solid',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '14px',
    fontWeight: '700',
    flexShrink: 0,
  },
  stageContent: { flex: 1 },
  stageNameRow: { display: 'flex', justifyContent: 'space-between', marginBottom: '2px' },
  stageName: { fontSize: '14px', fontWeight: '700', color: '#f8fafc' },
  duration: { fontSize: '12px', color: '#64748b' },
  stageDesc: { margin: 0, fontSize: '12px', color: '#94a3b8' },
  metrics: { marginTop: '4px', fontSize: '11px', color: '#38bdf8' },
}
