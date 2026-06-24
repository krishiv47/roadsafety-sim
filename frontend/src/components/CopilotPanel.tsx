import React, { useState, useRef, useEffect } from 'react';
import { BrainCircuit, Send, Sparkles, Cpu, ShieldAlert, Zap, AlertTriangle, RefreshCw } from 'lucide-react';
import { SimEvent } from '../types';
import { apiBase } from '../data';

interface Msg { role: 'user' | 'ai'; text: string; impact?: string; }

interface Props { events: SimEvent[]; busCount: number; }

const QUICK_PROMPTS = [
  { label: 'Sector 4 timing failure', icon: AlertTriangle },
  { label: 'Ambulance routing priority', icon: Zap },
  { label: 'Waterlogging risk analysis', icon: AlertTriangle },
  { label: 'Critical event summary', icon: ShieldAlert },
];

function buildSystemPrompt(events: SimEvent[], busCount: number): string {
  const critical = events.filter(e => e.severity === 'critical');
  const unresolved = events.filter(e => e.overall_status !== 'completed');
  const summary = Object.entries(
    events.reduce<Record<string,number>>((acc, e) => { acc[e.type] = (acc[e.type]??0)+1; return acc; }, {})
  ).map(([k,v]) => `${k}:${v}`).join(', ');

  return `You are Civic Sentinel AI Copilot — an expert urban road-safety command assistant for Delhi, India.
Current live simulation state:
- ${busCount} buses active across Delhi routes
- ${events.length} total events (${unresolved.length} unresolved, ${critical.length} critical)
- Event breakdown: ${summary || 'none yet'}
- Critical events: ${critical.map(e => `${e.id}(${e.type} at ${e.lat.toFixed(3)},${e.lng.toFixed(3)})`).join('; ') || 'none'}

Your role: analyse the live data, suggest dispatch strategies, routing optimisations, and incident prioritisation.
Be concise (3-5 sentences max), use operational language, and always include a measurable strategic impact.
Format impact as: "Strategic Impact: <metric>"
No emojis. Use plain text only.`;
}

