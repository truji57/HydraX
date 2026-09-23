import type { RiskMode, Platform } from '../types';

export type TemplateKind = 'NT8' | 'MT5' | 'GNRL';

export function templateKind(mode: RiskMode | string): TemplateKind {
  if (mode === 'FIXED_CONTRACTS') return 'NT8';
  if (mode === 'FIXED_LOTS') return 'MT5';
  return 'GNRL';
}

export const KIND_STYLE: Record<TemplateKind, { label: string; color: string; bg: string; border: string }> = {
  NT8: { label: 'NT8', color: '#fb923c', bg: '#f9731622', border: '#f9731655' },
  MT5: { label: 'MT5', color: '#38bdf8', bg: '#38bdf81f', border: '#38bdf855' },
  GNRL: { label: 'GNRL', color: '#a3a3a3', bg: '#52525222', border: '#52525255' },
};

export const riskLabels: Record<string, string> = {
  FIXED: 'Contratos Fijos',
  FIXED_CONTRACTS: 'Contratos Fijos',
  FIXED_LOTS: 'Lotes Fijos',
  RISK_PERCENT: '% Riesgo',
  RISK_USD: 'Riesgo USD',
  RATIO: 'Multiplicador',
  BALANCE_PROP: 'Prop. Balance',
};

export const GENERAL_MODES: RiskMode[] = ['RISK_PERCENT', 'RISK_USD', 'RATIO', 'BALANCE_PROP'];

export function fixedModeFor(platform: Platform): 'FIXED_CONTRACTS' | 'FIXED_LOTS' {
  return platform === 'MT5' ? 'FIXED_LOTS' : 'FIXED_CONTRACTS';
}

export function fixedLabelFor(platform: Platform): string {
  return platform === 'MT5' ? 'Lotes Fijos' : 'Contratos Fijos';
}

export function maxLabelFor(platform: Platform): string {
  return platform === 'MT5' ? 'Max Lotes' : 'Max Contratos';
}

export function templateKindBadge(mode: RiskMode | string) {
  const cls = KIND_STYLE[templateKind(mode)];
  return {
    label: cls.label,
    style: { backgroundColor: cls.bg, color: cls.color, border: `1px solid ${cls.border}` },
  };
}