import type { HTMLAttributes, KeyboardEvent, ReactNode } from 'react';

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
}

export const Card = ({ children, className = '', onClick, ...props }: CardProps) => {
  // Clickable cards behave like buttons for keyboard and screen-reader users
  const interactive = onClick
    ? {
        role: 'button',
        tabIndex: 0,
        onKeyDown: (e: KeyboardEvent<HTMLDivElement>) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            e.currentTarget.click();
          }
        },
      }
    : {};
  return (
    <div
      className={`bg-white rounded-xl shadow-sm border border-gray-100 p-6 ${
        onClick ? 'cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-500' : ''
      } ${className}`}
      onClick={onClick}
      {...interactive}
      {...props}
    >
      {children}
    </div>
  );
};

export const CardHeader = ({
  children,
  className = '',
}: {
  children: ReactNode;
  className?: string;
}) => <div className={`mb-4 ${className}`}>{children}</div>;

export const CardTitle = ({
  children,
  className = '',
}: {
  children: ReactNode;
  className?: string;
}) => <h3 className={`text-lg font-semibold text-gray-900 ${className}`}>{children}</h3>;

export const CardContent = ({
  children,
  className = '',
}: {
  children: ReactNode;
  className?: string;
}) => <div className={className}>{children}</div>;
