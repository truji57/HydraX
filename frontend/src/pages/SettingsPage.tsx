import { useEffect, useRef, useState } from 'react';
import { Card } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { useStore } from '../store';
import { Download, Upload, Copy } from 'lucide-react';

interface ChangelogEntry {
  version: string;
  date: string;
  description: string;
}

export default function SettingsPage() {
  const { copierStatus, version, showToast } = useStore();
  const [importing, setImporting] = useState(false);
  const [changelog, setChangelog] = useState<ChangelogEntry[]>([]);
  const [updateAvail, setUpdateAvail] = useState(false);
  const [latestVer, setLatestVer] = useState('');
  const [bridgePort, setBridgePort] = useState(5555);
  const [savingPort, setSavingPort] = useState(false);
  const [copyingBridge, setCopyingBridge] = useState(false);
  const [showCopyHint, setShowCopyHint] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetch('/api/system/changelog')
      .then(r => r.json())
      .then(setChangelog)
      .catch(() => {});
    fetch('/api/system/update-check')
      .then(r => r.json())
      .then(d => { if (d.update_available) { setUpdateAvail(true); setLatestVer(d.latest); } })
      .catch(() => {});
    fetch('/api/system/bridge-config')
      .then(r => r.json())
      .then(d => { if (d.ok) setBridgePort(d.port); })
      .catch(() => {});
  }, []);

  const handleExport = async () => {
    try {
      const resp = await fetch('/api/system/backup/export');
      const data = await resp.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a'); a.href = url; a.download = `hydrax-backup-${new Date().toISOString().slice(0,10)}.json`; a.click();
      URL.revokeObjectURL(url);
      showToast('Backup exportado', 'ok');
    } catch { showToast('Error al exportar', 'error'); }
  };

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]; if (!file) return;
    setImporting(true);
    try {
      const fd = new FormData(); fd.append('file', file);
      const resp = await fetch('/api/system/backup/import', { method: 'POST', body: fd });
      const data = await resp.json();
      if (data.ok) { showToast(data.message, 'ok'); useStore.getState().fetchAccounts(); }
      else showToast(data.error || 'Error', 'error');
    } catch { showToast('Error', 'error'); }
    setImporting(false);
  };

  const handleCopyBridge = async () => {
    setCopyingBridge(true);
    try {
      const resp = await fetch('/api/system/copy-bridge', { method: 'POST' });
      const data = await resp.json();
      showToast(data.ok ? data.message : data.error, data.ok ? 'ok' : 'error');
    } catch { showToast('Error al copiar', 'error'); }
    setCopyingBridge(false);
  };

  const handleSavePort = async () => {
    setSavingPort(true);
    try {
      const resp = await fetch('/api/system/bridge-config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ port: bridgePort }),
      });
      const data = await resp.json();
      showToast(data.ok ? data.message : data.error, data.ok ? 'ok' : 'error');
      if (data.ok) setShowCopyHint(true);
    } catch { showToast('Error al guardar', 'error'); }
    setSavingPort(false);
  };

  return (
    <div className="space-y-6">
      <div><h2 className="text-xl font-bold text-white">Ajustes</h2><p className="text-sm text-zinc-500">Configuracion global</p></div>
      <div className="grid grid-cols-2 gap-6">
        <Card className="p-4 space-y-4">
          <h3 className="text-sm font-medium text-white">Informacion</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-zinc-400">Version</span><span className="text-white">{version || '...'} {updateAvail && <span className="text-amber-400">(v{latestVer} disponible)</span>}</span></div>
            <div className="flex justify-between"><span className="text-zinc-400">Backend</span><span className="text-emerald-400">http://localhost:8006</span></div>
            <div className="flex justify-between"><span className="text-zinc-400">Frontend</span><span className="text-emerald-400">http://localhost:5173</span></div>
            <div className="flex justify-between"><span className="text-zinc-400">API Docs</span><a href="http://localhost:8006/docs" target="_blank" className="text-blue-400 hover:underline">Swagger UI</a></div>
          </div>
          <div className="pt-2 border-t border-zinc-700 space-y-2">
            <p className="text-xs text-zinc-500">Puerto del Bridge NT8</p>
            <div className="flex gap-2">
              <input
                type="number"
                value={bridgePort}
                onChange={e => setBridgePort(Number(e.target.value))}
                className="flex h-8 w-24 rounded-md border border-zinc-700 bg-zinc-800/50 px-2 py-1 text-sm text-zinc-200 focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
              />
              <Button variant="primary" size="sm" onClick={handleSavePort} disabled={savingPort}>{savingPort ? '...' : 'Guardar'}</Button>
              <Button variant="outline" size="sm" onClick={handleCopyBridge} disabled={copyingBridge}><Copy size={14} /> {copyingBridge ? '...' : 'Copiar a NT8'}</Button>
            </div>
            {showCopyHint && (
              <p className="text-xs text-amber-400">Puerto guardado. Ahora haz clic en <b>Copiar a NT8</b> para aplicar el cambio al bridge. Luego recompila (F5).</p>
            )}
            <p className="text-[10px] text-zinc-600">Guarda el puerto y copia los archivos a NT8. Luego recompila (F5).</p>
          </div>
        </Card>
        <Card className="p-4 space-y-4">
          <h3 className="text-sm font-medium text-white">Backup y Restauracion</h3>
          <p className="text-xs text-zinc-500">Exporta/importa toda la configuracion (cuentas, slaves, etc).</p>
          <div className="flex gap-2">
            <Button variant="primary" size="sm" onClick={handleExport}><Download size={14} /> Exportar</Button>
            <Button variant="outline" size="sm" disabled={importing} onClick={() => fileInputRef.current?.click()}><Upload size={14} /> {importing ? 'Importando...' : 'Importar'}</Button>
            <input ref={fileInputRef} type="file" accept=".json" onChange={handleImport} className="hidden" />
          </div>
        </Card>
        <Card className="p-4 space-y-4">
          <h3 className="text-sm font-medium text-white">Estado del Copiador</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-zinc-400">Estado</span><span className={copierStatus.running ? 'text-emerald-400' : 'text-red-400'}>{copierStatus.running ? 'Activo' : 'Detenido'}</span></div>
            <div className="flex justify-between"><span className="text-zinc-400">Masters</span><span className="text-white">{copierStatus.active_masters}</span></div>
            <div className="flex justify-between"><span className="text-zinc-400">Slaves</span><span className="text-white">{copierStatus.active_slaves}</span></div>
          </div>
        </Card>
      </div>
      {changelog.length > 0 && (
        <Card className="p-4">
          <h3 className="text-sm font-medium text-white mb-3">Historial de Versiones</h3>
          <div className="space-y-2 text-xs max-h-96 overflow-auto">
            {changelog.map((entry, i) => (
              <div key={i} className="flex items-start gap-3 py-1.5 px-1 hover:bg-zinc-800/30 rounded">
                <span className="text-emerald-400 font-medium shrink-0 w-14">{entry.version}</span>
                <span className="text-zinc-600 shrink-0 w-20">{entry.date}</span>
                <span className="text-zinc-400">{entry.description}</span>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
