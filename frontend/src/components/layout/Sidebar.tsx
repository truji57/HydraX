import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Users,
  ArrowLeftRight,
  History,
  Settings,
  Play,
  Square,
  Activity,
  Server,
} from 'lucide-react';
import { cn } from '../../lib/utils';
import { useStore } from '../../store';
import { api } from '../../lib/api';

const links = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/accounts', icon: Users, label: 'Cuentas' },
  { to: '/slaves', icon: ArrowLeftRight, label: 'Slaves' },
  { to: '/symbols', icon: Activity, label: 'Símbolos' },
  { to: '/servers', icon: Server, label: 'Servers' },
  { to: '/history', icon: History, label: 'Historial' },
  { to: '/settings', icon: Settings, label: 'Ajustes' },
];

export function Sidebar() {
  const { copierStatus, version, fetchStatus } = useStore();

  const handleStartStop = async () => {
    if (copierStatus.running) {
      await api.post('/copier/stop');
    } else {
      await api.post('/copier/start');
    }
    fetchStatus();
  };

  return (
    <aside className="w-56 h-screen border-r border-zinc-800 bg-zinc-950 flex flex-col">
      <div className="p-4 border-b border-zinc-800">
        <h1 className="text-2xl font-bold text-emerald-400 flex items-center gap-2">
          <Activity size={26} />
          HydraX
        </h1>
        <span className="text-xs text-zinc-500">Trade Copier v{version || "..."}</span>
      </div>

      <nav className="flex-1 p-3 space-y-1">
        {links.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors',
                isActive
                  ? 'bg-emerald-500/10 text-emerald-400'
                  : 'text-zinc-400 hover:bg-zinc-800/50 hover:text-zinc-200'
              )
            }
          >
            <Icon size={18} />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="p-3 border-t border-zinc-800">
        <div className="flex items-center gap-2 mb-2">
          <div
            className={cn(
              'h-2 w-2 rounded-full',
              copierStatus.running ? 'bg-emerald-400 animate-pulse' : 'bg-zinc-600'
            )}
          />
          <span className="text-xs text-zinc-500">
            {copierStatus.running ? 'RUNNING' : 'STOPPED'}
          </span>
        </div>
        <button
          onClick={handleStartStop}
          className={cn(
            'w-full flex items-center justify-center gap-2 py-2 rounded-md text-sm font-medium transition-colors',
            copierStatus.running
              ? 'bg-red-500/10 text-red-400 hover:bg-red-500/20'
              : 'bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20'
          )}
        >
          {copierStatus.running ? (
            <>
              <Square size={14} /> STOP
            </>
          ) : (
            <>
              <Play size={14} /> RUN
            </>
          )}
        </button>
        {copierStatus.running && copierStatus.active_masters > 0 && (
          <div className="mt-2 text-xs text-zinc-500 text-center">
            {copierStatus.active_masters}M / {copierStatus.active_slaves}S
          </div>
        )}
      </div>
    </aside>
  );
}
