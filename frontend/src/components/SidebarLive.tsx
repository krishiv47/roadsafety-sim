import React, { useState, useRef, useCallback } from 'react';
import { Map, Siren } from 'lucide-react';
import { SimEvent, LeftTabType, ViewType, SEV_TO_CAT } from '../types';
import { EventIcon } from '../icons';
import { detectImage, detectSample, injectToMap, setScale, setSpeed } from '../data';

interface Toast { id: string; title: string; message: string; type: 'info' | 'success' | 'warning'; }

interface Props {
  currentView: 'map' | 'kanban';
  activeLeftTab: LeftTabType;
  setActiveLeftTab: (t: LeftTabType) => void;
  events: SimEvent[];
  selectedEvent: SimEvent | null;
  setSelectedEvent: (e: SimEvent) => void;
  searchQuery: string;
  setSearchQuery: (q: string) => void;
  kanbanFilter: 'All' | 'Critical' | 'Routine';
  setKanbanFilter: (f: 'All' | 'Critical' | 'Routine') => void;
  selectedAgency: string;
  setSelectedAgency: (a: string) => void;
  addToast: (t: Toast) => void;
  onScaleChange?: () => void;
}

const SEV_COLOR: Record<string, string> = {
  critical: '#ef4444', high: '#f97316', medium: '#eab308', low: '#22c55e',
};
const SEV_BG: Record<string, string> = {
  critical: 'rgba(239,68,68,0.08)', high: 'rgba(249,115,22,0.07)',
  medium: 'rgba(234,179,8,0.06)', low: 'rgba(34,197,94,0.06)',
};

const AGENCIES = [
  { label: 'All Agencies',   key: 'All' },
  { label: 'Police',         key: 'police' },
  { label: 'EMS',            key: 'ambulance' },
  { label: 'PWD Road',       key: 'road_authority' },
  { label: 'Municipal',      key: 'municipal' },
];

const DEMO_SCENES = [
  { label: 'Pothole Road',   type: 'pothole',       n: 0 },
  { label: 'Traffic Light',  type: 'heavy_traffic', n: 1 },
  { label: 'Accident Scene', type: 'accident',      n: 2 },
  { label: 'Waterlogging',   type: 'waterlogging',  n: 3 },
  { label: 'Heavy Traffic',  type: 'heavy_traffic', n: 4 },
];

