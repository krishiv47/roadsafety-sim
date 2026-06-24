import React, { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { SimEvent, SimBus, RouteInfo, ROUTE_COLORS } from '../types';
import { eventIconSvg, busIconSvg, warnIconSvg } from '../icons';

interface Props {
  events: SimEvent[];
  selectedEvent: SimEvent | null;
  setSelectedEvent: (e: SimEvent) => void;
  buses: SimBus[];
  routes: RouteInfo[];
}

const SEV_COLOR: Record<string, string> = {
  critical: '#ef4444', high: '#f97316', medium: '#eab308', low: '#22c55e',
};

function tooltip(html: string) {
  return `<div style="background:rgba(5,12,24,0.97);border:1px solid rgba(249,115,22,0.3);border-radius:10px;padding:10px 12px;color:#dde6f0;font-family:Inter,sans-serif;box-shadow:0 8px 32px rgba(0,0,0,0.5)">${html}</div>`;
}

export const MapView: React.FC<Props> = ({ events, selectedEvent, setSelectedEvent, buses, routes }) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const markerGroupRef = useRef<L.LayerGroup | null>(null);
  const routeLayerRef = useRef<L.LayerGroup | null>(null);
  const busMarkersRef = useRef<Map<string, L.Marker>>(new Map());
  const evtMarkersRef = useRef<Map<string, L.Marker>>(new Map());

  /* Init map once */
  useEffect(() => {
    if (!mapContainerRef.current) return;

    // Force the container to have explicit pixel dimensions before Leaflet reads them
    const el = mapContainerRef.current;
    const parent = el.parentElement;
    if (parent) {
      el.style.width  = parent.offsetWidth  + 'px';
      el.style.height = parent.offsetHeight + 'px';
    }

    const map = L.map(el, {
      zoomControl: false, attributionControl: false, scrollWheelZoom: true,
    }).setView([28.6139, 77.2090], 11);

    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', { maxZoom: 19 }).addTo(map);

    mapRef.current = map;
    markerGroupRef.current = L.layerGroup().addTo(map);
    routeLayerRef.current  = L.layerGroup().addTo(map);

    // Invalidate Leaflet size when container changes
    const ro = new ResizeObserver(() => { map.invalidateSize({ animate: false }); });
    ro.observe(el);

    // Also invalidate on font/icon load
    setTimeout(() => map.invalidateSize({ animate: false }), 100);
    setTimeout(() => map.invalidateSize({ animate: false }), 500);

    return () => {
      ro.disconnect();
      map.remove();
      mapRef.current = null;
      busMarkersRef.current.clear();
      evtMarkersRef.current.clear();
    };
  }, []);

  /* Auto-zoom when route set changes (scale mode switch) */
  useEffect(() => {
    const map = mapRef.current;
    if (!map || routes.length === 0) return;
    if (routes.length > 20) {
      // India scale — zoom out to show the whole country
      map.setView([20.5937, 78.9629], 5, { animate: true });
    } else if (routes.length > 10) {
      // NCR scale — zoom to Delhi + NCR region
      map.setView([28.5500, 77.2500], 9, { animate: true });
    } else {
      // City scale — Delhi
      map.setView([28.6139, 77.2090], 11, { animate: true });
    }
  }, [routes.length]);

  /* Route polylines — stable after first load */
  useEffect(() => {
    const rl = routeLayerRef.current; if (!rl) return;
    rl.clearLayers();
    routes.forEach(r => {
      if (!r.waypoints || r.waypoints.length < 2) return;
      const pts = r.waypoints.map(w => [w.lat, w.lng] as [number, number]);
      const col = r.color || ROUTE_COLORS[r.name] || '#f97316';
      L.polyline(pts, { color: col, weight: 2.5, opacity: 0.55 }).addTo(rl);
    });
  }, [routes]);

  /* Bus markers — incremental update, NO clearLayers */
  useEffect(() => {
    const map = mapRef.current; const mg = markerGroupRef.current;
    if (!map || !mg) return;
    const bm = busMarkersRef.current;
    const incoming = new Set(buses.map(b => b.id));

    for (const [id, marker] of bm) {
      if (!incoming.has(id)) { mg.removeLayer(marker); bm.delete(id); }
    }

    buses.forEach(bus => {
      const existing = bm.get(bus.id);
      if (existing) {
        existing.setLatLng([bus.lat, bus.lng]);
        return;
      }
      const col = ROUTE_COLORS[bus.route] ?? '#f97316';
      const offline = bus.network === 'offline';
      const weak    = bus.network === 'weak';
      const border  = offline ? '#ef4444' : weak ? '#eab308' : 'rgba(0,0,0,0.6)';

      const icon = L.divIcon({
        className: '',
        html: `<div style="width:28px;height:28px;border-radius:50%;background:${col};border:2px solid ${border};
          display:flex;align-items:center;justify-content:center;
          box-shadow:0 0 10px ${col}55,0 2px 8px rgba(0,0,0,0.4);">
          ${busIconSvg(13, 'rgba(0,0,0,0.8)')}
          ${offline ? `<span style="position:absolute;top:-4px;right:-4px;display:flex;">${warnIconSvg(10)}</span>` : ''}
        </div>`,
        iconSize: [28, 28], iconAnchor: [14, 14],
      });

      const marker = L.marker([bus.lat, bus.lng], { icon });
      marker.bindTooltip(tooltip(`
        <p style="font-weight:600;font-size:12px;margin:0 0 2px">${bus.id}</p>
        <p style="font-size:11px;color:rgba(255,255,255,0.5);margin:0">${bus.route} · ${bus.speed.toFixed(0)} km/h · ${bus.network}</p>
      `), { direction: 'top', offset: [0, -14] });

      mg.addLayer(marker);
      bm.set(bus.id, marker);
    });
  }, [buses]);

  /* Event markers — incremental update */
  useEffect(() => {
    const map = mapRef.current; const mg = markerGroupRef.current;
    if (!map || !mg) return;
    const em = evtMarkersRef.current;
    const incoming = new Set(events.filter(e => e.overall_status !== 'completed').map(e => e.id));

    for (const [id, marker] of em) {
      if (!incoming.has(id)) { mg.removeLayer(marker); em.delete(id); }
    }

    events.forEach(ev => {
      if (ev.overall_status === 'completed') return;
      const col  = SEV_COLOR[ev.severity] ?? '#fb923c';
      const ring = ev.severity === 'critical' ? 'critical-ring' : 'pulse-ring';

      if (em.has(ev.id)) {
        em.get(ev.id)!.setLatLng([ev.lat, ev.lng]);
        return;
      }

      const icon = L.divIcon({
        className: '',
        html: `<div style="position:relative;width:36px;height:36px;display:flex;align-items:center;justify-content:center;">
          <div class="${ring}" style="position:absolute;width:20px;height:20px;border-radius:50%;background:${col};opacity:0.5;"></div>
          <div style="width:18px;height:18px;border-radius:50%;background:${col};border:2px solid rgba(255,255,255,0.85);
            box-shadow:0 0 12px ${col}88;z-index:1;display:flex;align-items:center;justify-content:center;">
            ${eventIconSvg(ev.type, 10, '#fff')}
          </div>
        </div>`,
        iconSize: [36, 36], iconAnchor: [18, 18],
      });

      const marker = L.marker([ev.lat, ev.lng], { icon });
      marker.on('click', () => { setSelectedEvent(ev); map.setView([ev.lat, ev.lng], 14, { animate: true }); });
      marker.bindTooltip(tooltip(`
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">
          <span style="display:flex;align-items:center;">${eventIconSvg(ev.type, 12, col)}</span>
          <p style="font-weight:600;font-size:12px;margin:0;text-transform:capitalize">${ev.type.replace(/_/g,' ')}</p>
          <span style="font-size:10px;padding:1px 6px;border-radius:99px;background:${col}22;color:${col};margin-left:auto">${ev.severity}</span>
        </div>
        <p style="font-size:11px;color:rgba(255,255,255,0.45);margin:0">${Math.round(ev.confidence*100)}% confidence · ${ev.detected_by.split(' ')[0]}</p>
      `), { direction: 'top', offset: [0, -18] });

      mg.addLayer(marker);
      em.set(ev.id, marker);
    });
  }, [events, setSelectedEvent]);

  /* Pan to selected */
  useEffect(() => {
    if (!mapRef.current || !selectedEvent) return;
    mapRef.current.setView([selectedEvent.lat, selectedEvent.lng], 14, { animate: true });
  }, [selectedEvent]);

  return (
    <div style={{ flex: 1, position: 'relative', minWidth: 0, minHeight: 0, background: '#080f1c' }}>
      <style>{`
        .critical-ring { animation: critical-ring 1.6s cubic-bezier(0.22,1,0.36,1) infinite; }
        .pulse-ring     { animation: pulse-ring     2.2s cubic-bezier(0.22,1,0.36,1) infinite; }
        @keyframes critical-ring { 0%{transform:scale(0.9);opacity:0.9} 70%{transform:scale(2.2);opacity:0} 100%{transform:scale(2.2);opacity:0} }
        @keyframes pulse-ring    { 0%{transform:scale(0.85);opacity:0.7} 60%{transform:scale(2);opacity:0} 100%{transform:scale(2);opacity:0} }
        .leaflet-container { width:100%!important; height:100%!important; }
      `}</style>

      {/* Leaflet needs an absolute-positioned, fully-sized div */}
      <div ref={mapContainerRef}
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }} />

      {/* Zoom controls */}
      <div className="absolute top-4 right-4 z-[500] flex flex-col rounded-xl overflow-hidden"
        style={{ background: 'rgba(7,14,28,0.92)', backdropFilter: 'blur(16px)', border: '1px solid rgba(255,255,255,0.08)', boxShadow: '0 8px 24px rgba(0,0,0,0.4)' }}>
        {[{ icon: 'add', action: () => mapRef.current?.zoomIn() }, { icon: 'remove', action: () => mapRef.current?.zoomOut() }].map(({ icon, action }) => (
          <button key={icon} onClick={action}
            className="w-8 h-8 flex items-center justify-center transition-colors duration-150 cursor-pointer"
            style={{ color: 'rgba(255,255,255,0.5)' }}
            onMouseEnter={e => (e.currentTarget.style.color = '#fff')}
            onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.5)')}>
            <span className="material-symbols-outlined text-sm">{icon}</span>
          </button>
        ))}
      </div>

      {/* Legend */}
      <div className="absolute bottom-5 left-4 z-[500] p-3.5 rounded-xl"
        style={{ background: 'rgba(7,14,28,0.92)', backdropFilter: 'blur(16px)', border: '1px solid rgba(255,255,255,0.07)', boxShadow: '0 8px 24px rgba(0,0,0,0.4)' }}>
        <p className="text-xs font-medium mb-2.5" style={{ color: 'rgba(255,255,255,0.35)' }}>Legend</p>
        {[
          { color: '#22c55e', label: 'Bus (active)' },
          { color: '#ef4444', label: 'Critical incident', ring: true },
          { color: '#f97316', label: 'High severity' },
          { color: '#f97316', label: 'Bus route' },
        ].map(({ color, label, ring }) => (
          <div key={label} className="flex items-center gap-2.5 mb-2 last:mb-0">
            <div className="relative flex items-center justify-center w-3 h-3 flex-shrink-0">
              {ring && <div className="absolute w-3 h-3 rounded-full animate-ping opacity-50" style={{ background: color }} />}
              {label.includes('route')
                ? <div className="w-5 h-0.5 rounded-full" style={{ background: color, opacity: 0.6 }} />
                : <div className="w-2.5 h-2.5 rounded-full" style={{ background: color }} />}
            </div>
            <span className="text-xs" style={{ color: 'rgba(255,255,255,0.45)' }}>{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
};
