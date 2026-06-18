import { useState, useEffect } from 'react';
import { Button } from './button';
import { Card } from './card';
import { Folder, HardDrive, File, X, ChevronLeft, Search } from 'lucide-react';

interface Entry {
  name: string;
  path: string;
  is_dir: boolean;
}

interface BrowseData {
  path: string;
  parent: string | null;
  entries: Entry[];
  drives: string[];
}

interface FileBrowserProps {
  open: boolean;
  onClose: () => void;
  onSelect: (path: string) => void;
  title?: string;
}

export function FileBrowser({ open, onClose, onSelect, title }: FileBrowserProps) {
  const [currentPath, setCurrentPath] = useState('');
  const [entries, setEntries] = useState<Entry[]>([]);
  const [drives, setDrives] = useState<string[]>([]);
  const [parent, setParent] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchPath = async (path: string) => {
    setLoading(true);
    try {
      const res = await fetch(`/api/system/browse?path=${encodeURIComponent(path)}`);
      const data: BrowseData = await res.json();
      setCurrentPath(data.path);
      setEntries(data.entries);
      setDrives(data.drives);
      setParent(data.parent);
    } catch {}
    setLoading(false);
  };

  useEffect(() => {
    if (open) fetchPath('');
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <Card className="w-[550px] max-h-[500px] flex flex-col overflow-hidden">
        <div className="flex items-center justify-between p-3 border-b border-zinc-800">
          <h3 className="text-sm font-medium text-white">{title || 'Seleccionar archivo'}</h3>
          <Button variant="ghost" size="sm" onClick={onClose}><X size={16} /></Button>
        </div>

        <div className="flex items-center gap-2 p-2 border-b border-zinc-800 text-xs">
          <Button
            variant="ghost"
            size="sm"
            disabled={!parent && !currentPath}
            onClick={() => parent ? fetchPath(parent) : fetchPath('')}
          >
            <ChevronLeft size={14} />
          </Button>
          <span className="text-zinc-400 truncate flex-1 font-mono">
            {currentPath || 'Equipos'}
          </span>
        </div>

        <div className="flex-1 overflow-auto p-1">
          {loading && <p className="text-zinc-500 text-xs p-4">Cargando...</p>}

          {drives.length > 0 && (
            <div className="space-y-0.5">
              {drives.map((drive) => (
                <button
                  key={drive}
                  onClick={() => fetchPath(drive)}
                  className="w-full flex items-center gap-2 px-3 py-2 rounded hover:bg-zinc-800/50 text-left text-sm text-zinc-300"
                >
                  <HardDrive size={16} className="text-zinc-500" />
                  {drive}
                </button>
              ))}
            </div>
          )}

          {entries.length === 0 && !loading && drives.length === 0 && (
            <p className="text-zinc-600 text-xs p-4">Vacío o sin permisos</p>
          )}

          <div className="space-y-0.5">
            {entries.map((entry) => (
              <div key={entry.path} className="flex items-center gap-2">
                {entry.is_dir ? (
                  <button
                    onClick={() => fetchPath(entry.path)}
                    className="flex-1 flex items-center gap-2 px-3 py-2 rounded hover:bg-zinc-800/50 text-left text-sm text-zinc-300"
                  >
                    <Folder size={16} className="text-amber-500 shrink-0" />
                    <span className="truncate">{entry.name}</span>
                  </button>
                ) : (
                  <button
                    onClick={() => { onSelect(entry.path); onClose(); }}
                    className="flex-1 flex items-center gap-2 px-3 py-2 rounded hover:bg-emerald-500/10 text-left text-sm text-emerald-400"
                  >
                    <File size={16} className="text-emerald-500 shrink-0" />
                    <span className="truncate">{entry.name}</span>
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      </Card>
    </div>
  );
}
