interface BadgeProps {
  variant?: 'info' | 'success' | 'warning' | 'error';
  children: React.ReactNode;
}

const variantStyles = {
  info: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
  success: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
  warning: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
  error: 'bg-red-500/20 text-red-300 border-red-500/30',
};

export default function Badge({ variant = 'info', children }: BadgeProps) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${variantStyles[variant]}`}>
      {children}
    </span>
  );
}
