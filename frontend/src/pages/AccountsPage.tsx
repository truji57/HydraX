import { useEffect, useState } from 'react';
import { Button } from '../components/ui/button';
import { Input, Select, Label, Checkbox } from '../components/ui/input';
import { Card } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { FileBrowser } from '../components/ui/filebrowser';
import { api } from '../lib/api';
import { useStore } from '../store';
import type { Account, AccountForm, TestResult } from '../types';
import { Plus, Trash2, Wifi, X, Edit3, FolderOpen } from 'lucide-react';

const emptyForm: AccountForm = {
  name: '',
  role: 'MASTER',
  login: 0,
  password: '',
  server: '',
  terminal_path: 'C:/Program Files/MetaTrader 5/terminal64.exe',
  poll_interval: 0.5,
  active: true,
};

export default function AccountsPage() {
  const { accounts, fetchAccounts, showToast } = useStore();
  const [editing, setEditing] = useState<Account | null>(null);
  const [form, setForm] = useState<AccountForm>(emptyForm);
  const [showForm, setShowForm] = useState(false);
  const [testing, setTesting] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, TestResult>>({});
  const [fileBrowserOpen, setFileBrowserOpen] = useState(false);
  const [serverList, setServerList] = useState<string[]>([]);

  useEffect(() => {
    fetchAccounts();
    api.get<{ servers: string[] }>('/servers').then((d) => setServerList(d.servers)).catch(() => {});
  }, []);

  const resetForm = () => {
    setForm(emptyForm);
    setEditing(null);
    setShowForm(false);
  };

  const handleSubmit = async () => {
    try {
      if (editing) {
        await api.put(`/accounts/${editing.id}`, {
          ...form,
          password: form.password || undefined,
        });
        showToast('Cuenta actualizada', 'ok');
      } else {
        await api.post('/accounts', form);
        showToast('Cuenta creada', 'ok');
      }
      resetForm();
      fetchAccounts();
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : 'Error al guardar', 'error');
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Eliminar esta cuenta?')) return;
    try {
      await api.delete(`/accounts/${id}`);
      showToast('Cuenta eliminada', 'ok');
      fetchAccounts();
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : 'Error al eliminar', 'error');
    }
  };

  const handleTest = async (id: string) => {
    setTesting(id);
    try {
      const result = await api.post<TestResult>(`/accounts/${id}/test`);
      setTestResults((prev) => ({ ...prev, [id]: result }));
      showToast(result.success ? 'Conexión OK' : `Error: ${result.message}`, result.success ? 'ok' : 'error');
    } catch (e: unknown) {
      showToast(e instanceof Error ? e.message : 'Error en test', 'error');
    }
    setTesting(null);
  };

  const editAccount = (a: Account) => {
    setEditing(a);
    setForm({
      name: a.name,
      role: a.role,
      login: a.login,
      password: '',
      server: a.server,
      terminal_path: a.terminal_path,
      poll_interval: a.poll_interval,
      active: a.active,
    });
    setShowForm(true);
  };

  const openNew = (role: Account['role']) => {
    setEditing(null);
    setForm({ ...emptyForm, role });
    setShowForm(true);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white">Gestión de Cuentas</h2>
          <p className="text-sm text-zinc-500">{accounts.length} cuentas configuradas</p>
        </div>
        <div className="flex gap-2">
          <Button variant="primary" onClick={() => openNew('MASTER')}>
            <Plus size={14} /> Master
          </Button>
          <Button variant="outline" onClick={() => openNew('SLAVE')}>
            <Plus size={14} /> Slave
          </Button>
        </div>
      </div>

      {showForm && (
        <Card className="p-4 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-white">
              {editing ? 'Editar' : 'Nueva'} Cuenta
            </h3>
            <Button variant="ghost" size="sm" onClick={resetForm}>
              <X size={14} />
            </Button>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>Nombre</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </div>
            <div>
              <Label>Rol</Label>
              <Select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as 'MASTER' | 'SLAVE' })}>
                <option value="MASTER">MASTER</option>
                <option value="SLAVE">SLAVE</option>
              </Select>
            </div>
            <div>
              <Label>Login</Label>
              <Input type="number" value={form.login || ''} onChange={(e) => setForm({ ...form, login: Number(e.target.value) })} />
            </div>
            <div>
              <Label>Password</Label>
              <Input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} placeholder={editing ? 'Dejar vacío para no cambiar' : ''} />
            </div>
            <div>
              <Label>Servidor</Label>
              <Select
                value={form.server}
                onChange={(e) => setForm({ ...form, server: e.target.value })}
              >
                <option value="">Seleccionar servidor...</option>
                {serverList.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
                {form.server && !serverList.includes(form.server) && (
                  <option value={form.server}>{form.server}</option>
                )}
              </Select>
            </div>
            <div>
              <Label>Ruta terminal64.exe</Label>
              <div className="flex gap-2">
                <Input
                  value={form.terminal_path}
                  onChange={(e) => setForm({ ...form, terminal_path: e.target.value })}
                  className="flex-1 font-mono text-xs"
                  placeholder="C:/Program Files/MetaTrader 5/terminal64.exe"
                />
                <Button variant="outline" size="sm" onClick={() => setFileBrowserOpen(true)} className="shrink-0">
                  <FolderOpen size={14} />
                </Button>
              </div>
            </div>
            <div>
              <Label>Poll Interval (s)</Label>
              <Input type="number" step="0.1" value={form.poll_interval} onChange={(e) => setForm({ ...form, poll_interval: Number(e.target.value) })} />
            </div>
            <div className="flex items-end gap-2 pb-1">
              <Checkbox checked={form.active} onChange={(e) => setForm({ ...form, active: e.target.checked })} />
              <Label>Activo</Label>
            </div>
          </div>
          <div className="flex gap-2 justify-end">
            <Button variant="ghost" onClick={resetForm}>Cancelar</Button>
            <Button variant="primary" onClick={handleSubmit}>
              {editing ? 'Guardar Cambios' : 'Crear Cuenta'}
            </Button>
          </div>
        </Card>
      )}

      <div className="space-y-2">
        {accounts.map((a) => (
          <Card key={a.id} className="flex items-center justify-between p-4">
            <div className="flex items-center gap-4">
              <Badge variant={a.role === 'MASTER' ? 'success' : 'warning'}>{a.role}</Badge>
              <div>
                <p className="text-sm font-medium text-white">{a.name}</p>
                <p className="text-xs text-zinc-500">
                  {a.login}@{a.server}
                </p>
              </div>
              {!a.active && <Badge variant="danger">Inactivo</Badge>}
            </div>
            <div className="flex items-center gap-2">
              {testResults[a.id] && (
                <Badge variant={testResults[a.id].success ? 'success' : 'danger'}>
                  {testResults[a.id].success ? `Balance: ${testResults[a.id].balance}` : 'Fallo'}
                </Badge>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleTest(a.id)}
                disabled={testing === a.id}
              >
                <Wifi size={14} /> {testing === a.id ? '...' : 'Test'}
              </Button>
              <Button variant="ghost" size="sm" onClick={() => editAccount(a)}>
                <Edit3 size={14} />
              </Button>
              <Button variant="ghost" size="sm" onClick={() => handleDelete(a.id)}>
                <Trash2 size={14} className="text-red-400" />
              </Button>
            </div>
          </Card>
        ))}
      </div>

      <FileBrowser
        open={fileBrowserOpen}
        onClose={() => setFileBrowserOpen(false)}
        onSelect={(path) => setForm({ ...form, terminal_path: path })}
        title="Seleccionar terminal64.exe"
      />
    </div>
  );
}
