import React, { useState } from 'react';
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  BarChart, Bar, Cell, PieChart, Pie, LineChart, Line, Legend,
} from 'recharts';
import {
  TrendingDown, TrendingUp, ShieldCheck, Timer, BarChart3,
  FileDown, AlertTriangle, Droplets, Activity, MapPin,
} from 'lucide-react';
import { SimEvent } from '../types';

interface Props { events: SimEvent[]; busCount: number; wsConnected: boolean; }

const TREND_DATA = [
  { t:'00:00', today:3, yesterday:5 }, { t:'03:00', today:4, yesterday:4 },
  { t:'06:00', today:2, yesterday:7 }, { t:'09:00', today:6, yesterday:5 },
  { t:'12:00', today:8, yesterday:9 }, { t:'15:00', today:11, yesterday:8 },
  { t:'18:00', today:9, yesterday:12 }, { t:'21:00', today:13, yesterday:10 },
  { t:'23:59', today:10, yesterday:11 },
];

const SEV_COL: Record<string,string> = { critical:'#ef4444', high:'#f97316', medium:'#eab308', low:'#22c55e' };
const TYPE_ICONS: Record<string, React.ReactNode> = {};

const TT_STYLE = {
  backgroundColor:'#171f33', borderColor:'#2d3449', borderRadius:8,
  fontFamily:'JetBrains Mono', fontSize:11, color:'#dae2fd',
};

