// ── Real backend types ────────────────────────────────────────────────────────

export interface SimEvent {
  id: string;
  type: string;
  icon: string;
  lat: number;
  lng: number;
  confidence: number;
  severity: 'critical' | 'high' | 'medium' | 'low';
  detected_by: string;
  ts: number;
  age_s: number;
  verification: 'unverified' | 'partially_verified' | 'fully_verified';
  verifier_count: number;
  emergency: string | null;
  timeline: { ts: number; msg: string }[];
  priority?: 'p1' | 'p2' | 'p3' | 'p4' | null;
  overall_status?: string;
  assignments?: Record<string, AssignmentInfo>;
  eligible_authorities?: string[];
  full_timeline?: { ts: number; msg: string }[];
}

export interface AssignmentInfo {
  assigned: boolean;
  status: string | null;
  ts_updated: number | null;
  notes: string;
  meta?: { label: string; icon: string; color: string };
}

export interface SimBus {
  id: string; route: string; lat: number; lng: number;
  speed: number; network: string; icon?: string;
}

export interface SimAlert {
  ts: number; type: string; level: string; msg: string; event_id?: string;
}

export interface RouteInfo {
  id: string; name: string; color: string;
  waypoints: { lat: number; lng: number }[];
}

export interface WsState {
  type: 'state'; buses: SimBus[]; events: SimEvent[]; alerts: SimAlert[];
}

export type ViewType = 'map' | 'kanban' | 'analytics' | 'copilot';
export type LeftTabType = 'live' | 'detect' | 'scale';

export const SEV_TO_CAT = {
  critical: 'Critical', high: 'Elevated', medium: 'Routine', low: 'Routine',
} as const;

export const STATUS_LABEL: Record<string, string> = {
  unassigned: 'New', new: 'New',
  acknowledged: 'In Progress', in_progress: 'In Progress', completed: 'Completed',
};

export const PRI_LABEL: Record<string, string> = {
  p1: 'P1 Critical', p2: 'P2 High', p3: 'P3 Medium', p4: 'P4 Low',
};

export const AUTH_META: Record<string, { label: string; icon: string; color: string }> = {
  police:         { label: 'Delhi Police',    icon: 'police',         color: '#3B82F6' },
  ambulance:      { label: 'EMS / Ambulance', icon: 'ambulance',      color: '#EF4444' },
  road_authority: { label: 'PWD Road Auth',   icon: 'road_authority', color: '#F97316' },
  municipal:      { label: 'Municipal Corp',  icon: 'municipal',      color: '#22C55E' },
};

export const ROUTE_COLORS: Record<string, string> = {
  Red: '#EF4444', Blue: '#3B82F6', Green: '#22C55E', Yellow: '#EAB308',
  Orange: '#F97316', Purple: '#A855F7', Brown: '#92400E', Gray: '#6B7280',
  Pink: '#EC4899', Teal: '#14B8A6',
};
