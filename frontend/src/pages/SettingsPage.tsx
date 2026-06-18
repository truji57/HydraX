import { useState } from 'react';
import { Card } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { useStore } from '../store';

export default function SettingsPage() {
  const { copierStatus } = useStore();
  const [backendPort, setBackendPort] = useState('8000');

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-white">Ajustes</h2>
        <p className="text-sm text-zinc-500">Configuración global del sistema</p>
      </div>

      <div className="grid grid-cols-2 gap-6">
        <Card className="p-4 space-y-4">
          <h3 className="text-sm font-medium text-white">Información del Sistema</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-zinc-400">Versión</span>
              <span className="text-white">2.0.0</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-400">Backend</span>
              <span className="text-emerald-400">http://localhost:{backendPort}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-400">Frontend</span>
              <span className="text-emerald-400">http://localhost:5173</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-400">API Docs</span>
              <a href={`http://localhost:${backendPort}/docs`} target="_blank" className="text-blue-400 hover:underline">Swagger UI</a>
            </div>
          </div>
        </Card>

        <Card className="p-4 space-y-4">
          <h3 className="text-sm font-medium text-white">Estado del Copiador</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-zinc-400">Estado</span>
              <span className={copierStatus.running ? 'text-emerald-400' : 'text-red-400'}>
                {copierStatus.running ? 'Activo' : 'Detenido'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-400">Masters Activos</span>
              <span className="text-white">{copierStatus.active_masters}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-400">Slaves Activos</span>
              <span className="text-white">{copierStatus.active_slaves}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-400">Magic Number</span>
              <span className="text-amber-400">0 (manual mode)</span>
            </div>
          </div>
        </Card>

        <Card className="p-4 space-y-4">
          <h3 className="text-sm font-medium text-white">Atajos</h3>
          <div className="flex flex-col gap-2">
            <Button variant="outline" size="sm" onClick={() => window.open(`http://localhost:${backendPort}/docs`, '_blank')}>
              Abrir API Docs (Swagger)
            </Button>
            <Button variant="outline" size="sm" onClick={() => window.open(`http://localhost:${backendPort}/redoc`, '_blank')}>
              Abrir ReDoc
            </Button>
          </div>
        </Card>

        <Card className="p-4 space-y-4">
          <h3 className="text-sm font-medium text-white">Leyenda de Colores</h3>
          <div className="space-y-2 text-xs">
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 rounded-full bg-emerald-400" />
              <span className="text-zinc-400">Master / Activo / Éxito</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 rounded-full bg-amber-400" />
              <span className="text-zinc-400">Slave / Pendiente</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 rounded-full bg-red-400" />
              <span className="text-zinc-400">Error / Detenido</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 rounded-full bg-blue-400" />
              <span className="text-zinc-400">Información</span>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
