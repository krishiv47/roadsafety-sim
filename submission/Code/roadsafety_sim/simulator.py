"""
Road Safety Simulation Engine v2.0
====================================
• 100 virtual buses on 10 Delhi routes
• Real-time GPS movement (linear waypoint interpolation)
• AI-driven event generation via YOLOv8s + OpenCV (ai_bridge.py)
• Multi-bus verification pipeline (unverified → partial → full)
• Network simulation (good / weak / none) with offline queue + auto-sync
• Emergency response timeline (police → ambulance → authority → resolved)
• Performance stats + scalability extrapolation
"""

import asyncio
import math
import random
import time
import uuid
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Optional

# AI bridge — loads YOLOv8s from roadsafety_ai, provides get_result()
try:
    from ai_bridge import bridge as _ai_bridge
    _AI_MODE = True
except Exception as _ai_err:
    _ai_bridge = None
    _AI_MODE = False
    print(f"[Simulator] AI bridge unavailable: {_ai_err}")

# ─────────────────────────────────────────────────────────────
# Route data  –  10 real Delhi corridors, each ~10-14 waypoints
# ─────────────────────────────────────────────────────────────

ROUTES = [
    {"id": 1,  "name": "Red – North Ring",     "color": "#ef4444",
     "wp": [(28.7041,77.1025),(28.7121,77.1180),(28.7205,77.1380),(28.7156,77.1580),
            (28.7030,77.1720),(28.6920,77.1820),(28.6830,77.1920),(28.6750,77.2020),
            (28.6700,77.2200),(28.6780,77.2100),(28.6900,77.2000),(28.7010,77.1750)]},
    {"id": 2,  "name": "Blue – East Delhi",    "color": "#3b82f6",
     "wp": [(28.6430,77.2800),(28.6330,77.2920),(28.6230,77.3010),(28.6130,77.3100),
            (28.6030,77.3050),(28.5930,77.2950),(28.5870,77.2850),(28.5830,77.2750),
            (28.5930,77.2650),(28.6030,77.2600),(28.6230,77.2700)]},
    {"id": 3,  "name": "Green – South Delhi",  "color": "#22c55e",
     "wp": [(28.5244,77.1855),(28.5150,77.1950),(28.5080,77.2050),(28.5030,77.2200),
            (28.4970,77.2480),(28.5030,77.2600),(28.5150,77.2700),(28.5280,77.2800),
            (28.5380,77.2700),(28.5430,77.2550),(28.5380,77.2400),(28.5330,77.2250)]},
    {"id": 4,  "name": "Yellow – Central",     "color": "#eab308",
     "wp": [(28.6347,77.2219),(28.6280,77.2180),(28.6180,77.2100),(28.6080,77.2050),
            (28.5980,77.2100),(28.5870,77.2200),(28.5800,77.2300),(28.5700,77.2300),
            (28.5780,77.2200),(28.5900,77.2150),(28.6050,77.2200),(28.6200,77.2250)]},
    {"id": 5,  "name": "Orange – West Delhi",  "color": "#f97316",
     "wp": [(28.6430,77.1130),(28.6330,77.1280),(28.6280,77.1450),(28.6350,77.1600),
            (28.6430,77.1750),(28.6530,77.1850),(28.6580,77.1950),(28.6630,77.2050),
            (28.6650,77.2150),(28.6600,77.2250),(28.6550,77.2100),(28.6480,77.1950)]},
    {"id": 6,  "name": "Purple – NH48",        "color": "#a855f7",
     "wp": [(28.5555,77.1000),(28.5650,77.1200),(28.5780,77.1450),(28.5900,77.1700),
            (28.6030,77.1850),(28.6150,77.1950),(28.6270,77.2050),(28.6350,77.2150),
            (28.6400,77.2200),(28.6500,77.2100)]},
    {"id": 7,  "name": "Brown – Outer Ring N", "color": "#92400e",
     "wp": [(28.7200,77.1500),(28.7150,77.1750),(28.7050,77.2000),(28.6950,77.2200),
            (28.6850,77.2400),(28.6750,77.2600),(28.6650,77.2750),(28.6550,77.2600),
            (28.6450,77.2450),(28.6500,77.2200),(28.6600,77.2050),(28.6800,77.1900),
            (28.7000,77.1700)]},
    {"id": 8,  "name": "Gray – South Loop",    "color": "#9ca3af",
     "wp": [(28.5030,77.2200),(28.5080,77.2450),(28.5130,77.2650),(28.5080,77.2850),
            (28.5230,77.3000),(28.5380,77.2900),(28.5480,77.2800),(28.5550,77.2700),
            (28.5500,77.2500),(28.5400,77.2300),(28.5250,77.2150)]},
    {"id": 9,  "name": "Pink – Airport Exp",   "color": "#ec4899",
     "wp": [(28.5565,77.0861),(28.5700,77.1050),(28.5850,77.1200),(28.5980,77.1400),
            (28.6100,77.1600),(28.6200,77.1900),(28.6350,77.2100),(28.6300,77.2250)]},
    {"id": 10, "name": "Teal – Inner Ring",    "color": "#14b8a6",
     "wp": [(28.6347,77.2219),(28.6450,77.2100),(28.6550,77.2000),(28.6600,77.2150),
            (28.6650,77.2300),(28.6600,77.2450),(28.6500,77.2550),(28.6350,77.2600),
            (28.6250,77.2500),(28.6150,77.2400),(28.6100,77.2250),(28.6250,77.2000)]},
]

