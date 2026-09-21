import { useEffect, useMemo, useState } from 'react';
import { Card } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input, Select, Label } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { api } from '../lib/api';
import { useStore } from '../store';
import { downloadJson, todayStamp } from '../lib/share';
import { ExportButton, ImportButton } from '../components/ui/sharebuttons';
import { Plus, Trash2, Edit3, X, AlertTriangle, ChevronRight } from 'lucide-react';
import { cn } from '../lib/utils';

interface MT5Server { id: string; name: string; platform: 'NT8' | 'MT5'; }
interface SymbolRow { id: string; base_symbol: string; broker_server: string; broker_symbol: string; }

const emptyServer = { name: '', platform: 'MT5' as 'NT8' | 'MT5' };
const emptySymbol = { base_symbol: '', broker_server: '', broker_symbol: '' };

export default function PreferencesPage() {
  const { showToast } = useStore();
  const [tab, setTab] = useState<'servers' | 'symbols'>('servers');

  // --- Servidores ---
  const [servers, setServers] = useState<MT5Server[]>([]);
  const [editingServer, setEditingServer] = useState<MT5Server | null>(null);
  const [serverForm, setServerForm] = useState(emptyServer);
  const [showServerForm, setShowServerForm] = useState(false);
  const [serverDelete, setServerDelete] = useState<MT5Server | null>(null);

  // --- Simbolos ---
  const [symbols, setSymbols] = useState<SymbolRow[]>([]);
  const [editingSymbol, setEditingSymbol] = useState<SymbolRow | null>(null);
  const [symbolForm, setSymbolForm] = useState(emptySymbol);
  const [showSymbolForm, setShowSymbolForm] = useState(false);
  const [symbolDelete, setSymbolDelete] = useState<SymbolRow | null>(null);
  const [manualServer, setManualServer] = useState(false);
  const [expandedBase, setExpandedBase] = useState<string | null>(null);

  const loadServers = async () => {
    try { setServers(await api.get<MT5Server[]>('/servers/list')); } catch {}
  };
  const loadSymbols = async () => {
    try {
      const list = await api.get<SymbolRow[]>('/symbols/map');
      setSymbols([...list].sort((a, b) => a.base_symbol.localeCompare(b.base_symbol) || a.broker_server.localeCompare(b.broker_server)));
    } catch {}
  };

  useEffect(() => { loadServers(); loadSymbols(); }, []);

  const serverNames = servers.map(s => s.name);
  const resetServerForm = () => { setServerForm(emptyServer); setEditingServer(null); setShowServerForm(false); };
  const resetSymbolForm = () => { setSymbolForm(emptySymbol); setEditingSymbol(null); setShowSymbolForm(false); setManualServer(false); };

  const saveServer = async () => {
    if (!serverForm.name.trim()) { showToast('El nombre es obligatorio', 'error'); return; }
    try {
      if (editingServer) {
        await api.put(`/servers/${editingServer.id}`, serverForm);
        showToast('Servidor actualizado', 'ok');
      } else {
        await api.post('/servers', serverForm);
        showToast('Servidor añadido', 'ok');
      }
      resetServerForm(); loadServers();
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : 'Error al guardar servidor', 'error');
    }
  };

  const editServer = (s: MT5Server) => { setEditingServer(s); setShowServerForm(false); setServerForm({ name: s.name, platform: s.platform || 'MT5' }); };

  const confirmDeleteServer = async () => {
    if (!serverDelete) return;
    try { await api.delete(`/servers/${serverDelete.id}`); showToast('Servidor eliminado', 'ok'); loadServers(); setServerDelete(null); }
    catch (e: unknown) { showToast(e instanceof Error ? e.message : 'Error', 'error'); }
  };

  const saveSymbol = async () => {
    if (!symbolForm.base_symbol.trim() || !symbolForm.broker_server.trim() || !symbolForm.broker_symbol.trim()) {
      showToast('Completa simbolo base, servidor y simbolo del broker', 'error');
      return;
    }
    try {
      if (editingSymbol) {
        await api.put(`/symbols/map/${editingSymbol.id}`, symbolForm);
        showToast('Entrada actualizada', 'ok');
      } else {
        await api.post('/symbols/map', symbolForm);
        showToast('Entrada añadida', 'ok');
      }
      resetSymbolForm(); loadSymbols();
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : 'Error al guardar (¿duplicado?)', 'error');
    }
  };

  const editSymbol = (s: SymbolRow) => { setEditingSymbol(s); setShowSymbolForm(false); setManualServer(!serverNames.includes(s.broker_server)); setSymbolForm({ ...s }); };

  const addSymbolFor = (base: string) => {
    setEditingSymbol(null);
    setShowSymbolForm(true);
    setManualServer(false);
    setSymbolForm({ base_symbol: base, broker_server: '', broker_symbol: '' });
  };

  const symbolGroups = useMemo(() => {
    const groups = new Map<string, SymbolRow[]>();
    for (const s of symbols) {
      const arr = groups.get(s.base_symbol) || [];
      arr.push(s);
      groups.set(s.base_symbol, arr);
    }
    return [...groups.entries()].sort((a, b) => a[0].localeCompare(b[0]));
  }, [symbols]);

  const confirmDeleteSymbol = async () => {
    if (!symbolDelete) return;
    try { await api.delete(`/symbols/map/${symbolDelete.id}`); showToast('Entrada eliminada', 'ok'); loadSymbols(); setSymbolDelete(null); }
    catch (e: unknown) { showToast(e instanceof Error ? e.message : 'Error', 'error'); }
  };

  const handleServersExport = async () => {
    try {
      const data = await api.get<Record<string, unknown>>('/servers/export');
      downloadJson(`hydrax-servers-${todayStamp()}.json`, data);
    } catch { showToast('Error al exportar', 'error'); }
  };

  const handleServersImport = async (data: Record<string, unknown>) => {
    try {
      const r = await api.post<{ ok: boolean; imported?: number; error?: string }>('/servers/import', data);
      if (r.ok) { showToast(`Importados ${r.imported ?? 0} servidores`, 'ok'); loadServers(); }
      else showToast(r.error || 'Error al importar', 'error');
    } catch (e: unknown) { showToast(e instanceof Error ? e.message : 'Error al importar', 'error'); }
  };

  const handleSymbolsExport = async () => {
    try {
      const data = await api.get<Record<string, unknown>>('/symbols/export');
      downloadJson(`hydrax-symbols-${todayStamp()}.json`, data);
    } catch { showToast('Error al exportar', 'error'); }
  };

  const handleSymbolsImport = async (data: Record<string, unknown>) => {
    try {
      const r = await api.post<{ ok: boolean; imported?: number; error?: string }>('/symbols/import', data);
      if (r.ok) { showToast(`Importadas ${r.imported ?? 0} entradas`, 'ok'); loadSymbols(); }
      else showToast(r.error || 'Error al importar', 'error');
    } catch (e: unknown) { showToast(e instanceof Error ? e.message : 'Error al importar', 'error'); }
  };

  return (
    <div className="space-y-6">
      <div><h2 className="text-xl font-bold text-white">Preferencias</h2></div>

      <div className="flex gap-2">
        {(['servers', 'symbols'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={cn('px-4 py-1.5 rounded-md text-sm font-medium border transition-colors',
              tab === t ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40' : 'text-zinc-400 border-zinc-700 hover:text-zinc-200')}>
            {t === 'servers' ? 'Servidores MT5' : 'Mapa de Simbolos'}
          </button>
        ))}
      </div>

      {tab === 'servers' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-zinc-500">{servers.length} servidores</p>
            <div className="flex gap-2">
              <ExportButton label="Exportar" onClick={handleServersExport} disabled={servers.length === 0} />
              <ImportButton label="Importar" onImport={handleServersImport} />
              <Button variant="primary" size="sm" onClick={() => { setEditingServer(null); setShowServerForm(true); }}><Plus size={14} /> Nuevo</Button>
            </div>
          </div>

          {(showServerForm || editingServer) && (
            <Card className="p-4 space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium text-white">{editingServer ? `Editar ${editingServer.name}` : 'Nuevo Servidor'}</h3>
                <Button variant="ghost" size="sm" onClick={resetServerForm}><X size={14} /></Button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div><Label>Nombre</Label><Input value={serverForm.name} onChange={e => setServerForm({ ...serverForm, name: e.target.value })} placeholder="ICMarkets-Demo" /></div>
                <div><Label>Plataforma</Label><Select value={serverForm.platform} onChange={e => setServerForm({ ...serverForm, platform: e.target.value as 'NT8' | 'MT5' })}><option value="MT5">MT5</option><option value="NT8">NT8</option></Select></div>
              </div>
              <div className="flex gap-2 justify-end">
                <Button variant="ghost" size="sm" onClick={resetServerForm}>Cancelar</Button>
                <Button variant="primary" size="sm" onClick={saveServer}>{editingServer ? 'Guardar' : 'Añadir'}</Button>
              </div>
            </Card>
          )}

          <Card className="divide-y divide-zinc-800/60">
            {servers.length === 0 && <p className="text-sm text-zinc-600 p-4 text-center">No hay servidores. Anade uno para usarlo en el desplegable de cuentas MT5.</p>}
            {servers.map(s => (
              <div key={s.id} className="flex items-center justify-between p-3">
                <div className="flex items-center gap-3">
                  <span className="text-sm font-medium text-white">{s.name}</span>
                  <Badge variant={s.platform === 'MT5' ? 'warning' : 'info'}>{s.platform || 'MT5'}</Badge>
                </div>
                <div className="flex items-center gap-2">
                  <Button variant="ghost" size="sm" onClick={() => editServer(s)}><Edit3 size={14} /></Button>
                  <Button variant="ghost" size="sm" onClick={() => setServerDelete(s)}><Trash2 size={14} className="text-red-400" /></Button>
                </div>
              </div>
            ))}
          </Card>
        </div>
      )}

      {tab === 'symbols' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-zinc-500">{symbolGroups.length} simbolos base · {symbols.length} entradas</p>
            <div className="flex gap-2">
              <ExportButton label="Exportar" onClick={handleSymbolsExport} disabled={symbols.length === 0} />
              <ImportButton label="Importar" onImport={handleSymbolsImport} />
              <Button variant="primary" size="sm" onClick={() => addSymbolFor('')}><Plus size={14} /> Nueva</Button>
            </div>
          </div>
          <p className="text-xs text-zinc-600">Ej: base <span className="text-emerald-400 font-mono">NAS100</span> → <span className="text-sky-400 font-mono">USTEC</span> en <span className="text-orange-400 font-mono">ICMarkets-Demo</span>. Se usa para traducir simbolos entre brokers MT5 distintos.</p>

          {(showSymbolForm || editingSymbol) && (
            <Card className="p-4 space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium text-white">{editingSymbol ? 'Editar entrada' : 'Nueva entrada'}</h3>
                <Button variant="ghost" size="sm" onClick={resetSymbolForm}><X size={14} /></Button>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div><Label>Simbolo base (canonico)</Label><Input value={symbolForm.base_symbol} onChange={e => setSymbolForm({ ...symbolForm, base_symbol: e.target.value })} placeholder="NAS100" /></div>
                <div><Label>Servidor del broker</Label>
                  <Select value={manualServer ? '__manual__' : symbolForm.broker_server} onChange={e => { const v = e.target.value; if (v === '__manual__') { setManualServer(true); setSymbolForm({ ...symbolForm, broker_server: '' }); } else { setManualServer(false); setSymbolForm({ ...symbolForm, broker_server: v }); } }}>
                    <option value="" disabled>Selecciona un servidor...</option>
                    {serverNames.map(n => <option key={n} value={n}>{n}</option>)}
                    <option value="__manual__">Escribir manualmente...</option>
                  </Select>
                  {manualServer && <Input className="mt-2" value={symbolForm.broker_server} onChange={e => setSymbolForm({ ...symbolForm, broker_server: e.target.value })} placeholder="Nombre del servidor" />}
                </div>
                <div><Label>Simbolo en ese broker</Label><Input value={symbolForm.broker_symbol} onChange={e => setSymbolForm({ ...symbolForm, broker_symbol: e.target.value })} placeholder="USTEC" /></div>
              </div>
              <div className="flex gap-2 justify-end">
                <Button variant="ghost" size="sm" onClick={resetSymbolForm}>Cancelar</Button>
                <Button variant="primary" size="sm" onClick={saveSymbol}>{editingSymbol ? 'Guardar' : 'Añadir'}</Button>
              </div>
            </Card>
          )}

          {symbolGroups.length === 0 && <p className="text-sm text-zinc-600 p-4 text-center">No hay entradas en el mapa de simbolos.</p>}
          <div className="space-y-2">
            {symbolGroups.map(([base, entries]) => (
              <Card key={base} className="p-0 overflow-hidden">
                <div className="flex items-center justify-between gap-2 p-3">
                  <button
                    onClick={() => setExpandedBase(expandedBase === base ? null : base)}
                    className="flex items-center gap-3 flex-1 text-left cursor-pointer group"
                  >
                    <ChevronRight size={16} className={cn('text-zinc-500 transition-transform shrink-0 group-hover:text-zinc-300', expandedBase === base && 'rotate-90')} />
                    <Badge variant="info">{base}</Badge>
                    <span className="text-xs text-zinc-500">{entries.length} brokers</span>
                    <span className="text-xs text-zinc-600 ml-auto pr-1">{expandedBase === base ? 'ocultar' : 'ver'}</span>
                  </button>
                  <Button variant="ghost" size="sm" onClick={() => addSymbolFor(base)} title="Anadir entrada en este simbolo base"><Plus size={14} /></Button>
                </div>
                {expandedBase === base && (
                  <div className="divide-y divide-zinc-800/60 border-t border-zinc-800">
                    {[...entries].sort((a, b) => a.broker_server.localeCompare(b.broker_server)).map(s => (
                      <div key={s.id} className="flex items-center justify-between p-3 gap-2 flex-wrap pl-7">
                        <div className="flex items-center gap-3 min-w-0">
                          <span className="text-sm text-zinc-400">{s.broker_server}</span>
                          <span className="text-zinc-600">→</span>
                          <span className="text-sm font-medium text-white">{s.broker_symbol}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <Button variant="ghost" size="sm" onClick={() => editSymbol(s)}><Edit3 size={14} /></Button>
                          <Button variant="ghost" size="sm" onClick={() => setSymbolDelete(s)}><Trash2 size={14} className="text-red-400" /></Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            ))}
          </div>
        </div>
      )}

      {serverDelete && (
        <ConfirmModal title="Eliminar Servidor" onCancel={() => setServerDelete(null)} onConfirm={confirmDeleteServer}>
          <p className="text-sm text-zinc-400 mb-2">Vas a eliminar el servidor:</p>
          <p className="text-sm font-medium text-white mb-4">{serverDelete.name}</p>
        </ConfirmModal>
      )}
      {symbolDelete && (
        <ConfirmModal title="Eliminar Entrada" onCancel={() => setSymbolDelete(null)} onConfirm={confirmDeleteSymbol}>
          <p className="text-sm text-zinc-400 mb-2">Vas a eliminar <b className="text-white">{symbolDelete.base_symbol}</b> en <b className="text-white">{symbolDelete.broker_server}</b> ({symbolDelete.broker_symbol})</p>
        </ConfirmModal>
      )}
    </div>
  );
}

function ConfirmModal({ title, children, onCancel, onConfirm }: {
  title: string; children: React.ReactNode; onCancel: () => void; onConfirm: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <Card className="w-[420px] p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-bold text-red-400 flex items-center gap-2"><AlertTriangle size={20} /> {title}</h3>
          <button onClick={onCancel} className="text-zinc-500 hover:text-white"><X size={18} /></button>
        </div>
        {children}
        <p className="text-xs text-red-400 mb-4">Esta accion no se puede deshacer.</p>
        <div className="flex gap-2 justify-end">
          <Button variant="ghost" size="sm" onClick={onCancel}>Cancelar</Button>
          <Button variant="danger" size="sm" onClick={onConfirm}>Eliminar</Button>
        </div>
      </Card>
    </div>
  );
}