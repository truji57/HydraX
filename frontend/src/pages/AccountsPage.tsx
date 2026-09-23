import { useEffect, useMemo, useState } from 'react';
import { Button } from '../components/ui/button';
import { Input, Select, Label, Checkbox, DecimalInput } from '../components/ui/input';
import { Card } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { PlatformBadge } from '../components/ui/platformbadge';
import { FileBrowser } from '../components/ui/filebrowser';
import { api } from '../lib/api';
import { useStore } from '../store';
import type { Account, AccountForm, TestResult, Platform } from '../types';
import { Plus, Trash2, Wifi, X, Edit3, FolderOpen } from 'lucide-react';

const emptyForm: AccountForm = {
  name: '', role: 'MASTER', platform: 'NT8', login: '',
  password: '', bridge_host: 'localhost', bridge_port: 5555,
  server: '', terminal_path: '', filling_mode: '', poll_interval: 0.5,
  active: true, color: '#3b82f6',
};

function AccountFormBody({ form, setForm, editing, loginOptions, manualLogin, setManualLogin, mt5Servers, manualServer, setManualServer, onBrowse }: {
  form: AccountForm;
  setForm: (f: AccountForm) => void;
  editing: boolean;
  loginOptions: string[];
  manualLogin: boolean;
  setManualLogin: (v: boolean) => void;
  mt5Servers: string[];
  manualServer: boolean;
  setManualServer: (v: boolean) => void;
  onBrowse: () => void;
}) {
  const isMt5 = form.platform === 'MT5';
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div><Label>Nombre</Label><Input value={form.name} onChange={e => setForm({...form, name: e.target.value})} /></div>
      <div><Label>Rol</Label><Select value={form.role} onChange={e => setForm({...form, role: e.target.value as 'MASTER'|'SLAVE'})}><option value="MASTER">MASTER</option><option value="SLAVE">SLAVE</option></Select></div>
      <div><Label>Plataforma</Label>
        <Select value={form.platform} onChange={e => { const plat = e.target.value as Platform; setForm({...form, platform: plat, terminal_path: '', password: ''}); setManualLogin(false); }}>
          <option value="NT8">NinjaTrader 8</option>
          <option value="MT5">MetaTrader 5</option>
        </Select>
      </div>

      {isMt5 ? (
        <>
          <div><Label>Cuenta MT5 (login)</Label><Input type="number" value={form.login} onChange={e => setForm({...form, login: e.target.value})} placeholder="512345" /></div>
          <div><Label>Password</Label><Input type="password" value={form.password} onChange={e => setForm({...form, password: e.target.value})} placeholder={editing ? 'Dejar vacio para no cambiar' : ''} /></div>
          <div><Label>Servidor</Label>
            <Select value={manualServer ? '__manual__' : (form.server || '')} onChange={e => { const v = e.target.value; if (v === '__manual__') { setManualServer(true); setForm({...form, server: ''}); } else { setManualServer(false); setForm({...form, server: v}); } }}>
              <option value="" disabled>Selecciona un servidor...</option>
              {mt5Servers.map(s => <option key={s} value={s}>{s}</option>)}
              <option value="__manual__">Escribir manualmente...</option>
            </Select>
            {manualServer && <Input className="mt-2" value={form.server} onChange={e => setForm({...form, server: e.target.value})} placeholder="ICMarkets-Demo" />}
            {mt5Servers.length === 0 && !manualServer && <p className="text-[11px] text-zinc-500 mt-1">No hay servidores configurados. Anadelos en Preferencias.</p>}
          </div>
          <div><Label>Filling Mode</Label>
            <Select value={form.filling_mode || ''} onChange={e => setForm({...form, filling_mode: e.target.value})}>
              <option value="">AUTO (detectar)</option>
              <option value="FOK">FOK</option>
              <option value="IOC">IOC</option>
              <option value="RETURN">RETURN</option>
            </Select>
            <p className="text-[11px] text-zinc-500 mt-1">Si el broker rechaza con 'Unsupported filling mode', prueba aqui el modo que exige.</p>
          </div>
          <div><Label>Terminal (terminal64.exe, opcional)</Label>
            <div className="flex gap-2">
              <Input value={form.terminal_path} onChange={e => setForm({...form, terminal_path: e.target.value})} placeholder="C:\Program Files\MetaTrader 5\terminal64.exe" />
              <Button variant="outline" size="sm" onClick={onBrowse} title="Buscar terminal64.exe"><FolderOpen size={14} /></Button>
            </div>
          </div>
        </>
      ) : (
        <>
          <div><Label>Cuenta NT8</Label><Select value={manualLogin ? '__manual__' : (form.login || '')} onChange={e => { const v = e.target.value; if (v === '__manual__') { setManualLogin(true); setForm({...form, login: ''}); } else { setManualLogin(false); setForm({...form, login: v}); } }}><option value="" disabled>Selecciona una cuenta...</option>{loginOptions.map(o => <option key={o} value={o}>{o}</option>)}<option value="__manual__">Escribir manualmente...</option></Select>{manualLogin && <Input className="mt-2" value={form.login} onChange={e => setForm({...form, login: e.target.value})} placeholder="Nombre exacto en NT8 (Sim101...)" />}{loginOptions.length === 0 && !manualLogin && <p className="text-[11px] text-zinc-500 mt-1">No hay cuentas nuevas disponibles (todas ya creadas o NT8 sin responder).</p>}</div>
          <div><Label>Bridge Host</Label><Input value={form.bridge_host} onChange={e => setForm({...form, bridge_host: e.target.value})} /></div>
          <div><Label>Bridge Port</Label><Input type="number" value={form.bridge_port} onChange={e => setForm({...form, bridge_port: Number(e.target.value)})} /></div>
        </>
      )}

      <div><Label>Poll Interval (s)</Label><DecimalInput value={form.poll_interval} onChange={v => setForm({...form, poll_interval: v})} /></div>
      <div className="flex items-end gap-2 pb-1"><Checkbox checked={form.active} onChange={e => setForm({...form, active: e.target.checked})} /><Label>Activo</Label></div>
      {form.role === 'MASTER' && (
        <div className="flex items-end gap-2 pb-1">
          <input type="color" value={form.color} onChange={e => setForm({...form, color: e.target.value})} className="h-10 w-10 rounded border border-zinc-700 bg-zinc-800/50 cursor-pointer" />
          <Label>Color</Label>
        </div>
      )}
    </div>
  );
}

