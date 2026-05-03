import React, { useState, useRef, useEffect, useCallback, useMemo } from "react";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";

const SESSION_ID = (() => {
  const k = "chatbot_sid";
  let id = sessionStorage.getItem(k);
  if (!id) { id = crypto.randomUUID(); sessionStorage.setItem(k, id); }
  return id;
})();

type Msg = { role: "user" | "assistant" | "system"; content: string; ts: Date };
type Biz = { id: string; name: string; industry: string; schedule?: string; contact_info?: string };

const ICONS: Record<string, string> = {
  veterinaria: "🐾", cafeteria: "☕", cafe: "☕", restaurant: "🍽️",
  restaurante: "🍽️", inmobiliaria: "🏠", dental: "🦷", clinica: "🏥",
  gym: "💪", gimnasio: "💪", peluqueria: "✂️", farmacia: "💊",
  libreria: "📚", ferreteria: "🔧", panaderia: "🥖", floreria: "🌸",
};

function icon(ind: string) {
  const k = Object.keys(ICONS).find(x => ind.toLowerCase().includes(x));
  return k ? ICONS[k] : "🏪";
}

function md(t: string) {
  const parts: React.JSX.Element[] = [];
  const lines = t.split("\n");
  lines.forEach((line, li) => {
    const segs: React.JSX.Element[] = [];
    const rx = /(\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`)/g;
    let last = 0, m;
    while ((m = rx.exec(line)) !== null) {
      if (m.index > last) segs.push(<span key={`t${li}-${last}`}>{line.slice(last, m.index)}</span>);
      if (m[2]) segs.push(<strong key={`b${li}-${m.index}`}>{m[2]}</strong>);
      else if (m[3]) segs.push(<em key={`i${li}-${m.index}`}>{m[3]}</em>);
      else if (m[4]) segs.push(<code key={`c${li}-${m.index}`} style={{ background: "rgba(99,102,241,0.1)", padding: "1px 5px", borderRadius: 4, fontSize: 13 }}>{m[4]}</code>);
      last = m.index + m[0].length;
    }
    if (last < line.length) segs.push(<span key={`e${li}`}>{line.slice(last)}</span>);
    if (segs.length === 0) segs.push(<span key={`empty${li}`}>{"\u00A0"}</span>);
    parts.push(<span key={`l${li}`}>{segs}{li < lines.length - 1 && <br />}</span>);
  });
  return <>{parts}</>;
}

function Skeleton() {
  const s: React.CSSProperties = {
    height: 80, borderRadius: 16, background: "linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%)",
    backgroundSize: "200% 100%", animation: "shimmer 1.5s infinite",
  };
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px,1fr))", gap: 14, marginTop: 20 }}>
      <div style={s} /> <div style={s} /> <div style={s} />
    </div>
  );
}

function Dots() {
  const d: React.CSSProperties = { width: 8, height: 8, borderRadius: "50%", background: "#94a3b8", display: "inline-block", animation: "bounce 1.2s infinite ease-in-out" };
  return (
    <div style={{ ...S.msgRow(false), animation: "fadeInUp .3s ease" }}>
      <div style={S.avatar}>{" "}</div>
      <div style={S.bubble("assistant")}>
        <div style={{ display: "flex", gap: 5, padding: "4px 0" }}>
          <span style={{ ...d, animationDelay: "0ms" }} />
          <span style={{ ...d, animationDelay: "160ms" }} />
          <span style={{ ...d, animationDelay: "320ms" }} />
        </div>
      </div>
    </div>
  );
}

function Bubble({ msg, bizIcon }: { msg: Msg; bizIcon: string }) {
  const u = msg.role === "user";
  if (msg.role === "system") return (
    <div style={{ textAlign: "center", fontSize: 12, color: "#ef4444", background: "rgba(239,68,68,0.08)", borderRadius: 10, padding: "8px 14px", margin: "4px 20px", animation: "fadeInUp .3s ease" }}>
      {msg.content}
    </div>
  );
  return (
    <div style={{ ...S.msgRow(u), animation: u ? "slideInRight .3s ease" : "slideInLeft .3s ease" }}>
      {!u && <div style={S.avatar}>{bizIcon}</div>}
      <div style={S.bubble(msg.role)}>
        <div style={{ margin: 0, fontSize: 14, lineHeight: 1.6 }}>{md(msg.content)}</div>
        <span style={{ display: "block", fontSize: 10, opacity: 0.5, marginTop: 4, textAlign: u ? "left" : "right" }}>
          {msg.ts.toLocaleTimeString("es-CL", { hour: "2-digit", minute: "2-digit" })}
        </span>
      </div>
      {u && <div style={S.avatar}>👤</div>}
    </div>
  );
}

export default function App() {
  const [biz, setBiz] = useState<Biz[]>([]);
  const [sel, setSel] = useState<Biz | null>(null);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [inp, setInp] = useState("");
  const [load, setLoad] = useState(false);
  const [loadBiz, setLoadBiz] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [hov, setHov] = useState<string | null>(null);
  const btm = useRef<HTMLDivElement>(null);
  const inpRef = useRef<HTMLTextAreaElement>(null);

  const bizIcon = useMemo(() => sel ? icon(sel.industry) : "🤖", [sel]);
  const charsLeft = 2000 - inp.length;

  useEffect(() => { btm.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, load]);

  useEffect(() => {
    (async () => {
      setLoadBiz(true);
      try {
        const r = await fetch(`${API}/businesses?active=true&limit=20`);
        if (!r.ok) throw new Error();
        const d = await r.json();
        setBiz(d.items || []);
        if (d.items?.length === 1) setSel(d.items[0]);
      } catch { setErr("No se pudo conectar al servidor. ¿Está corriendo el backend?"); }
      finally { setLoadBiz(false); }
    })();
  }, []);

  useEffect(() => {
    if (!sel) return;
    setMsgs([{ role: "assistant", content: `¡Hola! 👋 Soy el asistente virtual de **${sel.name}**. ¿En qué te puedo ayudar hoy?`, ts: new Date() }]);
    setTimeout(() => inpRef.current?.focus(), 100);
  }, [sel]);

  const send = useCallback(async () => {
    if (!inp.trim() || load || !sel) return;
    const um: Msg = { role: "user", content: inp.trim(), ts: new Date() };
    setMsgs(p => [...p, um]); setInp(""); setLoad(true); setErr(null);
    try {
      const r = await fetch(`${API}/chat`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: SESSION_ID, message: um.content, business_id: sel.id }),
      });
      if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || `Error ${r.status}`); }
      const d = await r.json();
      setMsgs(p => [...p, { role: "assistant", content: d.reply, ts: new Date() }]);
    } catch (e: any) {
      setMsgs(p => [...p, { role: "system", content: `⚠️ ${e.message || "Error de conexión"}`, ts: new Date() }]);
    } finally { setLoad(false); setTimeout(() => inpRef.current?.focus(), 50); }
  }, [inp, load, sel]);

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  };

  // ── Selector ──
  if (!sel) return (
    <div style={S.page}>
      <div style={S.selCard}>
        <div style={{ fontSize: 56, animation: "pulse 2.5s ease-in-out infinite" }}>🤖</div>
        <h1 style={{ margin: "12px 0 0", fontSize: 28, fontWeight: 800, background: "linear-gradient(135deg,#6366f1,#8b5cf6)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
          Chatbot IA Local
        </h1>
        <p style={{ color: "#64748b", marginTop: 8, fontSize: 14, lineHeight: 1.5 }}>
          Asistente virtual con IA privada para tu negocio
        </p>

        {loadBiz ? <Skeleton /> : err ? (
          <div style={{ marginTop: 24, background: "rgba(239,68,68,0.06)", border: "1px solid rgba(239,68,68,0.2)", borderRadius: 14, padding: "20px" }}>
            <div style={{ fontSize: 32, marginBottom: 8 }}>⚠️</div>
            <p style={{ color: "#dc2626", fontSize: 14, marginBottom: 14 }}>{err}</p>
            <button onClick={() => { setErr(null); setLoadBiz(true); window.location.reload(); }}
              style={{ padding: "8px 24px", borderRadius: 10, border: "none", background: "linear-gradient(135deg,#6366f1,#8b5cf6)", color: "#fff", cursor: "pointer", fontWeight: 600, fontSize: 13 }}>
              Reintentar
            </button>
          </div>
        ) : biz.length === 0 ? (
          <div style={{ marginTop: 24, background: "#f8fafc", borderRadius: 14, padding: 24, color: "#64748b" }}>
            <div style={{ fontSize: 32, marginBottom: 8 }}>📭</div>
            <p style={{ fontSize: 14 }}>No hay negocios activos.</p>
            <p style={{ fontSize: 12, color: "#94a3b8", marginTop: 6 }}>Crea uno desde el backend o ejecuta el SQL de demo.</p>
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px,1fr))", gap: 14, marginTop: 24 }}>
            {biz.map(b => (
              <button key={b.id} onClick={() => setSel(b)}
                onMouseEnter={() => setHov(b.id)} onMouseLeave={() => setHov(null)}
                style={{
                  display: "flex", flexDirection: "column", alignItems: "center", gap: 8,
                  padding: "24px 16px", border: hov === b.id ? "2px solid #6366f1" : "2px solid rgba(99,102,241,0.12)",
                  borderRadius: 18, background: hov === b.id ? "rgba(99,102,241,0.04)" : "white", cursor: "pointer",
                  transition: "all .2s ease", transform: hov === b.id ? "scale(1.03)" : "scale(1)",
                  boxShadow: hov === b.id ? "0 8px 30px rgba(99,102,241,0.18)" : "0 2px 12px rgba(0,0,0,0.04)",
                }}>
                <span style={{ fontSize: 36 }}>{icon(b.industry)}</span>
                <span style={{ fontWeight: 700, fontSize: 15, color: "#1e293b", textAlign: "center" }}>{b.name}</span>
                <span style={{ fontSize: 11, color: "#8b5cf6", background: "rgba(139,92,246,0.08)", padding: "3px 10px", borderRadius: 20, fontWeight: 600, textTransform: "capitalize" }}>{b.industry}</span>
              </button>
            ))}
          </div>
        )}

        <p style={{ marginTop: 28, fontSize: 11, color: "#94a3b8" }}>
          🔒 IA local • Datos privados • Sin servidores externos
        </p>
      </div>
    </div>
  );

  // ── Chat ──
  return (
    <div style={S.page}>
      <div style={S.chatWrap}>
        <div style={S.header}>
          <button onClick={() => setSel(null)} style={S.backBtn} title="Volver">←</button>
          <div style={{ flex: 1, display: "flex", flexDirection: "column" as const }}>
            <span style={{ fontWeight: 700, fontSize: 16 }}>{sel.name}</span>
            {sel.schedule && <span style={{ fontSize: 11, opacity: .8, marginTop: 1 }}>🕐 {sel.schedule}</span>}
          </div>
          <div style={S.onlineBadge}>
            <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#34d399", display: "inline-block", animation: "onlinePulse 2s infinite", marginRight: 5 }} />
            En línea
          </div>
        </div>

        <div style={S.msgArea}>
          {msgs.map((m, i) => <Bubble key={i} msg={m} bizIcon={bizIcon} />)}
          {load && <Dots />}
          <div ref={btm} />
        </div>

        <div style={S.inputWrap}>
          {charsLeft < 200 && (
            <div style={{ position: "absolute" as const, top: -22, right: 16, fontSize: 11, color: charsLeft < 50 ? "#ef4444" : "#94a3b8" }}>
              {charsLeft} caracteres restantes
            </div>
          )}
          <textarea ref={inpRef} style={S.input} value={inp}
            onChange={e => setInp(e.target.value.slice(0, 2000))}
            onKeyDown={onKey} placeholder="Escribe tu consulta..." disabled={load}
            rows={1}
            onInput={(e) => { const t = e.currentTarget; t.style.height = "auto"; t.style.height = Math.min(t.scrollHeight, 100) + "px"; }}
          />
          <button style={{ ...S.sendBtn, opacity: load || !inp.trim() ? .4 : 1 }}
            onClick={send} disabled={load || !inp.trim()} id="send-btn">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="19" x2="12" y2="5" /><polyline points="5 12 12 5 19 12" />
            </svg>
          </button>
        </div>

        <p style={{ textAlign: "center" as const, fontSize: 10, color: "#94a3b8", padding: "6px 0 10px", margin: 0 }}>
          🔒 IA local • Datos privados • No usan servidores externos
        </p>
      </div>
    </div>
  );
}

// ── Styles ──

const S = {
  page: {
    minHeight: "100vh", width: "100%", display: "flex", alignItems: "center", justifyContent: "center",
    background: "linear-gradient(-45deg, #6366f1, #8b5cf6, #3b82f6, #6366f1)",
    backgroundSize: "300% 300%", animation: "gradientShift 15s ease infinite",
    padding: 16, fontFamily: "'Inter', system-ui, sans-serif",
  } as React.CSSProperties,

  selCard: {
    background: "rgba(255,255,255,0.95)", backdropFilter: "blur(24px)", WebkitBackdropFilter: "blur(24px)",
    borderRadius: 24, padding: "44px 36px", maxWidth: 560, width: "100%",
    textAlign: "center" as const, boxShadow: "0 20px 60px rgba(0,0,0,0.12), 0 0 0 1px rgba(255,255,255,0.5)",
  } as React.CSSProperties,

  chatWrap: {
    display: "flex", flexDirection: "column" as const, height: "min(720px, 94vh)",
    width: "min(520px, 100%)", background: "rgba(255,255,255,0.95)",
    backdropFilter: "blur(20px)", WebkitBackdropFilter: "blur(20px)",
    borderRadius: 24, overflow: "hidden",
    boxShadow: "0 24px 64px rgba(0,0,0,0.15), 0 0 0 1px rgba(255,255,255,0.4)",
  } as React.CSSProperties,

  header: {
    background: "linear-gradient(135deg, #6366f1, #4f46e5)", color: "#fff",
    padding: "16px 18px", display: "flex", alignItems: "center", gap: 12,
  } as React.CSSProperties,

  backBtn: {
    background: "rgba(255,255,255,0.15)", border: "none", color: "#fff",
    width: 36, height: 36, borderRadius: "50%", cursor: "pointer", fontSize: 18,
    display: "flex", alignItems: "center", justifyContent: "center",
    transition: "background .2s",
  } as React.CSSProperties,

  onlineBadge: {
    fontSize: 11, opacity: 0.95, whiteSpace: "nowrap" as const, display: "flex", alignItems: "center",
  } as React.CSSProperties,

  msgArea: {
    flex: 1, overflowY: "auto" as const, padding: "18px 14px",
    display: "flex", flexDirection: "column" as const, gap: 10,
    background: "linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%)",
  } as React.CSSProperties,

  msgRow: (u: boolean): React.CSSProperties => ({
    display: "flex", flexDirection: u ? "row-reverse" : "row", alignItems: "flex-end", gap: 8,
  }),

  avatar: { fontSize: 22, flexShrink: 0, marginBottom: 4 } as React.CSSProperties,

  bubble: (role: string): React.CSSProperties => ({
    maxWidth: "75%", padding: "12px 16px",
    borderRadius: role === "user" ? "20px 20px 6px 20px" : "20px 20px 20px 6px",
    background: role === "user" ? "linear-gradient(135deg, #6366f1, #4f46e5)" : "white",
    color: role === "user" ? "#fff" : "#1e293b",
    boxShadow: role === "user" ? "0 4px 14px rgba(99,102,241,0.3)" : "0 2px 10px rgba(0,0,0,0.06)",
    border: role === "user" ? "none" : "1px solid rgba(226,232,240,0.8)",
  }),

  inputWrap: {
    display: "flex", padding: "12px 14px", gap: 10,
    borderTop: "1px solid rgba(226,232,240,0.6)", background: "white", position: "relative" as const,
  } as React.CSSProperties,

  input: {
    flex: 1, padding: "12px 18px", borderRadius: 22,
    border: "1.5px solid #e2e8f0", fontSize: 14, outline: "none",
    background: "#f8fafc", color: "#1e293b", resize: "none" as const,
    lineHeight: 1.5, maxHeight: 100, overflow: "auto" as const,
    transition: "border-color .2s",
  } as React.CSSProperties,

  sendBtn: {
    width: 44, height: 44, borderRadius: "50%",
    background: "linear-gradient(135deg, #6366f1, #4f46e5)",
    color: "#fff", border: "none", cursor: "pointer",
    display: "flex", alignItems: "center", justifyContent: "center",
    flexShrink: 0, transition: "all .2s", boxShadow: "0 4px 12px rgba(99,102,241,0.3)",
  } as React.CSSProperties,
};
