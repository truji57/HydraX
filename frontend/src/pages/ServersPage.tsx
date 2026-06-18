import { useEffect, useState } from 'react';
import { Card } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input, Label } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { api } from '../lib/api';
import { useStore } from '../store';
import { Plus, Trash2, Server as ServerIcon, X } from 'lucide-react';

export default function ServersPage() {
  const { showToast } = useStore();
  const [servers, setServers] = useState<string[]>([]);
  const [newServer, setNewServer] = useState('');
  const [symbolCounts, setSymbolCounts] = useState<Record<string, number>>({});

  const fetchServers = async () => {
    try {
      const data = await api.get<{ servers: string[] }>('/servers');
      setServers(data.servers);
    } catch {}
  };

  const fetchSymbolCounts = async () => {
    try {
      const entries = await api.get<{ base_symbol: string; broker_server: string }[]>('/symbols/map');
      const counts: Record<string, number> = {};
      for (const e of entries) {
        counts[e.broker_server] = (counts[e.broker_server] || 0) + 1;
      }
      setSymbolCounts(counts);
    } catch {}
  };

  useEffect(() => { fetchServers(); fetchSymbolCounts(); }, []);

  const addServer = async () => {
    const name = newServer.trim();
    if (!name) return;
    try {
      await api.post('/servers', { name });
      setNewServer('');
      showToast('Server añadido', 'ok');
      fetchServers();
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : 'Error', 'error');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') addServer();
  };

  const deleteServer = async (name: string) => {
    try {
      const list = await api.get<{ id: string; name: string }[]>('/servers/list');
      const found = list.find((s) => s.name === name);
      if (found) {
        await api.delete(`/servers/${found.id}`);
        showToast('Server eliminado', 'ok');
        fetchServers();
      }
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : 'Error', 'error');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white">Servers (Brokers)</h2>
          <p className="text-sm text-zinc-500">{servers.length} servidores configurados</p>
        </div>
      </div>

      <Card className="p-4">
        <div className="flex items-end gap-3">
          <div className="flex-1">
            <Label>Nuevo Servidor</Label>
            <Input
              value={newServer}
              onChange={(e) => setNewServer(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Nombre del broker server..."
            />
          </div>
          <Button variant="primary" onClick={addServer}>
            <Plus size={14} /> Añadir
          </Button>
        </div>
      </Card>

      <div className="grid grid-cols-2 xl:grid-cols-3 gap-3">
        {servers.map((name) => (
          <Card key={name} className="p-4 flex items-center justify-between group hover:border-zinc-600 transition-colors">
            <div className="flex items-center gap-3 min-w-0">
              <ServerIcon size={18} className="text-emerald-400 shrink-0" />
              <div className="min-w-0">
                <p className="text-sm font-medium text-white truncate">{name}</p>
                <p className="text-xs text-zinc-500">
                  {symbolCounts[name] || 0} símbolos mapeados
                </p>
              </div>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => deleteServer(name)}
              className="opacity-0 group-hover:opacity-100 shrink-0"
            >
              <Trash2 size={14} className="text-zinc-600 hover:text-red-400" />
            </Button>
          </Card>
        ))}
        {servers.length === 0 && (
          <p className="text-zinc-600 col-span-3 py-4">No hay servidores configurados.</p>
        )}
      </div>
    </div>
  );
}
