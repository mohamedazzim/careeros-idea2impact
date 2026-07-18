import React from 'react';

interface ToastProps {
  type: 'success' | 'error' | 'info';
  message: string;
  onDismiss: () => void;
}

const typeStyles = {
  success: 'bg-emerald-900/80 border-emerald-600 text-emerald-200',
  error: 'bg-red-900/80 border-red-600 text-red-200',
  info: 'bg-blue-900/80 border-blue-600 text-blue-200',
};

export default function Toast({ type, message, onDismiss }: ToastProps) {
  return (
    <div
      className={`fixed bottom-4 right-4 z-50 px-4 py-3 rounded-lg border shadow-lg animate-in slide-in-from-right ${typeStyles[type]}`}
      role="alert"
      aria-live="polite"
    >
      <div className="flex items-center gap-3">
        <span className="text-sm">{message}</span>
        <button onClick={onDismiss} className="text-current opacity-60 hover:opacity-100 ml-2" aria-label="Dismiss notification">✕</button>
      </div>
    </div>
  );
}
