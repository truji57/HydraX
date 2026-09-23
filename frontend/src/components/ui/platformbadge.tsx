import { cn } from '../../lib/utils';

const COLORS = {
  NT8: { color: '#fb923c', bg: '#f9731622', border: '#f9731655', label: 'NT8' },
  MT5: { color: '#38bdf8', bg: '#38bdf81f', border: '#38bdf855', label: 'MT5' },
} as const;

export function PlatformBadge({ platform, className }: { platform?: string | null; className?: string }) {
  const key = platform === 'MT5' ? 'MT5' : 'NT8';
  const c = COLORS[key];
  return (
    <span
      className={cn('inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide shrink-0', className)}
      style={{ backgroundColor: c.bg, color: c.color, border: `1px solid ${c.border}` }}
    >
      {c.label}
    </span>
  );
}

export function platformAccent(platform?: string | null): string {
  return platform === 'MT5' ? '#38bdf8' : '#f97316';
}