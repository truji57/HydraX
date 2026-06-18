import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { useStore } from '../../store';
import { useWebSocket } from '../../lib/ws';
import type { WSMessage } from '../../types';
import { X } from 'lucide-react';

export function Layout() {
  const { toast, clearToast, addLog } = useStore();

  useWebSocket((msg: WSMessage) => {
    const d = msg.data as Record<string, unknown>;
    let text = '';
    switch (msg.type) {
      case 'position_open':
        text = `${d.master || ''}: ${d.direction} ${d.volume} lots ${d.symbol} (ticket ${d.ticket})`;
        break;
      case 'position_close':
        text = `${d.master || ''}: cerrada ${d.symbol} (ticket ${d.ticket})`;
        break;
      case 'position_modify':
        text = `${d.master || ''}: SL/TP modificado ${d.symbol} (ticket ${d.ticket})`;
        break;
      case 'order_pending':
        text = `${d.master || ''}: Orden pendiente ${d.type} ${d.volume} ${d.symbol} @${d.price} (ticket ${d.ticket})`;
        break;
      case 'order_removed':
        text = `${d.master || ''}: Orden pendiente eliminada (ticket ${d.ticket})`;
        break;
      case 'copy_ok':
        text = `${d.slave || ''}: ${d.action} OK ${d.symbol} ${d.volume || ''} (master_ticket ${d.master_ticket})`;
        break;
      case 'copy_error':
        text = `${d.slave || ''}: ${d.action} ERROR ${d.symbol} - ${d.error || 'unknown'} (master_ticket ${d.master_ticket})`;
        break;
      default:
        return;
    }
    if (text) {
      addLog({ timestamp: msg.timestamp, message: text, type: msg.type });
    }
  });

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <div className="max-w-7xl mx-auto p-6">
          <Outlet />
        </div>
      </main>

      {toast && (
        <div className="fixed bottom-4 right-4 z-50 flex items-center gap-2 rounded-lg border px-4 py-3 shadow-lg bg-zinc-900 border-zinc-700">
          <span
            className={`text-sm ${
              toast.type === 'ok'
                ? 'text-emerald-400'
                : toast.type === 'error'
                ? 'text-red-400'
                : 'text-zinc-300'
            }`}
          >
            {toast.message}
          </span>
          <button onClick={clearToast} className="text-zinc-500 hover:text-white">
            <X size={14} />
          </button>
        </div>
      )}
    </div>
  );
}