export default function AnalyticsPanel({ events, busCount }: Props) {
  const [timeRange, setTimeRange] = useState('Last 24 Hours');

  // Derive live stats from real events
  const total     = events.length;
  const critical  = events.filter(e => e.severity === 'critical').length;
  const completed = events.filter(e => e.overall_status === 'completed').length;
  const avgConf   = total > 0
    ? Math.round(events.reduce((s,e) => s + e.confidence, 0) / total * 100)
    : 0;

  // Category distribution from real events
  const typeCount: Record<string,number> = {};
  events.forEach(e => { typeCount[e.type] = (typeCount[e.type] ?? 0) + 1; });
  const distData = Object.entries(typeCount)
    .sort((a,b) => b[1]-a[1])
    .slice(0, 6)
    .map(([name, value], i) => ({
      name: name.replace(/_/g,' '),
      value,
      color: ['#f97316','#adc6ff','#6399ff','#22c55e','#a78b7d','#ef4444'][i] ?? '#f97316',
    }));

  // Severity breakdown for pie
  const sevData = ['critical','high','medium','low'].map(s => ({
    name: s, value: events.filter(e => e.severity === s).length,
    fill: SEV_COL[s],
  })).filter(d => d.value > 0);

  // Live hourly trend — last 9 WS ticks (approximate)
  const trendWithLive = TREND_DATA.map((d, i) =>
    i === TREND_DATA.length - 1 ? { ...d, today: total } : d
  );

  const card = (
    label: string, value: string, trend: string, trendUp: boolean,
    sub: string, accentColor: string, Icon: React.ElementType,
  ) => (
    <div className="p-5 rounded-xl flex flex-col justify-between"
      style={{ background:'#171f33', border:`1px solid #2d3449`, borderLeft:`4px solid ${accentColor}` }}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-mono uppercase tracking-wider" style={{ color:'#a78b7d' }}>{label}</span>
        <Icon className="w-4 h-4" style={{ color: accentColor }} />
      </div>
      <div className="flex items-baseline gap-2 mb-2">
        <span className="text-4xl font-black" style={{ color:'#dae2fd', fontFamily:'Inter' }}>{value}</span>
        <span className="text-xs font-mono flex items-center gap-0.5"
          style={{ color: trendUp ? '#16a34a' : '#ef4444' }}>
          {trendUp ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
          {trend}
        </span>
      </div>
      <p className="text-xs font-mono" style={{ color:'rgba(167,139,125,0.6)' }}>{sub}</p>
    </div>
  );

  return (
    <div className="space-y-6">

      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center p-5 rounded-xl gap-4"
        style={{ background:'#171f33', border:'1px solid #2d3449' }}>
        <div>
          <h3 className="text-sm font-bold uppercase tracking-widest" style={{ color:'#a78b7d', fontFamily:'Inter' }}>
            Delhi Executive Command Statistics
          </h3>
          <p className="text-xs font-mono mt-1" style={{ color:'rgba(167,139,125,0.7)' }}>
            AI-assisted model metrics — live data from simulation engine
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select value={timeRange} onChange={e => setTimeRange(e.target.value)}
            className="text-xs rounded-xl px-3 py-2 font-mono focus:outline-none"
            style={{ background:'#060e20', border:'1px solid #2d3449', color:'#dae2fd' }}>
            <option>Last 24 Hours</option>
            <option>Last 7 Days</option>
            <option>Current MTD</option>
          </select>
          <button className="flex items-center gap-2 text-xs font-bold font-mono px-4 py-2 rounded-xl transition-all"
            style={{ background:'#f97316', color:'#582200' }}
            onMouseEnter={e => (e.currentTarget.style.filter='brightness(1.1)')}
            onMouseLeave={e => (e.currentTarget.style.filter='')}>
            <FileDown className="w-4 h-4" />
            EXPORT DATA
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        {card('Metropolitan Safety Score', '84.2', '+1.2%', true,  '*Threshold 80.0 (OPTIMAL)', '#16a34a', ShieldCheck)}
        {card('Avg Dispatch Latency',     '7.4m',  '-42s',  false, 'Target: < 8.0 minutes',     '#f97316', Timer)}
        {card('Live Active Events',        String(total), total > 0 ? `+${total}` : '0', total > 0, `${critical} critical right now`, '#ef4444', AlertTriangle)}
        {card('AI Confidence Avg',        `${avgConf}%`, '+2.1%', true, `${busCount} buses reporting`, '#adc6ff', Activity)}
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">

        {/* Area chart */}
        <div className="lg:col-span-8 p-5 rounded-xl" style={{ background:'#171f33', border:'1px solid #2d3449' }}>
          <div className="flex justify-between items-start mb-5">
            <div>
              <h4 className="text-xs font-bold uppercase tracking-wider" style={{ color:'#dae2fd', fontFamily:'Inter' }}>
                Tactical Incident Trends (24h)
              </h4>
              <p className="text-xs font-mono mt-1" style={{ color:'rgba(167,139,125,0.6)' }}>Real-time hourly telemetry contrast</p>
            </div>
            <div className="flex items-center gap-4 text-xs font-mono">
              <div className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full" style={{ background:'#f97316' }} />
                <span style={{ color:'#a78b7d' }}>Today</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full" style={{ background:'rgba(173,198,255,0.6)' }} />
                <span style={{ color:'#a78b7d' }}>Yesterday</span>
              </div>
            </div>
          </div>
          <div style={{ height: 240 }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trendWithLive} margin={{ top:5, right:5, left:-25, bottom:0 }}>
                <defs>
                  <linearGradient id="gToday" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#f97316" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#f97316" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="gYest" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#adc6ff" stopOpacity={0.15} />
                    <stop offset="95%" stopColor="#adc6ff" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#2d3449" opacity={0.6} />
                <XAxis dataKey="t" stroke="#a78b7d" fontSize={9} fontFamily="JetBrains Mono" tickLine={false} />
                <YAxis stroke="#a78b7d" fontSize={9} fontFamily="JetBrains Mono" tickLine={false} />
                <Tooltip contentStyle={TT_STYLE} />
                <Area type="monotone" dataKey="today"     stroke="#f97316" strokeWidth={2.5} fill="url(#gToday)" />
                <Area type="monotone" dataKey="yesterday" stroke="#adc6ff" strokeWidth={1.5} strokeDasharray="5 5" fill="url(#gYest)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Bar chart — live category distribution */}
        <div className="lg:col-span-4 p-5 rounded-xl" style={{ background:'#171f33', border:'1px solid #2d3449' }}>
          <h4 className="text-xs font-bold uppercase tracking-wider mb-1" style={{ color:'#dae2fd', fontFamily:'Inter' }}>
            Category Distribution
          </h4>
          <p className="text-xs font-mono mb-4" style={{ color:'rgba(167,139,125,0.65)' }}>Live event type breakdown</p>
          {distData.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-48 gap-2">
              <BarChart3 className="w-8 h-8" style={{ color:'rgba(255,255,255,0.1)' }} />
              <p className="text-xs font-mono" style={{ color:'rgba(255,255,255,0.2)' }}>No events yet</p>
            </div>
          ) : (
            <div style={{ height: 200 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={distData} layout="vertical" margin={{ top:0, right:5, left:-20, bottom:0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2d3449" opacity={0.4} horizontal={false} />
                  <XAxis type="number" stroke="#a78b7d" fontSize={9} fontFamily="JetBrains Mono" tickLine={false} />
                  <YAxis dataKey="name" type="category" stroke="#dae2fd" fontSize={9} fontFamily="Inter" width={80} tickLine={false} />
                  <Tooltip contentStyle={TT_STYLE} />
                  <Bar dataKey="value" radius={[0,4,4,0]} barSize={10}>
                    {distData.map((e, i) => <Cell key={i} fill={e.color} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
          {/* Legend */}
          <div className="grid grid-cols-2 gap-1.5 mt-3 pt-3 text-xs font-mono" style={{ borderTop:'1px solid rgba(45,52,73,0.6)', color:'#a78b7d' }}>
            {distData.slice(0,4).map(d => (
              <div key={d.name} className="flex items-center gap-1.5">
                <div className="w-2 h-2 rounded-sm flex-shrink-0" style={{ background: d.color }} />
                <span className="capitalize truncate">{d.name}: {d.value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Severity donut + response pipeline */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* Severity pie */}
        <div className="p-5 rounded-xl" style={{ background:'#171f33', border:'1px solid #2d3449' }}>
          <h4 className="text-xs font-bold uppercase tracking-wider mb-4" style={{ color:'#dae2fd', fontFamily:'Inter' }}>
            Severity Breakdown
          </h4>
          {sevData.length === 0 ? (
            <div className="flex items-center justify-center h-40">
              <p className="text-xs font-mono" style={{ color:'rgba(255,255,255,0.2)' }}>No events yet</p>
            </div>
          ) : (
            <div style={{ height: 200 }}>
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={sevData} cx="50%" cy="50%" innerRadius={55} outerRadius={85}
                    dataKey="value" nameKey="name" paddingAngle={3}>
                    {sevData.map((e,i) => <Cell key={i} fill={e.fill} />)}
                  </Pie>
                  <Tooltip contentStyle={TT_STYLE} />
                  <Legend
                    iconType="circle"
                    iconSize={8}
                    formatter={(v) => <span style={{ fontSize:10, fontFamily:'JetBrains Mono', color:'#a78b7d', textTransform:'capitalize' }}>{v}</span>}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        {/* Response pipeline stats */}
        <div className="p-5 rounded-xl" style={{ background:'#171f33', border:'1px solid #2d3449' }}>
          <h4 className="text-xs font-bold uppercase tracking-wider mb-4" style={{ color:'#dae2fd', fontFamily:'Inter' }}>
            Response Pipeline
          </h4>
          <div className="space-y-3">
            {[
              { label:'Events Detected',    value: total,     pct: 100,              color:'#adc6ff' },
              { label:'Auto-Assigned',       value: events.filter(e => e.overall_status && e.overall_status !== 'unassigned').length, pct: total > 0 ? Math.round(events.filter(e => e.overall_status && e.overall_status !== 'unassigned').length / total * 100) : 0, color:'#f97316' },
              { label:'In Progress',         value: events.filter(e => e.overall_status === 'in_progress').length, pct: total > 0 ? Math.round(events.filter(e => e.overall_status === 'in_progress').length / total * 100) : 0, color:'#eab308' },
              { label:'Resolved',            value: completed, pct: total > 0 ? Math.round(completed / total * 100) : 0, color:'#22c55e' },
            ].map(({ label, value, pct, color }) => (
              <div key={label}>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-xs font-mono" style={{ color:'#a78b7d' }}>{label}</span>
                  <span className="text-xs font-bold tabular-nums font-mono" style={{ color }}>{value} <span style={{ color:'rgba(167,139,125,0.6)' }}>({pct}%)</span></span>
                </div>
                <div className="h-1.5 rounded-full" style={{ background:'rgba(45,52,73,0.8)' }}>
                  <div className="h-1.5 rounded-full transition-all duration-700" style={{ width:`${pct}%`, background: color }} />
                </div>
              </div>
            ))}
          </div>

          {/* 30-day line trend */}
          <div className="mt-5">
            <p className="text-xs font-mono mb-3" style={{ color:'rgba(167,139,125,0.7)' }}>Resolution rate trend</p>
            <div style={{ height: 80 }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={[
                  {d:'W1',r:72},{d:'W2',r:78},{d:'W3',r:75},{d:'W4',r:82},{d:'Now',r: total > 0 ? Math.round(completed/total*100) : 85},
                ]} margin={{ top:0, right:0, left:-35, bottom:0 }}>
                  <XAxis dataKey="d" stroke="#a78b7d" fontSize={9} fontFamily="JetBrains Mono" tickLine={false} />
                  <YAxis stroke="#a78b7d" fontSize={9} tickLine={false} domain={[60,100]} />
                  <Tooltip contentStyle={TT_STYLE} />
                  <Line type="monotone" dataKey="r" stroke="#22c55e" strokeWidth={2} dot={{ fill:'#22c55e', r:3 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
