import { useEffect, useState } from 'react';
import { Card } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input, Select, Label, DecimalInput, Checkbox } from '../components/ui/input';
import { Badge } from '../components/ui/badge';
import { api } from '../lib/api';
import { useStore } from '../store';
import { downloadJson, todayStamp } from '../lib/share';
import { ExportButton, ImportButton } from '../components/ui/sharebuttons';
import { riskLabels, GENERAL_MODES, templateKind, templateKindBadge } from '../lib/risk';
import type { SlaveTemplate, RiskMode } from '../types';
import { Plus, Trash2, X, Edit3, Copy, AlertTriangle } from 'lucide-react';

const emptyTemplate: Omit<SlaveTemplate, 'id' | 'created_at' | 'updated_at'> = {
  name: '',
  risk_mode: 'FIXED_CONTRACTS',
  fixed_contracts: 1,
  fixed_lots: 0.01,
  risk_percent: 0.5,
  risk_usd: 50,
  lot_multiplier: 1,
  max_contracts: 100,
  max_lots: 10,
  max_positions: 100,
  autocopy_enable: true,
  copy_sl: true,
  copy_tp: true,
  inverse_copy: false,
  copy_modify: true,
  sync_close: false,
  daily_loss_enabled: false,
  daily_loss_limit: 0,
  daily_loss_mode: 'USD' as const,
  daily_profit_enabled: false,
  daily_profit_limit: 0,
  daily_profit_mode: 'USD' as const,
  delay_sec: 0,
  magic_number: 0,
};

function KindBadge({ mode }: { mode: RiskMode | string }) {
  const b = templateKindBadge(mode);
  return (
    <span className="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide" style={b.style}>{b.label}</span>
  );
}

