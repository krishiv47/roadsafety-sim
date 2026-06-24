// ── API service functions ──────────────────────────────────────────────────

// Backend base URL. Empty = same-origin (combined deploy: FastAPI serves this
// build). For a split deploy (frontend on Vercel, backend on Render/Cloud Run),
// set VITE_API_BASE to the backend's https URL at build time.
export const apiBase = () =>
  (import.meta.env.VITE_API_BASE || '').replace(/\/+$/, '');

// ── Routes ────────────────────────────────────────────────────────────────
export async function fetchRoutes() {
  const res = await fetch(`${apiBase()}/api/routes`);
  if (!res.ok) throw new Error(`fetchRoutes: ${res.status}`);
  const data = await res.json();
  return data.routes as import('./types').RouteInfo[];
}

// ── Events ────────────────────────────────────────────────────────────────
export async function fetchAllEvents() {
  const res = await fetch(`${apiBase()}/api/events/all`);
  if (!res.ok) throw new Error(`fetchAllEvents: ${res.status}`);
  const data = await res.json();
  return data.events as import('./types').SimEvent[];
}

export async function fetchEventDetail(id: string) {
  const res = await fetch(`${apiBase()}/api/events/${id}`);
  if (!res.ok) throw new Error(`fetchEventDetail: ${res.status}`);
  return (await res.json()) as import('./types').SimEvent;
}

// ── Priority / Assignment ─────────────────────────────────────────────────
export async function setPriority(id: string, level: string) {
  const res = await fetch(`${apiBase()}/api/events/${id}/priority/${level}`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error(`setPriority: ${res.status}`);
  return res.json();
}

export async function assignEvent(id: string, auth: string) {
  const res = await fetch(`${apiBase()}/api/events/${id}/assign/${auth}`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error(`assignEvent: ${res.status}`);
  return res.json();
}

export async function unassignEvent(id: string, auth: string) {
  const res = await fetch(`${apiBase()}/api/events/${id}/assign/${auth}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error(`unassignEvent: ${res.status}`);
  return res.json();
}

// ── Authority work ────────────────────────────────────────────────────────
export async function authWork(auth: string, id: string, action: string) {
  const res = await fetch(`${apiBase()}/api/authority/${auth}/work/${id}/${action}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  if (!res.ok) throw new Error(`authWork: ${res.status}`);
  return res.json();
}

export async function saveNote(auth: string, id: string, notes: string) {
  const res = await fetch(`${apiBase()}/api/authority/${auth}/work/${id}/note`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ notes }),
  });
  if (!res.ok) throw new Error(`saveNote: ${res.status}`);
  return res.json();
}

// ── Detect ────────────────────────────────────────────────────────────────
export async function detectImage(file: File) {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${apiBase()}/api/detect/image`, {
    method: 'POST',
    body: form,
  });
  if (!res.ok) throw new Error(`detectImage: ${res.status}`);
  return res.json();
}

export async function detectSample(n: number) {
  const res = await fetch(`${apiBase()}/api/detect/sample/${n}`);
  if (!res.ok) throw new Error(`detectSample: ${res.status}`);
  return res.json();
}

export async function injectToMap(
  detections: unknown[],
  lat: number,
  lng: number
) {
  const res = await fetch(`${apiBase()}/api/detect/inject`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ detections, lat, lng }),
  });
  if (!res.ok) throw new Error(`injectToMap: ${res.status}`);
  return res.json();
}

// ── Simulation controls ───────────────────────────────────────────────────
export async function setScale(n: number) {
  const res = await fetch(`${apiBase()}/api/scale/${n}`, { method: 'POST' });
  if (!res.ok) throw new Error(`setScale: ${res.status}`);
  return res.json();
}

export async function setSpeed(x: number) {
  const res = await fetch(`${apiBase()}/api/speed/${x}`, { method: 'POST' });
  if (!res.ok) throw new Error(`setSpeed: ${res.status}`);
  return res.json();
}
