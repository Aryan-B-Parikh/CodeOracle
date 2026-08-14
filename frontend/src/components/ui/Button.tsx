import React from 'react'

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost' | 'success'
  size?: 'sm' | 'md' | 'lg'
  icon?: React.ReactNode
  loading?: boolean
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'primary',
  size = 'md',
  icon,
  loading = false,
  disabled,
  style,
  ...props
}) => {
  const baseStyle: React.CSSProperties = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '8px',
    borderRadius: '8px',
    fontWeight: 600,
    cursor: disabled || loading ? 'not-allowed' : 'pointer',
    opacity: disabled || loading ? 0.6 : 1,
    transition: 'all 0.15s ease',
    border: '1px solid transparent',
    fontSize: size === 'sm' ? '12px' : size === 'lg' ? '16px' : '14px',
    padding:
      size === 'sm'
        ? '6px 12px'
        : size === 'lg'
        ? '12px 24px'
        : '8px 16px',
    ...style,
  }

  let variantStyle: React.CSSProperties = {}
  switch (variant) {
    case 'primary':
      variantStyle = {
        background: 'linear-gradient(135deg, #0284c7, #0369a1)',
        color: '#ffffff',
        boxShadow: '0 2px 4px rgba(2, 132, 199, 0.25)',
      }
      break
    case 'secondary':
      variantStyle = {
        background: 'var(--bg-card, #1e293b)',
        color: 'var(--text-primary, #f8fafc)',
        border: '1px solid var(--border-default, #334155)',
      }
      break
    case 'danger':
      variantStyle = {
        background: 'linear-gradient(135deg, #e11d48, #be123c)',
        color: '#ffffff',
      }
      break
    case 'success':
      variantStyle = {
        background: 'linear-gradient(135deg, #10b981, #059669)',
        color: '#ffffff',
      }
      break
    case 'ghost':
      variantStyle = {
        background: 'transparent',
        color: 'var(--text-muted, #94a3b8)',
      }
      break
  }

  return (
    <button
      style={{ ...baseStyle, ...variantStyle }}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? (
        <span
          style={{
            display: 'inline-block',
            width: '14px',
            height: '14px',
            border: '2px solid rgba(255,255,255,0.3)',
            borderTopColor: '#ffffff',
            borderRadius: '50%',
            animation: 'spin 0.8s linear infinite',
          }}
        />
      ) : (
        icon
      )}
      {children}
    </button>
  )
}
