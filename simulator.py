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
# Delhi NCR routes  (State scale – 1 000 buses)
# Cities: Gurgaon, Noida, Faridabad, Ghaziabad, Greater Noida
# ─────────────────────────────────────────────────────────────
NCR_ROUTES = [
    {"id":101,"name":"NCR Gurgaon Ring",      "color":"#f59e0b",
     "wp":[(28.4595,77.0266),(28.4700,77.0400),(28.4820,77.0550),(28.4950,77.0620),
           (28.5050,77.0700),(28.5080,77.0850),(28.5000,77.0980),(28.4880,77.0980),
           (28.4780,77.0880),(28.4680,77.0750),(28.4600,77.0580)]},
    {"id":102,"name":"NCR Noida Corridor",    "color":"#06b6d4",
     "wp":[(28.5355,77.3910),(28.5450,77.3800),(28.5600,77.3700),(28.5700,77.3600),
           (28.5850,77.3530),(28.5980,77.3450),(28.6080,77.3350),(28.6180,77.3250),
           (28.6100,77.3150),(28.5950,77.3200),(28.5800,77.3300),(28.5650,77.3400)]},
    {"id":103,"name":"NCR Faridabad Link",    "color":"#10b981",
     "wp":[(28.4089,77.3178),(28.4200,77.3100),(28.4350,77.3050),(28.4500,77.3000),
           (28.4650,77.2950),(28.4800,77.2950),(28.4920,77.3050),(28.5020,77.3150),
           (28.5000,77.3300),(28.4900,77.3380),(28.4750,77.3350),(28.4600,77.3250)]},
    {"id":104,"name":"NCR Ghaziabad East",   "color":"#8b5cf6",
     "wp":[(28.6692,77.4538),(28.6750,77.4400),(28.6800,77.4250),(28.6830,77.4100),
           (28.6780,77.3950),(28.6700,77.3850),(28.6600,77.3780),(28.6500,77.3750),
           (28.6420,77.3800),(28.6480,77.3950),(28.6580,77.4100),(28.6650,77.4300)]},
    {"id":105,"name":"NCR Greater Noida",    "color":"#e879f9",
     "wp":[(28.4744,77.5040),(28.4830,77.4900),(28.4950,77.4780),(28.5080,77.4700),
           (28.5180,77.4650),(28.5250,77.4550),(28.5200,77.4400),(28.5100,77.4300),
           (28.4980,77.4280),(28.4880,77.4350),(28.4800,77.4500),(28.4760,77.4680)]},
    {"id":106,"name":"NCR Dwarka Gurgaon",  "color":"#f97316",
     "wp":[(28.5921,77.0460),(28.5820,77.0580),(28.5700,77.0650),(28.5580,77.0700),
           (28.5450,77.0720),(28.5350,77.0650),(28.5280,77.0550),(28.5200,77.0450),
           (28.5300,77.0350),(28.5430,77.0380),(28.5580,77.0430)]},
    {"id":107,"name":"NCR Sonipat Loop",     "color":"#ef4444",
     "wp":[(28.9931,77.0151),(29.0050,77.0300),(29.0130,77.0450),(29.0100,77.0600),
           (29.0000,77.0700),(28.9900,77.0650),(28.9820,77.0500),(28.9800,77.0350),
           (28.9850,77.0200),(28.9920,77.0150)]},
    {"id":108,"name":"NCR Meerut Express",  "color":"#3b82f6",
     "wp":[(28.9845,77.7064),(28.9700,77.6900),(28.9550,77.6750),(28.9420,77.6600),
           (28.9320,77.6450),(28.9220,77.6300),(28.9120,77.6150),(28.9080,77.6000),
           (28.9150,77.5850),(28.9280,77.5900),(28.9400,77.6050),(28.9600,77.6200)]},
]

