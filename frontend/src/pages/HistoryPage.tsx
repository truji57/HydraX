import { useEffect, useState } from 'react';
import { Card } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { api } from '../lib/api';

interface TradeRow {
  id: string;
  timestamp: string | null;
  master_name: string;
  slave_name: string;
  master_ticket: number | null;
  slave_ticket: number | null;
  action: string | null;
  symbol: string;
  volume: number;
  price: number;
  sl: number | null;
  tp: number | null;
  result: string | null;
  error_code: number | null;
  error_message: string | null;
}

export default function HistoryPage() {
  const [trades, setTrades] = useState<TradeRow[]>([]);

  const fetchTrades = async () => {
    try {
      const list = await api.get<TradeRow[]>('/trades?limit=200');
      setTrades(list);
    } catch {}
  };

  useEffect(() => { fetchTrades(); }, []);

  const badge = (action: string | null) => {
    switch (action) {
      case 'OPEN': return <Badge variant="success">OPEN</Badge>;
      case 'CLOSE': return <Badge variant="danger">CLOSE</Badge>;
      case 'MODIFY': return <Badge variant="warning">MODIFY</Badge>;
      default: return <Badge>{action}</Badge>;
    }
  };

  const resultBadge = (r: string | null) => {
    switch (r) {
      case 'SUCCESS': return <Badge variant="success">OK</Badge>;
      case 'FAILED': return <Badge variant="danger">FAIL</Badge>;
      default: return <Badge>{r}</Badge>;
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white">Historial de Trades</h2>
          <p className="text-sm text-zinc-500">{trades.length} operaciones</p>
        </div>
        <button onClick={fetchTrades} className="text-xs text-zinc-500 hover:text-white">
          Refrescar
        </button>
      </div>

      <div className="overflow-x-auto rounded-lg border border-zinc-800">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-zinc-800 bg-zinc-900/50">
              <th className="py-3 px-3 text-left text-xs font-medium text-zinc-400 whitespace-nowrap">Fecha</th>
              <th className="py-3 px-3 text-left text-xs font-medium text-zinc-400 whitespace-nowrap">Acción</th>
              <th className="py-3 px-3 text-left text-xs font-medium text-zinc-400 whitespace-nowrap">Master</th>
              <th className="py-3 px-3 text-left text-xs font-medium text-zinc-400 whitespace-nowrap">Slave</th>
              <th className="py-3 px-3 text-left text-xs font-medium text-zinc-400 whitespace-nowrap">Símbolo</th>
              <th className="py-3 px-3 text-right text-xs font-medium text-zinc-400 whitespace-nowrap">Master T</th>
              <th className="py-3 px-3 text-right text-xs font-medium text-zinc-400 whitespace-nowrap">Slave T</th>
              <th className="py-3 px-3 text-right text-xs font-medium text-zinc-400 whitespace-nowrap">Vol</th>
              <th className="py-3 px-3 text-right text-xs font-medium text-zinc-400 whitespace-nowrap">Precio</th>
              <th className="py-3 px-3 text-right text-xs font-medium text-zinc-400 whitespace-nowrap">SL</th>
              <th className="py-3 px-3 text-right text-xs font-medium text-zinc-400 whitespace-nowrap">TP</th>
              <th className="py-3 px-3 text-center text-xs font-medium text-zinc-400 whitespace-nowrap">Result</th>
            </tr>
          </thead>
          <tbody>
            {trades.map((t) => (
              <tr key={t.id} className="border-b border-zinc-800/50 hover:bg-zinc-800/30">
                <td className="py-2.5 px-3 text-zinc-400 text-xs whitespace-nowrap">
                  {t.timestamp ? new Date(t.timestamp).toLocaleString() : '-'}
                </td>
                <td className="py-2.5 px-3">{badge(t.action)}</td>
                <td className="py-2.5 px-3 text-zinc-300 text-xs max-w-[120px] truncate" title={t.master_name}>
                  {t.master_name}
                </td>
                <td className="py-2.5 px-3 text-zinc-300 text-xs max-w-[120px] truncate" title={t.slave_name}>
                  {t.slave_name}
                </td>
                <td className="py-2.5 px-3 text-white font-medium text-xs">{t.symbol}</td>
                <td className="py-2.5 px-3 text-right text-emerald-400 font-mono text-xs">{t.master_ticket || '-'}</td>
                <td className="py-2.5 px-3 text-right text-blue-400 font-mono text-xs">{t.slave_ticket || '-'}</td>
                <td className="py-2.5 px-3 text-right text-zinc-300 text-xs">{t.volume}</td>
                <td className="py-2.5 px-3 text-right text-zinc-300 text-xs">{t.price}</td>
                <td className="py-2.5 px-3 text-right text-zinc-500 text-xs">{t.sl || '-'}</td>
                <td className="py-2.5 px-3 text-right text-zinc-500 text-xs">{t.tp || '-'}</td>
                <td className="py-2.5 px-3 text-center">{resultBadge(t.result)}</td>
              </tr>
            ))}
            {trades.length === 0 && (
              <tr>
                <td colSpan={12} className="py-8 text-center text-zinc-600">No hay operaciones registradas</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
