import { useEffect, useState } from 'react';
import { Card } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input, Select, Label, Checkbox } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { api } from '../lib/api';
import { useStore } from '../store';
import type { Account, SlaveConfig, SlaveMasterLink } from '../types';
import { HelpCircle } from 'lucide-react';

export default function SlaveConfigPage() {
  const { accounts, fetchAccounts, showToast } = useStore();
  const [selectedSlave, setSelectedSlave] = useState<Account | null>(null);
  const [config, setConfig] = useState<SlaveConfig | null>(null);
  const [linkedMasters, setLinkedMasters] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [showRiskHelp, setShowRiskHelp] = useState(false);

  const slaves = accounts.filter((a) => a.role === 'SLAVE');
  const masters = accounts.filter((a) => a.role === 'MASTER');

  useEffect(() => {
    fetchAccounts();
  }, []);

  const selectSlave = async (slave: Account) => {
    setSelectedSlave(slave);
    setLoading(true);
    try {
      const [cfg, links] = await Promise.all([
        api.get<SlaveConfig>(`/accounts/slaves/${slave.id}/config`),
        api.get<SlaveMasterLink[]>(`/accounts/slaves/${slave.id}/masters`),
      ]);
      setConfig(cfg);
      setLinkedMasters(links.map((l) => l.master_id));
    } catch {
      showToast('Error cargando configuración', 'error');
    }
    setLoading(false);
  };

  const saveConfig = async () => {
    if (!selectedSlave || !config) return;
    try {
      await api.put(`/accounts/slaves/${selectedSlave.id}/config`, config);
      await api.put(`/accounts/slaves/${selectedSlave.id}/masters`, {
        master_ids: linkedMasters,
      });
      showToast('Configuración guardada', 'ok');
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : 'Error al guardar', 'error');
    }
  };

  const toggleMaster = (masterId: string) => {
    setLinkedMasters((prev) =>
      prev.includes(masterId) ? prev.filter((id) => id !== masterId) : [...prev, masterId]
    );
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-white">Configuración de Slaves</h2>
        <p className="text-sm text-zinc-500">Selecciona un slave para configurar</p>
      </div>

      <div className="grid grid-cols-4 gap-4">
        {slaves.map((s) => (
          <Card
            key={s.id}
            className={`cursor-pointer p-4 transition-colors ${
              selectedSlave?.id === s.id ? 'border-emerald-500/50 bg-emerald-500/5' : 'hover:border-zinc-600'
            }`}
            onClick={() => selectSlave(s)}
          >
            <Badge variant="warning" className="mb-2">SLAVE</Badge>
            <p className="text-sm font-medium text-white">{s.name}</p>
            <p className="text-xs text-zinc-500">{s.login}@{s.server}</p>
          </Card>
        ))}
      </div>

      {selectedSlave && config && (
        <Card className="p-6 space-y-6">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-white">
              Configurando: {selectedSlave.name}
            </h3>
            <Button variant="primary" onClick={saveConfig}>
              Guardar Configuración
            </Button>
          </div>

          <div>
            <Label className="text-sm font-medium text-zinc-300 mb-2">Masters Vinculados</Label>
            <div className="flex flex-wrap gap-2">
              {masters.map((m) => (
                <label
                  key={m.id}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-xs cursor-pointer transition-colors ${
                    linkedMasters.includes(m.id)
                      ? 'bg-emerald-500/10 border border-emerald-500/30 text-emerald-400'
                      : 'bg-zinc-800/50 border border-zinc-700 text-zinc-400'
                  }`}
                >
                  <Checkbox
                    checked={linkedMasters.includes(m.id)}
                    onChange={() => toggleMaster(m.id)}
                  />
                  {m.name}
                </label>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div>
              <div className="flex items-center gap-1 mb-1">
                <Label>Modo de Riesgo</Label>
                <button
                  onClick={() => setShowRiskHelp(!showRiskHelp)}
                  className="text-zinc-500 hover:text-zinc-300"
                  title="Ayuda modos de riesgo"
                >
                  <HelpCircle size={14} />
                </button>
              </div>
              <Select
                value={config.risk_mode}
                onChange={(e) => setConfig({ ...config, risk_mode: e.target.value as SlaveConfig['risk_mode'] })}
              >
                <option value="FIXED">Lotes Fijos</option>
                <option value="RISK_PERCENT">% Riesgo del Balance</option>
                <option value="RISK_USD">Riesgo USD Fijo</option>
                <option value="RATIO">Multiplicador del Master</option>
                <option value="BALANCE_PROP">Proporcional al Balance</option>
              </Select>
            </div>

            {showRiskHelp && (
              <div className="col-span-3 p-3 rounded-lg bg-zinc-800/50 border border-zinc-700 text-xs text-zinc-400 space-y-2">
                <div className="font-medium text-zinc-300 mb-1">Guia de modos de riesgo:</div>
                <div className="grid grid-cols-1 gap-2">
                  <div><span className="text-emerald-400 font-medium">Lotes Fijos</span> — Siempre el mismo lotaje. Ej: 0.05 lots en cada operacion.</div>
                  <div><span className="text-emerald-400 font-medium">% Riesgo del Balance</span> — Arriesga un % del balance. Ej: 0.5% con balance 100k = riesgo 500 USD por trade.</div>
                  <div><span className="text-emerald-400 font-medium">Riesgo USD Fijo</span> — Cantidad fija en USD a arriesgar. Ej: 50 USD fijos en cada operacion, sin importar el balance.</div>
                  <div><span className="text-emerald-400 font-medium">Multiplicador del Master</span> — Multiplica los lots del master. Ej: master 0.10 lots × mult 0.5 = slave 0.05 lots.</div>
                  <div><span className="text-emerald-400 font-medium">Proporcional al Balance</span> — Ajusta segun ratio de balances. Ej: master 100k mete 0.10, slave 50k = 0.10 × (50k/100k) = 0.05 lots.</div>
                </div>
              </div>
            )}

            {config.risk_mode === 'FIXED' && (
              <div>
                <Label>Lotes Fijos</Label>
                <Input
                  type="number"
                  step="0.01"
                  value={config.fixed_lots}
                  onChange={(e) => setConfig({ ...config, fixed_lots: Number(e.target.value) })}
                />
              </div>
            )}

            {config.risk_mode === 'RISK_PERCENT' && (
              <div>
                <Label>% Riesgo</Label>
                <Input
                  type="number"
                  step="0.1"
                  value={config.risk_percent}
                  onChange={(e) => setConfig({ ...config, risk_percent: Number(e.target.value) })}
                />
              </div>
            )}

            {config.risk_mode === 'RISK_USD' && (
              <div>
                <Label>Riesgo USD Fijo</Label>
                <Input
                  type="number"
                  step="1"
                  value={config.risk_usd ?? 50}
                  onChange={(e) => setConfig({ ...config, risk_usd: Number(e.target.value) })}
                />
              </div>
            )}

            {config.risk_mode === 'RATIO' && (
              <div>
                <Label>Multiplicador</Label>
                <Input
                  type="number"
                  step="0.1"
                  value={config.lot_multiplier}
                  onChange={(e) => setConfig({ ...config, lot_multiplier: Number(e.target.value) })}
                />
              </div>
            )}

            <div>
              <Label>Max Lots</Label>
              <Input
                type="number"
                step="0.1"
                value={config.max_lots}
                onChange={(e) => setConfig({ ...config, max_lots: Number(e.target.value) })}
              />
            </div>

            <div>
              <Label>Max Posiciones</Label>
              <Input
                type="number"
                value={config.max_positions}
                onChange={(e) => setConfig({ ...config, max_positions: Number(e.target.value) })}
              />
            </div>

            <div>
              <Label>Delay (segundos)</Label>
              <Input
                type="number"
                step="0.1"
                value={config.delay_sec}
                onChange={(e) => setConfig({ ...config, delay_sec: Number(e.target.value) })}
              />
            </div>

            <div>
              <Label>Comentario de Orden</Label>
              <Input
                value={config.order_comment || ''}
                onChange={(e) => setConfig({ ...config, order_comment: e.target.value })}
              />
            </div>

            <div>
              <Label>Magic Number</Label>
              <Input
                type="number"
                value={config.magic_number ?? 0}
                onChange={(e) => setConfig({ ...config, magic_number: Number(e.target.value) })}
              />
            </div>

            <div>
              <Label>Modo Símbolos</Label>
              <Select
                value={config.symbol_mode}
                onChange={(e) => setConfig({ ...config, symbol_mode: e.target.value as SlaveConfig['symbol_mode'] })}
              >
                <option value="ALL">Todos</option>
                <option value="WHITELIST">Whitelist</option>
                <option value="BLACKLIST">Blacklist</option>
              </Select>
            </div>

            {config.symbol_mode !== 'ALL' && (
              <div>
                <Label>Símbolos ({config.symbol_mode === 'WHITELIST' ? 'permitidos' : 'bloqueados'})</Label>
                <Input
                  value={config.symbol_filter?.join(', ') || ''}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      symbol_filter: e.target.value.split(',').map((s) => s.trim()).filter(Boolean),
                    })
                  }
                  placeholder="EURUSD, XAUUSD, NASDAQ"
                />
              </div>
            )}
          </div>

          <div className="flex flex-wrap gap-6">
            <label className="flex items-center gap-2 text-sm text-zinc-300">
              <Checkbox
                checked={config.autocopy_enable}
                onChange={(e) => setConfig({ ...config, autocopy_enable: e.target.checked })}
              />
              AutoCopy Enable
            </label>
            <label className="flex items-center gap-2 text-sm text-zinc-300">
              <Checkbox
                checked={config.copy_sl}
                onChange={(e) => setConfig({ ...config, copy_sl: e.target.checked })}
              />
              Copiar SL
            </label>
            <label className="flex items-center gap-2 text-sm text-zinc-300">
              <Checkbox
                checked={config.copy_tp}
                onChange={(e) => setConfig({ ...config, copy_tp: e.target.checked })}
              />
              Copiar TP
            </label>
            <label className="flex items-center gap-2 text-sm text-zinc-300">
              <Checkbox
                checked={config.inverse_copy}
                onChange={(e) => setConfig({ ...config, inverse_copy: e.target.checked })}
              />
              Copia Inversa
            </label>
          </div>
        </Card>
      )}
    </div>
  );
}