function TemplateFormFields({ form, setForm }: {
  form: Omit<SlaveTemplate, 'id' | 'created_at' | 'updated_at'>;
  setForm: (f: typeof form) => void;
}) {
  const isFixedContracts = form.risk_mode === 'FIXED_CONTRACTS' || form.risk_mode === 'FIXED';
  const isFixedLots = form.risk_mode === 'FIXED_LOTS';
  const isGeneral = GENERAL_MODES.includes(form.risk_mode as RiskMode);
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div>
        <Label>Modo de Riesgo</Label>
        <Select value={form.risk_mode} onChange={e => setForm({...form, risk_mode: e.target.value as SlaveTemplate['risk_mode']})}>
          <option value="FIXED_CONTRACTS">Contratos fijos (NT8)</option>
          <option value="FIXED_LOTS">Lotes fijos (MT5)</option>
          <option value="RISK_PERCENT">% Riesgo</option>
          <option value="RISK_USD">Riesgo USD</option>
          <option value="RATIO">Multiplicador</option>
          <option value="BALANCE_PROP">Prop. Balance</option>
        </Select>
        {isGeneral && (
          <p className="text-xs text-emerald-400 mt-1">Plantilla <span className="font-medium">GNRL</span>: se puede aplicar a cuentas NT8 y MT5.</p>
        )}
        {isFixedContracts && <p className="text-xs text-orange-400 mt-1">Plantilla <span className="font-medium">NT8</span>: solo aplicable a cuentas NinjaTrader.</p>}
        {isFixedLots && <p className="text-xs text-sky-400 mt-1">Plantilla <span className="font-medium">MT5</span>: solo aplicable a cuentas MetaTrader.</p>}
        {(form.risk_mode === 'RISK_USD' || form.risk_mode === 'RISK_PERCENT') && (
          <p className="text-xs text-amber-400 mt-1">Depende de SL. Si el master abre sin SL se usara Prop. Balance.</p>
        )}
      </div>
      {isFixedContracts && <div><Label>Contratos Fijos</Label><Input type="number" value={form.fixed_contracts} onChange={e => setForm({...form, fixed_contracts: Number(e.target.value)})} /></div>}
      {isFixedLots && <div><Label>Lotes Fijos</Label><DecimalInput value={form.fixed_lots} onChange={v => setForm({...form, fixed_lots: v})} /></div>}
      {form.risk_mode === 'RISK_PERCENT' && <div><Label>% Riesgo</Label><DecimalInput value={form.risk_percent} onChange={v => setForm({...form, risk_percent: v})} /></div>}
      {form.risk_mode === 'RISK_USD' && <div><Label>Riesgo USD</Label><DecimalInput value={form.risk_usd} onChange={v => setForm({...form, risk_usd: v})} /></div>}
      {form.risk_mode === 'RATIO' && <div><Label>Multiplicador</Label><DecimalInput value={form.lot_multiplier} onChange={v => setForm({...form, lot_multiplier: v})} /></div>}
      {isFixedContracts && <div><Label>Max Contratos</Label><Input type="number" value={form.max_contracts} onChange={e => setForm({...form, max_contracts: Number(e.target.value)})} /></div>}
      {isFixedLots && <div><Label>Max Lotes</Label><DecimalInput value={form.max_lots} onChange={v => setForm({...form, max_lots: v})} /></div>}
      {isGeneral && (
        <>
          <div><Label>Max Contratos (NT8)</Label><Input type="number" value={form.max_contracts} onChange={e => setForm({...form, max_contracts: Number(e.target.value)})} /></div>
          <div><Label>Max Lotes (MT5)</Label><DecimalInput value={form.max_lots} onChange={v => setForm({...form, max_lots: v})} /></div>
        </>
      )}
      {isGeneral && <div className="space-y-2"><Label>Limite</Label><p className="text-xs text-zinc-500">Los modos generales aplican a ambas plataformas; solo se configuran los maximos por plataforma.</p></div>}
      <div><Label>Max Posiciones</Label><Input type="number" value={form.max_positions} onChange={e => setForm({...form, max_positions: Number(e.target.value)})} /></div>
      <div><Label>Delay (seg)</Label><DecimalInput value={form.delay_sec} onChange={v => setForm({...form, delay_sec: v})} /></div>
      <div><Label>Magic Number</Label><Input type="number" value={form.magic_number} onChange={e => setForm({...form, magic_number: Number(e.target.value)})} /></div>
    </div>
  );
}