# ─────────────────────────────────────────────────────────────
# India-wide routes  (National scale – 10 000 buses)
# Major cities: Mumbai, Chennai, Bangalore, Kolkata, Hyderabad,
#               Pune, Ahmedabad, Jaipur, Lucknow, Surat
# ─────────────────────────────────────────────────────────────
INDIA_ROUTES = [
    {"id":201,"name":"Mumbai Western Express", "color":"#ef4444",
     "wp":[(19.0760,72.8777),(19.0900,72.8700),(19.1050,72.8650),(19.1200,72.8600),
           (19.1350,72.8550),(19.1500,72.8500),(19.1650,72.8550),(19.1800,72.8600),
           (19.1700,72.8750),(19.1550,72.8800),(19.1350,72.8820),(19.1150,72.8780),
           (19.0950,72.8800),(19.0800,72.8820)]},
    {"id":202,"name":"Mumbai Harbour Line",    "color":"#f97316",
     "wp":[(18.9389,72.8355),(18.9500,72.8450),(18.9650,72.8550),(18.9800,72.8650),
           (18.9950,72.8730),(19.0100,72.8760),(19.0250,72.8780),(19.0400,72.8800),
           (19.0550,72.8820),(19.0700,72.8780),(19.0600,72.8650),(19.0450,72.8580)]},
    {"id":203,"name":"Bangalore Ring Road",    "color":"#22c55e",
     "wp":[(12.9716,77.5946),(12.9850,77.6100),(12.9980,77.6250),(13.0100,77.6350),
           (13.0200,77.6200),(13.0150,77.6000),(13.0050,77.5850),(12.9950,77.5700),
           (12.9830,77.5600),(12.9700,77.5650),(12.9620,77.5780),(12.9680,77.5920)]},
    {"id":204,"name":"Chennai Mount Road",     "color":"#06b6d4",
     "wp":[(13.0827,80.2707),(13.0700,80.2600),(13.0580,80.2520),(13.0450,80.2450),
           (13.0320,80.2480),(13.0200,80.2550),(13.0080,80.2600),(12.9980,80.2650),
           (13.0080,80.2780),(13.0200,80.2800),(13.0350,80.2770),(13.0500,80.2720)]},
    {"id":205,"name":"Hyderabad HMDA Ring",    "color":"#a855f7",
     "wp":[(17.3850,78.4867),(17.3980,78.5000),(17.4100,78.5150),(17.4200,78.5300),
           (17.4250,78.5450),(17.4200,78.5600),(17.4080,78.5700),(17.3950,78.5720),
           (17.3820,78.5650),(17.3720,78.5500),(17.3700,78.5350),(17.3760,78.5200),
           (17.3820,78.5050)]},
    {"id":206,"name":"Kolkata Metro Corridor", "color":"#eab308",
     "wp":[(22.5726,88.3639),(22.5600,88.3700),(22.5480,88.3780),(22.5350,88.3850),
           (22.5200,88.3900),(22.5050,88.3850),(22.4920,88.3780),(22.4820,88.3700),
           (22.4750,88.3580),(22.4820,88.3480),(22.4970,88.3450),(22.5130,88.3500),
           (22.5300,88.3560),(22.5480,88.3600)]},
    {"id":207,"name":"Pune NH48 Corridor",     "color":"#ec4899",
     "wp":[(18.5204,73.8567),(18.5350,73.8700),(18.5480,73.8820),(18.5600,73.8920),
           (18.5700,73.9050),(18.5780,73.9200),(18.5700,73.9350),(18.5580,73.9400),
           (18.5450,73.9350),(18.5300,73.9250),(18.5200,73.9100),(18.5150,73.8950),
           (18.5180,73.8800)]},
    {"id":208,"name":"Ahmedabad BRTS",         "color":"#14b8a6",
     "wp":[(23.0225,72.5714),(23.0350,72.5850),(23.0450,72.5980),(23.0520,72.6100),
           (23.0580,72.6250),(23.0550,72.6400),(23.0450,72.6500),(23.0330,72.6520),
           (23.0200,72.6450),(23.0100,72.6320),(23.0070,72.6150),(23.0100,72.6000),
           (23.0180,72.5870)]},
    {"id":209,"name":"Jaipur Pink City Bus",   "color":"#f59e0b",
     "wp":[(26.9124,75.7873),(26.9250,75.7980),(26.9380,75.8100),(26.9480,75.8200),
           (26.9550,75.8350),(26.9500,75.8480),(26.9380,75.8550),(26.9250,75.8530),
           (26.9130,75.8450),(26.9050,75.8320),(26.9020,75.8150),(26.9070,75.7980)]},
    {"id":210,"name":"Lucknow Rapid Transit",  "color":"#10b981",
     "wp":[(26.8467,80.9462),(26.8580,80.9580),(26.8700,80.9700),(26.8800,80.9820),
           (26.8880,80.9950),(26.8820,81.0080),(26.8700,81.0150),(26.8580,81.0120),
           (26.8480,81.0040),(26.8400,80.9900),(26.8390,80.9760),(26.8430,80.9620)]},
    {"id":211,"name":"Surat Diamond Ring",     "color":"#8b5cf6",
     "wp":[(21.1702,72.8311),(21.1820,72.8430),(21.1920,72.8550),(21.2000,72.8680),
           (21.2050,72.8820),(21.1980,72.8950),(21.1860,72.9000),(21.1730,72.8970),
           (21.1620,72.8870),(21.1560,72.8730),(21.1580,72.8580),(21.1650,72.8450)]},
    {"id":212,"name":"Kochi Metro Extend",     "color":"#3b82f6",
     "wp":[(9.9312,76.2673),(9.9430,76.2780),(9.9550,76.2870),(9.9650,76.2950),
           (9.9750,76.3050),(9.9820,76.3180),(9.9780,76.3300),(9.9650,76.3350),
           (9.9520,76.3320),(9.9400,76.3240),(9.9320,76.3120),(9.9280,76.2980)]},
]

