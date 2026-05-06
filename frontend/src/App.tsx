import { useState, useRef, useEffect, useCallback } from "react";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const SESSION_ID = (() => {
  const k = "cpyme_sid";
  let id = sessionStorage.getItem(k);
  if (!id) { id = crypto.randomUUID(); sessionStorage.setItem(k, id); }
  return id;
})();

const IS_EMBED = new URLSearchParams(window.location.search).get("embed") === "true";
const PRESET_BIZ = new URLSearchParams(window.location.search).get("business") || null;

type Role = "user" | "assistant" | "system";
type Message = { role: Role; content: string; ts: Date };
type Business = { id: string; name: string; industry: string; schedule?: string; contact_info?: string };

function parseMarkdown(text: string): React.ReactNode {
  const lines = text.split("\n");
  return lines.map((line, i) => {
    const parts = line.split(/(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g);
    const nodes = parts.map((p, j) => {
      if (p.startsWith("**") && p.endsWith("**"))
        return <strong key={j} style={{ fontWeight: 600 }}>{p.slice(2, -2)}</strong>;
      if (p.startsWith("*") && p.endsWith("*"))
        return <em key={j}>{p.slice(1, -1)}</em>;
      if (p.startsWith("`") && p.endsWith("`"))
        return <code key={j} style={{ background: "rgba(0,0,0,0.08)", borderRadius: 4, padding: "1px 5px", fontSize: "0.9em", fontFamily: "monospace" }}>{p.slice(1, -1)}</code>;
      return p;
    });
    return <span key={i}>{nodes}{i < lines.length - 1 && <br />}</span>;
  });
}

function bizIcon(industry: string): string {
  const map: Record<string, string> = {
    veterinaria: "🐾", vet: "🐾", cafeteria: "☕", cafe: "☕", coffee: "☕",
    restaurant: "🍽️", restaurante: "🍽️", inmobiliaria: "🏠", dental: "🦷",
    clinica: "🏥", clinic: "🏥", gym: "💪", gimnasio: "💪",
    peluqueria: "✂️", salon: "✂️", farmacia: "💊", pharmacy: "💊",
    educacion: "📚", escuela: "📚", hotel: "🏨", turismo: "✈️",
  };
  const k = Object.keys(map).find(key => industry.toLowerCase().includes(key));
  return k ? map[k] : "🏪";
}

function fmtTime(d: Date): string {
  return d.toLocaleTimeString("es-CL", { hour: "2-digit", minute: "2-digit" });
}

const CSS = `
  *{box-sizing:border-box;margin:0;padding:0;}
  body{font-family:'Segoe UI',system-ui,sans-serif;}
  @keyframes bounce{0%,80%,100%{transform:translateY(0)}40%{transform:translateY(-7px)}}
  @keyframes pulse{0%,100%{transform:scale(1)}50%{transform:scale(1.06)}}
  @keyframes shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}
  @keyframes slideUp{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:none}}
  @keyframes bgShift{from{background-position:0% 50%}to{background-position:100% 50%}}
  ::-webkit-scrollbar{width:4px}
  ::-webkit-scrollbar-track{background:transparent}
  ::-webkit-scrollbar-thumb{background:#ddd;border-radius:4px}
`;

function Skeleton() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12, padding: "8px 0" }}>
      {[180, 220, 160].map((w, i) => (
        <div key={i} style={{
          height: 72, width: w, borderRadius: 16,
          background: "linear-gradient(90deg,#f0f0f0 25%,#e0e0e0 50%,#f0f0f0 75%)",
          backgroundSize: "200% 100%", animation: "shimmer 1.4s infinite",
        }} />
      ))}
    </div>
  );
}

function TypingDots({ color }: { color: string }) {
  return (
    <div style={{ display: "flex", gap: 5, padding: "6px 2px", alignItems: "center" }}>
      {[0, 1, 2].map(i => (
        <div key={i} style={{
          width: 7, height: 7, borderRadius: "50%", background: color,
          animation: `bounce 1.2s ease-in-out ${i * 0.16}s infinite`,
        }} />
      ))}
    </div>
  );
}

