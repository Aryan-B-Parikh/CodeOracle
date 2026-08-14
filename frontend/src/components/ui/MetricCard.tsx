import React from 'react'
import { Card } from './Card'

export interface MetricCardProps {
  label: string
  value: string | number
  subValue?: string
  icon?: React.ReactNode
  variant?: 'sky' | 'emerald' | 'amber' | 'indigo' | 'rose'
  trend?: 'up' | 'down' | 'neutral'
}

export const MetricCard: React.FC<MetricCardProps> = ({
  label,
  value,
  subValue,
  icon,
  variant = 'sky',
}) => {
  const accentColorMap = {
    sky: '#38bdf8',
    emerald: '#10b981',
    amber: '#f59e0b',
    indigo: '#6366f1',
    rose: '#f43f5e',
  }

  const accent = accentColorMap[variant]

  return (
    <Card padding="md" style={{ position: 'relative', overflow: 'hidden' }}>
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          height: '3px',
          backgroundColor: accent,
        }}
      />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
        <span style={{ fontSize: '13px', color: 'var(--text-muted, #94a3b8)', fontWeight: 500 }}>
          {label}
        </span>
        {icon && <span style={{ color: accent, fontSize: '16px' }}>{icon}</span>}
      </div>
      <div style={{ fontSize: '28px', fontWeight: 800, color: 'var(--text-primary, #f8fafc)', letterSpacing: '-0.5px' }}>
        {value}
      </div>
      {subValue && (
        <div style={{ fontSize: '12px', color: 'var(--text-subtle, #64748b)', marginTop: '4px' }}>
          {subValue}
        </div>
      )}
    </Card>
  )
}
