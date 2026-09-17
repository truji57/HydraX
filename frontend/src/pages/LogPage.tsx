import { useEffect, useMemo, useState } from 'react';
import { Card } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { api } from '../lib/api';
import { formatEvent } from '../lib/events';
import { RefreshCw, Search } from 'lucide-react';

interface LogEntry { id: string; timestamp: string | null; type: string; data: Record<string, unknown>; }

function formatLog(type: string, data: Record<string, unknown>): string {
  switch (type) {
    case 'app_start': return 'HydraX iniciado';
    case 'app_stop': return 'HydraX detenido';
    case 'copier_start': return `Copiador iniciado: ${data.message || ''}`;
    case 'copier_start_error': return `Fallo al iniciar copiador: ${data.message || ''}`;
    case 'copier_stop': return 'Copiador detenido';
    case 'account_created': return `Cuenta creada: ${data.name} (${data.role} · ${data.platform}${data.server ? ' · ' + data.server : ''})`;
    case 'account_updated': return `Cuenta actualizada: ${data.name}`;
    case 'account_deleted': return `Cuenta eliminada: ${data.name}`;
    case 'slave_config_updated': return `Config de riesgo actualizada: ${data.name}`;
    case 'slave_masters_updated': return `Masters vinculados actualizados: ${data.name}`;
    case 'template_created': return `Plantilla creada: ${data.name}`;
    case 'template_updated': return `Plantilla actualizada: ${data.name}${data.slaves_actualizados ? ` (${data.slaves_actualizados} slaves actualizados)` : ''}`;
    case 'template_deleted': return `Plantilla eliminada: ${data.name}`;
    case 'server_created': return `Servidor añadido: ${data.name}`;
    case 'server_updated': return `Servidor actualizado: ${data.name}`;
    case 'server_deleted': return `Servidor eliminado: ${data.name}`;
    case 'symbol_created': return `Simbolo añadido: ${data.base_symbol} → ${data.broker_server} = ${data.broker_symbol}`;
    case 'symbol_updated': return `Simbolo actualizado: ${data.base_symbol} → ${data.broker_server} = ${data.broker_symbol}`;
    case 'symbol_deleted': return `Simbolo eliminado: ${data.base_symbol} (${data.broker_server})`;
    default: {
      const known = formatEvent(type, data);
      if (known) return known;
      try { return `${type}: ${JSON.stringify(data)}`; } catch { return type; }
    }
  }
}

function badgeVariant(type: string): 'default' | 'success' | 'danger' | 'warning' | 'info' {
  if (type.includes('error')) return 'danger';
  if (type === 'copy_ok') return 'success';
  if (type.startsWith('position_') || type === 'order_pending' || type === 'order_removed') return 'info';
  if (['app_start', 'app_stop', 'copier_start', 'copier_stop'].includes(type)) return 'success';
  if (type.startsWith('account') || type.startsWith('template') || type.startsWith('server') || type.startsWith('symbol') || type.startsWith('slave')) return 'warning';
  return 'default';
}

export default function LogPage() {
  const [entries, setEntries] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('ALL');

  const load = async () => {
    setLoading(true);
    try { setEntries(await api.get<LogEntry[]>('/events?limit=2000')); } catch {}
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const types = useMemo(() => ['ALL', ...Array.from(new Set(entries.map(e => e.type)))].sort(), [entries]);
  const messages = useMemo(() => entries.map(e => ({ e, text: formatLog(e.type, e.data || {}) })), [entries]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return messages.filter(({ e, text }) => {
      if (typeFilter !== 'ALL' && e.type !== typeFilter) return false;
      if (!q) return true;
      return text.toLowerCase().includes(q) || e.type.toLowerCase().includes(q);
    });
  }, [messages, query, typeFilter]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div><h2 className="text-xl font-bold text-white">Log</h2><p className="text-sm text-zinc-500">{entries.length} eventos registrados</p></div>
        <Button variant="outline" size="sm" onClick={load} disabled={loading}><RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Actualizar</Button>
      </div>

      <div className="flex gap-2 flex-wrap">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" />
          <Input className="pl-9" placeholder="Buscar..." value={query} onChange={e => setQuery(e.target.value)} />
        </div>
        <select
          value={typeFilter}
          onChange={e => setTypeFilter(e.target.value)}
          className="h-10 rounded-md border border-zinc-700 bg-zinc-800/50 px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
        >
          {types.map(t => <option key={t} value={t}>{t === 'ALL' ? 'Todos los tipos' : t}</option>)}
        </select>
      </div>

      <Card className="max-h-[calc(100vh-14rem)] overflow-auto">
        {filtered.length === 0 ? (
          <p className="text-sm text-zinc-600 py-6 text-center">No hay eventos que coincidan.</p>
        ) : (
          <div className="space-y-1 p-2">
            {filtered.map(({ e, text }, i) => (
              <div key={e.id || i} className="flex items-start gap-2 py-1 px-2 rounded hover:bg-zinc-800/30">
                <span className="text-zinc-600 shrink-0 font-mono text-[11px] w-40 pt-0.5">{e.timestamp ? new Date(e.timestamp).toLocaleString() : '—'}</span>
                <Badge variant={badgeVariant(e.type)} className="shrink-0 w-24 justify-center">{e.type}</Badge>
                <span className="text-zinc-300 text-xs leading-5 break-all">{text}</span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}