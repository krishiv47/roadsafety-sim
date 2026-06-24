import React, { useState } from 'react';
import {
  ShieldAlert, CheckCircle2, RefreshCw, AlertTriangle, Save, X, Zap,
  ShieldCheck, Ambulance, Construction, Building2, Building,
} from 'lucide-react';
import { SimEvent, AUTH_META, PRI_LABEL } from '../types';
import { EventIcon, stripEmoji } from '../icons';
import { setPriority, assignEvent, unassignEvent, authWork, saveNote } from '../data';

interface Toast { id: string; title: string; message: string; type: 'info' | 'success' | 'warning'; }

interface Props {
  selectedEvent: SimEvent | null;
  onClose: () => void;
  onUpdatePriority: (id: string, cat: string) => void;
  onToggleUnit: (id: string, agency: string) => void;
  onDeployFieldCommand: (id: string) => void;
  addToast: (t: Toast) => void;
}

const SEV_COL: Record<string, string> = { critical:'#ef4444', high:'#f97316', medium:'#eab308', low:'#22c55e' };
const PRI_COL: Record<string, string> = { p1:'#ef4444', p2:'#f97316', p3:'#eab308', p4:'#22c55e' };
const VER_META: Record<string, { Icon: React.ElementType; color: string }> = {
  fully_verified:     { Icon: CheckCircle2,  color: '#34d399' },
  partially_verified: { Icon: RefreshCw,     color: '#60a5fa' },
  unverified:         { Icon: AlertTriangle, color: '#fbbf24' },
};
const AUTH_ICON: Record<string, { Icon: React.ElementType; color: string }> = {
  police:         { Icon: ShieldCheck,  color: '#3B82F6' },
  ambulance:      { Icon: Ambulance,    color: '#EF4444' },
  road_authority: { Icon: Construction, color: '#F97316' },
  municipal:      { Icon: Building2,    color: '#22C55E' },
};
const STATUS_COL: Record<string, string> = {
  new:'#94a3b8', acknowledged:'#60a5fa', in_progress:'#fb923c', completed:'#34d399', unassigned:'#475569',
};
const ACT_NEXT: Record<string, string> = {
  unassigned:'acknowledge', new:'acknowledge', acknowledged:'start', in_progress:'complete', completed:'complete',
};