function AccountGroup({ label, accounts, editing, form, setForm, onTest, testing, testResults, copierRunning, allAccounts, loginOptions, manualLogin, setManualLogin, mt5Servers, manualServer, setManualServer, onEdit, onDeleteClick, onSave, onCancel, onBrowse }: {
  label: string;
  accounts: Account[];
  editing: Account | null;
  form: AccountForm;
  setForm: (f: AccountForm) => void;
  onTest: (id: string) => void;
  testing: string | null;
  testResults: Record<string, TestResult>;
  copierRunning: boolean;
  allAccounts: Account[];
  loginOptions: string[];
  manualLogin: boolean;
  setManualLogin: (v: boolean) => void;
  mt5Servers: string[];
  manualServer: boolean;
  setManualServer: (v: boolean) => void;
  onEdit: (a: Account) => void;
  onDeleteClick: (a: Account) => void;
  onSave: () => void;
  onCancel: () => void;
  onBrowse: () => void;
}) {
  if (accounts.length === 0) return null;
  return (
    <div className="space-y-2">
      <p className="text-xs font-medium uppercase tracking-wider text-zinc-600">{label}</p>
      {accounts.map(a => (
        <div key={a.id}>
          <Card className="flex items-center justify-between p-4">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <PlatformBadge platform={a.platform} />
                <Badge variant={a.role === 'MASTER' ? 'success' : 'warning'}>{a.role}</Badge>
              </div>
              <div>
                <p className="text-sm font-medium text-white">{a.name}</p>
                <p className="text-xs text-zinc-500">Cuenta: {a.login || '—'}{a.platform === 'MT5' && a.server ? <><span className="text-zinc-600"> · </span>{a.server}</> : null}</p>
                {a.role === 'SLAVE' && (a.linked_masters || []).length > 0 && (
                  <div className="flex items-center gap-1 mt-1 flex-wrap">
                    <span className="text-[10px] text-zinc-600">copia de</span>
                    {a.linked_masters.map(m => {
                      const masterColor = allAccounts.find(ac => ac.name === m)?.color || '#3b82f6';
                      return (
                      <span key={m} className="text-[10px] px-1.5 py-0.5 rounded font-medium" style={{backgroundColor: masterColor + '20', color: masterColor, border: '1px solid ' + masterColor + '40'}}>{m}</span>
                      );
                    })}
                  </div>
                )}
              </div>
              {!a.active && <Badge variant="danger">Inactivo</Badge>}
            </div>
            <div className="flex items-center gap-2">
              {testResults[a.id] && <Badge variant={testResults[a.id].success ? 'success' : 'danger'}>{testResults[a.id].message || (testResults[a.id].success ? 'OK' : 'Fallo')}</Badge>}
              <Button variant="outline" size="sm" onClick={() => onTest(a.id)} disabled={testing === a.id}><Wifi size={14} /> {testing === a.id ? '...' : 'Test'}</Button>
              <Button variant="ghost" size="sm" onClick={() => onEdit(a)} disabled={copierRunning} title={copierRunning ? 'Para el copiador para editar' : ''}><Edit3 size={14} /></Button>
              <Button variant="ghost" size="sm" onClick={() => onDeleteClick(a)} disabled={copierRunning} title={copierRunning ? 'Para el copiador para eliminar' : ''}><Trash2 size={14} className="text-red-400" /></Button>
            </div>
          </Card>
          {editing?.id === a.id && (
            <Card className="mt-2 p-4 space-y-4 border-emerald-500/30">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium text-white">Editar {a.name}</h3>
                <Button variant="ghost" size="sm" onClick={onCancel}><X size={14} /></Button>
              </div>
              <AccountFormBody form={form} setForm={setForm} editing={true} loginOptions={loginOptions} manualLogin={manualLogin} setManualLogin={setManualLogin} mt5Servers={mt5Servers} manualServer={manualServer} setManualServer={setManualServer} onBrowse={onBrowse} />
              <div className="flex gap-2 justify-end"><Button variant="ghost" onClick={onCancel}>Cancelar</Button><Button variant="primary" onClick={onSave}>Guardar</Button></div>
            </Card>
          )}
        </div>
      ))}
    </div>
  );
}

