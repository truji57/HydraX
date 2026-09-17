import { useEffect, useState } from 'react';
import { Card } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input, Select, Label, Checkbox, Switch, DecimalInput } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { PlatformBadge } from '../components/ui/platformbadge';
import { api } from '../lib/api';
import { useStore } from '../store';
import { fixedModeFor, fixedLabelFor, templateKind } from '../lib/risk';
import type { Account, SlaveConfig, SlaveTemplate } from '../types';
import { HelpCircle } from 'lucide-react';

const platform = (a: { platform?: Account['platform'] | null }) => a.platform ?? 'NT8';

export default function SlaveConfigPage() {
  const { accounts, copierStatus, fetchAccounts, showToast } = useStore();
  const [selectedSlave, setSelectedSlave] = useState<Account | null>(null);
  const [config, setConfig] = useState<SlaveConfig | null>(null);
  const [linkedMasters, setLinkedMasters] = useState<string[]>([]);
  const [showRiskHelp, setShowRiskHelp] = useState(false);
  const [templates, setTemplates] = useState<SlaveTemplate[]>([]);

  const slaves = accounts.filter(a => a.role === 'SLAVE');
  const masters = accounts.filter(a => a.role === 'MASTER');

  useEffect(() => { fetchAccounts(); fetchTemplates(); }, []);

  const fetchTemplates = async () => {
    try { setTemplates(await api.get<SlaveTemplate[]>('/templates')); } catch {}
  };

  const selectSlave = async (slave: Account) => {
    if (selectedSlave?.id === slave.id) { setSelectedSlave(null); setConfig(null); return; }
    setSelectedSlave(slave);
    try {
      const [rawCfg, links] = await Promise.all([
        api.get<SlaveConfig>(`/accounts/slaves/${slave.id}/config`),
        api.get<{slave_id:string;master_id:string}[]>(`/accounts/slaves/${slave.id}/masters`),
      ]);
      const cfg = { ...rawCfg, risk_mode: (rawCfg.risk_mode === 'FIXED' ? fixedModeFor(platform(slave)) : rawCfg.risk_mode) as SlaveConfig['risk_mode'] };
      setConfig(cfg);
      setLinkedMasters(links.map(l => l.master_id));
    } catch { showToast('Error cargando config', 'error'); }
  };

  const saveConfig = async () => {
    if (!selectedSlave || !config) return;
    try {
      await api.put(`/accounts/slaves/${selectedSlave.id}/config`, config);
      await api.put(`/accounts/slaves/${selectedSlave.id}/masters`, { master_ids: linkedMasters });
      fetchAccounts();
      showToast('Guardado', 'ok');
      setSelectedSlave(null);
      setConfig(null);
    } catch (e: unknown) { showToast(e instanceof Error ? e.message : 'Error', 'error'); }
  };

  const toggleMaster = (masterId: string) => {
    setLinkedMasters(prev => prev.includes(masterId) ? prev.filter(id => id !== masterId) : [...prev, masterId]);
  };

  const applyTemplate = (templateId: string) => {
    const t = templates.find(tp => tp.id === templateId);
    if (!t || !config || !selectedSlave) return;
    const kind = templateKind(t.risk_mode);
    const plat = platform(selectedSlave);
    if ((kind === 'NT8' && plat !== 'NT8') || (kind === 'MT5' && plat !== 'MT5')) {
      showToast(`La plantilla "${t.name}" es solo para ${kind === 'NT8' ? 'NinjaTrader (NT8)' : 'MetaTrader (MT5)'}`, 'error');
      return;
    }
    setConfig({
      ...config,
      template_id: templateId,
      risk_mode: (t.risk_mode === 'FIXED' ? fixedModeFor(plat) : t.risk_mode) as SlaveConfig['risk_mode'],
      fixed_contracts: t.fixed_contracts,
      fixed_lots: t.fixed_lots,
      risk_percent: t.risk_percent,
      risk_usd: t.risk_usd,
      lot_multiplier: t.lot_multiplier,
      max_contracts: t.max_contracts,
      max_lots: t.max_lots,
      max_positions: t.max_positions,
      autocopy_enable: t.autocopy_enable,
      copy_sl: t.copy_sl,
      copy_tp: t.copy_tp,
      inverse_copy: t.inverse_copy,
      copy_modify: t.copy_modify,
      sync_close: t.sync_close,
      daily_loss_enabled: t.daily_loss_enabled,
      daily_loss_limit: t.daily_loss_limit,
      daily_loss_mode: t.daily_loss_mode,
      daily_profit_enabled: t.daily_profit_enabled,
      daily_profit_limit: t.daily_profit_limit,
      daily_profit_mode: t.daily_profit_mode,
      delay_sec: t.delay_sec,
      magic_number: t.magic_number,
    });
  };

  const clearTemplate = () => {
    if (!config) return;
    setConfig({ ...config, template_id: null });
  };

  const updateConfig = (patch: Partial<SlaveConfig>) => {
    if (!config) return;
    setConfig({ ...config, ...patch, template_id: null });
  };

  const slavePlatform = selectedSlave ? platform(selectedSlave) : 'NT8';
  const availableTemplates = templates.filter(t => {
    const kind = templateKind(t.risk_mode);
    return kind === 'GNRL' || (kind === 'NT8' && slavePlatform === 'NT8') || (kind === 'MT5' && slavePlatform === 'MT5');
  });
  const templateLocked = !!config?.template_id;
  const templateName = config?.template_id ? (templates.find(t => t.id === config.template_id)?.name || '') : '';

  return (
    <div className="space-y-6">
      <div><h2 className="text-xl font-bold text-white">Configuracion de Slaves</h2><p className="text-sm text-zinc-500">Selecciona un slave</p></div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {slaves.map(s => (
          <>
            <Card
              key={s.id}
              className={`cursor-pointer p-4 ${selectedSlave?.id === s.id ? 'border-emerald-500/50 bg-emerald-500/5' : 'hover:border-zinc-600'}`}
              onClick={() => selectSlave(s)}
            >
              <div className="flex items-center gap-2 mb-2"><Badge variant="warning">SLAVE</Badge><PlatformBadge platform={s.platform} /></div>
              <p className="text-sm font-medium text-white">{s.name}</p>
              <p className="text-xs text-zinc-500">Cuenta: {s.login || '—'}{s.platform === 'MT5' && s.server ? <><span className="text-zinc-600"> · </span>{s.server}</> : null}</p>
              {(s.linked_masters || []).length > 0 && (
                <div className="flex items-center gap-1 mt-1.5 flex-wrap">
                  <span className="text-[10px] text-zinc-600">copia de</span>
                  {s.linked_masters.map(m => {
                    const masterColor = accounts.find(a => a.name === m)?.color || '#3b82f6';
                    return (
                    <span key={m} className="text-[10px] px-1.5 py-0.5 rounded font-medium" style={{backgroundColor: masterColor + '20', color: masterColor, border: '1px solid ' + masterColor + '40'}}>{m}</span>
                    );
                  })}
                </div>
              )}
            </Card>
            {selectedSlave?.id === s.id && config && (
              <Card className="mt-2 p-6 space-y-6 col-span-full border-emerald-500/30">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-medium text-white">Configurando: <span className="text-2xl font-bold">{selectedSlave.name}</span></h3>
                  <div className="flex items-center gap-2"><PlatformBadge platform={selectedSlave.platform} /><Button variant="primary" onClick={saveConfig} disabled={copierStatus.running} title={copierStatus.running ? 'Para el copiador para modificar' : ''}>Guardar</Button></div>
                </div>

                <div>
                  <Label className="text-sm font-medium text-zinc-300 mb-2">Masters Vinculados <span className="text-[10px] text-zinc-600 normal-case">(solo plataforma {platform(selectedSlave)})</span></Label>
                  <div className="flex flex-wrap gap-2">
                    {masters.filter(m => platform(m) === platform(selectedSlave)).map(m => (
                      <label key={m.id} className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-xs cursor-pointer ${linkedMasters.includes(m.id) ? 'bg-emerald-500/10 border border-emerald-500/30 text-emerald-400' : 'bg-zinc-800/50 border border-zinc-700 text-zinc-400'}`}>
                        <Checkbox checked={linkedMasters.includes(m.id)} onChange={() => toggleMaster(m.id)} />{m.name}
                      </label>
                    ))}
                    {masters.filter(m => platform(m) === platform(selectedSlave)).length === 0 && <p className="text-xs text-zinc-600">No hay masters {platform(selectedSlave)} disponibles.</p>}
                  </div>
                </div>

                {templates.length > 0 && (
                  <div>
                    <Label>Cargar Plantilla <span className="text-[10px] text-zinc-600 normal-case">(solo {platform(selectedSlave) === 'MT5' ? 'MT5 y GNRL' : 'NT8 y GNRL'})</span></Label>
                    <Select value={config.template_id || ''} onChange={e => { if (e.target.value) applyTemplate(e.target.value); else clearTemplate(); }}>
                      <option value="">Sin plantilla</option>
                      {availableTemplates.map(t => (
                        <option key={t.id} value={t.id}>{t.name} ({templateKind(t.risk_mode)})</option>
                      ))}
                    </Select>
                    {templateLocked && templateName && <p className="text-xs text-emerald-400 mt-1">Plantilla <span className="font-medium">{templateName}</span> asignada. Elige "Sin plantilla" para editar los valores.</p>}
                    {availableTemplates.length === 0 && <p className="text-xs text-zinc-500 mt-1">No hay plantillas disponibles para cuentas {platform(selectedSlave)}.</p>}
                  </div>
                )}

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div>
                    <div className="flex items-center gap-1 mb-1"><Label>Modo de Riesgo</Label><button onClick={() => setShowRiskHelp(!showRiskHelp)} className="text-zinc-500 hover:text-zinc-300" title="Ayuda"><HelpCircle size={14} /></button></div>
                    <Select value={config.risk_mode} disabled={templateLocked} onChange={e => updateConfig({risk_mode: e.target.value as SlaveConfig['risk_mode']})}>
                      {platform(selectedSlave) === 'MT5'
                        ? <option value="FIXED_LOTS">Lotes Fijos</option>
                        : <option value="FIXED_CONTRACTS">Contratos Fijos</option>}
                      <option value="RISK_PERCENT">% Riesgo del Balance</option>
                      <option value="RISK_USD">Riesgo USD Fijo</option>
                      <option value="RATIO">Multiplicador del Master</option>
                      <option value="BALANCE_PROP">Proporcional al Balance</option>
                    </Select>
                    {(config.risk_mode === 'RISK_USD' || config.risk_mode === 'RISK_PERCENT') && (
                      <p className="text-xs text-amber-400 mt-1">Modo de riesgo dependiente de SL. Si el master abre sin SL, se usara <span className="font-medium">Proporcional al Balance</span> como modo por defecto.</p>
                    )}
                  </div>

                  {showRiskHelp && (
                    <div className="col-span-1 md:col-span-3 p-3 rounded-lg bg-zinc-800/50 border border-zinc-700 text-xs text-zinc-400 space-y-1">
                      <div className="font-medium text-zinc-300 mb-1">Modos de riesgo (Futuros):</div>
                      <div><span className="text-emerald-400 font-medium">Contratos Fijos</span> — Siempre el mismo numero de contratos</div>
                      <div><span className="text-emerald-400 font-medium">% Riesgo</span> — Calcula contratos segun % del balance y distancia SL</div>
                      <div><span className="text-emerald-400 font-medium">Riesgo USD Fijo</span> — Cantidad fija en USD a arriesgar</div>
                      <div><span className="text-emerald-400 font-medium">Multiplicador</span> — Multiplica los contratos del master</div>
                      <div><span className="text-emerald-400 font-medium">Prop. Balance</span> — Ajusta segun ratio de balances</div>
                    </div>
                  )}

                  {config.risk_mode === 'FIXED_CONTRACTS' && <div><Label>Contratos Fijos</Label><Input type="number" disabled={templateLocked} value={config.fixed_contracts} onChange={e => updateConfig({fixed_contracts: Number(e.target.value)})} /></div>}
                  {config.risk_mode === 'FIXED_LOTS' && <div><Label>Lotes Fijos</Label><DecimalInput disabled={templateLocked} value={config.fixed_lots ?? 0.01} onChange={v => updateConfig({fixed_lots: v})} /></div>}
                  {config.risk_mode === 'FIXED' && <div><Label>{fixedLabelFor(platform(selectedSlave))}</Label>{platform(selectedSlave) === 'MT5' ? <DecimalInput disabled={templateLocked} value={config.fixed_lots ?? 0.01} onChange={v => updateConfig({fixed_lots: v})} /> : <Input type="number" disabled={templateLocked} value={config.fixed_contracts} onChange={e => updateConfig({fixed_contracts: Number(e.target.value)})} />}</div>}
                  {config.risk_mode === 'RISK_PERCENT' && <div><Label>% Riesgo</Label><DecimalInput disabled={templateLocked} value={config.risk_percent} onChange={v => updateConfig({risk_percent: v})} /></div>}
                  {config.risk_mode === 'RISK_USD' && <div><Label>Riesgo USD</Label><DecimalInput disabled={templateLocked} value={config.risk_usd ?? 50} onChange={v => updateConfig({risk_usd: v})} /></div>}
                  {config.risk_mode === 'RATIO' && <div><Label>Multiplicador</Label><DecimalInput disabled={templateLocked} value={config.lot_multiplier} onChange={v => updateConfig({lot_multiplier: v})} /></div>}

                  {platform(selectedSlave) === 'MT5'
                    ? <div><Label>Max Lotes</Label><DecimalInput disabled={templateLocked} value={config.max_lots ?? 10} onChange={v => updateConfig({max_lots: v})} /></div>
                    : <div><Label>Max Contratos</Label><Input type="number" disabled={templateLocked} value={config.max_contracts} onChange={e => updateConfig({max_contracts: Number(e.target.value)})} /></div>}
                  <div><Label>Max Posiciones</Label><Input type="number" disabled={templateLocked} value={config.max_positions} onChange={e => updateConfig({max_positions: Number(e.target.value)})} /></div>
                  <div><Label>Delay (seg)</Label><DecimalInput disabled={templateLocked} value={config.delay_sec} onChange={v => updateConfig({delay_sec: v})} /></div>
                  <div><Label>Magic Number</Label><Input type="number" disabled={templateLocked} value={config.magic_number ?? 0} onChange={e => updateConfig({magic_number: Number(e.target.value)})} /></div>
                </div>
                <div className="flex items-center justify-between p-4 rounded-lg border border-zinc-700 bg-zinc-800/30">
                  <div>
                    <p className="text-sm font-medium text-white">AutoCopy</p>
                    <p className="text-xs text-zinc-500">{config.autocopy_enable ? 'El slave esta copiando activamente' : 'El slave no copiara operaciones'}</p>
                  </div>
                  <Switch checked={config.autocopy_enable} disabled={templateLocked} onChange={v => updateConfig({autocopy_enable: v})} />
                </div>

                <div className="flex flex-wrap gap-6">
                  <label className="flex items-center gap-2 text-sm text-zinc-300"><Checkbox disabled={templateLocked} checked={config.copy_sl} onChange={e => updateConfig({copy_sl: e.target.checked})} />Copiar SL</label>
                  <label className="flex items-center gap-2 text-sm text-zinc-300"><Checkbox disabled={templateLocked} checked={config.copy_tp} onChange={e => updateConfig({copy_tp: e.target.checked})} />Copiar TP</label>
                  <label className="flex items-center gap-2 text-sm text-zinc-300"><Checkbox disabled={templateLocked} checked={config.copy_modify} onChange={e => updateConfig({copy_modify: e.target.checked})} />Copiar Modificaciones</label>
                  <label className="flex items-center gap-2 text-sm text-zinc-300"><Checkbox disabled={templateLocked} checked={config.sync_close} onChange={e => updateConfig({sync_close: e.target.checked})} />Cierre Sincronizado</label>
                </div>

                <div className="p-4 rounded-lg border border-zinc-700 bg-zinc-800/30 space-y-3">
                  <p className="text-sm font-medium text-white">Limites Diarios (Prop Firm)</p>
                  <div className="flex items-center gap-3">
                    <label className="flex items-center gap-2 text-sm text-zinc-300 min-w-[130px]">
                      <Checkbox disabled={templateLocked} checked={config.daily_loss_enabled} onChange={e => updateConfig({daily_loss_enabled: e.target.checked})} />
                      Max perdida
                    </label>
                    <DecimalInput disabled={templateLocked} value={config.daily_loss_limit ?? 0} onChange={v => updateConfig({daily_loss_limit: v})} />
                    <Select value={config.daily_loss_mode ?? 'USD'} disabled={templateLocked} onChange={e => updateConfig({daily_loss_mode: e.target.value as 'USD' | 'PERCENT'})}>
                      <option value="USD">USD</option>
                      <option value="PERCENT">%</option>
                    </Select>
                  </div>
                  <div className="flex items-center gap-3">
                    <label className="flex items-center gap-2 text-sm text-zinc-300 min-w-[130px]">
                      <Checkbox disabled={templateLocked} checked={config.daily_profit_enabled} onChange={e => updateConfig({daily_profit_enabled: e.target.checked})} />
                      Max ganancia
                    </label>
                    <DecimalInput disabled={templateLocked} value={config.daily_profit_limit ?? 0} onChange={v => updateConfig({daily_profit_limit: v})} />
                    <Select value={config.daily_profit_mode ?? 'USD'} disabled={templateLocked} onChange={e => updateConfig({daily_profit_mode: e.target.value as 'USD' | 'PERCENT'})}>
                      <option value="USD">USD</option>
                      <option value="PERCENT">%</option>
                    </Select>
                  </div>
                </div>
              </Card>
            )}
          </>
        ))}
      </div>
    </div>
  );
}
