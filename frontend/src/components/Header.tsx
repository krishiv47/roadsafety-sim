import React from 'react';
import { Map, LayoutGrid, BarChart3, BrainCircuit } from 'lucide-react';
import { ViewType } from '../types';

interface HeaderProps {
  currentView: ViewType;
  setView: (v: ViewType) => void;
  wsConnected: boolean;
  busCount: number;
  criticalCount: number;
  activeCount: number;
}

export const Header: React.FC<HeaderProps> = ({
  currentView, setView, wsConnected, busCount, criticalCount, activeCount,
}) => (
  <header
    style={{
      flexShrink: 0,
      height: 56,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 20px',
      background: '#0b1220',
      borderBottom: '1px solid rgba(255,255,255,0.07)',
      boxShadow: '0 2px 20px rgba(0,0,0,0.3)',
      zIndex: 50,
    }}
  >
    {/* ── Left ─────────────────────────────────── */}
    <div className="flex items-center gap-4">
      {/* Logo */}
      <button
        onClick={() => setView('map')}
        className="flex items-center gap-2 select-none focus:outline-none"
      >
        <div className="w-7 h-7 rounded-lg flex items-center justify-center"
          style={{ background: 'linear-gradient(135deg,#f97316,#ea580c)', boxShadow: '0 2px 8px rgba(249,115,22,0.35)' }}>
          <span className="material-symbols-outlined text-white" style={{ fontSize: 16, fontVariationSettings: "'wght' 700" }}>security</span>
        </div>
        <span className="font-bold text-sm tracking-tight" style={{ color: '#f1f5f9' }}>
          CIVIC<span style={{ color: '#f97316' }}>_AI</span>
        </span>
      </button>

      {/* Divider */}
      <div className="w-px h-5" style={{ background: 'rgba(255,255,255,0.08)' }} />

      {/* View toggle */}
      <div className="flex items-center p-0.5 rounded-lg gap-0.5"
        style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.07)' }}>
        {([
          { v: 'map' as ViewType,       label: 'Live Map',   Icon: Map },
          { v: 'kanban' as ViewType,    label: 'Operations', Icon: LayoutGrid },
          { v: 'analytics' as ViewType, label: 'Analytics',  Icon: BarChart3 },
          { v: 'copilot' as ViewType,   label: 'Copilot',    Icon: BrainCircuit },
        ]).map(({ v, label, Icon }) => (
          <button
            key={v}
            onClick={() => setView(v)}
            className="px-3 py-1.5 rounded-md text-xs font-medium transition-all duration-150 cursor-pointer flex items-center gap-1.5"
            style={currentView === v ? {
              background: 'linear-gradient(135deg,#ea580c,#f97316)',
              color: '#fff',
              boxShadow: '0 2px 8px rgba(234,88,12,0.4)',
            } : { color: 'rgba(255,255,255,0.45)' }}
          >
            <Icon className="w-3.5 h-3.5" />
            {label}
          </button>
        ))}
      </div>

      {/* Stats — hidden on small screens */}
      <div className="hidden lg:flex items-center gap-2">
        {[
          { icon: 'radio_button_checked', label: 'Active', value: activeCount, color: '#34d399' },
          { icon: 'warning', label: 'Critical', value: criticalCount, color: '#f87171' },
          { icon: 'directions_bus', label: 'Buses', value: busCount, color: '#fb923c' },
        ].map(({ icon, label, value, color }) => (
          <div key={label} className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs"
            style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.06)' }}>
            <span className="material-symbols-outlined" style={{ fontSize: 13, color }}>{icon}</span>
            <span style={{ color: 'rgba(255,255,255,0.4)' }}>{label}</span>
            <span className="font-semibold tabular-nums" style={{ color: 'rgba(255,255,255,0.85)' }}>
              {value}
            </span>
          </div>
        ))}
      </div>
    </div>

    {/* ── Right ────────────────────────────────── */}
    <div className="flex items-center gap-3">
      <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium"
        style={wsConnected
          ? { background: 'rgba(52,211,153,0.1)', color: '#34d399', border: '1px solid rgba(52,211,153,0.2)' }
          : { background: 'rgba(248,113,113,0.1)', color: '#f87171', border: '1px solid rgba(248,113,113,0.2)' }}>
        <div className={`w-1.5 h-1.5 rounded-full ${wsConnected ? 'animate-pulse' : ''}`}
          style={{ background: wsConnected ? '#34d399' : '#f87171' }} />
        {wsConnected ? 'Live' : 'Offline'}
      </div>

      <button className="material-symbols-outlined cursor-pointer transition-colors duration-150"
        style={{ fontSize: 18, color: 'rgba(255,255,255,0.35)' }}
        onMouseEnter={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.75)')}
        onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.35)')}>
        notifications
      </button>

      <div className="w-7 h-7 rounded-full flex items-center justify-center text-white text-xs font-semibold cursor-pointer select-none"
        style={{ background: 'linear-gradient(135deg,#ea580c,#c2410c)', boxShadow: '0 2px 8px rgba(234,88,12,0.35)' }}>
        AA
      </div>
    </div>
  </header>
);
