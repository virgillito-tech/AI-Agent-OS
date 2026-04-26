"use client";

import { useState, useRef, useEffect, useCallback } from "react";

// ---------------------------------------------------------------------------
// TIPI
// ---------------------------------------------------------------------------

type Message = {
  role: "user" | "ai";
  content: string;
  imageUrl?: string;
  isStreaming?: boolean;
  reasoning?: string[];
};

type SetupStep = "checking" | "ollama_missing" | "permissions" | "ready";

type SysStats = {
  cpu: number;
  ramPercent: number;
  ramUsed: number;
  ramTotal: number;
  gpu: number;
};

const API = "http://localhost:8000";

// ---------------------------------------------------------------------------
// COMPONENTE PRINCIPALE
// ---------------------------------------------------------------------------

export default function Home() {
  const [chatMode, setChatMode] = useState<"fast" | "agent">("agent");
  const [setupStep, setSetupStep] = useState<SetupStep>("checking");
  const [isReady, setIsReady] = useState(false);
  
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [loadingStatus, setLoadingStatus] = useState("In attesa...");

  const [currentPlan, setCurrentPlan] = useState<string[]>([]);
  const [completedSteps, setCompletedSteps] = useState<string[]>([]);

  const [isMac, setIsMac] = useState(false);
  const [engine, setEngine] = useState("ollama");
  const [selectedModel, setSelectedModel] = useState("qwen2.5:7b");
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [isCustomModel, setIsCustomModel] = useState(false);
  const [engineStatus, setEngineStatus] = useState<"spento" | "in_avvio" | "acceso">("spento");
  const [engineError, setEngineError] = useState<string | null>(null);

  const [allowGlobalWrite, setAllowGlobalWrite] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [settingsTab, setSettingsTab] = useState<"general" | "auth" | "ollama" | "mlx" | "images" | "video">("general");
  const [envSettings, setEnvSettings] = useState({
  TELEGRAM_TOKEN: "", TG_API_ID: "", TG_API_HASH: "", EMAIL_USER: "", EMAIL_PASSWORD: "",
  ICLOUD_EMAIL: "", ICLOUD_APP_PASSWORD: "", SANDBOX_DIR: "sandbox",
  IMAGE_GEN_API_URL: "http://localhost:8000/generate", IMAGE_MODEL_NAME: "flux",
  ACTIVE_ENGINE: "ollama", TEXT_MODEL_NAME: "", FAST_MODEL_NAME: "", BASE_URL_TEXT: "http://localhost:11434", 
  VISION_MODEL_NAME: "", BASE_URL_VISION: "http://localhost:11434", MAX_TOKENS: "4096",
  MLX_TEXT_MODEL_NAME: "", MLX_BASE_URL: "http://localhost:8080", MLX_VISION_MODEL_NAME: "", MLX_FAST_MODEL_NAME: "",
  VIDEO_MODEL_NAME: "THUDM/CogVideoX-2b", 
    VIDEO_DEVICE: "auto"
});

  const [sysStats, setSysStats] = useState<SysStats>({ cpu: 0, ramPercent: 0, ramUsed: 0, ramTotal: 0, gpu: 0 });
  const [isRecording, setIsRecording] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const stopRequestedRef = useRef(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const planLength = currentPlan.length;
  const doneLength = completedSteps.length;
  const progressPercent = planLength > 0 ? Math.round((doneLength / planLength) * 100) : 0;
  const isFinalizing = planLength > 0 && doneLength === planLength;

  // ---------------------------------------------------------------------------
  // EFFETTI DI BASE E SETUP
  // ---------------------------------------------------------------------------

  const checkSystemReadiness = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/setup/health`);
      if (!res.ok) throw new Error("Backend non pronto");
      const status = await res.json();
      if (!status.ollama_active) setSetupStep("ollama_missing");
      else if (!status.workspace_granted) setSetupStep("permissions");
      else { setSetupStep("ready"); setIsReady(true); }
    } catch { setTimeout(checkSystemReadiness, 2000); }
  }, []);

  const requestFolderAccess = async () => {
    try {
      let selectedPath = "sandbox";
      try {
        if (typeof window !== 'undefined' && (window as any).__TAURI__) {
          // @ts-ignore
          const { open } = await import("@tauri-apps/plugin-dialog");
          const selected = await open({
            directory: true, multiple: false, title: "Seleziona cartella di lavoro",
          });
          if (selected) selectedPath = selected as string;
        } else { throw new Error("Non in ambiente Tauri"); }
      } catch {
        alert("⚠️ Interfaccia desktop nativa non rilevata. Uso cartella predefinita 'sandbox/'.");
      }

      await fetch(`${API}/api/setup/workspace`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: selectedPath }),
      });
      checkSystemReadiness();
    } catch (e) { console.error(e); }
  };

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const res = await fetch(`${API}/api/history`);
        if (res.ok) {
          const data = await res.json();
          setMessages(prev => {
            if (prev.length > 0 && prev[prev.length - 1].isStreaming) return prev;
            if (JSON.stringify(prev) === JSON.stringify(data)) return prev;
            return data;
          });
        }
      } catch (e) {}
    };
    fetchHistory();
    const interval = setInterval(fetchHistory, 3000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    checkSystemReadiness();
    const mac = (window.navigator?.userAgent?.toLowerCase() || "").includes("mac");
    setIsMac(mac);
    if (!mac) setEngine("ollama");

    const statsInterval = setInterval(async () => {
      try {
        const res = await fetch(`${API}/api/system_stats`);
        if (res.ok) {
          const d = await res.json();
          if (!d.error) setSysStats({ cpu: d.cpu_percent, ramPercent: d.ram_percent, ramUsed: d.ram_used_gb, ramTotal: d.ram_total_gb, gpu: d.gpu_percent ?? 0 });
        }
      } catch { }
    }, 2000);
    return () => clearInterval(statsInterval);
  }, [checkSystemReadiness]);

  useEffect(() => {
    fetch(`${API}/api/settings/permissions`).then(res => res.json()).then(data => setAllowGlobalWrite(data.allow_global_write)).catch(() => {});
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API}/api/models?engine=${engine}`);
        if (res.ok) {
          const data = await res.json();
          const models: string[] = data.models ?? [];
          setAvailableModels(models);
          if (models.length > 0) { setSelectedModel(models[0]); setIsCustomModel(false); } 
          else { setSelectedModel(""); setIsCustomModel(true); }
          setEngineError(data.error || null);
        }
      } catch { }
    })();
  }, [engine]);

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  // ---------------------------------------------------------------------------
  // FUNZIONI PANNELLO .ENV
  // ---------------------------------------------------------------------------

  const openSettings = async () => {
    try {
      const res = await fetch(`${API}/api/settings/env`);
      if(res.ok) setEnvSettings(await res.json());
    } catch (e) {}
    setIsSettingsOpen(true);
  };

  const saveSettings = async () => {
    try {
      await fetch(`${API}/api/settings/env`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(envSettings) });
      setIsSettingsOpen(false);
    } catch (e) { alert("Errore nel salvataggio."); }
  };

  const toggleGlobalWrite = async (val: boolean) => {
    setAllowGlobalWrite(val);
    await fetch(`${API}/api/settings/permissions`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ allow_global_write: val }) });
  };

  // ---------------------------------------------------------------------------
  // GESTIONE CHAT E RAGIONAMENTO (STREAMING)
  // ---------------------------------------------------------------------------

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!input.trim() && !file) return;

    const userMsg: Message = { role: "user", content: input, imageUrl: file ? URL.createObjectURL(file) : undefined };
    setMessages((prev) => [...prev, userMsg]);
    setInput(""); setFile(null); setIsLoading(true); setCurrentPlan([]); setCompletedSteps([]); setLoadingStatus("Elaborazione...");

    const form = new FormData();
    form.append("message", userMsg.content);
    form.append("engine", engine);
    form.append("max_tokens", envSettings.MAX_TOKENS || "4096");
    form.append("mode", chatMode);
    if (userMsg.imageUrl && file) form.append("file", file);

    try {
      const response = await fetch(`${API}/api/chat`, { method: "POST", body: form });
      if (!response.ok) throw new Error("Errore Server");
      if (!response.body) throw new Error("No body");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = ""; 
      
      let currentAIResponse = "";
      let currentReasoning: string[] = [];

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const dataStr = line.slice(6).trim();
          if (dataStr === "[DONE]") { setIsLoading(false); break; }

          try {
            const data = JSON.parse(dataStr);
            
            if (data.type === "status") {
              setLoadingStatus(data.content);
            }
            else if (data.type === "reasoning") {
              currentReasoning.push(data.content);
              setMessages(prev => {
                const msgs = [...prev];
                const last = msgs[msgs.length - 1];
                if (last?.role === "ai" && last.isStreaming) {
                  last.reasoning = [...currentReasoning];
                } else {
                  msgs.push({ role: "ai", content: "", isStreaming: true, reasoning: [...currentReasoning] });
                }
                return msgs;
              });
            }
            else if (data.type === "chunk") {
              currentAIResponse += data.content;
              setMessages(prev => {
                const msgs = [...prev];
                const last = msgs[msgs.length - 1];
                if (last?.role === "ai" && last.isStreaming) {
                  last.content = currentAIResponse;
                } else {
                  msgs.push({ role: "ai", content: currentAIResponse, isStreaming: true, reasoning: [...currentReasoning] });
                }
                return msgs;
              });
            }
            else if (data.type === "final") {
              setMessages(prev => {
                const msgs = [...prev];
                if (msgs[msgs.length - 1]?.role === "ai") msgs[msgs.length - 1].isStreaming = false;
                return msgs;
              });
              setIsLoading(false);
            }
            else if (data.type === "error") { 
              setMessages(prev => [...prev, { role: "ai", content: `⚠️ ${data.content}` }]); 
              setIsLoading(false); 
            }
          } catch { }
        }
      }
    } catch { setMessages(prev => [...prev, { role: "ai", content: "⚠️ Errore backend." }]); setIsLoading(false); }
  };

  const handleStartEngine = async () => { if (!selectedModel?.trim()) return setEngineError("Seleziona un modello."); setEngineStatus("in_avvio"); setEngineError(null); const form = new FormData(); form.append("engine", engine); form.append("model", selectedModel); try { const res = await fetch(`${API}/api/engine/start`, { method: "POST", body: form }); const data = await res.json(); if (data.status === "ok") setEngineStatus("acceso"); else { setEngineStatus("spento"); setEngineError(data.message); } } catch { setEngineStatus("spento"); setEngineError("Errore connessione."); } };
  const handleStopEngine = async () => { try { await fetch(`${API}/api/engine/stop`, { method: "POST" }); } catch { } setEngineStatus("spento"); };
  const handleClearChat = async () => { try { await fetch(`${API}/api/history/clear`, { method: "POST" }); setMessages([]); } catch { } };
  
  const startRecording = async (e?: any) => { if (e) e.preventDefault(); stopRequestedRef.current = false; try { const stream = await navigator.mediaDevices.getUserMedia({ audio: true }); if (stopRequestedRef.current) return stream.getTracks().forEach(t => t.stop()); const recorder = new MediaRecorder(stream); mediaRecorderRef.current = recorder; audioChunksRef.current = []; recorder.ondataavailable = (event) => event.data.size > 0 && audioChunksRef.current.push(event.data); recorder.onstop = async () => { const mimeType = recorder.mimeType || "audio/webm"; const ext = mimeType.includes("mp4") ? "mp4" : mimeType.includes("ogg") ? "ogg" : "webm"; await sendAudioToBackend(new Blob(audioChunksRef.current, { type: mimeType }), ext); stream.getTracks().forEach((track) => track.stop()); }; recorder.start(); setIsRecording(true); } catch { alert("🎤 Impossibile accedere al microfono."); } };
  const stopRecording = (e?: any) => { if (e) e.preventDefault(); stopRequestedRef.current = true; setIsRecording(false); if (mediaRecorderRef.current?.state === "recording") mediaRecorderRef.current.stop(); };
  const sendAudioToBackend = async (blob: Blob, ext: string) => { setIsLoading(true); setLoadingStatus("Trascrizione in corso..."); const form = new FormData(); form.append("audio", blob, `recording.${ext}`); try { const res = await fetch(`${API}/api/transcribe`, { method: "POST", body: form }); const data = await res.json(); if (data.text) setInput((prev) => prev + (prev ? " " : "") + data.text); } catch {} finally { setIsLoading(false); setLoadingStatus("In attesa..."); } };

  // ---------------------------------------------------------------------------
  // RENDER BLOCCHI STATO INIZIALE
  // ---------------------------------------------------------------------------
  if (!isReady) {
    return (
      <div className="flex flex-col items-center justify-center h-screen bg-zinc-950 text-zinc-200 p-4">
        <div className="max-w-md w-full bg-zinc-900 rounded-xl p-8 border border-zinc-800 shadow-2xl text-center space-y-6">
          {setupStep === "checking" && (<><div className="text-4xl animate-spin text-zinc-500">⚙️</div><h2 className="text-lg font-medium text-zinc-300">Inizializzazione sistema...</h2></>)}
          {setupStep === "ollama_missing" && (<><div className="text-4xl">🦙</div><h2 className="text-lg font-medium text-amber-400">Motore AI Locale non rilevato</h2><button onClick={checkSystemReadiness} className="w-full bg-zinc-100 hover:bg-white text-zinc-900 font-medium py-2 rounded-md transition-colors">Ricontrolla connessione</button></>)}
          {setupStep === "permissions" && (<><div className="text-4xl">📁</div><h2 className="text-lg font-medium text-zinc-300">Configurazione Workspace</h2><button onClick={requestFolderAccess} className="w-full bg-blue-600 hover:bg-blue-500 text-white font-medium py-2 rounded-md transition-colors">Seleziona Directory</button></>)}
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // RENDER INTERFACCIA PRINCIPALE
  // ---------------------------------------------------------------------------
  return (
    <div className="flex flex-col h-screen bg-zinc-950 text-zinc-200 font-sans selection:bg-blue-500/30">
      
      {/* HEADER TIPO DESKTOP APP */}
      <header className="px-4 py-3 bg-zinc-950 border-b border-zinc-800 flex-shrink-0 flex flex-col md:flex-row items-center justify-between gap-3 select-none">
        
        {/* LOGO E SELETTORE MOTORE */}
        <div className="flex items-center gap-4 w-full md:w-auto">
          <div className="font-semibold text-zinc-100 tracking-wide flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-blue-500"></div>
            AgentOS
          </div>
          
          <div className="h-4 w-px bg-zinc-800 hidden md:block"></div>

          <div className="flex items-center gap-2 text-sm">
            {isMac ? (
              <select value={engine} onChange={(e) => setEngine(e.target.value)} disabled={engineStatus !== "spento"} className="bg-zinc-900 text-zinc-300 px-2 py-1 rounded border border-zinc-800 outline-none focus:border-zinc-600">
                <option value="ollama">Ollama</option>
                <option value="mlx">Apple MLX</option>
              </select>
            ) : (
              <span className="bg-zinc-900 text-zinc-400 px-2 py-1 rounded border border-zinc-800">Ollama</span>
            )}

            {!isCustomModel ? (
              <select value={selectedModel} onChange={(e) => { if (e.target.value === "custom") { setIsCustomModel(true); setSelectedModel(""); } else setSelectedModel(e.target.value); }} disabled={engineStatus !== "spento"} className="bg-zinc-900 text-zinc-200 px-2 py-1 rounded border border-zinc-800 outline-none focus:border-zinc-600 max-w-[150px] truncate">
                {availableModels.length === 0 && <option value="" disabled>Nessun modello</option>}
                {availableModels.map(m => <option key={m} value={m}>{m}</option>)}
                <option value="custom">Personalizzato...</option>
              </select>
            ) : (
              <div className="flex items-center gap-1">
                <input type="text" value={selectedModel} onChange={e => setSelectedModel(e.target.value)} disabled={engineStatus !== "spento"} placeholder="ID modello" className="bg-zinc-900 text-zinc-200 px-2 py-1 rounded border border-zinc-800 outline-none w-[150px]" />
                <button onClick={() => { setIsCustomModel(false); if(availableModels.length) setSelectedModel(availableModels[0]); }} disabled={engineStatus !== "spento"} className="text-zinc-500 hover:text-zinc-300">✕</button>
              </div>
            )}

            {engineStatus === "spento" && <button onClick={handleStartEngine} className="bg-zinc-800 hover:bg-zinc-700 text-zinc-200 px-3 py-1 rounded border border-zinc-700 transition-colors">Carica</button>}
            {engineStatus === "in_avvio" && <button disabled className="bg-zinc-800 text-zinc-500 px-3 py-1 rounded border border-zinc-800">Caricamento...</button>}
            {engineStatus === "acceso" && <button onClick={handleStopEngine} className="bg-red-900/30 text-red-400 hover:bg-red-900/50 px-3 py-1 rounded border border-red-900/50 transition-colors">Scarica</button>}
          </div>
        </div>

        {/* MONITOR RISORSE E AZIONI */}
        <div className="flex items-center gap-4 w-full md:w-auto overflow-x-auto scrollbar-hide text-xs font-mono text-zinc-400">
          <div className="flex items-center gap-2">
            <span>CPU</span>
            <span className="w-8 text-right text-zinc-300">{sysStats.cpu.toFixed(0)}%</span>
          </div>
          <div className="flex items-center gap-2">
            <span>GPU</span>
            <span className="w-8 text-right text-zinc-300">{sysStats.gpu.toFixed(0)}%</span>
          </div>
          <div className="flex items-center gap-2">
            <span>RAM</span>
            <span className="text-zinc-300 w-16 text-right">{sysStats.ramUsed.toFixed(1)}GB</span>
          </div>

          <div className="h-4 w-px bg-zinc-800 mx-2"></div>

          <button onClick={handleClearChat} className="text-zinc-500 hover:text-zinc-300 transition-colors" title="Nuova Chat">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
          </button>
          <button onClick={openSettings} className="text-zinc-500 hover:text-zinc-300 transition-colors" title="Impostazioni">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
          </button>
        </div>
      </header>

      {/* AREA CHAT (Layout Piatto, Larghezza Fissa) */}
      <main className="flex-1 overflow-y-auto custom-scrollbar">
        {messages.length === 0 && !isLoading && (
          <div className="h-full flex flex-col items-center justify-center text-zinc-600">
            <div className="w-16 h-16 rounded-2xl border border-zinc-800 flex items-center justify-center mb-4">
              <span className="text-2xl">⚡️</span>
            </div>
            <p className="text-sm font-medium tracking-wide">Pronto per ricevere istruzioni.</p>
          </div>
        )}

        <div className="flex flex-col">
          {messages.map((msg, i) => (
            <div key={i} className={`py-6 px-4 md:px-8 border-b border-zinc-800/50 ${msg.role === "user" ? "bg-zinc-900/30" : "bg-transparent"}`}>
              <div className="max-w-4xl mx-auto flex gap-4 md:gap-6">
                
                {/* Avatar minimale */}
                <div className="flex-shrink-0 mt-1">
                  {msg.role === "user" ? (
                    <div className="w-6 h-6 rounded bg-zinc-800 flex items-center justify-center text-xs text-zinc-400">TU</div>
                  ) : (
                    <div className="w-6 h-6 rounded bg-blue-900/30 border border-blue-800/50 flex items-center justify-center text-xs text-blue-400">AI</div>
                  )}
                </div>

                {/* Contenuto Messaggio */}
                <div className="flex-1 min-w-0 text-sm md:text-base leading-relaxed text-zinc-300">
                  {msg.imageUrl && (
                    <img src={msg.imageUrl} className="max-w-sm w-full h-auto rounded border border-zinc-700 mb-4" alt="Allegato utente" />
                  )}
                  
                  {/* Logica Agente (Stile Console) */}
                  {msg.role === "ai" && msg.reasoning && msg.reasoning.length > 0 && (
                    <div className="mb-4 text-xs font-mono bg-black/50 border border-zinc-800 rounded">
                      <details className="group">
                        <summary className="p-2 cursor-pointer text-zinc-500 hover:text-zinc-300 select-none flex items-center gap-2">
                          <span className="text-zinc-600">❯</span>
                          <span>Processo in background ({msg.reasoning.length} step)</span>
                        </summary>
                        <div className="p-3 pt-1 text-zinc-400 border-t border-zinc-800/50 space-y-1.5">
                          {msg.reasoning.map((r, idx) => (
                            <div key={idx} className="flex gap-2 break-words">
                              <span className="text-zinc-600">[{idx+1}]</span>
                              <span>{r}</span>
                            </div>
                          ))}
                        </div>
                      </details>
                    </div>
                  )}

                  {/* Testo Risposta */}
                  <div className="whitespace-pre-wrap break-words">
                    {msg.content}
                    {msg.isStreaming && <span className="animate-pulse font-mono text-zinc-500 ml-1">▍</span>}
                  </div>
                </div>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} className="h-6" />
        </div>
      </main>

      {/* INPUT AREA (Console Style) */}
      <footer className="p-4 bg-zinc-950 flex-shrink-0">
        <div className="max-w-4xl mx-auto">
          
          <form onSubmit={handleSubmit} className="bg-zinc-900 border border-zinc-800 rounded-lg overflow-hidden flex flex-col focus-within:border-zinc-600 transition-colors shadow-sm">
            
            {/* Anteprima Allegato */}
            {file && (
              <div className="px-3 py-2 bg-zinc-950/50 border-b border-zinc-800 flex items-center gap-2 text-xs">
                <span className="text-zinc-400">{file.type.startsWith("image/") ? "🖼️" : "📄"}</span>
                <span className="text-zinc-300 truncate max-w-[200px]">{file.name}</span>
                <button type="button" onClick={() => setFile(null)} className="text-zinc-500 hover:text-red-400 ml-2">✕</button>
              </div>
            )}

            <textarea 
              value={input} 
              onChange={(e) => setInput(e.target.value)} 
              placeholder={isLoading ? loadingStatus : "Digita il prompt qui..."} 
              className="w-full bg-transparent text-zinc-200 p-3 md:p-4 resize-none max-h-40 text-sm md:text-base outline-none custom-scrollbar" 
              rows={1} 
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSubmit(); } }} 
              disabled={isLoading}
            />
            
            <div className="px-3 py-2 bg-zinc-900 flex justify-between items-center">
              
              {/* Controlli di sinistra (File, Voice, Mode) */}
              <div className="flex items-center gap-1">
                <label className="p-1.5 text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800 rounded cursor-pointer transition-colors">
                  <input type="file" className="hidden" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" /></svg>
                </label>
                
                <button type="button" onMouseDown={startRecording} onMouseUp={stopRecording} onMouseLeave={stopRecording} onTouchStart={startRecording} onTouchEnd={stopRecording} className={`p-1.5 rounded transition-colors ${isRecording ? "text-red-400 bg-red-900/20" : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800"}`}>
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" /></svg>
                </button>

                <div className="h-4 w-px bg-zinc-800 mx-1"></div>

                <select value={chatMode} onChange={(e) => setChatMode(e.target.value as "fast" | "agent")} className="bg-transparent text-xs text-zinc-400 outline-none cursor-pointer hover:text-zinc-300">
                  <option value="agent">Modalità Agente OS</option>
                  <option value="fast">Chat Veloce (No Tool)</option>
                </select>
              </div>

              {/* Tasto Invia */}
              <button type="submit" disabled={isLoading || (!input.trim() && !file)} className="px-3 py-1 bg-zinc-100 hover:bg-white text-zinc-900 text-sm font-medium rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2">
                {isLoading ? <span className="w-4 h-4 border-2 border-zinc-900 border-t-transparent rounded-full animate-spin"></span> : "Invia"}
              </button>
            </div>
          </form>
          
          <div className="text-center mt-2">
            <span className="text-[10px] text-zinc-600 font-mono">L'agente può compiere azioni sul sistema. Usa con cautela.</span>
          </div>
        </div>
      </footer>

      {/* MODALE IMPOSTAZIONI (Stile Finestra Preferenze Native) */}
      {isSettingsOpen && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 backdrop-blur-sm p-4">
          <div className="bg-[#1C1C1C] border border-[#333] rounded-lg w-full max-w-3xl shadow-2xl overflow-hidden flex flex-col h-[80vh]">
            
            <div className="px-4 py-3 bg-[#2D2D2D] border-b border-[#111] flex justify-between items-center cursor-default">
              <h2 className="text-sm font-semibold text-zinc-200">Preferenze di Sistema</h2>
              <button onClick={() => setIsSettingsOpen(false)} className="text-zinc-400 hover:text-white">✕</button>
            </div>
            
            <div className="flex flex-1 overflow-hidden">
              <div className="w-48 bg-[#252525] border-r border-[#111] py-2 flex flex-col gap-0.5">
                {[
                  { id: "general", label: "Generale" },
                  { id: "auth", label: "Credenziali" },
                  { id: "ollama", label: "Ollama" },
                  { id: "mlx", label: "Apple MLX" },
                  { id: "images", label: "Immagini" },
                  { id: "video", label: "Video" }
                ].map(tab => (
                  <button key={tab.id} onClick={() => setSettingsTab(tab.id as any)} className={`text-left px-4 py-1.5 text-sm transition-colors ${settingsTab === tab.id ? "bg-blue-600 text-white" : "text-zinc-400 hover:bg-[#333] hover:text-zinc-200"}`}>
                    {tab.label}
                  </button>
                ))}
              </div>

              <div className="flex-1 p-6 overflow-y-auto bg-[#1C1C1C] text-sm text-zinc-300 custom-scrollbar">
                
                {/* SEZIONE GENERALE */}
                {settingsTab === "general" && (
                  <div className="space-y-6">
                    <div>
                      <h3 className="text-zinc-100 font-medium mb-4">Sicurezza e Accesso ai File</h3>
                      <label className="flex items-start gap-3 cursor-pointer">
                        <input type="checkbox" checked={allowGlobalWrite} onChange={(e) => toggleGlobalWrite(e.target.checked)} className="mt-1 accent-blue-600" />
                        <div>
                          <p className="text-zinc-200">Consenti scrittura globale sul disco</p>
                          <p className="text-xs text-zinc-500 mt-0.5">Se disabilitato, l'agente potrà creare/modificare file solo all'interno della cartella Sandbox.</p>
                        </div>
                      </label>
                    </div>
                    
                    <div className="border-t border-[#333] pt-6">
                      <h3 className="text-zinc-100 font-medium mb-4">Configurazione</h3>
                      <div className="space-y-4">
                        <div>
                          <label className="block text-xs text-zinc-500 mb-1">Finestra di Contesto (MAX_TOKENS)</label>
                          <input type="number" value={envSettings.MAX_TOKENS} onChange={e => setEnvSettings({...envSettings, MAX_TOKENS: e.target.value})} className="w-32 bg-[#0D0D0D] border border-[#333] rounded px-2 py-1 text-zinc-200 outline-none focus:border-blue-500" />
                        </div>
                        <div>
                          <label className="block text-xs text-zinc-500 mb-1">Percorso Cartella Sandbox</label>
                          <input type="text" value={envSettings.SANDBOX_DIR} onChange={e => setEnvSettings({...envSettings, SANDBOX_DIR: e.target.value})} className="w-full bg-[#0D0D0D] border border-[#333] rounded px-2 py-1 text-zinc-200 outline-none focus:border-blue-500" />
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* ALTRE SEZIONI SEMPLIFICATE */}
                {settingsTab === "auth" && (
                  <div className="space-y-6">
                    <div>
                      <h3 className="text-zinc-100 font-medium mb-4">Telegram Bot API</h3>
                      <div className="space-y-3">
                        <input type="password" placeholder="Bot Token" value={envSettings.TELEGRAM_TOKEN} onChange={e => setEnvSettings({...envSettings, TELEGRAM_TOKEN: e.target.value})} className="w-full bg-[#0D0D0D] border border-[#333] rounded px-2 py-1 outline-none focus:border-blue-500" />
                        <div className="flex gap-3">
                          <input type="text" placeholder="API ID" value={envSettings.TG_API_ID} onChange={e => setEnvSettings({...envSettings, TG_API_ID: e.target.value})} className="w-1/2 bg-[#0D0D0D] border border-[#333] rounded px-2 py-1 outline-none focus:border-blue-500" />
                          <input type="password" placeholder="API Hash" value={envSettings.TG_API_HASH} onChange={e => setEnvSettings({...envSettings, TG_API_HASH: e.target.value})} className="w-1/2 bg-[#0D0D0D] border border-[#333] rounded px-2 py-1 outline-none focus:border-blue-500" />
                        </div>
                      </div>
                    </div>
                    <div className="border-t border-[#333] pt-6">
                      <h3 className="text-zinc-100 font-medium mb-4">Account Email (IMAP/SMTP)</h3>
                      <div className="grid grid-cols-2 gap-3">
                        <input type="text" placeholder="Utente Gmail" value={envSettings.EMAIL_USER} onChange={e => setEnvSettings({...envSettings, EMAIL_USER: e.target.value})} className="bg-[#0D0D0D] border border-[#333] rounded px-2 py-1 outline-none focus:border-blue-500" />
                        <input type="password" placeholder="App Password Gmail" value={envSettings.EMAIL_PASSWORD} onChange={e => setEnvSettings({...envSettings, EMAIL_PASSWORD: e.target.value})} className="bg-[#0D0D0D] border border-[#333] rounded px-2 py-1 outline-none focus:border-blue-500" />
                        <input type="text" placeholder="Email iCloud" value={envSettings.ICLOUD_EMAIL} onChange={e => setEnvSettings({...envSettings, ICLOUD_EMAIL: e.target.value})} className="bg-[#0D0D0D] border border-[#333] rounded px-2 py-1 outline-none focus:border-blue-500" />
                        <input type="password" placeholder="App Password iCloud" value={envSettings.ICLOUD_APP_PASSWORD} onChange={e => setEnvSettings({...envSettings, ICLOUD_APP_PASSWORD: e.target.value})} className="bg-[#0D0D0D] border border-[#333] rounded px-2 py-1 outline-none focus:border-blue-500" />
                      </div>
                    </div>
                  </div>
                )}

                {settingsTab === "ollama" && (
                  <div className="space-y-4">
                    <h3 className="text-zinc-100 font-medium mb-4">Configurazione Ollama</h3>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="col-span-2">
                        <label className="block text-xs text-zinc-500 mb-1">Motore di Default</label>
                        <select value={envSettings.ACTIVE_ENGINE} onChange={e => setEnvSettings({...envSettings, ACTIVE_ENGINE: e.target.value})} className="w-full bg-[#0D0D0D] border border-[#333] rounded px-2 py-1 outline-none focus:border-blue-500">
                          <option value="ollama">Ollama (Raccomandato Windows/Linux)</option>
                          <option value="mlx">Apple MLX (Raccomandato Mac)</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs text-zinc-500 mb-1">Text Model</label>
                        <input type="text" value={envSettings.TEXT_MODEL_NAME} onChange={e => setEnvSettings({...envSettings, TEXT_MODEL_NAME: e.target.value})} className="w-full bg-[#0D0D0D] border border-[#333] rounded px-2 py-1 outline-none focus:border-blue-500" />
                      </div>
                      <div>
                        <label className="block text-xs text-zinc-500 mb-1">Base URL</label>
                        <input type="text" value={envSettings.BASE_URL_TEXT} onChange={e => setEnvSettings({...envSettings, BASE_URL_TEXT: e.target.value})} className="w-full bg-[#0D0D0D] border border-[#333] rounded px-2 py-1 outline-none focus:border-blue-500" />
                      </div>
                      <div className="col-span-2">
                        <label className="block text-xs text-zinc-500 mb-1">Fast Model (Sub-Agenti)</label>
                        <input type="text" value={envSettings.FAST_MODEL_NAME} onChange={e => setEnvSettings({...envSettings, FAST_MODEL_NAME: e.target.value})} className="w-full bg-[#0D0D0D] border border-[#333] rounded px-2 py-1 outline-none focus:border-blue-500" />
                      </div>
                    </div>
                  </div>
                )}

                {settingsTab === "mlx" && (
                  <div className="space-y-4">
                    <h3 className="text-zinc-100 font-medium mb-4">Configurazione Apple MLX</h3>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="col-span-2">
                        <label className="block text-xs text-zinc-500 mb-1">Base URL</label>
                        <input type="text" value={envSettings.MLX_BASE_URL} onChange={e => setEnvSettings({...envSettings, MLX_BASE_URL: e.target.value})} className="w-full bg-[#0D0D0D] border border-[#333] rounded px-2 py-1 outline-none focus:border-blue-500" />
                      </div>
                      <div>
                        <label className="block text-xs text-zinc-500 mb-1">Text Model</label>
                        <input type="text" value={envSettings.MLX_TEXT_MODEL_NAME} onChange={e => setEnvSettings({...envSettings, MLX_TEXT_MODEL_NAME: e.target.value})} className="w-full bg-[#0D0D0D] border border-[#333] rounded px-2 py-1 outline-none focus:border-blue-500" />
                      </div>
                      <div>
                        <label className="block text-xs text-zinc-500 mb-1">Fast Model</label>
                        <input type="text" value={envSettings.MLX_FAST_MODEL_NAME} onChange={e => setEnvSettings({...envSettings, MLX_FAST_MODEL_NAME: e.target.value})} className="w-full bg-[#0D0D0D] border border-[#333] rounded px-2 py-1 outline-none focus:border-blue-500" />
                      </div>
                    </div>
                  </div>
                )}

                {settingsTab === "images" && (
                  <div className="space-y-4">
                    <h3 className="text-zinc-100 font-medium mb-4">Generazione Immagini</h3>
                    <div className="space-y-4">
                      <div>
                        <label className="block text-xs text-zinc-500 mb-1">API URL</label>
                        <input type="text" value={envSettings.IMAGE_GEN_API_URL} onChange={e => setEnvSettings({...envSettings, IMAGE_GEN_API_URL: e.target.value})} className="w-full bg-[#0D0D0D] border border-[#333] rounded px-2 py-1 outline-none focus:border-blue-500" />
                      </div>
                      <div>
                        <label className="block text-xs text-zinc-500 mb-1">Model Name</label>
                        <input type="text" value={envSettings.IMAGE_MODEL_NAME} onChange={e => setEnvSettings({...envSettings, IMAGE_MODEL_NAME: e.target.value})} className="w-full bg-[#0D0D0D] border border-[#333] rounded px-2 py-1 outline-none focus:border-blue-500" />
                      </div>
                    </div>
                  </div>
                )}

                {/* SEZIONE VIDEO - REFINED */}
                {settingsTab === "video" && (
                  <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
                    <div>
                      <h3 className="text-zinc-100 font-medium mb-1 flex items-center gap-2">
                        <span className="text-blue-400 text-lg">🎬</span> 
                        Video Generation Factory
                      </h3>
                      <p className="text-xs text-zinc-500 mb-6">Configura il motore di rendering per le clip video AI.</p>
                    </div>

                    <div className="space-y-5 bg-zinc-900/30 p-4 rounded-xl border border-zinc-800/50">
                      <div className="space-y-2">
                        <label className="block text-[11px] uppercase tracking-wider text-zinc-500 font-semibold">
                          Modello HuggingFace ID
                        </label>
                        <input 
                            type="text" 
                            placeholder="es. THUDM/CogVideoX-2b" 
                            value={envSettings.VIDEO_MODEL_NAME} 
                            onChange={e => setEnvSettings({...envSettings, VIDEO_MODEL_NAME: e.target.value})} 
                            className="w-full bg-[#0D0D0D] border border-[#333] rounded-lg px-3 py-2 text-zinc-200 outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20 font-mono text-sm transition-all" 
                        />
                        <p className="text-[10px] text-amber-500/80 mt-2 flex items-center gap-1">
                           <span>⚠️</span> Richiede circa 14GB di spazio e 18GB+ di RAM unificata.
                        </p>
                      </div>

                      <div className="space-y-2">
                        <label className="block text-[11px] uppercase tracking-wider text-zinc-500 font-semibold">
                          Accelerazione Hardware
                        </label>
                        <select 
                            value={envSettings.VIDEO_DEVICE} 
                            onChange={e => setEnvSettings({...envSettings, VIDEO_DEVICE: e.target.value})} 
                            className="w-full bg-[#0D0D0D] border border-[#333] rounded-lg px-3 py-2 text-zinc-200 outline-none focus:border-blue-500/50 transition-all appearance-none cursor-pointer"
                        >
                          <option value="auto">Rilevamento Automatico (GPU Default)</option>
                          <option value="mps">Apple Metal (M1/M2/M3 Pro)</option>
                          <option value="cuda">NVIDIA CUDA (Windows/Linux)</option>
                          <option value="cpu">Solo CPU (Lento - Solo test)</option>
                        </select>
                      </div>
                    </div>
                    
                    <div className="p-3 bg-blue-500/5 border border-blue-500/10 rounded-lg">
                      <p className="text-[11px] text-zinc-400 leading-relaxed">
                        <strong className="text-blue-400">Pro Tip:</strong> Se riscontri errori di memoria (VRAM) su M3 Pro, 
                        usa il modello leggero <code className="text-zinc-200 bg-zinc-800 px-1 rounded">damo-vilab/text-to-video-ms-1.5m</code>.
                      </p>
                    </div>
                  </div>
                )}

              </div>
            </div>

            <div className="p-4 border-t border-[#111] bg-[#252525] flex justify-end gap-3">
              <button onClick={() => setIsSettingsOpen(false)} className="px-4 py-1.5 text-sm text-zinc-400 hover:text-white">Annulla</button>
              <button onClick={saveSettings} className="px-4 py-1.5 text-sm bg-zinc-200 hover:bg-white text-zinc-900 font-medium rounded">Salva Modifiche</button>
            </div>

          </div>
        </div>
      )}
    </div>
  );
}