export default function CopilotPanel({ events, busCount }: Props) {
  const [messages, setMessages] = useState<Msg[]>([{
    role: 'ai',
    text: 'Civic Sentinel AI Copilot active. Monitoring live simulation. Ask me to formulate routing strategies, dispatch priorities, or system optimisations.',
  }]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async (text: string) => {
    if (!text.trim() || loading) return;

    setMessages(p => [...p, { role: 'user', text }]);
    setInput('');
    setLoading(true);

    try {
      // Calls the server-side proxy — the Groq key stays on the backend,
      // never shipped to the browser.
      const systemPrompt = buildSystemPrompt(events, busCount);
      const res = await fetch(`${apiBase()}/api/copilot`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: [
            { role: 'system', content: systemPrompt },
            { role: 'user', content: text },
          ],
        }),
      });
      if (!res.ok) {
        const errBody = await res.text();
        throw new Error(errBody.slice(0, 200));
      }
      const data = await res.json();
      const raw = data.text ?? 'No response generated.';
      const impactMatch = raw.match(/Strategic Impact:\s*(.+)/i);
      const impact = impactMatch ? impactMatch[1].trim() : undefined;
      const body = raw.replace(/Strategic Impact:.*/is, '').trim();
      setMessages(p => [...p, { role: 'ai', text: body, impact }]);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setMessages(p => [...p, {
        role: 'ai',
        text: `Copilot error: ${msg.slice(0, 140)}`,
      }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full" style={{ maxHeight: '100%' }}>

      {/* Header */}
      <div className="flex-shrink-0 flex items-center justify-between pb-4 mb-4"
        style={{ borderBottom: '1px solid #2d3449' }}>
        <div className="flex items-center gap-2.5">
          <BrainCircuit className="w-5 h-5 text-orange-400 animate-pulse" />
          <div>
            <h3 className="text-sm font-bold uppercase tracking-widest" style={{ color:'#dae2fd', fontFamily:'Inter' }}>
              AI Operator Copilot
            </h3>
            <p className="text-xs font-mono" style={{ color:'#a78b7d' }}>Powered by Groq · Live simulation context</p>
          </div>
        </div>
        <span className="text-xs font-mono px-2 py-0.5 rounded-full"
          style={{ background:'rgba(22,163,74,0.1)', color:'#16a34a', border:'1px solid rgba(22,163,74,0.2)' }}>
          COGNITIVE ACTIVE
        </span>
      </div>

      {/* Live context pills */}
      <div className="flex-shrink-0 flex gap-2 mb-4 flex-wrap">
        {[
          { label: `${busCount} buses`, Icon: Cpu, color:'#adc6ff' },
          { label: `${events.filter(e=>e.overall_status!=='completed').length} active`, Icon: AlertTriangle, color:'#f97316' },
          { label: `${events.filter(e=>e.severity==='critical').length} critical`, Icon: ShieldAlert, color:'#ef4444' },
        ].map(({ label, Icon, color }) => (
          <div key={label} className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-mono"
            style={{ background:'rgba(23,31,51,0.8)', border:'1px solid #2d3449', color }}>
            <Icon className="w-3 h-3" />
            {label}
          </div>
        ))}
      </div>

      {/* Chat log */}
      <div className="flex-1 overflow-y-auto space-y-3 p-3 rounded-xl mb-4"
        style={{ background:'rgba(6,14,32,0.6)', border:'1px solid rgba(45,52,73,0.4)', minHeight: 0 }}>
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className="max-w-[85%] p-3 rounded-xl text-xs leading-relaxed"
              style={m.role === 'user'
                ? { background:'#f97316', color:'#1a0800', borderRadius:'12px 12px 0 12px' }
                : { background:'#222a3d', color:'#dae2fd', border:'1px solid #2d3449', borderRadius:'12px 12px 12px 0' }}>
              {m.role === 'ai' && (
                <div className="flex items-center gap-1.5 mb-2 text-xs font-mono font-semibold uppercase"
                  style={{ color:'#f97316' }}>
                  <Sparkles className="w-3 h-3" />
                  Civic Core Predictive Node
                </div>
              )}
              <p style={{ fontFamily: m.role === 'user' ? 'Inter' : 'DM Sans' }}>{m.text}</p>
              {m.impact && (
                <div className="flex items-center gap-1.5 mt-2 pt-2 text-xs font-mono"
                  style={{ borderTop:'1px solid rgba(45,52,73,0.5)', color:'#16a34a' }}>
                  <Cpu className="w-3 h-3" />
                  Strategic Impact: {m.impact}
                </div>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex items-center gap-2 text-xs font-mono"
            style={{ color:'#a78b7d' }}>
            <RefreshCw className="w-4 h-4 animate-spin text-orange-400" />
            Ingesting telemetry and formulating predictive plan...
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Quick prompts */}
      <div className="flex-shrink-0 mb-3">
        <p className="text-xs font-mono uppercase tracking-wider mb-2" style={{ color:'#a78b7d' }}>
          Quick directives
        </p>
        <div className="flex flex-wrap gap-2">
          {QUICK_PROMPTS.map(({ label, icon: Icon }) => (
            <button key={label} onClick={() => sendMessage(label)} disabled={loading}
              className="flex items-center gap-1.5 text-xs font-mono px-2.5 py-1.5 rounded-lg transition-all cursor-pointer disabled:opacity-40"
              style={{ background:'#222a3d', border:'1px solid #2d3449', color:'#dae2fd' }}
              onMouseEnter={e => !loading && ((e.currentTarget as HTMLElement).style.borderColor='rgba(249,115,22,0.5)')}
              onMouseLeave={e => ((e.currentTarget as HTMLElement).style.borderColor='#2d3449')}>
              <Icon className="w-3 h-3 text-orange-400" />
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Input */}
      <form onSubmit={e => { e.preventDefault(); sendMessage(input); }} className="flex-shrink-0 relative">
        <input type="text" value={input} onChange={e => setInput(e.target.value)}
          placeholder="Ask for dispatch route, status mitigation, or risk analysis..."
          className="w-full text-xs px-4 pr-12 py-3 rounded-xl font-mono focus:outline-none transition-all"
          style={{ background:'#060e20', border:'1px solid #2d3449', color:'#dae2fd' }}
          onFocus={e => (e.currentTarget.style.borderColor='#f97316')}
          onBlur={e => (e.currentTarget.style.borderColor='#2d3449')}
        />
        <button type="submit" disabled={!input.trim() || loading}
          className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1.5 rounded-lg transition-all disabled:opacity-40 cursor-pointer"
          style={{ color:'#f97316' }}
          onMouseEnter={e => !loading && (e.currentTarget.style.background='rgba(249,115,22,0.15)')}
          onMouseLeave={e => (e.currentTarget.style.background='transparent')}>
          <Send className="w-4 h-4" />
        </button>
      </form>
    </div>
  );
}