const panel = 'rounded-xl p-4 space-y-2.5';
const panelStyle = { background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' };
const labelStyle = { color: 'rgba(255,255,255,0.35)', fontSize: 11, fontWeight: 600, textTransform: 'uppercase' as const, letterSpacing: '0.06em' };
const valStyle = { color: '#dde6f0', fontSize: 12, fontWeight: 500 };

export const DetailPanel: React.FC<Props> = ({
  selectedEvent, onClose, onUpdatePriority, onToggleUnit, onDeployFieldCommand, addToast,
}) => {
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);

  // Collapse panel entirely when nothing is selected — no wasted space
  if (!selectedEvent) return null;

  const wrap = (children: React.ReactNode) => (
    <aside className="flex-shrink-0 flex flex-col h-full overflow-hidden slide-right"
      style={{
        width: 340,
        background: '#0c1422',
        borderLeft: '1px solid rgba(255,255,255,0.07)',
        boxShadow: '-8px 0 32px rgba(0,0,0,0.25)',
      }}>
      {children}
    </aside>
  );

  const ev   = selectedEvent;
  const sev  = ev.severity;
  const col  = SEV_COL[sev] ?? '#fb923c';
  const conf = Math.round(ev.confidence * 100);
  const isEmg = ev.emergency && ev.emergency !== 'resolved';
  const tl = (ev.full_timeline ?? ev.timeline ?? []).slice().sort((a, b) => b.ts - a.ts);
  const firstAssignedAuth = ev.eligible_authorities?.find(a => ev.assignments?.[a]?.assigned) ?? null;

  const handlePriority = async (level: string) => {
    try { await setPriority(ev.id, level); onUpdatePriority(ev.id, level); }
    catch (e) { addToast({ id: String(Date.now()), title: 'Error', message: String(e), type: 'warning' }); }
  };

  const handleAssign = async (auth: string) => {
    try { await assignEvent(ev.id, auth); addToast({ id: String(Date.now()), title: 'Assigned', message: `${AUTH_META[auth]?.label} assigned`, type: 'success' }); }
    catch (e) { addToast({ id: String(Date.now()), title: 'Error', message: String(e), type: 'warning' }); }
  };

  const handleUnassign = async (auth: string) => {
    try { await unassignEvent(ev.id, auth); }
    catch (e) { addToast({ id: String(Date.now()), title: 'Error', message: String(e), type: 'warning' }); }
  };

  const handleAction = async (auth: string, status: string) => {
    const action = ACT_NEXT[status ?? 'unassigned'];
    try { await authWork(auth, ev.id, action); onToggleUnit(ev.id, auth); }
    catch (e) { addToast({ id: String(Date.now()), title: 'Error', message: String(e), type: 'warning' }); }
  };

  const handleSaveNote = async () => {
    const auth = firstAssignedAuth;
    if (!auth) { addToast({ id: String(Date.now()), title: 'Not assigned', message: 'Assign to an authority first', type: 'warning' }); return; }
    setSaving(true);
    try {
      await saveNote(auth, ev.id, notes);
      addToast({ id: String(Date.now()), title: 'Note saved', message: '', type: 'success' });
    } catch (e) { addToast({ id: String(Date.now()), title: 'Error', message: String(e), type: 'warning' }); }
    finally { setSaving(false); }
  };

  return wrap(<>
    {/* Header */}
    <div className="flex-shrink-0 px-4 py-3" style={{ borderBottom: '1px solid rgba(255,255,255,0.055)' }}>
      <div className="flex items-center gap-2">
        <EventIcon type={ev.type} size={20} color={col} />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold capitalize truncate" style={{ color: '#dde6f0' }}>
            {ev.type.replace(/_/g,' ')}
          </p>
          <p className="text-xs font-mono" style={{ color: 'rgba(255,255,255,0.3)' }}>{ev.id}</p>
        </div>
        <button onClick={onClose} className="material-symbols-outlined text-lg cursor-pointer flex-shrink-0 transition-colors duration-150"
          style={{ color: 'rgba(255,255,255,0.25)' }}
          onMouseEnter={e => (e.currentTarget.style.color = '#f87171')}
          onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.25)')}>
          close
        </button>
      </div>

      {/* Quick status row */}
      <div className="flex items-center gap-2 mt-2.5">
        <span className="text-xs px-2 py-0.5 rounded-md font-medium" style={{ background: `${col}18`, color: col }}>{sev}</span>
        {ev.priority && (
          <span className="text-xs px-2 py-0.5 rounded-md font-medium"
            style={{ background: `${PRI_COL[ev.priority]}18`, color: PRI_COL[ev.priority] }}>
            {PRI_LABEL[ev.priority]}
          </span>
        )}
        {isEmg && (
          <span className="text-xs px-2 py-0.5 rounded-md font-medium animate-pulse inline-flex items-center gap-1"
            style={{ background: 'rgba(239,68,68,0.15)', color: '#fca5a5' }}>
            <ShieldAlert className="w-3 h-3" /> Emergency
          </span>
        )}
        <span className="ml-auto text-xs inline-flex items-center gap-1" style={{ color: 'rgba(255,255,255,0.3)' }}>
          {(() => {
            const vm = VER_META[ev.verification];
            return vm ? <vm.Icon style={{ width: 12, height: 12, color: vm.color }} /> : null;
          })()}
          {ev.verification.replace(/_/g,' ')}
        </span>
      </div>
    </div>

    {/* Body */}
    <div className="flex-1 overflow-y-auto p-3 space-y-3">

      {/* Overview */}
      <div className={panel} style={panelStyle}>
        <p className="text-xs font-semibold" style={labelStyle}>Overview</p>
        <div className="grid grid-cols-2 gap-2">
          {[
            { label: 'AI Confidence', value: `${conf}%`, color: conf >= 85 ? '#34d399' : conf >= 65 ? '#fbbf24' : '#f87171' },
            { label: 'Status', value: (ev.overall_status ?? 'unassigned').replace(/_/g,' '), color: STATUS_COL[ev.overall_status ?? 'unassigned'] },
            { label: 'Age', value: ev.age_s < 60 ? `${ev.age_s}s` : `${Math.floor(ev.age_s/60)}m`, color: undefined },
            { label: 'Detections', value: `Bus ${ev.detected_by.split(' ')[0]}`, color: undefined },
          ].map(({ label, value, color }) => (
            <div key={label} className="rounded-lg px-2.5 py-2" style={{ background: 'rgba(255,255,255,0.03)' }}>
              <p style={labelStyle}>{label}</p>
              <p className="text-xs font-semibold mt-0.5" style={{ color: color ?? 'rgba(255,255,255,0.7)' }}>{value}</p>
            </div>
          ))}
        </div>
        <div className="rounded-lg px-2.5 py-2" style={{ background: 'rgba(255,255,255,0.03)' }}>
          <p style={labelStyle}>Location</p>
          <p className="text-xs font-mono mt-0.5" style={{ color: 'rgba(255,255,255,0.6)' }}>
            {ev.lat.toFixed(5)}, {ev.lng.toFixed(5)}
          </p>
        </div>
      </div>

      {/* Priority */}
      <div className={panel} style={panelStyle}>
        <p className="text-xs font-semibold" style={labelStyle}>Priority</p>
        <div className="grid grid-cols-2 gap-1.5">
          {(['p1','p2','p3','p4'] as const).map(p => {
            const active = ev.priority === p;
            const c = PRI_COL[p];
            return (
              <button key={p} onClick={() => handlePriority(p)}
                className="py-2 rounded-lg text-xs font-semibold transition-all duration-150 cursor-pointer"
                style={active
                  ? { background: `${c}22`, color: c, border: `1px solid ${c}55`, boxShadow: `0 0 12px ${c}22` }
                  : { background: 'rgba(255,255,255,0.03)', color: 'rgba(255,255,255,0.4)', border: '1px solid rgba(255,255,255,0.06)' }}>
                {PRI_LABEL[p]}
              </button>
            );
          })}
        </div>
        {ev.priority && (
          <button onClick={() => handlePriority('none')}
            className="w-full py-1.5 rounded-lg text-xs transition-all duration-150 cursor-pointer flex items-center justify-center gap-1"
            style={{ color: 'rgba(255,255,255,0.3)', background: 'transparent', border: 'none' }}
            onMouseEnter={e => (e.currentTarget.style.color = '#f87171')}
            onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.3)')}>
            <X className="w-3 h-3" /> Clear priority
          </button>
        )}
      </div>

      {/* Authorities */}
      <div className={panel} style={panelStyle}>
        <p className="text-xs font-semibold" style={labelStyle}>Assignments</p>
        {(ev.eligible_authorities ?? []).length === 0 && (
          <p className="text-xs" style={{ color: 'rgba(255,255,255,0.25)' }}>No eligible authorities</p>
        )}
        {(ev.eligible_authorities ?? []).map(auth => {
          const meta  = AUTH_META[auth] ?? { label: auth, icon: auth, color: '#fb923c' };
          const authIcon = AUTH_ICON[auth] ?? { Icon: Building, color: meta.color };
          const asgn  = ev.assignments?.[auth];
          const assigned = asgn?.assigned;
          const status = asgn?.status ?? 'unassigned';
          const stCol = STATUS_COL[status] ?? '#475569';
          return (
            <div key={auth} className="flex items-center gap-2.5 px-3 py-2.5 rounded-lg"
              style={assigned
                ? { background: `${meta.color}0d`, border: `1px solid ${meta.color}25` }
                : { background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)' }}>
              <authIcon.Icon className="flex-shrink-0" style={{ width: 16, height: 16, color: authIcon.color }} />
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium" style={{ color: 'rgba(255,255,255,0.7)' }}>{meta.label}</p>
                {assigned && <p className="text-xs capitalize" style={{ color: stCol }}>{status.replace(/_/g,' ')}</p>}
              </div>
              {assigned ? (<>
                <button onClick={() => handleAction(auth, status)}
                  className="text-xs px-2 py-1 rounded-md transition-all duration-150 cursor-pointer"
                  style={{ background: `${meta.color}1a`, color: meta.color, border: `1px solid ${meta.color}30` }}
                  onMouseEnter={e => (e.currentTarget.style.background = `${meta.color}30`)}
                  onMouseLeave={e => (e.currentTarget.style.background = `${meta.color}1a`)}>
                  {status === 'completed' ? 'Done' : status === 'in_progress' ? 'Complete' : status === 'acknowledged' ? 'Start' : 'Ack'}
                </button>
                <button onClick={() => handleUnassign(auth)} className="material-symbols-outlined text-sm cursor-pointer"
                  style={{ color: 'rgba(255,255,255,0.2)' }}
                  onMouseEnter={e => (e.currentTarget.style.color = '#f87171')}
                  onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.2)')}>
                  close
                </button>
              </>) : (
                <button onClick={() => handleAssign(auth)}
                  className="text-xs px-2 py-1 rounded-md transition-all duration-150 cursor-pointer"
                  style={{ background: 'rgba(249,115,22,0.1)', color: '#fb923c', border: '1px solid rgba(249,115,22,0.2)' }}
                  onMouseEnter={e => (e.currentTarget.style.background = 'rgba(249,115,22,0.2)')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'rgba(249,115,22,0.1)')}>
                  Assign
                </button>
              )}
            </div>
          );
        })}
      </div>

      {/* Notes */}
      <div className={panel} style={panelStyle}>
        <p className="text-xs font-semibold" style={labelStyle}>Field Notes</p>
        <textarea value={notes} onChange={e => setNotes(e.target.value)} rows={3}
          placeholder="Add notes…"
          className="w-full text-xs rounded-lg p-2.5 outline-none resize-none transition-all duration-150"
          style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', color: '#dde6f0' }}
          onFocus={e => (e.currentTarget.style.borderColor = 'rgba(249,115,22,0.4)')}
          onBlur={e => (e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)')} />
        <button onClick={handleSaveNote} disabled={saving}
          className="w-full py-1.5 rounded-lg text-xs font-medium transition-all duration-150 cursor-pointer disabled:opacity-50 flex items-center justify-center gap-1.5"
          style={{ background: 'rgba(249,115,22,0.15)', color: '#fb923c', border: '1px solid rgba(249,115,22,0.2)' }}
          onMouseEnter={e => !saving && (e.currentTarget.style.background = 'rgba(249,115,22,0.25)')}
          onMouseLeave={e => (e.currentTarget.style.background = 'rgba(249,115,22,0.15)')}>
          {saving ? 'Saving…' : <><Save className="w-3 h-3" /> Save Note</>}
        </button>
      </div>

      {/* Timeline */}
      <div className={panel} style={panelStyle}>
        <p className="text-xs font-semibold" style={labelStyle}>Timeline ({tl.length})</p>
        <div className="relative pl-4">
          {tl.length === 0 && <p className="text-xs" style={{ color: 'rgba(255,255,255,0.25)' }}>No entries yet</p>}
          {tl.map((entry, i) => {
            const ts = entry.ts ? new Date(entry.ts * 1000).toLocaleTimeString([], { hour:'2-digit', minute:'2-digit', second:'2-digit' }) : '';
            const isFirst = i === 0;
            return (
              <div key={i} className="relative pb-3 last:pb-0">
                {i < tl.length - 1 && (
                  <div className="absolute left-[-9px] top-3 bottom-0 w-px" style={{ background: 'rgba(255,255,255,0.06)' }} />
                )}
                <div className="absolute left-[-12px] top-1 w-2 h-2 rounded-full"
                  style={{ background: isFirst ? '#f97316' : 'rgba(255,255,255,0.12)', boxShadow: isFirst ? '0 0 6px rgba(249,115,22,0.5)' : 'none' }} />
                <p className="text-xs leading-relaxed" style={{ color: 'rgba(255,255,255,0.55)' }}>{stripEmoji(entry.msg)}</p>
                <p className="text-xs mt-0.5 font-mono" style={{ color: 'rgba(255,255,255,0.2)' }}>{ts}</p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Deploy action */}
      <button onClick={() => onDeployFieldCommand(ev.id)}
        className="w-full py-2.5 rounded-xl text-xs font-semibold transition-all duration-200 cursor-pointer flex items-center justify-center gap-1.5"
        style={{
          background: 'linear-gradient(135deg,rgba(234,88,12,0.3),rgba(124,58,237,0.3))',
          color: '#fdba74',
          border: '1px solid rgba(249,115,22,0.3)',
        }}
        onMouseEnter={e => (e.currentTarget.style.background = 'linear-gradient(135deg,rgba(234,88,12,0.5),rgba(124,58,237,0.5))')}
        onMouseLeave={e => (e.currentTarget.style.background = 'linear-gradient(135deg,rgba(234,88,12,0.3),rgba(124,58,237,0.3))')}>
        <Zap className="w-3.5 h-3.5" /> Deploy Field Command
      </button>
    </div>
  </>);
};
