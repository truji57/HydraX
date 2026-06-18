import { useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardValue } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { useStore } from '../store';
import { TrendingUp, TrendingDown, Wallet, BarChart3 } from 'lucide-react';

export default function DashboardPage() {
  const { copierStatus, accounts, fetchStatus, logs } = useStore();

  useEffect(() => {
    fetchStatus();
    useStore.getState().fetchAccounts();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  const masters = accounts.filter((a) => a.role === 'MASTER' && a.active);
  const slaves = accounts.filter((a) => a.role === 'SLAVE' && a.active);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white">Dashboard</h2>
          <p className="text-sm text-zinc-500">
            {copierStatus.running ? 'Copiador activo' : 'Copiador detenido'}
          </p>
        </div>
        <Badge variant={copierStatus.running ? 'success' : 'default'}>
          {copierStatus.running ? 'RUNNING' : 'STOPPED'}
        </Badge>
      </div>

      <div className="grid grid-cols-4 gap-4">
        <Card>
          <CardHeader>
            <CardTitle>Masters</CardTitle>
            <Wallet size={18} className="text-emerald-400" />
          </CardHeader>
          <CardValue>{copierStatus.active_masters}</CardValue>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Slaves</CardTitle>
            <BarChart3 size={18} className="text-blue-400" />
          </CardHeader>
          <CardValue>{copierStatus.active_slaves}</CardValue>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Posiciones Copiadas</CardTitle>
            <TrendingUp size={18} className="text-amber-400" />
          </CardHeader>
          <CardValue>{copierStatus.total_positions}</CardValue>
          <p className="text-xs text-zinc-600 mt-1">abiertas activas</p>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Uptime</CardTitle>
            <TrendingDown size={18} className="text-purple-400" />
          </CardHeader>
          <CardValue>
            {copierStatus.uptime_seconds
              ? `${Math.floor(copierStatus.uptime_seconds / 60)}m ${Math.floor(copierStatus.uptime_seconds % 60)}s`
              : '--'}
          </CardValue>
        </Card>
      </div>

      <div>
        <h3 className="text-sm font-medium text-zinc-400 mb-3">Cuentas Master</h3>
        <div className="grid grid-cols-3 gap-4">
          {masters.length === 0 && (
            <p className="text-sm text-zinc-600 col-span-3">No hay cuentas master configuradas.</p>
          )}
          {masters.map((m) => (
            <Card key={m.id}>
              <CardHeader>
                <CardTitle>{m.name}</CardTitle>
                <Badge variant="success">MASTER</Badge>
              </CardHeader>
              <div className="space-y-1 text-xs text-zinc-500">
                <p>Login: {m.login}</p>
                <p>Server: {m.server}</p>
                <p>Poll: {m.poll_interval}s</p>
              </div>
            </Card>
          ))}
        </div>
      </div>

      <div>
        <h3 className="text-sm font-medium text-zinc-400 mb-3">Cuentas Slave</h3>
        <div className="grid grid-cols-3 gap-4">
          {slaves.length === 0 && (
            <p className="text-sm text-zinc-600 col-span-3">No hay cuentas slave configuradas.</p>
          )}
          {slaves.map((s) => (
            <Card key={s.id}>
              <CardHeader>
                <CardTitle>{s.name}</CardTitle>
                <Badge variant="warning">SLAVE</Badge>
              </CardHeader>
              <div className="space-y-1 text-xs text-zinc-500">
                <p>Login: {s.login}</p>
                <p>Server: {s.server}</p>
              </div>
            </Card>
          ))}
        </div>
      </div>

      <div>
        <h3 className="text-sm font-medium text-zinc-400 mb-3">Eventos Recientes</h3>
        <Card className="max-h-64 overflow-auto">
          {logs.length === 0 ? (
            <p className="text-sm text-zinc-600 py-2">Esperando eventos...</p>
          ) : (
            <div className="space-y-1 text-xs">
              {logs.map((log, i) => (
                <div key={i} className="flex items-start gap-2 py-1.5 px-1 hover:bg-zinc-800/30 rounded">
                  <span className="text-zinc-600 shrink-0 w-20">
                    {new Date(log.timestamp).toLocaleTimeString()}
                  </span>
                  <Badge
                    variant={
                      log.type === 'position_open' ? 'success' :
                      log.type === 'position_close' ? 'danger' :
                      log.type === 'position_modify' ? 'warning' :
                      log.type === 'order_pending' ? 'default' :
                      log.type === 'order_removed' ? 'danger' :
                      log.type === 'copy_ok' ? 'success' :
                      log.type === 'copy_error' ? 'danger' : 'default'
                    }
                  >
                    {log.type === 'position_open' ? 'OPEN' :
                     log.type === 'position_close' ? 'CLOSE' :
                     log.type === 'position_modify' ? 'MODIFY' :
                     log.type === 'order_pending' ? 'PEND' :
                     log.type === 'order_removed' ? 'DEL' :
                     log.type === 'copy_ok' ? 'OK' :
                     log.type === 'copy_error' ? 'FAIL' : log.type}
                  </Badge>
                  <span className="text-zinc-300 truncate">{log.message}</span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
