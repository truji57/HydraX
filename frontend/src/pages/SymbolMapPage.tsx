import { useEffect, useMemo, useState } from 'react';
import { Card } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input, Select, Label } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { api } from '../lib/api';
import { useStore } from '../store';
import type { SymbolMapEntry } from '../types';
import { Plus, Trash2, X, ChevronDown, ChevronRight } from 'lucide-react';

export default function SymbolMapPage() {
  const { showToast } = useStore();
  const [entries, setEntries] = useState<SymbolMapEntry[]>([]);
  const [serverList, setServerList] = useState<string[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [baseSymbol, setBaseSymbol] = useState('');
  const [brokerServer, setBrokerServer] = useState('');
  const [brokerSymbol, setBrokerSymbol] = useState('');
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  const fetchEntries = async () => {
    try {
      const list = await api.get<SymbolMapEntry[]>('/symbols/map');
      setEntries(list);
    } catch {}
  };

  const fetchServers = async () => {
    try {
      const data = await api.get<{ servers: string[] }>('/servers');
      setServerList(data.servers);
    } catch {}
  };

  useEffect(() => { fetchEntries(); fetchServers(); }, []);

  const grouped = useMemo(() => {
    const map = new Map<string, SymbolMapEntry[]>();
    for (const e of entries) {
      const arr = map.get(e.base_symbol) || [];
      arr.push(e);
      map.set(e.base_symbol, arr);
    }
    return [...map.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [entries]);

  const servers = useMemo(() => [...new Set(entries.map((e) => e.broker_server))].sort(), [entries]);

  const addEntry = async () => {
    if (!baseSymbol || !brokerServer || !brokerSymbol) return;
    try {
      await api.post('/symbols/map', { base_symbol: baseSymbol, broker_server: brokerServer, broker_symbol: brokerSymbol });
      setBaseSymbol('');
      setBrokerServer('');
      setBrokerSymbol('');
      showToast('Entrada añadida', 'ok');
      fetchEntries();
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : 'Error', 'error');
    }
  };

  const deleteEntry = async (id: string) => {
    try {
      await api.delete(`/symbols/map/${id}`);
      fetchEntries();
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : 'Error', 'error');
    }
  };

  const toggleCollapse = (symbol: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(symbol)) next.delete(symbol);
      else next.add(symbol);
      return next;
    });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white">Symbol Map</h2>
          <p className="text-sm text-zinc-500">
            {grouped.length} símbolos · {servers.length} brokers · {entries.length} mapeos
          </p>
        </div>
        <Button variant={showForm ? 'ghost' : 'primary'} onClick={() => setShowForm(!showForm)}>
          {showForm ? <X size={14} /> : <Plus size={14} />}
          {showForm ? 'Cerrar' : 'Añadir'}
        </Button>
      </div>

      {showForm && (
        <Card className="p-4">
          <div className="grid grid-cols-4 gap-3 items-end">
            <div>
              <Label>Símbolo Base</Label>
              <Input value={baseSymbol} onChange={(e) => setBaseSymbol(e.target.value)} placeholder="EURUSD" />
            </div>
            <div>
              <Label>Broker Server</Label>
              <Select value={brokerServer} onChange={(e) => setBrokerServer(e.target.value)}>
                <option value="">Seleccionar server...</option>
                {serverList.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </Select>
            </div>
            <div>
              <Label>Símbolo Broker</Label>
              <Input value={brokerSymbol} onChange={(e) => setBrokerSymbol(e.target.value)} placeholder="EURUSD.raw" />
            </div>
            <Button variant="primary" onClick={addEntry} className="h-10">
              <Plus size={14} /> Añadir
            </Button>
          </div>
        </Card>
      )}

      <div className="grid grid-cols-2 xl:grid-cols-3 gap-3">
        {grouped.map(([symbol, mappings]) => {
          const isCollapsed = collapsed.has(symbol);
          const sorted = [...mappings].sort((a, b) => a.broker_server.localeCompare(b.broker_server));
          const first = sorted[0];

          return (
            <Card key={symbol} className="overflow-hidden">
              <button
                onClick={() => toggleCollapse(symbol)}
                className="w-full flex items-center justify-between p-3 border-b border-zinc-800 hover:bg-zinc-800/30 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <span className="font-bold text-white text-sm">{symbol}</span>
                  <Badge variant="default">{mappings.length} brokers</Badge>
                </div>
                {isCollapsed ? <ChevronRight size={16} className="text-zinc-500" /> : <ChevronDown size={16} className="text-zinc-500" />}
              </button>

              {!isCollapsed && (
                <div className="divide-y divide-zinc-800/50">
                  {sorted.map((e) => (
                    <div
                      key={e.id}
                      className="flex items-center justify-between px-3 py-2 hover:bg-zinc-800/20 transition-colors"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="text-xs text-zinc-500 truncate">{e.broker_server}</p>
                        <p className="text-sm text-emerald-400 font-mono">{e.broker_symbol}</p>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => deleteEntry(e.id)}
                        className="shrink-0 ml-2"
                      >
                        <Trash2 size={12} className="text-zinc-600 hover:text-red-400" />
                      </Button>
                    </div>
                  ))}
                </div>
              )}

              {isCollapsed && first && (
                <div className="px-3 py-2 text-xs text-zinc-500 truncate">
                  {first.broker_server}: {first.broker_symbol}
                  {sorted.length > 1 && <span className="text-zinc-600"> +{sorted.length - 1} más</span>}
                </div>
              )}
            </Card>
          );
        })}
      </div>
    </div>
  );
}
