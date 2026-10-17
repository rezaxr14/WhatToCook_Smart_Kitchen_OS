import React from 'react';

export type BadgeVariant = 'orange' | 'teal' | 'amber' | 'emerald' | 'rose' | 'neutral' | 'gemini';

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  size?: 'sm' | 'md';
  icon?: React.ReactNode;
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'orange',
  size = 'md',
  icon,
  className = '',
}) => {
  const getStyles = () => {
    switch (variant) {
      case 'teal':
        return 'bg-teal-50 text-teal-700 border-teal-200';
      case 'amber':
        return 'bg-amber-50 text-amber-800 border-amber-200';
      case 'emerald':
        return 'bg-emerald-50 text-emerald-700 border-emerald-200';
      case 'rose':
        return 'bg-rose-50 text-rose-700 border-rose-200';
      case 'gemini':
        return 'bg-linear-to-r/srgb from-blue-500/10 via-indigo-500/10 to-purple-500/10 text-indigo-700 border-indigo-200 font-medium';
      case 'neutral':
        return 'bg-stone-100 text-stone-700 border-stone-200';
      case 'orange':
      default:
        return 'bg-orange-50 text-orange-700 border-orange-200';
    }
  };

  const sizeStyles = size === 'sm' ? 'text-xs px-2.5 py-0.5' : 'text-sm px-3 py-1';

  return (
    <span
      className={`inline-flex items-center gap-1.5 font-medium rounded-full border shadow-xs ${getStyles()} ${sizeStyles} ${className}`}
    >
      {icon && <span className="shrink-0">{icon}</span>}
      {children}
    </span>
  );
};
