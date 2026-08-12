import React, { useMemo } from 'react'

interface DiffLine {
  type: 'removed' | 'added' | 'unchanged'
  content: string
  lineNum: number
}

function computeDiff(original: string, proposed: string): DiffLine[] {
  const origLines = original.split('\n')
  const propLines = proposed.split('\n')

  // Simple LCS-based diff visualization
  const result: DiffLine[] = []
  const origSet = new Set(origLines)
  const propSet = new Set(propLines)

  let origIdx = 0
  let propIdx = 0

  while (origIdx < origLines.length || propIdx < propLines.length) {
    const origLine = origLines[origIdx]
    const propLine = propLines[propIdx]

    if (origIdx >= origLines.length) {
      result.push({ type: 'added', content: propLine, lineNum: propIdx + 1 })
      propIdx++
    } else if (propIdx >= propLines.length) {
      result.push({ type: 'removed', content: origLine, lineNum: origIdx + 1 })
      origIdx++
    } else if (origLine === propLine) {
      result.push({ type: 'unchanged', content: origLine, lineNum: origIdx + 1 })
      origIdx++
      propIdx++
    } else if (!propSet.has(origLine)) {
      result.push({ type: 'removed', content: origLine, lineNum: origIdx + 1 })
      origIdx++
    } else if (!origSet.has(propLine)) {
      result.push({ type: 'added', content: propLine, lineNum: propIdx + 1 })
      propIdx++
    } else {
      // Both exist somewhere — treat as changed block
      result.push({ type: 'removed', content: origLine, lineNum: origIdx + 1 })
      result.push({ type: 'added', content: propLine, lineNum: propIdx + 1 })
      origIdx++
      propIdx++
    }
  }

  return result
}

interface DiffViewerProps {
  original: string
  proposed: string
  entityName: string
}

export const DiffViewer: React.FC<DiffViewerProps> = ({ original, proposed, entityName }) => {
  const diffLines = useMemo(() => computeDiff(original, proposed), [original, proposed])

  const hasChanges = diffLines.some((l) => l.type !== 'unchanged')
  const removedCount = diffLines.filter((l) => l.type === 'removed').length
  const addedCount = diffLines.filter((l) => l.type === 'added').length

  return (
    <div style={styles.wrapper} data-testid="diff-viewer">
      {/* Diff Header */}
      <div style={styles.header}>
        <span style={styles.filename}>{entityName}</span>
        <div style={styles.diffStats}>
          <span style={styles.removedStat}>−{removedCount}</span>
          <span style={styles.addedStat}>+{addedCount}</span>
        </div>
      </div>

      {!hasChanges && (
        <div style={styles.noChanges}>No changes proposed — original code is unchanged.</div>
      )}

      {/* Diff Lines */}
      <div style={styles.diffBody}>
        {diffLines.map((line, idx) => (
          <div
            key={idx}
            style={{
              ...styles.diffLine,
              backgroundColor:
                line.type === 'removed'
                  ? 'rgba(239,68,68,0.15)'
                  : line.type === 'added'
                    ? 'rgba(34,197,94,0.15)'
                    : 'transparent',
              borderLeft: `3px solid ${
                line.type === 'removed'
                  ? '#ef4444'
                  : line.type === 'added'
                    ? '#22c55e'
                    : 'transparent'
              }`,
            }}
          >
            <span style={styles.lineGutter}>
              {line.type === 'removed' ? '−' : line.type === 'added' ? '+' : ' '}
            </span>
            <span
              style={{
                ...styles.lineContent,
                color:
                  line.type === 'removed'
                    ? '#fca5a5'
                    : line.type === 'added'
                      ? '#86efac'
                      : '#e2e8f0',
              }}
            >
              {line.content || ' '}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

const styles: Record<string, React.CSSProperties> = {
  wrapper: {
    backgroundColor: '#0f172a',
    border: '1px solid #334155',
    borderRadius: '8px',
    overflow: 'hidden',
    fontFamily: 'JetBrains Mono, Fira Code, Consolas, monospace',
    fontSize: '13px',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '10px 16px',
    backgroundColor: '#1e293b',
    borderBottom: '1px solid #334155',
  },
  filename: {
    color: '#94a3b8',
    fontWeight: '600',
    fontSize: '12px',
  },
  diffStats: {
    display: 'flex',
    gap: '10px',
  },
  removedStat: {
    color: '#f87171',
    fontWeight: '700',
  },
  addedStat: {
    color: '#4ade80',
    fontWeight: '700',
  },
  noChanges: {
    padding: '16px',
    color: '#94a3b8',
    fontSize: '13px',
    textAlign: 'center',
  },
  diffBody: {
    maxHeight: '420px',
    overflowY: 'auto',
  },
  diffLine: {
    display: 'flex',
    alignItems: 'flex-start',
    padding: '2px 0',
  },
  lineGutter: {
    width: '28px',
    textAlign: 'center',
    color: '#64748b',
    flexShrink: 0,
    userSelect: 'none',
    paddingTop: '1px',
  },
  lineContent: {
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-all',
    flex: 1,
    paddingRight: '12px',
  },
}
