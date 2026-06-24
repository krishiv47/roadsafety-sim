import { useState, useEffect, useRef, useCallback } from 'react';
import { SimEvent, SimBus, SimAlert, RouteInfo, ViewType, LeftTabType, SEV_TO_CAT } from './types';
import { fetchRoutes, fetchAllEvents, setPriority, assignEvent, unassignEvent, authWork } from './data';
import { Header } from './components/Header';
import { SidebarLive } from './components/SidebarLive';
import { MapView } from './components/MapView';
import { KanbanBoard } from './components/KanbanBoard';
import { DetailPanel } from './components/DetailPanel';
import AnalyticsPanel from './components/AnalyticsPanel';
import CopilotPanel from './components/CopilotPanel';

interface ToastMessage {
  id: string;
  title: string;
  message: string;
  type: 'info' | 'success' | 'warning';
}

// Map category label → priority level
function catToLevel(cat: string): string {
  if (cat === 'Critical') return 'p1';
  if (cat === 'Elevated') return 'p2';
  if (cat === 'Routine') return 'p3';
  return 'none';
}

export default function App() {
  const [events, setEvents] = useState<SimEvent[]>([]);
  const [buses, setBuses] = useState<SimBus[]>([]);
  const [alerts, setAlerts] = useState<SimAlert[]>([]);
  const [routes, setRoutes] = useState<RouteInfo[]>([]);
  const [wsConnected, setWsConnected] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState<SimEvent | null>(null);

  const [currentView, setView] = useState<ViewType>('map');
  const [activeLeftTab, setActiveLeftTab] = useState<LeftTabType>('live');
  const [searchQuery, setSearchQuery] = useState('');
  const [kanbanFilter, setKanbanFilter] = useState<'All' | 'Critical' | 'Routine'>('All');
  const [selectedAgency, setSelectedAgency] = useState<string>('All');
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const wsRef = useRef<WebSocket | null>(null);
  const backoffRef = useRef<number>(500);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const prevEventIdsRef = useRef<Set<string>>(new Set());
  // Rate-limit non-emergency toast: track last batch toast time
  const lastBatchToastRef = useRef<number>(0);

  const addToast = useCallback((toast: ToastMessage) => {
    setToasts(prev => [toast, ...prev].slice(0, 6));
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== toast.id));
    }, 6000);
  }, []);

  const removeToast = (id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  };

  // ── WebSocket with exponential backoff ────────────────────────────────────
  const connectWs = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState < 2) return;

    // Same-origin by default; if VITE_API_BASE is set (split deploy), derive the
    // ws(s):// URL from it so the live feed reaches the remote backend.
    const base = (import.meta.env.VITE_API_BASE || '').replace(/\/+$/, '');
    const wsUrl = base
      ? base.replace(/^http/, 'ws') + '/ws'
      : `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/ws`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setWsConnected(true);
      backoffRef.current = 500;
    };

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg.type === 'state') {
          const incomingEvents: SimEvent[] = msg.events || [];
          const incomingBuses: SimBus[] = msg.buses || [];
          const incomingAlerts: SimAlert[] = msg.alerts || [];

          // FIX: Only toast for emergencies individually; batch regular new events
          const newEventIds: string[] = [];
          const emergencyEvents: SimEvent[] = [];

          incomingEvents.forEach((ev) => {
            if (!prevEventIdsRef.current.has(ev.id)) {
              if (ev.emergency && ev.emergency !== 'resolved') {
                emergencyEvents.push(ev);
              } else {
                newEventIds.push(ev.id);
              }
            }
          });

          // Fire individual toasts for emergencies
          emergencyEvents.forEach((ev) => {
            addToast({
              id: `ev-${ev.id}-${Date.now()}`,
              title: 'Emergency Detected',
              message: `${ev.type} at [${ev.lat.toFixed(3)}, ${ev.lng.toFixed(3)}] — ${Math.round(ev.confidence * 100)}% conf`,
              type: 'warning',
            });
          });

          // Batch non-emergency new events, rate-limited to 1 per 3s
          if (newEventIds.length > 0) {
            const now = Date.now();
            if (now - lastBatchToastRef.current > 3000) {
              lastBatchToastRef.current = now;
              const label = newEventIds.length === 1
                ? '1 new event detected'
                : `${newEventIds.length} new events detected`;
              addToast({
                id: `batch-${now}`,
                title: 'New Events',
                message: label,
                type: 'info',
              });
            }
          }

          prevEventIdsRef.current = new Set(incomingEvents.map(e => e.id));

          // Stable references: only replace objects whose key fields changed.
          // This prevents React from re-rendering every card every 2 seconds.
          setEvents(prev => {
            const prevMap = new Map(prev.map(e => [e.id, e]));
            let changed = prev.length !== incomingEvents.length;
            const next = incomingEvents.map(ev => {
              const ex = prevMap.get(ev.id);
              if (ex && ex.lat === ev.lat && ex.lng === ev.lng &&
                  ex.severity === ev.severity && ex.verification === ev.verification &&
                  ex.emergency === ev.emergency && ex.verifier_count === ev.verifier_count) {
                return ex; // same ref — no child re-render
              }
              changed = true;
              return ev;
            });
            return changed ? next : prev;
          });

          setBuses(prev => {
            const prevMap = new Map(prev.map(b => [b.id, b]));
            let changed = prev.length !== incomingBuses.length;
            const next = incomingBuses.map(b => {
              const ex = prevMap.get(b.id);
              if (ex && ex.lat === b.lat && ex.lng === b.lng && ex.network === b.network) return ex;
              changed = true;
              return b;
            });
            return changed ? next : prev;
          });

          setAlerts(incomingAlerts);
        }
      } catch (_) {
        // ignore malformed messages
      }
    };

    ws.onclose = () => {
      setWsConnected(false);
      const delay = Math.min(backoffRef.current, 8000);
      backoffRef.current = Math.min(backoffRef.current * 2, 8000);
      reconnectTimerRef.current = setTimeout(connectWs, delay);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [addToast]);

  useEffect(() => {
    connectWs();
    return () => {
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      wsRef.current?.close();
    };
  }, [connectWs]);

  // ── Poll /api/events/all every 4s to enrich events ─────────────────────
  useEffect(() => {
    const poll = async () => {
      try {
        const enriched = await fetchAllEvents();
        // FIX: Only update events that have actually changed fields
        setEvents(prev => {
          const enrichedMap = new Map(enriched.map(e => [e.id, e]));
          let changed = false;
          const next = prev.map(ev => {
            const en = enrichedMap.get(ev.id);
            if (!en) return ev;
            if (
              en.priority !== ev.priority ||
              en.overall_status !== ev.overall_status ||
              JSON.stringify(en.assignments) !== JSON.stringify(ev.assignments)
            ) {
              changed = true;
              return {
                ...ev,
                priority: en.priority,
                overall_status: en.overall_status,
                assignments: en.assignments,
                eligible_authorities: en.eligible_authorities,
                full_timeline: en.full_timeline,
              };
            }
            return ev;
          });
          return changed ? next : prev;
        });
      } catch (_) {
        // silent — WS still provides live data
      }
    };

    poll();
    const timer = setInterval(poll, 4000);
    return () => clearInterval(timer);
  }, []);

  // ── Load routes (re-fetch after scale changes) ───────────────────────────
  const loadRoutes = useCallback(() => {
    fetchRoutes().then(setRoutes).catch(() => {});
  }, []);

  useEffect(() => { loadRoutes(); }, [loadRoutes]);

  // ── Keep selectedEvent in sync with events list ───────────────────────────
  // FIX: Only update if data actually changed
  useEffect(() => {
    if (!selectedEvent) return;
    const updated = events.find(e => e.id === selectedEvent.id);
    if (updated && JSON.stringify(updated) !== JSON.stringify(selectedEvent)) {
      setSelectedEvent(updated);
    }
  }, [events]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Action handlers ───────────────────────────────────────────────────────
  const handleAcknowledge = async (id: string) => {
    try {
      await authWork('police', id, 'acknowledge');
      addToast({
        id: String(Date.now()),
        title: 'Alert Acknowledged',
        message: `Event ${id} acknowledged by police.`,
        type: 'success',
      });
    } catch (err) {
      addToast({ id: String(Date.now()), title: 'Error', message: String(err), type: 'warning' });
    }
  };

  const handleComplete = async (id: string) => {
    const ev = events.find(e => e.id === id);
    const assigned = Object.entries(ev?.assignments ?? {})
      .filter(([, v]) => v.assigned)
      .map(([auth]) => auth);
    const auths = assigned.length ? assigned : ['police'];
    try {
      await Promise.all(auths.map(a => authWork(a, id, 'complete')));
      addToast({
        id: String(Date.now()),
        title: 'Incident Resolved',
        message: `Event ${id} marked complete.`,
        type: 'success',
      });
    } catch (err) {
      addToast({ id: String(Date.now()), title: 'Error', message: String(err), type: 'warning' });
    }
  };

  const handleUpdatePriority = async (id: string, cat: string) => {
    try {
      await setPriority(id, catToLevel(cat));
    } catch (err) {
      addToast({ id: String(Date.now()), title: 'Error', message: String(err), type: 'warning' });
    }
  };

  const handleToggleUnit = async (id: string, agency: string) => {
    const ev = events.find(e => e.id === id);
    const asgn = ev?.assignments?.[agency];
    if (!asgn) {
      try { await assignEvent(id, agency); } catch (_) { /* ignore */ }
      return;
    }
    const status = asgn.status;
    let action = 'acknowledge';
    if (status === 'acknowledged') action = 'start';
    else if (status === 'in_progress') action = 'complete';
    try {
      await authWork(agency, id, action);
    } catch (err) {
      addToast({ id: String(Date.now()), title: 'Error', message: String(err), type: 'warning' });
    }
  };

  const handleDeployField = async (id: string) => {
    try {
      await assignEvent(id, 'police');
      addToast({
        id: String(Date.now()),
        title: 'Field Command Activated',
        message: `Police deployed to incident ${id}.`,
        type: 'warning',
      });
    } catch (err) {
      addToast({ id: String(Date.now()), title: 'Error', message: String(err), type: 'warning' });
    }
  };

  // Adapt SimEvent → legacy incident-like for Header stats
  const criticalCount = events.filter(e => SEV_TO_CAT[e.severity] === 'Critical' && e.overall_status !== 'completed').length;
  const activeCount = events.filter(e => e.overall_status !== 'completed').length;

  return (
    <div style={{ display:'flex', flexDirection:'column', width:'100vw', height:'100vh', overflow:'hidden', background:'#080f1c', color:'#dde6f0' }}>

      <Header
        currentView={currentView}
        setView={setView}
        wsConnected={wsConnected}
        busCount={buses.length}
        criticalCount={criticalCount}
        activeCount={activeCount}
      />

      {/* Main workspace — fills remaining space below the 56px header */}
      <div style={{ display:'flex', flex:1, overflow:'hidden', minHeight:0 }}>

        {(currentView === 'map' || currentView === 'kanban') && (
          <SidebarLive
            currentView={currentView}
            activeLeftTab={activeLeftTab}
            setActiveLeftTab={setActiveLeftTab}
            events={events}
            selectedEvent={selectedEvent}
            setSelectedEvent={setSelectedEvent}
            searchQuery={searchQuery}
            setSearchQuery={setSearchQuery}
            kanbanFilter={kanbanFilter}
            setKanbanFilter={setKanbanFilter}
            selectedAgency={selectedAgency}
            setSelectedAgency={setSelectedAgency}
            addToast={addToast}
            onScaleChange={loadRoutes}
          />
        )}

        {currentView === 'map' && (
          <MapView
            events={events}
            selectedEvent={selectedEvent}
            setSelectedEvent={setSelectedEvent}
            buses={buses}
            routes={routes}
          />
        )}

        {currentView === 'kanban' && (
          <KanbanBoard
            events={events}
            selectedEvent={selectedEvent}
            setSelectedEvent={setSelectedEvent}
            kanbanFilter={kanbanFilter}
            selectedAgency={selectedAgency}
            onAcknowledge={handleAcknowledge}
            onComplete={handleComplete}
            searchQuery={searchQuery}
          />
        )}

        {currentView === 'analytics' && (
          <div style={{ flex: 1, overflowY: 'auto', padding: 24, minHeight: 0 }}>
            <AnalyticsPanel events={events} busCount={buses.length} wsConnected={wsConnected} />
          </div>
        )}

        {currentView === 'copilot' && (
          <div style={{ flex: 1, overflow: 'hidden', padding: 24, display: 'flex', justifyContent: 'center' }}>
            <div style={{ width: '100%', maxWidth: 760, height: '100%', display: 'flex', flexDirection: 'column', background: '#171f33', border: '1px solid #2d3449', borderRadius: 16, padding: 20 }}>
              <CopilotPanel events={events} busCount={buses.length} />
            </div>
          </div>
        )}

        {(currentView === 'map' || currentView === 'kanban') && (
          <DetailPanel
            selectedEvent={selectedEvent}
            onClose={() => setSelectedEvent(null)}
            onUpdatePriority={handleUpdatePriority}
            onToggleUnit={handleToggleUnit}
            onDeployFieldCommand={handleDeployField}
            addToast={addToast}
          />
        )}

      </div>

      {/* Toasts */}
      <div className="fixed bottom-5 right-5 z-[2000] flex flex-col gap-2" style={{ maxWidth: 340 }}>
        {toasts.map(t => {
          const accent = t.type === 'success' ? '#34d399' : t.type === 'warning' ? '#f87171' : '#fb923c';
          const icon   = t.type === 'success' ? 'check_circle' : t.type === 'warning' ? 'warning' : 'info';
          return (
            <div key={t.id} className="slide-right flex items-start gap-3 px-4 py-3 rounded-xl"
              style={{
                background: 'rgba(10,18,36,0.97)',
                border: `1px solid ${accent}22`,
                boxShadow: `0 8px 32px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.04)`,
                backdropFilter: 'blur(20px)',
              }}>
              <div className="w-0.5 self-stretch rounded-full flex-shrink-0" style={{ background: accent }} />
              <span className="material-symbols-outlined text-base flex-shrink-0 mt-0.5" style={{ color: accent }}>{icon}</span>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-semibold leading-snug" style={{ color: '#f0f4ff' }}>{t.title}</p>
                {t.message && <p className="text-xs mt-0.5 leading-snug" style={{ color: 'rgba(255,255,255,0.4)' }}>{t.message}</p>}
              </div>
              <button onClick={() => removeToast(t.id)} className="material-symbols-outlined text-sm cursor-pointer mt-0.5 flex-shrink-0"
                style={{ color: 'rgba(255,255,255,0.2)' }}
                onMouseEnter={e => (e.currentTarget.style.color = '#f87171')}
                onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.2)')}>
                close
              </button>
            </div>
          );
        })}
      </div>

      {/* Offline banner */}
      {!wsConnected && (
        <div className="fixed top-14 left-1/2 -translate-x-1/2 z-[2000] flex items-center gap-2 px-4 py-1.5 rounded-b-lg text-xs font-medium"
          style={{ background: 'rgba(248,113,113,0.15)', color: '#fca5a5', border: '1px solid rgba(248,113,113,0.2)', backdropFilter: 'blur(12px)' }}>
          <div className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse" />
          Reconnecting…
        </div>
      )}

      {alerts.length === 0 && null}
    </div>
  );
}
