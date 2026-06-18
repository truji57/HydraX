import { create } from 'zustand';
import { api } from '../lib/api';
import type { Account, CopierStatus } from '../types';

interface LogEntry {
  timestamp: string;
  message: string;
  type: string;
}

interface AppState {
  copierStatus: CopierStatus;
  accounts: Account[];
  logs: LogEntry[];
  toast: { message: string; type: 'ok' | 'error' | 'info' } | null;

  fetchStatus: () => Promise<void>;
  fetchAccounts: () => Promise<void>;
  setStatus: (s: CopierStatus) => void;
  addLog: (entry: LogEntry) => void;
  showToast: (message: string, type?: 'ok' | 'error' | 'info') => void;
  clearToast: () => void;
}

const MAX_LOGS = 100;

export const useStore = create<AppState>((set, get) => ({
  copierStatus: {
    running: false,
    uptime_seconds: null,
    active_masters: 0,
    active_slaves: 0,
    total_positions: 0,
    last_error: null,
  },
  accounts: [],
  logs: [],
  toast: null,

  fetchStatus: async () => {
    try {
      const s = await api.get<CopierStatus>('/copier/status');
      set({ copierStatus: s });
    } catch {}
  },

  fetchAccounts: async () => {
    try {
      const list = await api.get<Account[]>('/accounts');
      set({ accounts: list });
    } catch {}
  },

  setStatus: (s) => set({ copierStatus: s }),

  addLog: (entry) => {
    set((state) => ({
      logs: [entry, ...state.logs].slice(0, MAX_LOGS),
    }));
  },

  showToast: (message, type = 'info') => {
    set({ toast: { message, type } });
    setTimeout(() => get().clearToast(), 4000);
  },

  clearToast: () => set({ toast: null }),
}));
