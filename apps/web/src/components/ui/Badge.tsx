import type { ReactNode } from 'react';

type BadgeVariant = 'success' | 'danger' | 'warning' | 'neutral' | 'primary';

export const Badge = ({ children, variant = 'neutral', className = '' }: { children: ReactNode; variant?: BadgeVariant; className?: string }) => {
  const variants = {
    success: 'bg-green-100 text-green-800',
    danger: 'bg-red-100 text-red-800',
    warning: 'bg-yellow-100 text-yellow-800',
    neutral: 'bg-gray-100 text-gray-800',
    primary: 'bg-blue-100 text-blue-800',
  };

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${variants[variant]} ${className}`}>
      {children}
    </span>
  );
};