ALL_ROUTES = ROUTES + NCR_ROUTES + INDIA_ROUTES

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

        # Real Delhi buses + virtual scaled buses on NCR / India routes
        real_buses = [b.to_dict() for b in self.buses.values()]
        virtual    = self._virtual_buses(now)

        return {
            "type":   "state",
            "ts":     now,
            "buses":  real_buses + virtual,
            "events": [e.to_dict() for e in evs[:160]],
            "alerts": list(self.alerts)[:25],
            "stats":  stats,
        }

    def _virtual_buses(self, now: float) -> list:
        """
        Generate virtual bus positions for NCR (state) and India (national) scale.
        Buses move along pre-defined routes using a deterministic offset so they
        appear to travel without actually being simulated.
        """
        if self.scale_mode == 100:
            return []

        result = []
        # NCR: 900 extra buses for state scale; India: 9900 extra for national
        # We only render up to 400 virtual buses to keep the payload reasonable
        # (enough to visualise spread without overwhelming the client)
        if self.scale_mode == 1000:
            routes = NCR_ROUTES
            n_virtual = 400          # shown; implies ~1 000 total
        else:  # 10000
            routes = NCR_ROUTES + INDIA_ROUTES
            n_virtual = 600          # shown; implies ~10 000 total

        for i in range(n_virtual):
            route  = routes[i % len(routes)]
            wp     = route["wp"]
            n_wp   = len(wp)
            # Each virtual bus gets a unique phase offset → they spread across the route
            phase  = (i * 0.618033988749895) % 1.0   # golden-ratio spread
            # Which segment and how far along it
            raw    = phase * n_wp
            seg    = int(raw) % n_wp
            frac   = raw - int(raw)
            nxt    = (seg + 1) % n_wp
            lat    = wp[seg][0] + frac * (wp[nxt][0] - wp[seg][0])
            lng    = wp[seg][1] + frac * (wp[nxt][1] - wp[seg][1])
            # Add tiny jitter so buses on the same segment aren't perfectly stacked
            jitter = (i % 5 - 2) * 0.0002
            result.append({
                "id":      f"V-{route['id']}-{i:04d}",
                "route":   route["name"].split("–")[-1].strip() if "–" in route["name"] else route["name"],
                "lat":     round(lat + jitter, 6),
                "lng":     round(lng + jitter, 6),
                "speed":   round(20 + (i % 7) * 5, 1),
                "network": "good",
                "icon":    "🚌",
                "virtual": True,
            })
        return result

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
            # Push fresh state immediately so the client sees the map change now
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._broadcast(self.get_state()))
            except Exception:
                pass

    def set_speed(self, mult: float):
        self.speed_mult = round(max(0.25, min(8.0, mult)), 2)

    def get_state(self) -> dict:
        return self._state_cache or self._build_state(time.time())

    def get_routes(self) -> list:
        """Return routes appropriate for current scale mode."""
        if self.scale_mode == 10000:
            route_set = ALL_ROUTES
        elif self.scale_mode == 1000:
            route_set = ROUTES + NCR_ROUTES
        else:
            route_set = ROUTES
        return [{"id":r["id"],"name":r["name"],"color":r["color"],
                 "waypoints":[{"lat":p[0],"lng":p[1]} for p in r["wp"]]}
                for r in route_set]