export const SidebarLive: React.FC<Props> = ({
  currentView, activeLeftTab, setActiveLeftTab,
  events, selectedEvent, setSelectedEvent,
  searchQuery, setSearchQuery, kanbanFilter, setKanbanFilter,
  selectedAgency, setSelectedAgency, addToast, onScaleChange,
}) => {
  const [detectLoading, setDetectLoading] = useState(false);
  const [annotatedImg, setAnnotatedImg] = useState<string | null>(null);
  const [detections, setDetections] = useState<{ class_name: string; confidence: number; severity?: string }[]>([]);
  const [trafficInfo, setTrafficInfo] = useState<{ vehicle_count?: number; density?: string } | null>(null);
  const [lastDetections, setLastDetections] = useState<unknown[]>([]);
  const [lastLat] = useState(28.6139);
  const [lastLng] = useState(77.2090);
  const [activeScale, setActiveScaleState] = useState<number | null>(100);
  const [simSpeed, setSimSpeed] = useState(1.0);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const applyResult = useCallback((r: { detections?: { class_name: string; confidence: number; severity?: string }[]; traffic?: { vehicle_count?: number; density?: string }; annotated_b64?: string }) => {
    setAnnotatedImg(r.annotated_b64 ? `data:image/jpeg;base64,${r.annotated_b64}` : null);
    setDetections(r.detections ?? []);
    setTrafficInfo(r.traffic ?? null);
    setLastDetections(r.detections ?? []);
  }, []);

  const handleFile = async (file: File) => {
    setDetectLoading(true);
    try { applyResult(await detectImage(file)); }
    catch (e) { addToast({ id: String(Date.now()), title: 'Detection failed', message: String(e), type: 'warning' }); }
    finally { setDetectLoading(false); }
  };

  const handleDemo = async (n: number) => {
    setDetectLoading(true);
    try { applyResult(await detectSample(n)); }
    catch (e) { addToast({ id: String(Date.now()), title: 'Sample failed', message: String(e), type: 'warning' }); }
    finally { setDetectLoading(false); }
  };

  const handleInject = async () => {
    try {
      const r = await injectToMap(lastDetections, lastLat, lastLng);
      addToast({ id: String(Date.now()), title: 'Injected to map', message: `Event ${r.event_id ?? 'created'} added.`, type: 'success' });
    } catch (e) { addToast({ id: String(Date.now()), title: 'Inject failed', message: String(e), type: 'warning' }); }
  };

  const handleScale = async (n: number) => {
    try {
      await setScale(n);
      setActiveScaleState(n);
      // Re-fetch routes so map polylines match the new scale area
      setTimeout(() => onScaleChange?.(), 300);
      const label = n === 100 ? 'Delhi City (100 buses)'
                  : n === 1000 ? 'Delhi NCR (1,000 buses)'
                  : 'All India (10,000 buses)';
      addToast({ id: String(Date.now()), title: 'Scale changed', message: label, type: 'info' });
    }
    catch (e) { addToast({ id: String(Date.now()), title: 'Scale failed', message: String(e), type: 'warning' }); }
  };

  const handleSpeed = async (v: number) => {
    setSimSpeed(v);
    try { await setSpeed(v); } catch (_) { /* silent */ }
  };

  const activeEvents = events.filter(e => e.overall_status !== 'completed');

  /* ── Shared panel wrapper ─── */
  const panel = (children: React.ReactNode) => (
    <aside style={{
      width: 280, flexShrink: 0, display: 'flex', flexDirection: 'column',
      height: '100%', minHeight: 0,          /* minHeight:0 lets flex children scroll */
      background: '#0c1422', borderRight: '1px solid rgba(255,255,255,0.07)',
      overflow: 'hidden',
    }}>
      {children}
    </aside>
  );

  /* ── Shared tab bar ─── */
  const tabs = (_: ViewType, tabList: LeftTabType[]) => (
    <div className="flex border-b" style={{ borderColor: 'rgba(255,255,255,0.07)' }}>
      {tabList.map(t => {
        const label = t === 'live' ? 'Live Feed' : t === 'detect' ? 'Detect' : 'Scale';
        const active = activeLeftTab === t;
        return (
          <button key={t} onClick={() => setActiveLeftTab(t)}
            className="flex-1 py-2.5 text-xs font-medium transition-all duration-150 cursor-pointer relative"
            style={active
              ? { color: '#f97316', borderBottom: '2px solid #f97316', marginBottom: -1 }
              : { color: 'rgba(255,255,255,0.3)', borderBottom: '2px solid transparent', marginBottom: -1 }}>
            {label}
          </button>
        );
      })}
    </div>
  );

  if (currentView === 'map') {
    return panel(<>
      {tabs('map', ['live', 'detect', 'scale'])}
      <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '12px' }} className="space-y-2">

        {/* ── LIVE FEED ── */}
        {activeLeftTab === 'live' && (<>
          <div className="flex items-center justify-between mb-1 px-1">
            <span className="text-xs font-medium" style={{ color: 'rgba(255,255,255,0.35)' }}>Active Events</span>
            <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: 'rgba(239,68,68,0.12)', color: '#fca5a5' }}>
              {activeEvents.length}
            </span>
          </div>

          {activeEvents.length === 0 && (
            <div className="flex flex-col items-center py-12 gap-2">
              <span className="material-symbols-outlined text-3xl" style={{ color: 'rgba(255,255,255,0.12)' }}>location_off</span>
              <p className="text-xs" style={{ color: 'rgba(255,255,255,0.25)' }}>No active events</p>
            </div>
          )}

          {activeEvents.map(ev => {
            const sev = ev.severity;
            const col = SEV_COLOR[sev] ?? '#f97316';
            const bg  = SEV_BG[sev] ?? 'rgba(249,115,22,0.06)';
            const sel = selectedEvent?.id === ev.id;
            const conf = Math.round(ev.confidence * 100);

            return (
              <button key={ev.id} onClick={() => setSelectedEvent(ev)} className="w-full text-left rounded-xl p-3 transition-all duration-150 block"
                style={{
                  background: sel ? 'rgba(249,115,22,0.12)' : bg,
                  border: sel ? '1px solid rgba(249,115,22,0.4)' : '1px solid rgba(255,255,255,0.05)',
                  borderLeft: `3px solid ${col}`,
                  boxShadow: sel ? '0 0 0 1px rgba(249,115,22,0.2)' : 'none',
                }}>
                {/* Row 1: type + conf */}
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-1.5">
                    <EventIcon type={ev.type} size={15} color={col} />
                    <span className="text-xs font-semibold capitalize" style={{ color: '#dde6f0' }}>
                      {ev.type.replace(/_/g, ' ')}
                    </span>
                  </div>
                  <span className="text-xs font-semibold tabular-nums" style={{ color: col }}>{conf}%</span>
                </div>
                {/* Confidence bar */}
                <div className="h-0.5 rounded-full mb-2" style={{ background: 'rgba(255,255,255,0.06)' }}>
                  <div className="h-0.5 rounded-full transition-all duration-500" style={{ width: `${conf}%`, background: col }} />
                </div>
                {/* Row 2: meta */}
                <div className="flex items-center justify-between">
                  <span className="text-xs" style={{ color: 'rgba(255,255,255,0.3)' }}>
                    {ev.severity} · {ev.age_s < 60 ? `${ev.age_s}s` : `${Math.floor(ev.age_s/60)}m`} ago
                  </span>
                  {ev.emergency && ev.emergency !== 'resolved' && (
                    <span className="inline-flex items-center px-1.5 py-0.5 rounded-full" style={{ background: 'rgba(239,68,68,0.15)' }}>
                      <Siren style={{ width: 12, height: 12, color: '#fca5a5' }} />
                    </span>
                  )}
                  {!ev.emergency && (
                    <span className="text-xs capitalize" style={{ color: 'rgba(255,255,255,0.25)' }}>
                      {(ev.overall_status ?? 'new').replace(/_/g, ' ')}
                    </span>
                  )}
                </div>
              </button>
            );
          })}
        </>)}

        {/* ── DETECT ── */}
        {activeLeftTab === 'detect' && (<>
          <input ref={fileInputRef} type="file" accept="image/*" className="hidden"
            onChange={e => e.target.files?.[0] && handleFile(e.target.files[0])} />

          {/* Drop zone */}
          <div
            className="rounded-xl p-5 flex flex-col items-center gap-2 cursor-pointer transition-all duration-200"
            style={{
              border: `1.5px dashed ${dragOver ? '#f97316' : 'rgba(255,255,255,0.12)'}`,
              background: dragOver ? 'rgba(249,115,22,0.07)' : 'rgba(255,255,255,0.02)',
            }}
            onClick={() => fileInputRef.current?.click()}
            onDragOver={e => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={e => { e.preventDefault(); setDragOver(false); const f = e.dataTransfer.files[0]; if (f) handleFile(f); }}
          >
            {detectLoading
              ? <div className="w-6 h-6 rounded-full border-2 border-orange-400 border-t-transparent animate-spin" />
              : <span className="material-symbols-outlined text-3xl" style={{ color: 'rgba(249,115,22,0.7)' }}>upload_file</span>}
            <p className="text-xs font-medium" style={{ color: 'rgba(255,255,255,0.5)' }}>
              {detectLoading ? 'Analysing…' : 'Drop image or click to upload'}
            </p>
          </div>

          {/* Demo scenes */}
          <p className="text-xs px-1 mt-2" style={{ color: 'rgba(255,255,255,0.25)' }}>Demo scenes</p>
          <div className="grid grid-cols-1 gap-1.5">
            {DEMO_SCENES.map(s => (
              <button key={s.n} onClick={() => handleDemo(s.n)} disabled={detectLoading}
                className="text-left px-3 py-2 rounded-lg text-xs font-medium transition-all duration-150 cursor-pointer disabled:opacity-40 flex items-center gap-2"
                style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.07)', color: 'rgba(255,255,255,0.65)' }}
                onMouseEnter={e => !detectLoading && ((e.currentTarget as HTMLElement).style.background = 'rgba(249,115,22,0.1)')}
                onMouseLeave={e => (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.04)'}>
                <EventIcon type={s.type} size={14} color="#fb923c" />
                {s.label}
              </button>
            ))}
          </div>

          {/* Results */}
          {annotatedImg && (
            <div className="rounded-xl overflow-hidden" style={{ border: '1px solid rgba(255,255,255,0.08)' }}>
              <img src={annotatedImg} alt="Detection result" className="w-full object-cover" style={{ maxHeight: 140 }} />
            </div>
          )}

          {detections.length > 0 && (
            <div className="rounded-xl p-3 space-y-2" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
              <p className="text-xs font-semibold" style={{ color: 'rgba(255,255,255,0.5)' }}>
                {detections.length} detection{detections.length !== 1 ? 's' : ''}
                {trafficInfo?.vehicle_count != null && ` · ${trafficInfo.vehicle_count} vehicles`}
              </p>
              {detections.map((d, i) => {
                const pct = Math.round(d.confidence * 100);
                const col = d.severity ? (SEV_COLOR[d.severity] ?? '#fb923c') : '#fb923c';
                return (
                  <div key={i} className="flex items-center gap-2">
                    <div className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: col }} />
                    <span className="text-xs capitalize flex-1" style={{ color: 'rgba(255,255,255,0.65)' }}>{d.class_name.replace(/_/g, ' ')}</span>
                    <span className="text-xs font-medium tabular-nums" style={{ color: col }}>{pct}%</span>
                  </div>
                );
              })}
              <button onClick={handleInject}
                className="w-full mt-1 py-1.5 rounded-lg text-xs font-medium transition-all duration-150 cursor-pointer flex items-center justify-center gap-1.5"
                style={{ background: 'rgba(249,115,22,0.15)', color: '#fb923c', border: '1px solid rgba(249,115,22,0.25)' }}
                onMouseEnter={e => (e.currentTarget.style.background = 'rgba(249,115,22,0.25)')}
                onMouseLeave={e => (e.currentTarget.style.background = 'rgba(249,115,22,0.15)')}>
                <Map className="w-3.5 h-3.5" />
                Inject to Live Map
              </button>
            </div>
          )}
        </>)}

        {/* ── SCALE ── */}
        {activeLeftTab === 'scale' && (<>
          {/* Speed */}
          <div className="rounded-xl p-4" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-medium" style={{ color: 'rgba(255,255,255,0.5)' }}>Simulation Speed</span>
              <span className="text-xs font-semibold" style={{ color: '#fb923c' }}>{simSpeed}×</span>
            </div>
            <input type="range" min="0.5" max="10" step="0.5" value={simSpeed}
              onChange={e => handleSpeed(parseFloat(e.target.value))}
              className="w-full cursor-pointer" style={{ accentColor: '#f97316' }} />
            <div className="flex justify-between mt-1">
              <span className="text-xs" style={{ color: 'rgba(255,255,255,0.2)' }}>0.5×</span>
              <span className="text-xs" style={{ color: 'rgba(255,255,255,0.2)' }}>10×</span>
            </div>
          </div>

          {/* Scale modes */}
          <p className="text-xs px-1 mt-1" style={{ color: 'rgba(255,255,255,0.25)' }}>Deployment scale</p>
          {[
            { n: 100,   label: 'City',  sub: '100 buses · Delhi NCR',            icon: 'location_city' },
            { n: 1000,  label: 'State', sub: '1,000 buses · Delhi + NCR cities', icon: 'map'           },
            { n: 10000, label: 'India', sub: '10,000 buses · All major cities',  icon: 'public'        },
          ].map(({ n, label, sub, icon }) => {
            const active = activeScale === n;
            return (
              <button key={n} onClick={() => handleScale(n)}
                className="w-full text-left p-3 rounded-xl flex items-center gap-3 transition-all duration-150 cursor-pointer"
                style={{
                  background: active ? 'rgba(249,115,22,0.12)' : 'rgba(255,255,255,0.03)',
                  border: active ? '1px solid rgba(249,115,22,0.35)' : '1px solid rgba(255,255,255,0.06)',
                }}>
                <div className="w-7 h-7 rounded-lg flex items-center justify-center"
                  style={{ background: active ? 'rgba(249,115,22,0.2)' : 'rgba(255,255,255,0.06)' }}>
                  <span className="material-symbols-outlined" style={{ fontSize: 15, color: active ? '#fb923c' : 'rgba(255,255,255,0.35)' }}>
                    {icon}
                  </span>
                </div>
                <div className="flex-1">
                  <p className="text-xs font-semibold" style={{ color: active ? '#dde6f0' : 'rgba(255,255,255,0.55)' }}>{label}</p>
                  <p className="text-xs" style={{ color: 'rgba(255,255,255,0.25)' }}>{sub}</p>
                </div>
                {active && <span className="material-symbols-outlined text-sm" style={{ color: '#f97316' }}>check_circle</span>}
              </button>
            );
          })}
        </>)}
      </div>
    </>);
  }

  /* ── KANBAN sidebar ── */
  return panel(<>
    <div className="px-3 py-3">
      {/* Search */}
      <div className="flex items-center gap-2 px-3 py-2 rounded-lg mb-3"
        style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.07)' }}>
        <span className="material-symbols-outlined text-sm" style={{ color: 'rgba(255,255,255,0.3)' }}>search</span>
        <input value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
          placeholder="Search events…"
          className="flex-1 bg-transparent text-xs outline-none" style={{ color: '#dde6f0' }} />
      </div>

      {/* Priority filter */}
      <div className="flex gap-1 p-0.5 rounded-lg mb-3"
        style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.06)' }}>
        {(['All', 'Critical', 'Routine'] as const).map(f => (
          <button key={f} onClick={() => setKanbanFilter(f)}
            className="flex-1 py-1.5 rounded-md text-xs font-medium transition-all duration-150 cursor-pointer"
            style={kanbanFilter === f
              ? { background: 'linear-gradient(135deg,#ea580c,#f97316)', color: '#fff' }
              : { color: 'rgba(255,255,255,0.4)' }}>
            {f}
          </button>
        ))}
      </div>

      {/* Agency filter */}
      <div className="space-y-1">
        {AGENCIES.map(({ label, key }) => {
          const cnt = key === 'All' ? events.filter(e => e.overall_status !== 'completed').length
            : events.filter(e => e.overall_status !== 'completed' && e.assignments?.[key]?.assigned).length;
          const sel = selectedAgency === key;
          return (
            <button key={key} onClick={() => setSelectedAgency(sel ? 'All' : key)}
              className="w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs transition-all duration-150 cursor-pointer"
              style={{
                background: sel ? 'rgba(249,115,22,0.12)' : 'rgba(255,255,255,0.03)',
                border: sel ? '1px solid rgba(249,115,22,0.3)' : '1px solid rgba(255,255,255,0.05)',
                color: sel ? '#dde6f0' : 'rgba(255,255,255,0.45)',
              }}>
              <span>{label}</span>
              <span className="font-semibold tabular-nums" style={{ color: sel ? '#fb923c' : 'rgba(255,255,255,0.3)' }}>
                {cnt.toString().padStart(2, '0')}
              </span>
            </button>
          );
        })}
      </div>
    </div>

    {/* Activity log */}
    <div className="mt-auto px-3 pb-4 border-t pt-3" style={{ borderColor: 'rgba(255,255,255,0.055)' }}>
      <p className="text-xs mb-2 px-1" style={{ color: 'rgba(255,255,255,0.25)' }}>Recent Activity</p>
      {events.slice(0, 3).map(e => (
        <div key={e.id} className="flex items-center gap-2 px-1 py-1.5">
          <div className="w-1 h-1 rounded-full flex-shrink-0" style={{ background: SEV_COLOR[e.severity] ?? '#fb923c' }} />
          <span className="text-xs flex-1 truncate" style={{ color: 'rgba(255,255,255,0.35)' }}>
            <span className="font-mono" style={{ color: 'rgba(255,255,255,0.5)' }}>{e.id}</span>
            {' '}{(e.overall_status ?? 'new').replace(/_/g, ' ')}
          </span>
        </div>
      ))}
    </div>
  </>);
};