function Bubble({ msg, icon, accentColor }: { msg: Message; icon: string; accentColor: string }) {
  const isUser = msg.role === "user";
  if (msg.role === "system") return (
    <div style={{ textAlign: "center", fontSize: 12, color: "#e53935", background: "#fff0f0", borderRadius: 8, padding: "6px 14px", margin: "2px 0" }}>
      {msg.content}
    </div>
  );
  return (
    <div style={{ display: "flex", flexDirection: isUser ? "row-reverse" : "row", alignItems: "flex-end", gap: 8 }}>
      {!isUser && (
        <div style={{ width: 32, height: 32, borderRadius: "50%", background: accentColor + "22", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16, flexShrink: 0 }}>
          {icon}
        </div>
      )}
      <div style={{
        maxWidth: "74%", padding: "10px 14px",
        borderRadius: isUser ? "18px 18px 4px 18px" : "4px 18px 18px 18px",
        background: isUser ? accentColor : "white",
        color: isUser ? "white" : "#1a1a1a",
        boxShadow: isUser ? `0 2px 12px ${accentColor}44` : "0 1px 6px rgba(0,0,0,0.08)",
        border: isUser ? "none" : "1px solid #f0f0f0",
        fontSize: 14, lineHeight: 1.55,
      }}>
        <div style={{ whiteSpace: "pre-wrap" }}>{parseMarkdown(msg.content)}</div>
        <div style={{ fontSize: 10, marginTop: 5, opacity: 0.55, textAlign: isUser ? "right" : "left" }}>
          {fmtTime(msg.ts)}
        </div>
      </div>
    </div>
  );
}

function BizCard({ biz, onClick }: { biz: Business; onClick: () => void }) {
  const [hov, setHov] = useState(false);
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHov(true)}
      onMouseLeave={() => setHov(false)}
      style={{
        display: "flex", flexDirection: "column", alignItems: "center", gap: 10,
        padding: "24px 16px", border: hov ? "2px solid #4F6FF0" : "2px solid #eee",
        borderRadius: 16, background: hov ? "#f7f8ff" : "white", cursor: "pointer",
        transition: "all 0.18s ease", transform: hov ? "translateY(-2px)" : "none",
        boxShadow: hov ? "0 8px 24px rgba(79,111,240,0.12)" : "none",
      }}
    >
      <div style={{ width: 56, height: 56, borderRadius: 14, background: "linear-gradient(135deg,#f0f3ff,#e8ecff)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 28 }}>
        {bizIcon(biz.industry)}
      </div>
      <div style={{ textAlign: "center" }}>
        <div style={{ fontWeight: 600, fontSize: 14, color: "#1a1a1a", marginBottom: 4 }}>{biz.name}</div>
        <div style={{ fontSize: 11, color: "#4F6FF0", background: "#f0f3ff", borderRadius: 20, padding: "2px 10px", textTransform: "capitalize", display: "inline-block" }}>
          {biz.industry}
        </div>
      </div>
    </button>
  );
}

