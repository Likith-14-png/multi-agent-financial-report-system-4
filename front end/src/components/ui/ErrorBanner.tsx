import React from 'react';
import { AlertCircle, RefreshCw, X } from 'lucide-react';
import { Button } from './Button';

export interface ErrorBannerProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  onDismiss?: () => void;
  className?: string;
}

export function ErrorBanner({
  title = 'System Notice',
  message,
  onRetry,
  onDismiss,
  className = '',
}: ErrorBannerProps) {
  return (
    <div
      className={`flex items-start gap-3.5 p-4 rounded-xl border border-rose-800/60 bg-rose-950/30 text-rose-200 ${className}`}
      role="alert"
    >
      <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <h4 className="text-sm font-semibold text-rose-300">{title}</h4>
        <p className="text-xs text-rose-300/80 mt-0.5 leading-relaxed">{message}</p>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {onRetry && (
          <Button
            size="sm"
            variant="outline"
            onClick={onRetry}
            leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
            className="text-rose-300 border-rose-800/80 hover:bg-rose-900/40"
          >
            Retry
          </Button>
        )}
        {onDismiss && (
          <button
            onClick={onDismiss}
            className="text-rose-400 hover:text-rose-200 p-1 rounded-lg hover:bg-rose-900/40"
            aria-label="Dismiss error"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>
    </div>
  );
}