export default function TemplatesPage() {
  const { copierStatus, showToast } = useStore();
  const copierRunning = copierStatus.running;
  const [templates, setTemplates] = useState<SlaveTemplate[]>([]);
  const [editing, setEditing] = useState<SlaveTemplate | null>(null);
  const [form, setForm] = useState(emptyTemplate);
  const [showNewForm, setShowNewForm] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<SlaveTemplate | null>(null);

  useEffect(() => { fetchTemplates(); }, []);

  const fetchTemplates = async () => {
    try { setTemplates(await api.get<SlaveTemplate[]>('/templates')); } catch {}
  };

  const resetForm = () => { setForm(emptyTemplate); setEditing(null); setShowNewForm(false); };

  const handleSubmit = async () => {
    try {
      if (editing) {
        await api.put(`/templates/${editing.id}`, form);
        showToast('Plantilla actualizada', 'ok');
      } else {
        await api.post('/templates', form);
        showToast('Plantilla creada', 'ok');
      }
      resetForm(); fetchTemplates();
    } catch (e: unknown) { showToast(e instanceof Error ? e.message : 'Error', 'error'); }
  };

  const handleConfirmDelete = async () => {
    if (!deleteTarget) return;
    try { await api.delete(`/templates/${deleteTarget.id}`); showToast('Eliminada', 'ok'); fetchTemplates(); setDeleteTarget(null); }
    catch (e: unknown) { showToast(e instanceof Error ? e.message : 'Error', 'error'); }
  };

  const handleExport = async () => {
    try {
      const data = await api.get<Record<string, unknown>>('/templates/export');
      downloadJson(`hydrax-templates-${todayStamp()}.json`, data);
    } catch { showToast('Error al exportar', 'error'); }
  };

  const handleImport = async (data: Record<string, unknown>) => {
    try {
      const r = await api.post<{ ok: boolean; imported?: number; error?: string }>('/templates/import', data);
      if (r.ok) { showToast(`Importadas ${r.imported ?? 0} plantillas`, 'ok'); fetchTemplates(); }
      else showToast(r.error || 'Error al importar', 'error');
    } catch (e: unknown) { showToast(e instanceof Error ? e.message : 'Error al importar', 'error'); }
  };

  const editTemplate = (t: SlaveTemplate) => {
    setEditing(t);
    setShowNewForm(false);
    setForm({
      name: t.name, risk_mode: t.risk_mode, fixed_contracts: t.fixed_contracts, fixed_lots: t.fixed_lots,
      risk_percent: t.risk_percent, risk_usd: t.risk_usd, lot_multiplier: t.lot_multiplier,
      max_contracts: t.max_contracts, max_lots: t.max_lots, max_positions: t.max_positions,
      autocopy_enable: t.autocopy_enable, copy_sl: t.copy_sl, copy_tp: t.copy_tp,
      inverse_copy: t.inverse_copy, copy_modify: t.copy_modify, sync_close: t.sync_close,
      daily_loss_enabled: t.daily_loss_enabled, daily_loss_limit: t.daily_loss_limit,
      daily_loss_mode: t.daily_loss_mode,
      daily_profit_enabled: t.daily_profit_enabled, daily_profit_limit: t.daily_profit_limit,
      daily_profit_mode: t.daily_profit_mode,
      delay_sec: t.delay_sec, magic_number: t.magic_number,
    });
  };

  const summary = (t: SlaveTemplate) => {
    if (t.risk_mode === 'FIXED_LOTS') return `${t.fixed_lots} lote(s) | max ${t.max_lots} | x${t.lot_multiplier}`;
    if (t.risk_mode === 'FIXED_CONTRACTS' || t.risk_mode === 'FIXED') return `${t.fixed_contracts} contr | max ${t.max_contracts} | x${t.lot_multiplier}`;
    return `max ${t.max_contracts} contr / ${t.max_lots} lots | x${t.lot_multiplier}`;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div><h2 className="text-xl font-bold text-white">Plantillas de Riesgo</h2><p className="text-sm text-zinc-500">{templates.length} plantillas</p></div>
        <div className="flex gap-2">
          <ExportButton label="Exportar" onClick={handleExport} disabled={copierRunning || templates.length === 0} />
          <ImportButton label="Importar" onImport={handleImport} disabled={copierRunning} />
          <Button variant="primary" onClick={() => { resetForm(); setShowNewForm(true); }} disabled={copierRunning} title={copierRunning ? 'Para el copiador para crear plantillas' : ''}><Plus size={14} /> Nueva</Button>
        </div>
      </div>

      {showNewForm && (
        <Card className="p-4 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-white">Nueva Plantilla</h3>
            <Button variant="ghost" size="sm" onClick={resetForm}><X size={14} /></Button>
          </div>
          <div><Label>Nombre</Label><Input value={form.name} onChange={e => setForm({...form, name: e.target.value})} /></div>
          <TemplateFormFields form={form} setForm={setForm} />
          <div className="flex flex-wrap gap-6">
            <label className="flex items-center gap-2 text-sm text-zinc-300"><Checkbox checked={form.copy_sl} onChange={e => setForm({...form, copy_sl: e.target.checked})} />Copiar SL</label>
            <label className="flex items-center gap-2 text-sm text-zinc-300"><Checkbox checked={form.copy_tp} onChange={e => setForm({...form, copy_tp: e.target.checked})} />Copiar TP</label>
            <label className="flex items-center gap-2 text-sm text-zinc-300"><Checkbox checked={form.copy_modify} onChange={e => setForm({...form, copy_modify: e.target.checked})} />Copiar Modificaciones</label>
            <label className="flex items-center gap-2 text-sm text-zinc-300"><Checkbox checked={form.sync_close} onChange={e => setForm({...form, sync_close: e.target.checked})} />Cierre Sincronizado</label>
          </div>
          <div className="p-4 rounded-lg border border-zinc-700 bg-zinc-800/30 space-y-3">
            <p className="text-sm font-medium text-white">Limites Diarios</p>
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-2 text-sm text-zinc-300 min-w-[130px]"><Checkbox checked={form.daily_loss_enabled} onChange={e => setForm({...form, daily_loss_enabled: e.target.checked})} />Max perdida</label>
              <DecimalInput value={form.daily_loss_limit ?? 0} onChange={v => setForm({...form, daily_loss_limit: v})} />
              <Select value={form.daily_loss_mode ?? 'USD'} onChange={e => setForm({...form, daily_loss_mode: e.target.value as 'USD' | 'PERCENT'})}>
                <option value="USD">USD</option>
                <option value="PERCENT">%</option>
              </Select>
            </div>
            <div className="flex items-center gap-3">
              <label className="flex items-center gap-2 text-sm text-zinc-300 min-w-[130px]"><Checkbox checked={form.daily_profit_enabled} onChange={e => setForm({...form, daily_profit_enabled: e.target.checked})} />Max ganancia</label>
              <DecimalInput value={form.daily_profit_limit ?? 0} onChange={v => setForm({...form, daily_profit_limit: v})} />
              <Select value={form.daily_profit_mode ?? 'USD'} onChange={e => setForm({...form, daily_profit_mode: e.target.value as 'USD' | 'PERCENT'})}>
                <option value="USD">USD</option>
                <option value="PERCENT">%</option>
              </Select>
            </div>
          </div>
          <div className="flex gap-2 justify-end"><Button variant="ghost" onClick={resetForm}>Cancelar</Button><Button variant="primary" onClick={handleSubmit}>Crear</Button></div>
        </Card>
      )}

      <div className="space-y-2">
        {templates.map(t => (
          <div key={t.id}>
            <Card className="flex items-center justify-between p-4">
              <div className="flex items-center gap-4 flex-wrap">
                <div className="flex items-center gap-2">
                  <Copy size={14} className="text-zinc-500" />
                  <p className="text-sm font-medium text-white">{t.name}</p>
                </div>
                <KindBadge mode={t.risk_mode} />
                <Badge variant="default">{riskLabels[t.risk_mode] || t.risk_mode}</Badge>
                <span className="text-xs text-zinc-500">{summary(t)}</span>
              </div>
              <div className="flex items-center gap-2">
                <Button variant="ghost" size="sm" onClick={() => editTemplate(t)} disabled={copierRunning} title={copierRunning ? 'Para el copiador para editar' : ''}><Edit3 size={14} /></Button>
                <Button variant="ghost" size="sm" onClick={() => setDeleteTarget(t)} disabled={copierRunning} title={copierRunning ? 'Para el copiador para eliminar' : ''}><Trash2 size={14} className="text-red-400" /></Button>
              </div>
            </Card>
            {editing?.id === t.id && (
              <Card className="mt-2 p-4 space-y-4 border-emerald-500/30">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-medium text-white">Editar {t.name}</h3>
                  <Button variant="ghost" size="sm" onClick={resetForm}><X size={14} /></Button>
                </div>
                <div><Label>Nombre</Label><Input value={form.name} onChange={e => setForm({...form, name: e.target.value})} /></div>
                <TemplateFormFields form={form} setForm={setForm} />
                <div className="flex flex-wrap gap-6">
                  <label className="flex items-center gap-2 text-sm text-zinc-300"><Checkbox checked={form.copy_sl} onChange={e => setForm({...form, copy_sl: e.target.checked})} />Copiar SL</label>
                  <label className="flex items-center gap-2 text-sm text-zinc-300"><Checkbox checked={form.copy_tp} onChange={e => setForm({...form, copy_tp: e.target.checked})} />Copiar TP</label>
                  <label className="flex items-center gap-2 text-sm text-zinc-300"><Checkbox checked={form.copy_modify} onChange={e => setForm({...form, copy_modify: e.target.checked})} />Copiar Modificaciones</label>
                  <label className="flex items-center gap-2 text-sm text-zinc-300"><Checkbox checked={form.sync_close} onChange={e => setForm({...form, sync_close: e.target.checked})} />Cierre Sincronizado</label>
                </div>
                <div className="p-4 rounded-lg border border-zinc-700 bg-zinc-800/30 space-y-3">
                  <p className="text-sm font-medium text-white">Limites Diarios</p>
                  <div className="flex items-center gap-3">
                    <label className="flex items-center gap-2 text-sm text-zinc-300 min-w-[130px]"><Checkbox checked={form.daily_loss_enabled} onChange={e => setForm({...form, daily_loss_enabled: e.target.checked})} />Max perdida</label>
                    <DecimalInput value={form.daily_loss_limit ?? 0} onChange={v => setForm({...form, daily_loss_limit: v})} />
                    <Select value={form.daily_loss_mode ?? 'USD'} onChange={e => setForm({...form, daily_loss_mode: e.target.value as 'USD' | 'PERCENT'})}>
                      <option value="USD">USD</option>
                      <option value="PERCENT">%</option>
                    </Select>
                  </div>
                  <div className="flex items-center gap-3">
                    <label className="flex items-center gap-2 text-sm text-zinc-300 min-w-[130px]"><Checkbox checked={form.daily_profit_enabled} onChange={e => setForm({...form, daily_profit_enabled: e.target.checked})} />Max ganancia</label>
                    <DecimalInput value={form.daily_profit_limit ?? 0} onChange={v => setForm({...form, daily_profit_limit: v})} />
                    <Select value={form.daily_profit_mode ?? 'USD'} onChange={e => setForm({...form, daily_profit_mode: e.target.value as 'USD' | 'PERCENT'})}>
                      <option value="USD">USD</option>
                      <option value="PERCENT">%</option>
                    </Select>
                  </div>
                </div>
                <div className="flex gap-2 justify-end"><Button variant="ghost" onClick={resetForm}>Cancelar</Button><Button variant="primary" onClick={handleSubmit}>Guardar</Button></div>
              </Card>
            )}
          </div>
        ))}
        {templates.length === 0 && <p className="text-sm text-zinc-600 py-4 text-center">No hay plantillas. Crea una para empezar.</p>}
      </div>

      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <Card className="w-[420px] p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-red-400 flex items-center gap-2"><AlertTriangle size={20} /> Eliminar Plantilla</h3>
              <button onClick={() => setDeleteTarget(null)} className="text-zinc-500 hover:text-white"><X size={18} /></button>
            </div>
            <p className="text-sm text-zinc-400 mb-2">Vas a eliminar permanentemente la plantilla:</p>
            <p className="text-sm font-medium text-white mb-1">{deleteTarget.name}</p>
            <p className="text-xs text-zinc-500 mb-4">({templateKind(deleteTarget.risk_mode)} · {riskLabels[deleteTarget.risk_mode] || deleteTarget.risk_mode}) {summary(deleteTarget)}</p>
            <p className="text-xs text-red-400 mb-4">Esta accion no se puede deshacer.</p>
            <div className="flex gap-2 justify-end">
              <Button variant="ghost" size="sm" onClick={() => setDeleteTarget(null)}>Cancelar</Button>
              <Button variant="danger" size="sm" onClick={handleConfirmDelete}>Eliminar</Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}