ROUTE_MAP = {r["id"]: r for r in ROUTES}

# ─────────────────────────────────────────────────────────────
# Event configuration
# ─────────────────────────────────────────────────────────────

EVENT_CFG = [
    # (type,            weight, possible_severities,          icon)
    ("pothole",          0.27, ["low","medium","high"],        "🕳️"),
    ("road_crack",       0.18, ["low","medium"],               "〰️"),
    ("accident",         0.08, ["high","critical"],            "🚗"),
    ("waterlogging",     0.12, ["medium","high"],              "🌊"),
    ("heavy_traffic",    0.14, ["low","medium","high"],        "🚦"),
    ("fallen_tree",      0.06, ["high","critical"],            "🌲"),
    ("roadblock",        0.08, ["medium","high"],              "🚧"),
    ("animal_crossing",  0.07, ["low","medium"],               "🐄"),
]

_ET_NAMES  = [e[0] for e in EVENT_CFG]
_ET_PROBS  = [e[1] for e in EVENT_CFG]
_ET_SEVS   = {e[0]: e[2] for e in EVENT_CFG}
_ET_ICONS  = {e[0]: e[3] for e in EVENT_CFG}
CRITICAL   = {"accident", "fallen_tree", "roadblock"}

# Emergency response steps: (current_state, delay_s, next_state, message)
EMG_STEPS = [
    ("pending",            30,  "police_notified",    "🚔 Police unit dispatched"),
    ("police_notified",    60,  "ambulance_notified", "🚑 Ambulance en route"),
    ("ambulance_notified", 90,  "authority_notified", "🚧 Road authority alerted"),
    ("authority_notified", 180, "resolved",           "✅ Incident resolved & road cleared"),
]


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _hav(p1, p2) -> float:
    """Haversine distance in km."""
    lat1, lng1 = math.radians(p1[0]), math.radians(p1[1])
    lat2, lng2 = math.radians(p2[0]), math.radians(p2[1])
    dlat = lat2 - lat1; dlng = lng2 - lng1
    a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlng/2)**2
    return 6371 * 2 * math.asin(math.sqrt(min(1.0, a)))


# ─────────────────────────────────────────────────────────────
# Data models
# ─────────────────────────────────────────────────────────────

@dataclass
class Bus:
    bus_id:   str
    route_id: int
    lat:      float
    lng:      float
    speed:    float     # km/h
    heading:  float     # 0–360°
    network:  str       # good / weak / none
    wp_idx:   int
    wp_frac:  float     # 0→1 progress on current segment
    offline_q: list = field(default_factory=list)   # queued event_ids

    def to_dict(self):
        return {
            "id":      self.bus_id,
            "route":   self.route_id,
            "lat":     round(self.lat, 6),
            "lng":     round(self.lng, 6),
            "speed":   round(self.speed, 1),
            "heading": round(self.heading, 1),
            "network": self.network,
            "queued":  len(self.offline_q),
            "color":   ROUTE_MAP[self.route_id]["color"],
        }


