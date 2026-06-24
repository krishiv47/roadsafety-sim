import React from 'react';
import { SimEvent, SEV_TO_CAT, STATUS_LABEL } from '../types';
import { EventIcon } from '../icons';

interface Props {
  events: SimEvent[];
  selectedEvent: SimEvent | null;
  setSelectedEvent: (e: SimEvent) => void;
  kanbanFilter: 'All' | 'Critical' | 'Routine';
  selectedAgency: string;
  onAcknowledge: (id: string) => void;
  onComplete: (id: string) => void;
  searchQuery: string;
}

const SEV_COL: Record<string, string> = {
  critical: '#ef4444', high: '#f97316', medium: '#eab308', low: '#22c55e',
};
// selectedAgency holds assignment keys directly: police | ambulance | road_authority | municipal
const AGENCY_KEYS = new Set(['police', 'ambulance', 'road_authority', 'municipal']);

export const KanbanBoard: React.FC<Props> = ({
  events, selectedEvent, setSelectedEvent,
  kanbanFilter, selectedAgency, onAcknowledge, onComplete, searchQuery,
}) => {
  const statusOf = (ev: SimEvent) => STATUS_LABEL[ev.overall_status ?? 'unassigned'] ?? 'New';

  const filtered = events.filter(ev => {
    const cat = SEV_TO_CAT[ev.severity];
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      if (!ev.id.toLowerCase().includes(q) && !ev.type.toLowerCase().includes(q) && !ev.detected_by.toLowerCase().includes(q)) return false;
    }
    if (kanbanFilter === 'Critical' && cat !== 'Critical') return false;
    if (kanbanFilter === 'Routine' && cat === 'Critical') return false;
    if (AGENCY_KEYS.has(selectedAgency)) {
      if (!ev.assignments?.[selectedAgency]?.assigned) return false;
    }
    return true;
  });

  const newCards  = filtered.filter(e => statusOf(e) === 'New');
  const progCards = filtered.filter(e => statusOf(e) === 'In Progress');
  const doneCards = filtered.filter(e => statusOf(e) === 'Completed');

  const col = (
    title: string,
    badge: string,
    badgeCol: string,
    icon: string,
    cards: SimEvent[],
    colType: 'new' | 'prog' | 'done',
  ) => (
    <div className="flex-1 flex flex-col min-w-0 overflow-hidden rounded-xl"
      style={{ background: '#0e1828', border: '1px solid rgba(255,255,255,0.07)', minWidth: 240 }}>
      {/* Column header */}
      <div className="flex items-center gap-2 px-3 py-2.5 flex-shrink-0"
        style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <span className="material-symbols-outlined text-sm" style={{ color: badgeCol }}>{icon}</span>
        <span className="text-xs font-bold uppercase tracking-wider" style={{ color: 'rgba(255,255,255,0.55)' }}>{title}</span>
        <span className="ml-auto text-xs font-bold px-1.5 py-0.5 rounded-md tabular-nums"
          style={{ background: `${badgeCol}18`, color: badgeCol }}>{cards.length}</span>
      </div>

      {/* Cards scroll */}
      <div className="flex-1 overflow-y-auto p-2.5 space-y-2">
        {cards.length === 0 && (
          <div className="flex flex-col items-center py-10 gap-2 rounded-xl"
            style={{ border: '1.5px dashed rgba(255,255,255,0.07)' }}>
            <span className="material-symbols-outlined text-2xl" style={{ color: 'rgba(255,255,255,0.1)' }}>
              {colType === 'done' ? 'check_circle' : colType === 'prog' ? 'build' : 'inbox'}
            </span>
            <p className="text-xs" style={{ color: 'rgba(255,255,255,0.2)' }}>
              {colType === 'done' ? 'None resolved' : colType === 'prog' ? 'Nothing active' : 'Queue empty'}
            </p>
          </div>
        )}

        {cards.map(ev => {
          const sev = ev.severity;
          const col = SEV_COL[sev] ?? '#fb923c';
          const sel = selectedEvent?.id === ev.id;
          const conf = Math.round(ev.confidence * 100);

          return (
            <div key={ev.id} onClick={() => setSelectedEvent(ev)}
              className="rounded-xl p-3.5 cursor-pointer transition-all duration-150"
              style={{
                background: sel ? 'rgba(249,115,22,0.1)' : 'rgba(255,255,255,0.03)',
                border: sel ? '1px solid rgba(249,115,22,0.35)' : '1px solid rgba(255,255,255,0.06)',
                borderLeft: `3px solid ${col}`,
                opacity: colType === 'done' ? 0.6 : 1,
              }}>
              {/* Header row */}
              <div className="flex items-start justify-between gap-2 mb-2">
                <div className="flex items-center gap-1.5 min-w-0">
                  <EventIcon type={ev.type} size={15} color={col} />
                  <span className="text-xs font-semibold capitalize truncate" style={{ color: '#dde6f0' }}>
                    {ev.type.replace(/_/g, ' ')}
                  </span>
                </div>
                <span className="text-xs px-1.5 py-0.5 rounded-md font-medium flex-shrink-0"
                  style={{ background: `${col}15`, color: col }}>{sev}</span>
              </div>

              {/* Confidence */}
              <div className="flex items-center gap-2 mb-2.5">
                <div className="flex-1 h-1 rounded-full" style={{ background: 'rgba(255,255,255,0.06)' }}>
                  <div className="h-1 rounded-full transition-all duration-700" style={{ width: `${conf}%`, background: col }} />
                </div>
                <span className="text-xs tabular-nums font-medium" style={{ color: col }}>{conf}%</span>
              </div>

              {/* Meta */}
              <div className="flex items-center justify-between text-xs" style={{ color: 'rgba(255,255,255,0.3)' }}>
                <span>{ev.age_s < 60 ? `${ev.age_s}s ago` : `${Math.floor(ev.age_s/60)}m ago`}</span>
                <span className="font-mono text-xs">{ev.id}</span>
              </div>

              {/* Actions */}
              {colType !== 'done' && (
                <div className="flex gap-1.5 mt-2.5 pt-2.5" style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}>
                  {colType === 'new' && (
                    <button onClick={e => { e.stopPropagation(); onAcknowledge(ev.id); }}
                      className="flex-1 py-1.5 rounded-lg text-xs font-medium transition-all duration-150 cursor-pointer"
                      style={{ background: 'rgba(249,115,22,0.15)', color: '#fb923c', border: '1px solid rgba(249,115,22,0.2)' }}
                      onMouseEnter={e => (e.currentTarget.style.background = 'rgba(249,115,22,0.25)')}
                      onMouseLeave={e => (e.currentTarget.style.background = 'rgba(249,115,22,0.15)')}>
                      Acknowledge
                    </button>
                  )}
                  <button onClick={e => { e.stopPropagation(); onComplete(ev.id); }}
                    className="flex-1 py-1.5 rounded-lg text-xs font-medium transition-all duration-150 cursor-pointer"
                    style={{ background: 'rgba(52,211,153,0.1)', color: '#34d399', border: '1px solid rgba(52,211,153,0.2)' }}
                    onMouseEnter={e => (e.currentTarget.style.background = 'rgba(52,211,153,0.2)')}
                    onMouseLeave={e => (e.currentTarget.style.background = 'rgba(52,211,153,0.1)')}>
                    {colType === 'prog' ? 'Complete' : 'Resolve'}
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );

  return (
    <div className="flex-grow flex flex-col overflow-hidden">
      {/* Sub-header bar */}
      <div className="h-10 flex-shrink-0 flex items-center justify-between px-5"
        style={{ borderBottom: '1px solid rgba(255,255,255,0.07)', background: '#0c1422' }}>
        <div className="flex items-center gap-2.5">
          <span className="material-symbols-outlined text-sm" style={{ color: '#f97316' }}>view_kanban</span>
          <span className="text-xs font-semibold" style={{ color: 'rgba(255,255,255,0.6)' }}>LIVE COMMAND</span>
          <span className="text-xs px-2 py-0.5 rounded-full tabular-nums"
            style={{ background: 'rgba(249,115,22,0.12)', color: '#fb923c', border: '1px solid rgba(249,115,22,0.2)' }}>
            {filtered.length}
          </span>
        </div>
        <div className="flex items-center gap-1.5 text-xs" style={{ color: '#34d399' }}>
          <div className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: '#34d399' }} />
          Auto-sync
        </div>
      </div>

      {/* Kanban columns */}
      <div className="flex-1 flex overflow-hidden" style={{ background: '#080f1c' }}>
        <div className="flex flex-1 gap-4 p-4 overflow-x-auto">
          <div className="flex-1 flex gap-4 min-w-0" style={{ minWidth: 680 }}>
            {col('New Alerts',    'new',  '#f87171', 'inbox',         newCards,  'new')}
            {col('In Progress',   'prog', '#fbbf24', 'build',         progCards, 'prog')}
            {col('Resolved',      'done', '#34d399', 'check_circle',  doneCards, 'done')}
          </div>
        </div>
      </div>
    </div>
  );
};
