import { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Users, ArrowLeftRight, History, Settings, Play, Square, Layers, Settings2, ScrollText } from 'lucide-react';
import { cn } from '../../lib/utils';
import { useStore } from '../../store';
import { api } from '../../lib/api';

const links = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/accounts', icon: Users, label: 'Cuentas' },
  { to: '/slaves', icon: ArrowLeftRight, label: 'Slaves (Config)' },
  { to: '/history', icon: History, label: 'Historial' },
  { to: '/templates', icon: Layers, label: 'Plantillas de riesgo' },
  { to: '/preferences', icon: Settings2, label: 'Preferencias' },
  { to: '/settings', icon: Settings, label: 'Ajustes' },
  { to: '/log', icon: ScrollText, label: 'Log' },
];

export function Sidebar() {
  const { copierStatus, wsConnected, version, fetchStatus } = useStore();
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(() => { fetchStatus(); }, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleStartStop = async () => {
    if (copierStatus.running) {
      await api.post('/copier/stop');
    } else {
      setStarting(true);
      const resp = await api.post<{ok: boolean; message: string}>('/copier/start');
      if (!resp.ok) useStore.getState().showToast(resp.message, 'error');
      setStarting(false);
    }
    fetchStatus();
  };

  return (
    <aside className="w-56 h-screen border-r border-zinc-800 bg-zinc-950 flex flex-col">
      <div className={cn('p-4 border-b border-zinc-800 text-center transition-all', copierStatus.running && 'border-emerald-500/40 shadow-[inset_0_-1px_0_rgba(34,197,94,0.2)]')}>
        <img src="/logo.png" alt="HydraX" className={cn('h-32 w-32 mx-auto mt-1 mb-2', copierStatus.running ? 'drop-shadow-[0_0_24px_rgba(34,197,94,0.7)]' : 'drop-shadow-[0_0_8px_rgba(34,197,94,0.2)]')} />
        <h1 className="text-xl font-extrabold text-emerald-400 tracking-tight" style={{fontFamily: 'Inter, sans-serif'}}>HydraX</h1>
        <span className="text-xs text-zinc-500">Trade Copier v{version || "..."}</span>
      </div>

      <nav className="flex-1 p-3 space-y-1">
        {links.map(({ to, icon: Icon, label }) => (
          <NavLink key={to} to={to} end={to === '/'}
            className={({ isActive }) => cn('flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors',
              isActive ? 'bg-emerald-500/10 text-emerald-400' : 'text-zinc-400 hover:bg-zinc-800/50 hover:text-zinc-200')}>
            <Icon size={18} />{label}
          </NavLink>
        ))}
      </nav>

      <div className={cn('p-3 pb-5 border-t', copierStatus.running ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-zinc-800')}>
        <div className="flex items-center gap-2 mb-1">
          <div className={cn('h-3 w-3 rounded-full', copierStatus.running && 'animate-pulse')} style={{backgroundColor: copierStatus.running ? '#34d399' : '#52525b'}} />
          <span className={cn('text-xs font-medium', copierStatus.running ? 'text-emerald-400' : 'text-zinc-500')}>{copierStatus.running ? 'RUNNING' : 'STOPPED'}</span>
        </div>
        <div className="h-5 flex items-center justify-center mb-1">
          {copierStatus.running && copierStatus.uptime_seconds ? (
            <p className="text-xs text-zinc-500">{Math.floor(copierStatus.uptime_seconds / 60)}m {Math.floor(copierStatus.uptime_seconds % 60)}s</p>
          ) : null}
        </div>
        <div className="mb-3 space-y-1.5">
          <div className="flex items-center gap-2">
            <span className={cn('inline-block h-2 w-2 rounded-full', wsConnected ? 'bg-emerald-500 shadow-[0_0_6px_#10b981]' : 'bg-red-500 shadow-[0_0_6px_#ef4444]')} />
            <span className={cn('text-[10px] font-medium', wsConnected ? 'text-emerald-400' : 'text-red-400')}>BACKEND</span>
            <span className={cn('ml-auto text-[10px]', wsConnected ? 'text-zinc-500' : 'text-red-400/70')}>{wsConnected ? 'Activo' : 'Sin conexion'}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className={cn('inline-block h-2 w-2 rounded-full', copierStatus.nt8_connected ? 'bg-emerald-500 shadow-[0_0_6px_#10b981]' : 'bg-red-500 shadow-[0_0_6px_#ef4444]')} />
            <span className={cn('text-[10px] font-medium', copierStatus.nt8_connected ? 'text-emerald-400' : 'text-red-400')}>NT8</span>
            <span className={cn('ml-auto text-[10px]', copierStatus.nt8_connected ? 'text-zinc-500' : 'text-red-400/70')}>{copierStatus.nt8_connected ? 'Conectado' : 'Desconectado'}</span>
          </div>
          <div className="flex items-center gap-2">
            <span className={cn('inline-block h-2 w-2 rounded-full', copierStatus.mt5_connected ? 'bg-emerald-500 shadow-[0_0_6px_#10b981]' : 'bg-red-500 shadow-[0_0_6px_#ef4444]')} />
            <span className={cn('text-[10px] font-medium', copierStatus.mt5_connected ? 'text-emerald-400' : 'text-red-400')}>MT5</span>
            <span className={cn('ml-auto text-[10px]', copierStatus.mt5_connected ? 'text-zinc-500' : 'text-red-400/70')}>{copierStatus.mt5_connected ? 'Conectado' : 'Desconectado'}</span>
          </div>
        </div>
        <button onClick={handleStartStop} disabled={starting}
          className={cn('w-full flex items-center justify-center gap-2 py-3 rounded-md text-base font-semibold transition-colors',
            starting ? 'bg-emerald-500/10 text-emerald-400 animate-pulse' :
            copierStatus.running ? 'bg-red-500/10 text-red-400 hover:bg-red-500/20' : 'bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20')}>
          {starting ? <><span className="inline-block w-4 h-4 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin" /> ARRANCANDO</> :
           copierStatus.running ? <><Square size={16} /> STOP</> : <><Play size={16} /> RUN</>}
        </button>
      </div>
    </aside>
  );
}
