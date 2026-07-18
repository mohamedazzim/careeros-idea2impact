interface ProgressBarProps {
  value: number;
  variant?: 'default' | 'success' | 'warning';
  showLabel?: boolean;
  className?: string;
}

const variantColors = {
  default: 'bg-indigo-500',
  success: 'bg-emerald-500',
  warning: 'bg-amber-500',
};

export default function ProgressBar({ value, variant = 'default', showLabel = true, className = '' }: ProgressBarProps) {
  const pct = Math.max(0, Math.min(100, value));
  return (
    <div className={`w-full ${className}`} role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label={`${Math.round(pct)}% complete`}>
      {showLabel && <div className="flex justify-between text-xs text-slate-400 mb-1"><span>{Math.round(pct)}%</span></div>}
      <div className="w-full h-2 bg-slate-700 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${variantColors[variant]}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
