import { useEffect, useState } from 'react';
import { Card, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Switch } from '../components/ui/input';
import { PlatformBadge, platformAccent } from '../components/ui/platformbadge';
import { useStore } from '../store';
import { api } from '../lib/api';
import { cn } from '../lib/utils';
import { AlertTriangle, X } from 'lucide-react';
import type { Account, SlaveConfig, SlaveTemplate } from '../types';

const platform = (a: { platform?: Account['platform'] | null }) => a.platform ?? 'NT8';

const platformCounts = (list: Account[]) => {
  const nt8 = list.filter(a => platform(a) === 'NT8').length;
  const mt5 = list.filter(a => platform(a) === 'MT5').length;
  return { total: list.length, nt8, mt5 };
};

export default function DashboardPage() {
  const { copierStatus, accounts, fetchStatus, logs } = useStore();
  const [confirmClose, setConfirmClose] = useState<Account | null>(null);
  const [closing, setClosing] = useState(false);
  const [confirmCloseAll, setConfirmCloseAll] = useState(false);
  const [closingAll, setClosingAll] = useState(false);
  const [platformFilter, setPlatformFilter] = useState<'ALL' | 'NT8' | 'MT5'>('ALL');
  const [slaveConfigs, setSlaveConfigs] = useState<Record<string, SlaveConfig>>({});
  const [templates, setTemplates] = useState<SlaveTemplate[]>([]);
  const [slaveStats, setSlaveStats] = useState<Record<string, {unrealized: number; positions: number; balance: number; day_pnl: number; loss_limit_usd?: number; profit_limit_usd?: number; connected: boolean}>>({});

  useEffect(() => {
    fetchStatus();
    useStore.getState().fetchAccounts();
    api.get<SlaveTemplate[]>('/templates').then(setTemplates).catch(() => {});
    const interval = setInterval(() => { fetchStatus(); fetchSlaveStats(); fetchSlaveConfigs(); }, 5000);
    fetchSlaveStats();
    return () => clearInterval(interval);
  }, []);

  const fetchSlaveStats = async () => {
    try {
      const resp = await api.get<{ok: boolean; data: Record<string, {unrealized: number; positions: number; balance: number; day_pnl: number; loss_limit_usd?: number; profit_limit_usd?: number; connected: boolean}>}>('/copier/dashboard');
      if (resp.ok) setSlaveStats(resp.data);
    } catch {}
  };

  const fetchSlaveConfigs = async () => {
    try {
      const newConfigs: Record<string, SlaveConfig> = {};
      for (const s of useStore.getState().accounts.filter(a => a.role === 'SLAVE' && a.active)) {
        try {
          const cfg = await api.get<SlaveConfig>(`/accounts/slaves/${s.id}/config`);
          newConfigs[s.id] = cfg;
        } catch {}
      }
      if (Object.keys(newConfigs).length > 0) setSlaveConfigs(prev => ({ ...prev, ...newConfigs }));
    } catch {}
  };

  const mastersAll = accounts.filter(a => a.role === 'MASTER' && a.active);
  const slavesAll = accounts.filter(a => a.role === 'SLAVE' && a.active);
  const masters = mastersAll.filter(a => platformFilter === 'ALL' || platform(a) === platformFilter);
  const slaves = slavesAll.filter(a => platformFilter === 'ALL' || platform(a) === platformFilter);
  const masterCounts = platformCounts(mastersAll);
  const slaveCounts = platformCounts(slavesAll);

  useEffect(() => {
    slaves.forEach(async (s) => {
      if (!slaveConfigs[s.id]) {
        try {
          const cfg = await api.get<SlaveConfig>(`/accounts/slaves/${s.id}/config`);
          setSlaveConfigs(prev => ({ ...prev, [s.id]: cfg }));
        } catch {}
      }
    });
  }, [slaves.map(s => s.id).join(',')]);

  const toggleAutocopy = async (slaveId: string, enabled: boolean) => {
    const cfg = slaveConfigs[slaveId];
    if (!cfg) return;
    const updated = { ...cfg, autocopy_enable: enabled };
    setSlaveConfigs(prev => ({ ...prev, [slaveId]: updated }));
    try {
      await api.put(`/accounts/slaves/${slaveId}/config`, updated);
    } catch {
      setSlaveConfigs(prev => ({ ...prev, [slaveId]: cfg }));
      useStore.getState().showToast('Error al actualizar', 'error');
    }
  };

  const toggleMasterCopy = async (master: Account, enabled: boolean) => {
    try {
      await api.put(`/accounts/${master.id}`, { copy_enable: enabled });
      useStore.getState().fetchAccounts();
    } catch {
      useStore.getState().showToast('Error al actualizar', 'error');
    }
  };

  const matchTemplate = (cfg: SlaveConfig): string | null => {
    if (!cfg.template_id) return null;
    return templates.find(tp => tp.id === cfg.template_id)?.name || null;
  };

  const handleEmergencyClose = async () => {
    if (!confirmClose) return;
    setClosing(true);
    try {
      const resp = await api.post<{ok:boolean;closed:number;errors:number;queued?:boolean;error?:string}>(`/copier/emergency-close/${confirmClose.id}`);
      if (resp.ok) {
        if (resp.queued) useStore.getState().showToast(`Cierre de emergencia solicitado en ${confirmClose.name} (MT5)`, 'ok');
        else useStore.getState().showToast(`Cerradas ${resp.closed} posiciones en ${confirmClose.name}`, 'ok');
      }
      else useStore.getState().showToast(resp.error || 'Error', 'error');
      fetchStatus();
    } catch (e: unknown) { useStore.getState().showToast(e instanceof Error ? e.message : 'Error', 'error'); }
    setClosing(false); setConfirmClose(null);
  };

const handleEmergencyCloseAll = async () => {
    setClosingAll(true);
    try {
      const resp = await api.post<{ok:boolean;closed:number;errors:number;slaves:number;queued_mt5?:number}>(`/copier/emergency-close-all`);
      if (resp.ok) {
        const extra = resp.queued_mt5 ? ` (${resp.queued_mt5} MT5 encolados)` : '';
        useStore.getState().showToast(`Cerradas ${resp.closed} posiciones en ${resp.slaves} slaves${extra} (${resp.errors} errores)`, 'ok');
      }
      else useStore.getState().showToast('Error', 'error');
      fetchStatus();
    } catch (e: unknown) { useStore.getState().showToast(e instanceof Error ? e.message : 'Error', 'error'); }
    setClosingAll(false); setConfirmCloseAll(false);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between mb-8">
        <div className="relative inline-block">
          <div className="absolute inset-0 rounded-sm bg-gradient-to-r from-emerald-500/20 via-emerald-500/20 via-60% to-transparent" />
          <h2 className="relative text-2xl font-bold text-white py-2 px-3">Dashboard</h2>
        </div>
        <Badge variant={copierStatus.running ? 'success' : 'default'} className="text-sm px-3 py-1">{copierStatus.running ? 'RUNNING' : 'STOPPED'}</Badge>
      </div>

      <div className="flex items-center gap-2 mb-4">
        {(['ALL', 'NT8', 'MT5'] as const).map(f => (
          <button
            key={f}
            onClick={() => setPlatformFilter(f)}
            className={cn('px-3 py-1 rounded-full text-xs font-medium border transition-colors',
              platformFilter === f ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40' : 'text-zinc-400 border-zinc-700 hover:text-zinc-200')}
          >
            {f === 'ALL' ? `Todas (${mastersAll.length + slavesAll.length})` : f}
          </button>
        ))}
      </div>

      <div><h3 className="text-base font-medium text-zinc-400 mb-3">Cuentas Master <span className="text-emerald-400">({masters.length})</span> <span className="text-xs text-zinc-600">NT8 {masterCounts.nt8} · MT5 {masterCounts.mt5}</span></h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {masters.length === 0 && <p className="text-sm text-zinc-600 col-span-full">No hay cuentas master configuradas.</p>}
          {masters.map(m => {
            const mStat = slaveStats[m.id];
            const mDc = mStat && mStat.connected === false;
            const mStopped = mDc && !copierStatus.running;
            return (
            <Card key={m.id} style={{ borderLeft: `3px solid ${platformAccent(m.platform)}` }} className={`relative overflow-hidden ${mDc && copierStatus.running ? 'border-red-500/60' : copierStatus.running ? 'border-emerald-500/20' : ''} ${m.copy_enable === false ? 'opacity-60' : ''} ${(slaveStats[m.id]?.positions ?? 0) > 0 ? 'border-emerald-500/40' : ''}`}>
              {mDc && copierStatus.running && <div className="absolute inset-0 bg-red-900/30" />}
              {mDc && copierStatus.running && <div className="absolute inset-0 z-10 flex items-center justify-center pointer-events-none"><div className="bg-red-500/95 text-white text-xs font-bold px-3 py-1.5 rounded-md border border-red-300/40 shadow-[0_0_12px_rgba(239,68,68,0.6)]">SIN CONEXION CON CUENTA</div></div>}
              {mStopped && <div className="absolute inset-0 bg-zinc-950/50" />}
              {mStopped && <div className="absolute inset-0 z-10 flex items-center justify-center pointer-events-none"><div className="bg-zinc-700/95 text-zinc-200 text-xs font-bold px-3 py-1.5 rounded-md border border-zinc-500/40">STOPPED</div></div>}
              {copierStatus.running && m.copy_enable !== false && <div className="absolute inset-0 bg-emerald-500/5 animate-[pulse_3s_ease-in-out_infinite]" />}
              {(slaveStats[m.id]?.positions ?? 0) > 0 && <div className="absolute inset-0 bg-emerald-500/10 animate-[pulse_1.5s_ease-in-out_infinite] shadow-[inset_0_0_20px_rgba(34,197,94,0.15)]" />}
              <div className="relative"><CardHeader><div className="flex items-center gap-2"><div className="h-3 w-3 rounded-full shrink-0" style={{backgroundColor: m.color || '#3b82f6', opacity: m.copy_enable === false ? 0.4 : 1}} /><CardTitle className={m.copy_enable === false ? 'text-zinc-500' : ''}>{m.name}</CardTitle></div><div className="flex items-center gap-1"><PlatformBadge platform={m.platform} /><Badge variant="success">MASTER</Badge></div></CardHeader>
              <div className="flex items-center justify-between">
                <p className="text-xs text-zinc-500">Cuenta: {m.login || '—'}{m.platform === 'MT5' && m.server ? <><span className="text-zinc-600"> · </span>{m.server}</> : null}</p>
                <Switch checked={m.copy_enable !== false} onChange={(v) => toggleMasterCopy(m, v)} />
              </div>
              {slaveStats[m.id] && (
                <p className="text-xs text-zinc-400 mt-0.5">
                  <span className="text-white font-medium">${slaveStats[m.id].balance.toFixed(0)}</span>
                  <span className="text-zinc-500 ml-1">
                    ({slaveStats[m.id].day_pnl >= 0 ? '+' : ''}{slaveStats[m.id].day_pnl.toFixed(2)})
                  </span>
                </p>
              )}
              {slaveStats[m.id] && (
                <p className="text-xs text-zinc-400">
                  <span className={slaveStats[m.id].unrealized >= 0 ? 'text-emerald-400' : 'text-red-400'}>
                    {slaveStats[m.id].unrealized >= 0 ? '+' : ''}{slaveStats[m.id].unrealized.toFixed(2)} USD
                  </span>
                  <span className="text-zinc-600 mx-2">|</span>
                  <span>{slaveStats[m.id].positions} pos.</span>
                </p>
              )}
            </div>
            </Card>
            );
          })}
        </div>
      </div>

      <div><div className="text-base font-medium text-zinc-400 mb-3 flex items-center justify-between"><span>Cuentas Slave <span className="text-amber-400">({slaves.length})</span> <span className="text-xs text-zinc-600">NT8 {slaveCounts.nt8} · MT5 {slaveCounts.mt5}</span></span>
            {slaves.length > 0 && (
              <Button variant="danger" size="sm" onClick={() => setConfirmCloseAll(true)}>
                <AlertTriangle size={12} /> Cerrar Todo
              </Button>
            )}
          </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {slaves.length === 0 && <p className="text-sm text-zinc-600 col-span-full">No hay cuentas slave configuradas.</p>}
          {slaves.map(s => {
            const autocopy = slaveConfigs[s.id]?.autocopy_enable ?? true;
            const sStat = slaveStats[s.id];
            const sDc = sStat && sStat.connected === false;
            const sStopped = sDc && !copierStatus.running;
            return (
            <Card key={s.id} style={{ borderLeft: `3px solid ${platformAccent(s.platform)}` }} className={`relative overflow-hidden ${sDc && copierStatus.running ? 'border-red-500/60' : !autocopy ? 'opacity-60 border-amber-800/40' : copierStatus.running ? 'border-amber-500/20' : ''} ${(slaveStats[s.id]?.positions ?? 0) > 0 ? 'border-amber-500/40' : ''}`}>
              {sDc && copierStatus.running && <div className="absolute inset-0 bg-red-900/30" />}
              {sDc && copierStatus.running && <div className="absolute inset-0 z-10 flex items-center justify-center pointer-events-none"><div className="bg-red-500/95 text-white text-xs font-bold px-3 py-1.5 rounded-md border border-red-300/40 shadow-[0_0_12px_rgba(239,68,68,0.6)]">SIN CONEXION CON CUENTA</div></div>}
              {sStopped && <div className="absolute inset-0 bg-zinc-950/50" />}
              {sStopped && <div className="absolute inset-0 z-10 flex items-center justify-center pointer-events-none"><div className="bg-zinc-700/95 text-zinc-200 text-xs font-bold px-3 py-1.5 rounded-md border border-zinc-500/40">STOPPED</div></div>}
              {copierStatus.running && autocopy && <div className="absolute inset-0 bg-amber-500/4 animate-[pulse_3s_ease-in-out_infinite]" />}
              {(slaveStats[s.id]?.positions ?? 0) > 0 && <div className="absolute inset-0 bg-amber-500/8 animate-[pulse_1.5s_ease-in-out_infinite] shadow-[inset_0_0_20px_rgba(245,158,11,0.12)]" />}
              <div className="relative flex flex-col sm:flex-row sm:justify-between sm:gap-3">
                <div className="flex-1 min-w-0">
                  <CardHeader className="mb-2 pb-0">
                    <div className="flex items-center gap-2">
                      <CardTitle className={`text-base font-semibold text-white ${!autocopy ? 'text-zinc-500' : ''}`}>{s.name}</CardTitle>
                      <PlatformBadge platform={s.platform} />
                      <Badge variant="warning">SLAVE</Badge>
                      {!autocopy && (
                        slaveConfigs[s.id] && (slaveConfigs[s.id].daily_loss_enabled || slaveConfigs[s.id].daily_profit_enabled)
                          ? <Badge variant="warning" className="!bg-red-500/15 !text-red-400 !border-red-500/30">PROT</Badge>
                          : <Badge variant="warning" className="!bg-amber-500/15 !text-amber-400 !border-amber-500/30">PAUSADO</Badge>
                      )}
                    </div>
                  </CardHeader>
                  <div className={`space-y-1 text-xs ${!autocopy ? 'text-zinc-600' : 'text-zinc-500'}`}>
                    <p>Cuenta: {s.login || '—'}{s.platform === 'MT5' && s.server ? <><span className="text-zinc-600"> · </span>{s.server}</> : null}</p>
                    {slaveStats[s.id] && (
                      <p className={!autocopy ? 'text-zinc-600' : 'text-zinc-300'}>
                        <span className={!autocopy ? '' : 'text-white font-medium'}>${slaveStats[s.id].balance.toFixed(0)}</span>
                        <span className="text-zinc-500 ml-1">
                          ({slaveStats[s.id].day_pnl >= 0 ? '+' : ''}{slaveStats[s.id].day_pnl.toFixed(2)})
                        </span>
                        {(slaveStats[s.id].loss_limit_usd || slaveStats[s.id].profit_limit_usd) && (
                          <span className="text-zinc-600 ml-2 text-[11px]">
                            [Prot: {slaveStats[s.id].loss_limit_usd != null ? `-$${slaveStats[s.id].loss_limit_usd!.toFixed(0)}` : ''}{slaveStats[s.id].loss_limit_usd != null && slaveStats[s.id].profit_limit_usd != null ? ' | ' : ''}{slaveStats[s.id].profit_limit_usd != null ? `+$${slaveStats[s.id].profit_limit_usd!.toFixed(0)}` : ''}]
                          </span>
                        )}
                      </p>
                    )}
                    {slaveStats[s.id] && (
                      <p className={!autocopy ? 'text-zinc-600' : 'text-zinc-300'}>
                        <span className={slaveStats[s.id].unrealized >= 0 ? 'text-emerald-400' : 'text-red-400'}>
                          {slaveStats[s.id].unrealized >= 0 ? '+' : ''}{slaveStats[s.id].unrealized.toFixed(2)} USD
                        </span>
                        <span className="text-zinc-600 mx-2">|</span>
                        <span>{slaveStats[s.id].positions} pos.</span>
                      </p>
                    )}
                    {slaveConfigs[s.id] && (
                      <p className={!autocopy ? 'text-zinc-600' : 'text-zinc-400'}>
                        Riesgo: {slaveConfigs[s.id].risk_mode === 'FIXED_LOTS' ? `${slaveConfigs[s.id].fixed_lots} lotes` :
                                 slaveConfigs[s.id].risk_mode === 'FIXED_CONTRACTS' || slaveConfigs[s.id].risk_mode === 'FIXED' ? `${slaveConfigs[s.id].fixed_contracts} contratos` :
                                 slaveConfigs[s.id].risk_mode === 'RISK_USD' ? `$${slaveConfigs[s.id].risk_usd} USD` :
                                 slaveConfigs[s.id].risk_mode === 'RISK_PERCENT' ? `${slaveConfigs[s.id].risk_percent}% balance` :
                                 slaveConfigs[s.id].risk_mode === 'RATIO' ? `x${slaveConfigs[s.id].lot_multiplier} master` :
                                 'Prop. balance'}
                        {matchTemplate(slaveConfigs[s.id]) && <span className="text-zinc-600"> ({matchTemplate(slaveConfigs[s.id])})</span>}
                      </p>
                    )}
                  </div>
                  {(s.linked_masters || []).length > 0 && (
                    <div className="mt-1 flex items-center gap-1 flex-wrap">
                      <span className="text-[10px] text-zinc-600">copia de</span>
                      {s.linked_masters.map(m => {
                        const masterColor = accounts.find(a => a.name === m)?.color || '#3b82f6';
                        return (
                        <span key={m} className="text-[10px] px-1.5 py-0.5 rounded font-medium" style={{backgroundColor: masterColor + '20', color: masterColor, border: '1px solid ' + masterColor + '40'}}>{m}</span>
                        );
                      })}
                    </div>
                  )}
                </div>
                <div className="flex flex-row sm:flex-col items-center sm:items-center gap-2 pt-0 sm:pt-1">
                  <Switch
                    checked={autocopy}
                    onChange={(v) => toggleAutocopy(s.id, v)}
                  />
                  <img
                    src="/stop.png"
                    alt="Emergency Close"
                    className="h-16 w-16 cursor-pointer hover:scale-110 transition-transform shrink-0"
                    onClick={() => setConfirmClose(s)}
                    title="Cerrar todas las posiciones"
                  />
                </div>
              </div>
            </Card>
            );
          })}
        </div>
      </div>

      <div><h3 className="text-sm font-medium text-zinc-400 mb-3">Eventos Recientes</h3>
        <Card className="max-h-64 overflow-auto">
          {logs.length === 0 ? <p className="text-sm text-zinc-600 py-2">Esperando eventos...</p> :
            <div className="space-y-1 text-xs">
              {logs.map((log, i) => (
                <div key={i} className="flex items-start gap-2 py-1.5 px-1 hover:bg-zinc-800/30 rounded">
                  <span className="text-zinc-600 shrink-0 w-20">{new Date(log.timestamp).toLocaleTimeString()}</span>
                  <Badge variant={log.type === 'position_open' ? 'info' : log.type === 'position_close' ? 'danger' : log.type === 'position_modify' ? 'warning' : log.type === 'copy_ok' ? 'success' : log.type === 'copy_error' ? 'danger' : 'default'}>
                    {log.type === 'position_open' ? 'OPEN' : log.type === 'position_close' ? 'CLOSE' : log.type === 'position_modify' ? 'MODIFY' : log.type === 'copy_ok' ? 'OK' : log.type === 'copy_error' ? 'FAIL' : log.type}
                  </Badge>
                  <span className="text-zinc-300 truncate">{log.message}</span>
                </div>
              ))}
            </div>}
        </Card>
      </div>

      {confirmClose && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <Card className="w-[420px] p-6">
            <div className="flex items-center justify-between mb-4"><h3 className="text-lg font-bold text-red-400 flex items-center gap-2"><AlertTriangle size={20} /> Emergency Close</h3><button onClick={() => setConfirmClose(null)} className="text-zinc-500 hover:text-white"><X size={18} /></button></div>
            <p className="text-sm text-zinc-400 mb-2">Vas a cerrar <b className="text-white">TODAS</b> las posiciones abiertas en:</p>
            <p className="text-sm font-medium text-white mb-1">{confirmClose.name}</p>
            <p className="text-xs text-red-400 mb-4">Esta accion no se puede deshacer.</p>
            <div className="flex gap-2 justify-end"><Button variant="ghost" size="sm" onClick={() => setConfirmClose(null)}>Cancelar</Button><Button variant="danger" size="sm" onClick={handleEmergencyClose} disabled={closing}>{closing ? 'Cerrando...' : 'Cerrar Todo'}</Button></div>
          </Card>
        </div>
      )}
      {confirmCloseAll && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <Card className="w-[420px] p-6">
            <div className="flex items-center justify-between mb-4"><h3 className="text-lg font-bold text-red-400 flex items-center gap-2"><AlertTriangle size={20} /> Cierre de Emergencia General</h3><button onClick={() => setConfirmCloseAll(false)} className="text-zinc-500 hover:text-white"><X size={18} /></button></div>
            <p className="text-sm text-zinc-400 mb-2">Vas a cerrar <b className="text-white">TODAS</b> las posiciones y cancelar ordenes pendientes en:</p>
            <p className="text-sm font-medium text-white mb-1">TODOS los slaves activos ({slaves.length} cuentas)</p>
            <p className="text-xs text-red-400 mb-4">Esta accion no se puede deshacer.</p>
            <div className="flex gap-2 justify-end"><Button variant="ghost" size="sm" onClick={() => setConfirmCloseAll(false)}>Cancelar</Button><Button variant="danger" size="sm" onClick={handleEmergencyCloseAll} disabled={closingAll}>{closingAll ? 'Cerrando...' : 'Cerrar Todo'}</Button></div>
          </Card>
        </div>
      )}
    </div>
  );
}