export default function AccountsPage() {
  const { accounts, copierStatus, fetchAccounts, showToast } = useStore();
  const copierRunning = copierStatus.running;
  const [editing, setEditing] = useState<Account | null>(null);
  const [form, setForm] = useState<AccountForm>(emptyForm);
  const [showNewForm, setShowNewForm] = useState(false);
  const [manualLogin, setManualLogin] = useState(false);
  const [testing, setTesting] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, TestResult>>({});
  const [deleteTarget, setDeleteTarget] = useState<Account | null>(null);
  const [defaultPort, setDefaultPort] = useState(5555);
  const [nt8Accounts, setNt8Accounts] = useState<string[]>([]);
  const [mt5Servers, setMt5Servers] = useState<string[]>([]);
  const [manualServer, setManualServer] = useState(false);
  const [browserOpen, setBrowserOpen] = useState(false);

  useEffect(() => {
    fetchAccounts();
    fetch('/api/system/bridge-config')
      .then(r => r.json())
      .then(d => { if (d.ok) setDefaultPort(d.port); })
      .catch(() => {});
    fetch('/api/servers?platform=MT5')
      .then(r => r.json())
      .then(d => { if (d.servers) setMt5Servers(d.servers.map((s: {name: string}) => s.name)); })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if ((editing || showNewForm) && !manualServer && form.platform === 'MT5' && form.server && !mt5Servers.includes(form.server)) {
      setManualServer(true);
    }
  }, [form.server, form.platform, mt5Servers, manualServer, editing, showNewForm]);

  const fetchNt8Accounts = async (host: string, port: number) => {
    try {
      const r = await api.get<{ok: boolean; accounts: string[]}>(`/accounts/nt8-available?host=${encodeURIComponent(host)}&port=${port}`);
      setNt8Accounts(r.ok ? r.accounts : []);
    } catch { setNt8Accounts([]); }
  };

  useEffect(() => {
    if (!showNewForm && !editing) return;
    if (form.platform === 'MT5') { setNt8Accounts([]); return; }
    const t = setTimeout(() => fetchNt8Accounts(form.bridge_host, form.bridge_port), 300);
    return () => clearTimeout(t);
  }, [form.bridge_host, form.bridge_port, form.platform, showNewForm, editing]);

  const usedLogins = useMemo(
    () => new Set(accounts.filter(a => (editing ? a.id !== editing.id : true)).map(a => String(a.login))),
    [accounts, editing]
  );

  const loginOptions = useMemo(() => {
    const opts = nt8Accounts.filter(a => !usedLogins.has(a));
    if (editing && editing.login && !opts.includes(String(editing.login))) return [String(editing.login), ...opts];
    return opts;
  }, [nt8Accounts, usedLogins, editing]);

  const resetForm = () => { setForm({ ...emptyForm, bridge_port: defaultPort }); setEditing(null); setShowNewForm(false); setManualLogin(false); setManualServer(false); };

  const handleSubmit = async () => {
    if (form.platform === 'MT5' && !editing && !form.password) {
      showToast('La contraseña es obligatoria para cuentas MT5', 'error');
      return;
    }
    try {
      if (editing) {
        await api.put(`/accounts/${editing.id}`, form);
        showToast('Cuenta actualizada', 'ok');
      } else {
        await api.post('/accounts', form);
        showToast('Cuenta creada', 'ok');
      }
      resetForm(); fetchAccounts();
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : 'Error', 'error');
    }
  };

  const handleDelete = async (id: string) => {
    try { await api.delete(`/accounts/${id}`); showToast('Eliminada', 'ok'); fetchAccounts(); setDeleteTarget(null); }
    catch (e: unknown) { showToast(e instanceof Error ? e.message : 'Error', 'error'); }
  };

  const handleTest = async (id: string) => {
    setTesting(id);
    try {
      const r = await api.post<TestResult>(`/accounts/${id}/test`);
      setTestResults(prev => ({ ...prev, [id]: r }));
      showToast(r.success ? 'Conexion OK' : r.message, r.success ? 'ok' : 'error');
    } catch (e: unknown) { showToast(e instanceof Error ? e.message : 'Error', 'error'); }
    setTesting(null);
  };

  const editAccount = (a: Account) => {
    setEditing(a);
    setShowNewForm(false);
    setManualLogin(false);
    setManualServer(false);
    setForm({
      name: a.name, role: a.role, platform: a.platform || 'NT8', login: a.login,
      password: '', bridge_host: a.bridge_host, bridge_port: a.bridge_port,
      server: a.server || '', terminal_path: a.terminal_path || '',
      filling_mode: a.filling_mode || '',
      poll_interval: a.poll_interval, active: a.active, color: a.color || '#3b82f6',
    });
  };

  const openNew = (role: Account['role']) => { setEditing(null); setForm({ ...emptyForm, role, bridge_port: defaultPort }); setShowNewForm(true); setManualLogin(false); setManualServer(false); };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div><h2 className="text-xl font-bold text-white">Cuentas</h2><p className="text-sm text-zinc-500">{accounts.length} cuentas · <span className="text-orange-400">NT8</span> {accounts.filter(a => (a.platform || 'NT8') === 'NT8').length} · <span className="text-sky-400">MT5</span> {accounts.filter(a => a.platform === 'MT5').length}</p></div>
        <div className="flex gap-2">
          <Button variant="primary" onClick={() => openNew('MASTER')} disabled={copierRunning} title={copierRunning ? 'Para el copiador para crear cuentas' : ''}><Plus size={14} /> Master</Button>
          <Button variant="outline" onClick={() => openNew('SLAVE')} disabled={copierRunning} title={copierRunning ? 'Para el copiador para crear cuentas' : ''}><Plus size={14} /> Slave</Button>
        </div>
      </div>

      {showNewForm && (
        <Card className="p-4 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-white">Nueva Cuenta</h3>
            <Button variant="ghost" size="sm" onClick={resetForm}><X size={14} /></Button>
          </div>
          <AccountFormBody form={form} setForm={setForm} editing={false} loginOptions={loginOptions} manualLogin={manualLogin} setManualLogin={setManualLogin} mt5Servers={mt5Servers} manualServer={manualServer} setManualServer={setManualServer} onBrowse={() => setBrowserOpen(true)} />
          <div className="flex gap-2 justify-end"><Button variant="ghost" onClick={resetForm}>Cancelar</Button><Button variant="primary" onClick={handleSubmit}>Crear</Button></div>
        </Card>
      )}

      <div className="space-y-6">
        <AccountGroup
          label="Masters"
          accounts={accounts.filter(a => a.role === 'MASTER')}
          editing={editing}
          form={form}
          setForm={setForm}
          onTest={handleTest}
          testing={testing}
          testResults={testResults}
          copierRunning={copierRunning}
          allAccounts={accounts}
          loginOptions={loginOptions}
          manualLogin={manualLogin}
          setManualLogin={setManualLogin}
          mt5Servers={mt5Servers}
          manualServer={manualServer}
          setManualServer={setManualServer}
          onEdit={editAccount}
          onDeleteClick={setDeleteTarget}
          onSave={handleSubmit}
          onCancel={resetForm}
          onBrowse={() => setBrowserOpen(true)}
        />
        {accounts.some(a => a.role === 'MASTER') && accounts.some(a => a.role === 'SLAVE') && (
          <div className="border-t border-zinc-800" />
        )}
        <AccountGroup
          label="Slaves"
          accounts={accounts.filter(a => a.role === 'SLAVE')}
          editing={editing}
          form={form}
          setForm={setForm}
          onTest={handleTest}
          testing={testing}
          testResults={testResults}
          copierRunning={copierRunning}
          allAccounts={accounts}
          loginOptions={loginOptions}
          manualLogin={manualLogin}
          setManualLogin={setManualLogin}
          mt5Servers={mt5Servers}
          manualServer={manualServer}
          setManualServer={setManualServer}
          onEdit={editAccount}
          onDeleteClick={setDeleteTarget}
          onSave={handleSubmit}
          onCancel={resetForm}
          onBrowse={() => setBrowserOpen(true)}
        />
      </div>

      <FileBrowser open={browserOpen} onClose={() => setBrowserOpen(false)} onSelect={(path) => { setForm({ ...form, terminal_path: path }); setBrowserOpen(false); }} title="Seleccionar terminal64.exe" />

      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <Card className="w-[400px] p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-red-400">Eliminar Cuenta</h3>
              <button onClick={() => setDeleteTarget(null)} className="text-zinc-500 hover:text-white"><X size={18} /></button>
            </div>
            <p className="text-sm text-zinc-400 mb-2">Vas a eliminar permanentemente:</p>
            <p className="text-sm font-medium text-white mb-1">{deleteTarget.name}</p>
            <p className="text-xs text-zinc-500 mb-4">({deleteTarget.role} · {deleteTarget.platform || 'NT8'}) Cuenta: {deleteTarget.login || '—'}</p>
            <p className="text-xs text-red-400 mb-4">Esta accion no se puede deshacer.</p>
            <div className="flex gap-2 justify-end">
              <Button variant="ghost" size="sm" onClick={() => setDeleteTarget(null)}>Cancelar</Button>
              <Button variant="danger" size="sm" onClick={() => handleDelete(deleteTarget.id)}>Eliminar</Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}