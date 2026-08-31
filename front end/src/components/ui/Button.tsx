import React, { ButtonHTMLAttributes, forwardRef } from 'react';
import { Loader2 } from 'lucide-react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger' | 'success';
  size?: 'sm' | 'md' | 'lg' | 'icon';
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant = 'primary',
      size = 'md',
      isLoading = false,
      leftIcon,
      rightIcon,
      disabled,
      children,
      ...props
    },
    ref
  ) => {
    const baseStyles =
      'inline-flex items-center justify-center font-medium transition-all duration-150 rounded-lg focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500 focus-visible:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed disabled:pointer-events-none select-none cursor-pointer';

    const variants = {
      primary:
        'bg-cyan-600 hover:bg-cyan-500 active:bg-cyan-700 text-white shadow-sm shadow-cyan-900/20 dark:bg-cyan-500 dark:hover:bg-cyan-400 dark:text-slate-950 font-semibold',
      secondary:
        'bg-slate-800 hover:bg-slate-700 active:bg-slate-900 text-slate-100 border border-slate-700/80 dark:bg-slate-800 dark:hover:bg-slate-700 dark:text-slate-200',
      outline:
        'bg-transparent border border-slate-700 hover:bg-slate-850 active:bg-slate-800 text-slate-300 hover:text-white dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800/80',
      ghost:
        'bg-transparent hover:bg-slate-800/60 active:bg-slate-800 text-slate-400 hover:text-slate-200 dark:text-slate-400 dark:hover:text-slate-200',
      danger:
        'bg-rose-600 hover:bg-rose-500 active:bg-rose-700 text-white shadow-sm shadow-rose-900/20 dark:bg-rose-600 dark:hover:bg-rose-500',
      success:
        'bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 text-white shadow-sm shadow-emerald-900/20 dark:bg-emerald-600 dark:hover:bg-emerald-500',
    };

    const sizes = {
      sm: 'text-xs px-2.5 py-1.5 gap-1.5 rounded-md',
      md: 'text-sm px-3.5 py-2 gap-2',
      lg: 'text-base px-5 py-2.5 gap-2.5 font-semibold',
      icon: 'p-2 rounded-lg text-slate-400 hover:text-slate-200',
    };

    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={twMerge(clsx(baseStyles, variants[variant], sizes[size], className))}
        {...props}
      >
        {isLoading ? (
          <Loader2 className="w-4 h-4 animate-spin text-current shrink-0" />
        ) : (
          leftIcon && <span className="shrink-0">{leftIcon}</span>
        )}
        {children}
        {!isLoading && rightIcon && <span className="shrink-0">{rightIcon}</span>}
      </button>
    );
  }
);

Button.displayName = 'Button';
