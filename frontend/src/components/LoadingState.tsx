'use client';

import React from 'react';
import { Loader2 } from 'lucide-react';

interface LoadingStateProps {
  message?: string;
  fullPage?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

export function LoadingState({ message = 'Loading...', fullPage = false, size = 'md' }: LoadingStateProps) {
  const sizeMap = { sm: 'h-4 w-4', md: 'h-8 w-8', lg: 'h-12 w-12' };
  const iconSize = sizeMap[size] || sizeMap.md;

  const content = (
    <div className="flex flex-col items-center justify-center gap-3">
      <Loader2 className={`${iconSize} text-indigo-400 animate-spin`} />
      {message && <p className="text-xs text-slate-400 font-medium">{message}</p>}
    </div>
  );

  if (fullPage) {
    return <div className="min-h-screen flex items-center justify-center bg-slate-950">{content}</div>;
  }

  return <div className="min-h-[200px] flex items-center justify-center">{content}</div>;
}

export function Skeleton({ className = '' }: { className?: string }) {
  return (
    <div className={`animate-pulse bg-slate-800 rounded ${className}`} />
  );
}

export function PageSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="p-6 space-y-4">
      <Skeleton className="h-8 w-48" />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-32" />
        ))}
      </div>
      <div className="space-y-3">
        {Array.from({ length: rows }).map((_, i) => (
          <Skeleton key={i} className="h-16 w-full" />
        ))}
      </div>
    </div>
  );
}

export function EmptyState({ icon, title, description, action }: {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="min-h-[200px] flex flex-col items-center justify-center text-center p-8">
      {icon && <div className="mb-3 text-slate-600">{icon}</div>}
      <h3 className="text-sm font-bold text-slate-300 mb-1">{title}</h3>
      {description && <p className="text-xs text-slate-500 mb-4 max-w-sm">{description}</p>}
      {action}
    </div>
  );
}
