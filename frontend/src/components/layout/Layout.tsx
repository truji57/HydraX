import { useEffect, useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { useStore } from '../../store';
import { useWebSocket } from '../../lib/ws';
import { formatEvent } from '../../lib/events';
import type { WSMessage } from '../../types';
import { X, Menu } from 'lucide-react';

export function Layout() {
  const { toast, clearToast, addLog } = useStore();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => { useStore.getState().fetchLogs(); }, []);

  useWebSocket((msg: WSMessage) => {
    const text = formatEvent(msg.type, msg.data as Record<string, unknown>);
    if (!text) return;
    if (msg.type === 'worker_error') useStore.getState().showToast(text, 'error');
    addLog({ timestamp: msg.timestamp, message: text, type: msg.type });
  }, (connected) => useStore.getState().setWsConnected(connected));

  return (
    <div className="flex h-screen overflow-hidden">
      <div className="hidden md:block">
        <Sidebar />
      </div>
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 bg-black/50" onClick={() => setSidebarOpen(false)} />
          <div className="absolute left-0 top-0 bottom-0">
            <Sidebar />
          </div>
        </div>
      )}
      <main className="flex-1 overflow-auto">
        <div className="md:hidden flex items-center gap-2 p-3 border-b border-zinc-800 bg-zinc-950">
          <button onClick={() => setSidebarOpen(true)} className="text-zinc-400 hover:text-white">
            <Menu size={20} />
          </button>
          <h1 className="text-lg font-bold text-emerald-400">HydraX</h1>
        </div>
        <div className="max-w-7xl mx-auto p-3 md:p-6"><Outlet /></div>
      </main>
      {toast && (
        <div className="fixed bottom-4 right-4 z-50 flex items-center gap-2 rounded-lg border px-4 py-3 shadow-lg bg-zinc-900 border-zinc-700 max-w-[90vw]">
          <span className={`text-sm ${toast.type === 'ok' ? 'text-emerald-400' : toast.type === 'error' ? 'text-red-400' : 'text-zinc-300'}`}>{toast.message}</span>
          <button onClick={clearToast} className="text-zinc-500 hover:text-white"><X size={14} /></button>
        </div>
      )}
    </div>
  );
}