@dataclass
class Event:
    event_id:    str
    etype:       str
    lat:         float
    lng:         float
    confidence:  float
    severity:    str
    detected_by: str
    ts:          float
    verification: str = "unverified"   # unverified / partially_verified / fully_verified
    verifiers:    list = field(default_factory=list)
    emergency:    Optional[str] = None  # None / pending / police_notified / …
    emg_ts:       float = 0.0
    timeline:     list = field(default_factory=list)

    def to_dict(self):
        return {
            "id":            self.event_id,
            "type":          self.etype,
            "icon":          _ET_ICONS.get(self.etype, "📍"),
            "lat":           self.lat,
            "lng":           self.lng,
            "confidence":    round(self.confidence, 2),
            "severity":      self.severity,
            "detected_by":   self.detected_by,
            "ts":            self.ts,
            "age_s":         round(time.time() - self.ts),
            "verification":  self.verification,
            "verifier_count": len(self.verifiers),
            "emergency":     self.emergency,
            "timeline":      self.timeline[-6:],
        }


# ─────────────────────────────────────────────────────────────
# Simulation Engine
# ─────────────────────────────────────────────────────────────

class SimEngine:
    TICK         = 2.0    # wall-clock seconds per sim step
    MAX_EVENTS   = 250
    VERIFY_M     = 65     # verification radius in metres
    EVENT_TTL    = 480    # seconds before events expire
    BUS_COUNT    = 100

    def __init__(self):
        self.buses:      dict[str, Bus]   = {}
        self.events:     dict[str, Event] = {}
        self.alerts:     deque            = deque(maxlen=60)
        self.start_ts:   float            = time.time()
        self.speed_mult: float            = 1.0
        self.scale_mode: int              = 100
        self._evt_ctr:   int              = 0
        self._ws_clients: set             = set()
        self._state_cache: dict           = {}
        self._event_ts:  list             = []   # timestamps of events last 60s

        self._init_buses(self.BUS_COUNT)

    # ──── Initialization ────────────────────────────────────

    def _init_buses(self, count: int):
        self.buses.clear()
        for i in range(count):
            route = ROUTES[i % len(ROUTES)]
            wp    = route["wp"]
            start = random.randint(0, len(wp) - 2)
            frac  = random.random()
            p0, p1 = wp[start], wp[(start + 1) % len(wp)]
            self.buses[f"BUS-{i+1:03d}"] = Bus(
                bus_id   = f"BUS-{i+1:03d}",
                route_id = route["id"],
                lat      = p0[0] + (p1[0] - p0[0]) * frac,
                lng      = p0[1] + (p1[1] - p0[1]) * frac,
                speed    = random.uniform(22, 62),
                heading  = 0.0,
                network  = random.choices(["good","weak","none"], weights=[70,20,10])[0],
                wp_idx   = start,
                wp_frac  = frac,
            )

    # ──── Main loop ──────────────────────────────────────────

    async def run(self):
        ev_timer  = 0.0
        net_timer = 0.0
        last_t    = time.time()

        while True:
            now = time.time()
            dt  = (now - last_t) * self.speed_mult
            last_t = now

            for bus in self.buses.values():
                self._move_bus(bus, dt)
                if bus.network != "none":
                    self._check_verification(bus, now)

            ev_timer += dt
            ev_rate = 6.0 / max(self.scale_mode / 100, 0.1)
            if ev_timer >= ev_rate:
                ev_timer = 0.0
                self._gen_event(now)

            net_timer += dt
            if net_timer >= 12.0:
                net_timer = 0.0
                self._update_network(now)

            self._process_emergencies(now)
            self._prune(now)

            state = self._build_state(now)
            self._state_cache = state
            await self._broadcast(state)

            await asyncio.sleep(max(0.1, self.TICK / self.speed_mult))

    # ──── Bus movement ───────────────────────────────────────

    def _move_bus(self, bus: Bus, dt: float):
        wp  = ROUTE_MAP[bus.route_id]["wp"]
        n   = len(wp)
        p0  = wp[bus.wp_idx % n]
        p1  = wp[(bus.wp_idx + 1) % n]

        seg_km   = _hav(p0, p1)
        seg_s    = (seg_km / max(bus.speed, 1)) * 3600

        bus.wp_frac += dt / seg_s
        while bus.wp_frac >= 1.0:
            bus.wp_frac -= 1.0
            bus.wp_idx   = (bus.wp_idx + 1) % n
            p0 = wp[bus.wp_idx % n]
            p1 = wp[(bus.wp_idx + 1) % n]

        f = bus.wp_frac
        bus.lat     = p0[0] + (p1[0] - p0[0]) * f + random.gauss(0, 0.000015)
        bus.lng     = p0[1] + (p1[1] - p0[1]) * f + random.gauss(0, 0.000015)
        bus.heading = math.degrees(math.atan2(p1[1]-p0[1], p1[0]-p0[0])) % 360
        bus.speed   = max(8, min(72, bus.speed + random.gauss(0, 0.8)))

    # ──── Verification ───────────────────────────────────────

    def _check_verification(self, bus: Bus, now: float):
        for ev in self.events.values():
            if ev.verification == "fully_verified":
                continue
            if bus.bus_id == ev.detected_by or bus.bus_id in ev.verifiers:
                continue
            dist_m = _hav((bus.lat, bus.lng), (ev.lat, ev.lng)) * 1000
            if dist_m <= self.VERIFY_M:
                ev.verifiers.append(bus.bus_id)
                old = ev.verification
                ev.verification = (
                    "fully_verified" if len(ev.verifiers) >= 2 else "partially_verified"
                )
                if ev.verification != old:
                    ev.timeline.append({
                        "ts": now,
                        "msg": f"{'✅' if ev.verification=='fully_verified' else '🔄'} "
                               f"{bus.bus_id} confirmed → {ev.verification.replace('_',' ')}"
                    })

    # ──── Event generation ───────────────────────────────────

    def _gen_event(self, now: float):
        if not self.buses:
            return
        bus   = random.choice(list(self.buses.values()))
        etype = random.choices(_ET_NAMES, weights=_ET_PROBS)[0]
        eid   = f"EVT-{self._evt_ctr:05d}"
        self._evt_ctr += 1

        # ── AI-driven confidence + severity ──────────────────
        if _AI_MODE and _ai_bridge is not None:
            conf, sev = _ai_bridge.get_result(etype)
            ai_label  = f"[{_ai_bridge.model_name}]"
        else:
            # Pure random fallback when AI bridge is unavailable
            conf     = round(random.uniform(0.60, 0.98), 2)
            sev      = random.choice(_ET_SEVS[etype])
            ai_label = "[random]"

        ev = Event(
            event_id   = eid,
            etype      = etype,
            lat        = round(bus.lat + random.gauss(0, 0.0004), 6),
            lng        = round(bus.lng + random.gauss(0, 0.0004), 6),
            confidence = conf,
            severity   = sev,
            detected_by= f"{bus.bus_id} {ai_label}",
            ts         = now,
        )
        ev.timeline.append({
            "ts":  now,
            "msg": (f"🤖 {bus.bus_id} detected {_ET_ICONS.get(etype,'')} {etype} "
                    f"(conf {conf:.0%}, {sev}) via {ai_label}")
        })

        # Offline bus → queue locally
        if bus.network == "none":
            bus.offline_q.append(eid)

        self.events[eid] = ev
        self._event_ts.append(now)

        # Critical event → trigger emergency
        if etype in CRITICAL and sev in ("high", "critical"):
            ev.emergency = "pending"
            ev.emg_ts    = now
            ev.timeline.append({"ts": now, "msg": "🚨 CRITICAL — Emergency protocol activated"})
            self.alerts.appendleft({
                "ts":       now,
                "level":    "critical",
                "type":     etype,
                "event_id": eid,
                "bus":      bus.bus_id,
                "lat":      ev.lat,
                "lng":      ev.lng,
                "severity": sev,
                "msg":      f"🚨 CRITICAL {etype.replace('_',' ').upper()} — {bus.bus_id}",
            })

    # ──── Network simulation ─────────────────────────────────

    def _update_network(self, now: float):
        # Markov-chain transition matrix
        T = {
            "good": [("good",0.91),("weak",0.08),("none",0.01)],
            "weak": [("good",0.45),("weak",0.49),("none",0.06)],
            "none": [("good",0.08),("weak",0.18),("none",0.74)],
        }
        for bus in self.buses.values():
            old  = bus.network
            opts = T[old]; states, probs = zip(*opts)
            bus.network = random.choices(states, weights=probs)[0]

            # Auto-sync when network returns
            if old == "none" and bus.network != "none" and bus.offline_q:
                n = len(bus.offline_q)
                bus.offline_q.clear()
                self.alerts.appendleft({
                    "ts":    now, "level": "info", "type": "sync",
                    "msg":   f"📶 {bus.bus_id} reconnected — synced {n} queued events",
                })

    # ──── Emergency response ─────────────────────────────────

    def _process_emergencies(self, now: float):
        for ev in self.events.values():
            if not ev.emergency or ev.emergency == "resolved":
                continue
            for cur, delay, nxt, msg in EMG_STEPS:
                if ev.emergency == cur and now - ev.emg_ts >= delay:
                    ev.emergency = nxt
                    ev.timeline.append({"ts": now, "msg": msg})
                    self.alerts.appendleft({
                        "ts": now, "level": "warning" if nxt != "resolved" else "success",
                        "type": "emergency_update", "event_id": ev.event_id, "msg": msg,
                    })
                    break

    # ──── Cleanup ────────────────────────────────────────────

    def _prune(self, now: float):
        dead = [eid for eid, e in self.events.items() if now - e.ts > self.EVENT_TTL]
        for eid in dead:
            del self.events[eid]
        if len(self.events) > self.MAX_EVENTS:
            for e in sorted(self.events.values(), key=lambda x: x.ts)[:30]:
                del self.events[e.event_id]
        # Trim event timestamp list to last 60s
        self._event_ts = [t for t in self._event_ts if now - t < 60]

    # ──── State snapshot ─────────────────────────────────────

    def _build_state(self, now: float) -> dict:
        evs  = sorted(self.events.values(), key=lambda e: e.ts, reverse=True)
        mult = self.scale_mode // 100
        uptime = int(now - self.start_ts)

        nc = {"good":0,"weak":0,"none":0}
        for b in self.buses.values():
            nc[b.network] += 1

        total  = len(self.events)
        unver  = sum(1 for e in self.events.values() if e.verification=="unverified")
        part   = sum(1 for e in self.events.values() if e.verification=="partially_verified")
        full   = sum(1 for e in self.events.values() if e.verification=="fully_verified")
        emg    = sum(1 for e in self.events.values() if e.emergency and e.emergency!="resolved")
        offq   = sum(len(b.offline_q) for b in self.buses.values())
        tput   = len(self._event_ts)    # events in last 60s

        by_type = {}
        for e in self.events.values():
            by_type[e.etype] = by_type.get(e.etype, 0) + 1

        stats = {
            "total_buses":    self.scale_mode,
            "active_buses":   int(len(self.buses) * mult * 0.97),
            "total_events":   total * mult,
            "unverified":     unver * mult,
            "partial":        part  * mult,
            "verified":       full  * mult,
            "emergencies":    emg,
            "net_good":       nc["good"],
            "net_weak":       nc["weak"],
            "net_none":       nc["none"],
            "offline_queued": offq * mult,
            "uptime_s":       uptime,
            "sim_speed":      self.speed_mult,
            "scale_mode":     self.scale_mode,
            "throughput_60s": tput * mult,
            "tput_per_min":   tput * mult,
            "avg_conf":       round(sum(e.confidence for e in self.events.values())/max(total,1), 2),
            "by_type":        {k: v*mult for k,v in by_type.items()},
            "scale_metrics": {
                100:   {"buses":100,    "events_min":max(1,tput),
                         "api_rps":5,    "db_writes":12,  "alert_ms":800},
                1000:  {"buses":1000,   "events_min":max(1,tput*10),
                         "api_rps":50,   "db_writes":120, "alert_ms":1500},
                10000: {"buses":10000,  "events_min":max(1,tput*100),
                         "api_rps":500,  "db_writes":1200,"alert_ms":4200},
            },
        }

        return {
            "type":   "state",
            "ts":     now,
            "buses":  [b.to_dict() for b in self.buses.values()],
            "events": [e.to_dict() for e in evs[:160]],
            "alerts": list(self.alerts)[:25],
            "stats":  stats,
        }

    # ──── WebSocket broadcast ────────────────────────────────

    async def _broadcast(self, state: dict):
        if not self._ws_clients:
            return
        import json
        payload = json.dumps(state, default=str)
        dead = set()
        for ws in list(self._ws_clients):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.add(ws)
        self._ws_clients -= dead

    # ──── Control API ────────────────────────────────────────

    def set_scale(self, mode: int):
        if mode in (100, 1000, 10000):
            self.scale_mode = mode

    def set_speed(self, mult: float):
        self.speed_mult = round(max(0.25, min(8.0, mult)), 2)

    def get_state(self) -> dict:
        return self._state_cache or self._build_state(time.time())

    def get_routes(self) -> list:
        return [{"id":r["id"],"name":r["name"],"color":r["color"],"wp":r["wp"]}
                for r in ROUTES]
