import React from 'react'

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'surface' | 'glass' | 'interactive'
  padding?: 'sm' | 'md' | 'lg' | 'none'
  selected?: boolean
}

export const Card: React.FC<CardProps> = ({
  children,
  variant = 'default',
  padding = 'md',
  selected = false,
  style,
  ...props
}) => {
  const padMap = {
    none: '0',
    sm: '12px',
    md: '20px',
    lg: '28px',
  }

  const baseStyle: React.CSSProperties = {
    borderRadius: '12px',
    border: selected
      ? '1px solid var(--accent-sky, #38bdf8)'
      : '1px solid var(--border-subtle, #1e293b)',
    padding: padMap[padding],
    transition: 'all 0.2s ease',
    ...style,
  }

  let variantStyle: React.CSSProperties = {}
  switch (variant) {
    case 'default':
      variantStyle = {
        backgroundColor: 'var(--bg-card, #1e293b)',
      }
      break
    case 'surface':
      variantStyle = {
        backgroundColor: 'var(--bg-surface, #0f172a)',
      }
      break
    case 'glass':
      variantStyle = {
        backgroundColor: 'rgba(15, 23, 42, 0.75)',
        backdropFilter: 'blur(12px)',
      }
      break
    case 'interactive':
      variantStyle = {
        backgroundColor: 'var(--bg-card, #1e293b)',
        cursor: 'pointer',
      }
      break
  }

  return (
    <div style={{ ...baseStyle, ...variantStyle }} {...props}>
      {children}
    </div>
  )
}