function ChatView({ biz, onBack, compact = false }: { biz: Business; onBack?: () => void; compact?: boolean }) {
  const accentColor = "#4F6FF0";
  const icon = bizIcon(biz.industry);
  const [messages, setMessages] = useState<Message[]>([{
    role: "assistant",
    content: `¡Hola! Soy el asistente de **${biz.name}**. ¿En qué te puedo ayudar hoy?`,
    ts: new Date(),
  }]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [charCount, setCharCount] = useState(0);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, loading]);
  useEffect(() => { inputRef.current?.focus(); }, []);

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || loading) return;
    setMessages(p => [...p, { role: "user", content: text, ts: new Date() }]);
    setInput(""); setCharCount(0); setLoading(true);
    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: SESSION_ID, message: text, business_id: biz.id }),
      });
      if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || `Error ${res.status}`); }
      const data = await res.json();
      setMessages(p => [...p, { role: "assistant", content: data.reply, ts: new Date() }]);
    } catch (e: any) {
      setMessages(p => [...p, { role: "system", content: `⚠️ ${e.message || "Error de conexión"}`, ts: new Date() }]);
    } finally { setLoading(false); }
  }, [input, loading, biz.id]);

  const handleKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value); setCharCount(e.target.value.length);
    e.target.style.height = "auto";
    e.target.style.height = Math.min(e.target.scrollHeight, 120) + "px";
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", background: "#fafbff" }}>
      <div style={{ minHeight: compact ? 56 : 68, background: `linear-gradient(135deg,${accentColor},#6C8FFF)`, display: "flex", alignItems: "center", padding: compact ? "0 14px" : "0 20px", gap: 12, flexShrink: 0 }}>
        {onBack && (
          <button onClick={onBack} style={{ background: "rgba(255,255,255,0.2)", border: "none", color: "white", width: 32, height: 32, borderRadius: "50%", cursor: "pointer", fontSize: 16, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
            ←
          </button>
        )}
        <div style={{ width: compact ? 32 : 40, height: compact ? 32 : 40, borderRadius: "50%", background: "rgba(255,255,255,0.2)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: compact ? 16 : 20, flexShrink: 0 }}>{icon}</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ color: "white", fontWeight: 700, fontSize: compact ? 13 : 15, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{biz.name}</div>
          {biz.schedule && !compact && <div style={{ color: "rgba(255,255,255,0.8)", fontSize: 11, marginTop: 1 }}>🕐 {biz.schedule}</div>}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 5, color: "rgba(255,255,255,0.9)", fontSize: 11, flexShrink: 0 }}>
          <div style={{ width: 7, height: 7, borderRadius: "50%", background: "#4ade80", boxShadow: "0 0 6px #4ade80" }} />
          En línea
        </div>
      </div>

      <div style={{ flex: 1, overflowY: "auto", padding: compact ? "12px 10px" : "16px", display: "flex", flexDirection: "column", gap: 10 }}>
        {messages.map((m, i) => <Bubble key={i} msg={m} icon={icon} accentColor={accentColor} />)}
        {loading && (
          <div style={{ display: "flex", alignItems: "flex-end", gap: 8 }}>
            <div style={{ width: 32, height: 32, borderRadius: "50%", background: accentColor + "22", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16 }}>{icon}</div>
            <div style={{ background: "white", borderRadius: "4px 18px 18px 18px", padding: "8px 14px", border: "1px solid #f0f0f0", boxShadow: "0 1px 6px rgba(0,0,0,0.06)" }}>
              <TypingDots color="#aaa" />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div style={{ borderTop: "1px solid #eef0f8", padding: compact ? "8px 10px" : "12px 16px", background: "white" }}>
        <div style={{ display: "flex", gap: 8, alignItems: "center", background: "#f4f5ff", borderRadius: 24, padding: "4px 4px 4px 16px", border: "1px solid #e8eaff" }}>
          <textarea
            ref={inputRef} value={input} onChange={handleInput} onKeyDown={handleKey}
            placeholder="Escribe tu consulta..." disabled={loading} maxLength={2000} rows={1}
            style={{ flex: 1, border: "none", background: "transparent", fontSize: 14, outline: "none", resize: "none", fontFamily: "inherit", color: "#1a1a1a", lineHeight: "24px", maxHeight: 120, overflowY: "auto", margin: 0, padding: "6px 0" }}
          />
          {charCount > 1800 && <span style={{ fontSize: 10, color: "#e53935", alignSelf: "flex-end", marginBottom: 6 }}>{2000 - charCount}</span>}
          <button
            onClick={send} disabled={loading || !input.trim()}
            style={{ width: 36, height: 36, borderRadius: "50%", background: loading || !input.trim() ? "#d0d4f0" : accentColor, border: "none", cursor: loading || !input.trim() ? "not-allowed" : "pointer", color: "white", fontSize: 16, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, transition: "background 0.15s" }}
          >↑</button>
        </div>
        <div style={{ textAlign: "center", fontSize: 10, color: "#bbb", marginTop: 6 }}>
          IA local • Datos privados • Sin servidores externos
        </div>
      </div>
    </div>
  );
}

function Selector({ onSelect, allowAutoSelect = true }: { onSelect: (b: Business) => void; allowAutoSelect?: boolean }) {
  const [businesses, setBusinesses] = useState<Business[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${API_URL}/businesses?active=true&limit=20`);
        if (!r.ok) throw new Error("Error cargando negocios");
        const d = await r.json();
        const items: Business[] = d.items || [];
        setBusinesses(items);
        if (!allowAutoSelect) return; // respeta la vuelta del usuario
        if (PRESET_BIZ) { const f = items.find(b => b.id === PRESET_BIZ); if (f) { onSelect(f); return; } }
      } catch { setError("No se pudo conectar al servidor"); }
      finally { setLoading(false); }
    })();
  }, []);

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", padding: 24, background: "linear-gradient(135deg,#eef2ff 0%,#f5f0ff 50%,#e8f4ff 100%)" }}>
      <div style={{ background: "rgba(255,255,255,0.92)", backdropFilter: "blur(20px)", borderRadius: 24, padding: "40px 36px", maxWidth: 520, width: "100%", boxShadow: "0 20px 60px rgba(79,111,240,0.1),0 4px 16px rgba(0,0,0,0.06)", border: "1px solid rgba(79,111,240,0.12)" }}>
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <div style={{ fontSize: 52, marginBottom: 14, animation: "pulse 2.5s ease-in-out infinite", display: "inline-block" }}>🤖</div>
          <h1 style={{ margin: 0, fontSize: 26, fontWeight: 700, color: "#1a1a1a", letterSpacing: "-0.5px" }}>Chatbot IA Local</h1>
          <p style={{ margin: "8px 0 0", fontSize: 15, color: "#666" }}>Asistente virtual con IA privada para tu negocio</p>
        </div>
        {loading ? <Skeleton /> : error ? (
          <div style={{ background: "#fff0f0", border: "1px solid #ffcdd2", borderRadius: 12, padding: "16px 20px", textAlign: "center" }}>
            <div style={{ fontSize: 24, marginBottom: 8 }}>⚠️</div>
            <div style={{ color: "#c62828", fontSize: 14 }}>{error}</div>
            <button onClick={() => window.location.reload()} style={{ marginTop: 12, padding: "8px 20px", background: "#c62828", color: "white", border: "none", borderRadius: 8, cursor: "pointer", fontSize: 13 }}>Reintentar</button>
          </div>
        ) : businesses.length === 0 ? (
          <div style={{ background: "#f8f9ff", borderRadius: 12, padding: 20, textAlign: "center", color: "#666", fontSize: 14 }}>No hay negocios activos configurados.</div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(160px,1fr))", gap: 14 }}>
            {businesses.map(b => <BizCard key={b.id} biz={b} onClick={() => onSelect(b)} />)}
          </div>
        )}
        <div style={{ marginTop: 28, paddingTop: 20, borderTop: "1px solid #f0f0f0", display: "flex", justifyContent: "center", gap: 20 }}>
          {["🔒 Datos privados", "⚡ IA local", "🇨🇱 Hecho en Chile"].map(t => (
            <span key={t} style={{ fontSize: 11, color: "#999" }}>{t}</span>
          ))}
        </div>
      </div>
    </div>
  );
}

function EmbedBubble() {
  const [open, setOpen] = useState(false);
  const [biz, setBiz] = useState<Business | null>(null);
  const [loadingBiz, setLoadingBiz] = useState(true);
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    if (!PRESET_BIZ) { setLoadingBiz(false); return; }
    fetch(`${API_URL}/businesses/${PRESET_BIZ}`)
      .then(r => r.json()).then(d => setBiz(d)).catch(() => {}).finally(() => setLoadingBiz(false));
  }, []);

  useEffect(() => {
    if (biz && !open) { const t = setTimeout(() => setUnread(1), 3000); return () => clearTimeout(t); }
  }, [biz, open]);

  if (loadingBiz) return null;

  return (
    <>
      {open && (
        <div style={{ position: "fixed", bottom: 90, right: 20, width: 370, height: 560, borderRadius: 20, overflow: "hidden", boxShadow: "0 20px 60px rgba(0,0,0,0.2),0 4px 16px rgba(79,111,240,0.15)", animation: "slideUp 0.25s ease", zIndex: 9998, border: "1px solid rgba(79,111,240,0.15)" }}>
          {biz ? <ChatView biz={biz} compact={true} /> : <Selector onSelect={b => setBiz(b)} />}
        </div>
      )}
      <button
        onClick={() => { if (!open) setUnread(0); setOpen(o => !o); }}
        style={{ position: "fixed", bottom: 20, right: 20, width: 56, height: 56, borderRadius: "50%", background: "linear-gradient(135deg,#4F6FF0,#6C8FFF)", border: "none", cursor: "pointer", boxShadow: "0 4px 20px rgba(79,111,240,0.45)", fontSize: 24, color: "white", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 9999 }}
        onMouseEnter={e => (e.currentTarget.style.transform = "scale(1.08)")}
        onMouseLeave={e => (e.currentTarget.style.transform = "scale(1)")}
      >
        {open ? "✕" : "💬"}
        {!open && unread > 0 && (
          <div style={{ position: "absolute", top: -2, right: -2, width: 18, height: 18, borderRadius: "50%", background: "#ef4444", color: "white", fontSize: 10, fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center", border: "2px solid white" }}>
            {unread}
          </div>
        )}
      </button>
    </>
  );
}

export default function App() {
  return (
    <>
      <style>{CSS}</style>
      {IS_EMBED ? <EmbedBubble /> : <Standalone />}
    </>
  );
}

function Standalone() {
  const [biz, setBiz] = useState<Business | null>(null);
  const [cameBack, setCameBack] = useState(false);

  const handleBack = () => { setBiz(null); setCameBack(true); };

  return !biz ? (
    <Selector onSelect={setBiz} allowAutoSelect={!cameBack} />
  ) : (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "100vh", background: "linear-gradient(135deg,#eef2ff 0%,#f5f0ff 50%,#e8f4ff 100%)", padding: 16 }}>
      <div style={{ width: "100%", maxWidth: 480, height: "min(680px,94vh)", borderRadius: 24, overflow: "hidden", boxShadow: "0 24px 80px rgba(79,111,240,0.15),0 4px 20px rgba(0,0,0,0.08)", border: "1px solid rgba(79,111,240,0.15)" }}>
        <ChatView biz={biz} onBack={handleBack} />
      </div>
    </div>
  );
}
