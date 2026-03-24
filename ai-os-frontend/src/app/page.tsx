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
  const [settingsTab, setSettingsTab] = useState<"general" | "auth" | "ollama" | "mlx" | "images">("general");
  const [envSettings, setEnvSettings] = useState({
    TELEGRAM_TOKEN: "", TG_API_ID: "", TG_API_HASH: "", EMAIL_USER: "", EMAIL_PASSWORD: "",
    ICLOUD_EMAIL: "", ICLOUD_APP_PASSWORD: "", SANDBOX_DIR: "sandbox",
    IMAGE_GEN_API_URL: "http://localhost:8000/generate", IMAGE_MODEL_NAME: "flux",
    ACTIVE_ENGINE: "ollama", TEXT_MODEL_NAME: "", FAST_MODEL_NAME: "", BASE_URL_TEXT: "http://localhost:11434", 
    VISION_MODEL_NAME: "", BASE_URL_VISION: "http://localhost:11434", MAX_TOKENS: "4096",
    MLX_TEXT_MODEL_NAME: "", MLX_BASE_URL: "http://localhost:8080", MLX_VISION_MODEL_NAME: "", MLX_FAST_MODEL_NAME: ""
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

  if (!isReady) {
    return (
      <div className="flex flex-col items-center justify-center h-screen bg-gray-900 text-gray-100 p-4 md:p-8">
        <div className="max-w-md w-full bg-gray-800 rounded-2xl p-6 md:p-8 border border-gray-700 shadow-2xl text-center space-y-6">
          {setupStep === "checking" && (<><div className="text-5xl animate-spin">⚙️</div><h2 className="text-xl font-bold text-blue-400">Connessione al backend...</h2></>)}
          {setupStep === "ollama_missing" && (<><div className="text-5xl">🦙</div><h2 className="text-xl font-bold text-yellow-400">Ollama non rilevato</h2><button onClick={checkSystemReadiness} className="w-full bg-blue-600 py-2.5 rounded-xl">🔄 Ricontrolla</button></>)}
          {setupStep === "permissions" && (<><div className="text-5xl">📁</div><h2 className="text-xl font-bold text-purple-400">Cartella di lavoro</h2><button onClick={requestFolderAccess} className="w-full bg-purple-600 py-2.5 rounded-xl">📂 Seleziona Cartella</button></>)}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-gray-900 text-gray-100 font-sans">
      
      {/* HEADER RESPONSIVO */}
      <header className="p-3 md:p-4 bg-gray-800 border-b border-gray-700 shadow-md flex-shrink-0">
        <div className="flex flex-col xl:flex-row items-start xl:items-center justify-between gap-4">
          
          {/* Container Sinistro: Titolo e Controlli */}
          <div className="flex flex-col md:flex-row flex-wrap items-start md:items-center gap-3 md:gap-4 w-full xl:w-auto">
            <h1 className="text-lg md:text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-500 whitespace-nowrap">
              AI Agent OS
            </h1>
            
            {/* Controlli Motore (Responsive flex-wrap) */}
            <div className="flex flex-wrap items-center gap-2 md:border-l border-gray-600 md:pl-4 w-full md:w-auto">
              {isMac ? (
                <select value={engine} onChange={(e) => setEngine(e.target.value)} disabled={engineStatus !== "spento"} className="bg-gray-900 text-green-400 text-sm px-2 py-1.5 rounded-lg border border-gray-600 flex-grow md:flex-grow-0">
                  <option value="ollama">🐢 Ollama</option>
                  <option value="mlx">🚀 Apple MLX</option>
                </select>
              ) : (
                <span className="bg-gray-900 text-green-400 text-sm px-3 py-1.5 rounded-lg border border-gray-600 flex-grow md:flex-grow-0 text-center">🐢 Ollama</span>
              )}

              <div className="flex items-center gap-2 flex-grow md:flex-grow-0 min-w-[200px]">
                {!isCustomModel ? (
                  <select value={selectedModel} onChange={(e) => { if (e.target.value === "custom") { setIsCustomModel(true); setSelectedModel(""); } else setSelectedModel(e.target.value); }} disabled={engineStatus !== "spento"} className="bg-gray-900 text-blue-400 text-sm px-2 py-1.5 rounded-lg border border-gray-600 w-full">
                    {availableModels.length === 0 && <option value="" disabled>Nessun modello</option>}
                    {availableModels.map(m => <option key={m} value={m}>{m}</option>)}
                    <option value="custom">➕ Personalizzato...</option>
                  </select>
                ) : (
                  <div className="flex gap-1 w-full">
                    <input type="text" value={selectedModel} onChange={e => setSelectedModel(e.target.value)} disabled={engineStatus !== "spento"} placeholder="Nome modello..." className="bg-gray-900 text-blue-400 text-sm px-2 py-1.5 rounded-lg border border-gray-600 w-full min-w-[120px]" />
                    <button onClick={() => { setIsCustomModel(false); if(availableModels.length) setSelectedModel(availableModels[0]); }} disabled={engineStatus !== "spento"} className="text-gray-400 hover:text-white px-2">✕</button>
                  </div>
                )}
              </div>

              {/* Bottoni Motore */}
              <div className="flex gap-2 w-full sm:w-auto mt-2 sm:mt-0">
                {engineStatus === "spento" && <button onClick={handleStartEngine} className="bg-blue-600 hover:bg-blue-500 text-white text-sm px-3 py-1.5 rounded-lg flex-1 sm:flex-none">▶ Avvia</button>}
                {engineStatus === "in_avvio" && <button disabled className="bg-yellow-600 text-white text-sm px-3 py-1.5 rounded-lg animate-pulse flex-1 sm:flex-none">⏳ Avvio...</button>}
                {engineStatus === "acceso" && <button onClick={handleStopEngine} className="bg-red-600 hover:bg-red-500 text-white text-sm px-3 py-1.5 rounded-lg flex-1 sm:flex-none">⏹ Spegni</button>}
              </div>
              {engineStatus === "spento" && engineError && <span className="text-red-400 text-xs ml-0 md:ml-2 px-2 py-1 rounded bg-red-900/20 w-full md:max-w-xs truncate" title={engineError}>⚠️ {engineError}</span>}
            </div>

            {/* Bottoni Azione */}
            <div className="flex flex-wrap gap-2 w-full md:w-auto mt-2 md:mt-0">
              <button onClick={handleClearChat} className="flex-1 md:flex-none justify-center text-red-400 hover:text-red-300 bg-red-900/20 px-3 py-1.5 rounded-lg border border-red-900/50 flex items-center gap-2 text-sm whitespace-nowrap">
                🗑️ Svuota
              </button>
              <button onClick={openSettings} className="flex-1 md:flex-none justify-center text-gray-300 hover:text-white bg-gray-700/50 hover:bg-gray-700 px-3 py-1.5 rounded-lg border border-gray-600 flex items-center gap-2 text-sm transition-all whitespace-nowrap">
                ⚙️ Setup
              </button>
            </div>
          </div>

          {/* Container Destro: Statistiche (Scrollabile orizzontalmente su mobile) */}
          <div className="flex items-center gap-3 bg-gray-900 px-3 py-2 rounded-xl border border-gray-700 text-xs font-mono w-full xl:w-auto overflow-x-auto whitespace-nowrap scrollbar-hide">
            <div className="flex flex-col items-center min-w-[60px]">
              <span className="text-gray-400 mb-1">Agente</span>
              {isLoading ? <span className="text-yellow-400 animate-pulse">⚙️ ELAB.</span> : <span className="text-green-400">● PRONTO</span>}
            </div>
            <div className="h-6 w-px bg-gray-700 mx-1" />
            <div className="flex flex-col min-w-[80px]">
              <span className="text-gray-400">CPU</span>
              <div className="flex items-center gap-2">
                <div className="w-12 md:w-16 h-1.5 md:h-2 bg-gray-700 rounded-full overflow-hidden"><div className={`h-full ${sysStats.cpu > 80 ? "bg-red-500" : sysStats.cpu > 50 ? "bg-yellow-500" : "bg-blue-500"}`} style={{ width: `${sysStats.cpu}%` }} /></div>
                <span className="w-8 text-right text-gray-200">{sysStats.cpu.toFixed(0)}%</span>
              </div>
            </div>
            <div className="flex flex-col min-w-[80px]">
              <span className="text-gray-400">GPU</span>
              <div className="flex items-center gap-2">
                <div className="w-12 md:w-16 h-1.5 md:h-2 bg-gray-700 rounded-full overflow-hidden"><div className={`h-full ${sysStats.gpu > 80 ? "bg-red-500" : sysStats.gpu > 50 ? "bg-yellow-500" : "bg-green-500"}`} style={{ width: `${sysStats.gpu}%` }} /></div>
                <span className="w-8 text-right text-gray-200">{sysStats.gpu.toFixed(0)}%</span>
              </div>
            </div>
            <div className="h-6 w-px bg-gray-700 mx-1" />
            <div className="flex flex-col min-w-[100px]">
              <span className="text-gray-400">RAM</span>
              <div className="flex items-center gap-2">
                <div className="w-12 md:w-16 h-1.5 md:h-2 bg-gray-700 rounded-full overflow-hidden"><div className={`h-full ${sysStats.ramPercent > 85 ? "bg-red-500" : "bg-purple-500"}`} style={{ width: `${sysStats.ramPercent}%` }} /></div>
                <span className="text-gray-200">{sysStats.ramUsed}/{sysStats.ramTotal} GB</span>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* AREA CHAT CON RAGIONAMENTI */}
      <main className="flex-1 overflow-y-auto p-3 md:p-4 space-y-4 md:space-y-6 relative custom-scrollbar">
        {messages.length === 0 && !isLoading && (
          <div className="h-full flex flex-col items-center justify-center text-gray-500 opacity-70">
            <div className="text-4xl mb-4">🛸</div>
            <p className="text-lg font-semibold text-center px-4">Sistema operativo pronto all'uso.</p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[95%] md:max-w-[80%] rounded-2xl p-3 md:p-4 shadow-lg ${msg.role === "user" ? "bg-blue-600 text-white rounded-br-none" : "bg-gray-800 border border-gray-700 text-gray-100 rounded-bl-none"}`}>
              {msg.imageUrl && <img src={msg.imageUrl} className="max-w-xs w-full h-auto rounded-lg mb-3 border border-gray-500" alt="Allegato" />}
              
              {/* ACCORDEON DEI RAGIONAMENTI */}
              {msg.role === "ai" && msg.reasoning && msg.reasoning.length > 0 && (
                <div className="mb-3 md:mb-4 bg-gray-900/60 border border-gray-700 rounded-lg overflow-hidden text-xs md:text-sm">
                  <details className="group">
                    <summary className="flex items-center gap-2 p-2 md:p-2.5 cursor-pointer text-gray-400 hover:text-gray-200 transition-colors select-none">
                      <span className="text-blue-500 animate-pulse">🧠</span>
                      <span className="font-semibold truncate">Processo di ragionamento ({msg.reasoning.length} passaggi)</span>
                      <span className="ml-auto transform group-open:rotate-180 transition-transform">▼</span>
                    </summary>
                    <div className="p-2 md:p-3 pt-1 border-t border-gray-800 text-gray-400 bg-black/20">
                      <ul className="space-y-1.5 list-none">
                        {msg.reasoning.map((r, idx) => (
                          <li key={idx} className="flex items-start gap-2 break-words">
                            <span className="text-gray-600 text-xs mt-0.5 flex-shrink-0">[{idx + 1}]</span>
                            <span>{r}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </details>
                </div>
              )}

              {/* TESTO FINALE */}
              <p className="whitespace-pre-wrap leading-relaxed text-sm md:text-base break-words">
                {msg.content}
                {msg.isStreaming && <span className="animate-pulse font-bold text-blue-400"> ▋</span>}
              </p>
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </main>

      {/* FOOTER INPUT RESPONSIVO */}
      <footer className="p-3 md:p-4 bg-gray-800 border-t border-gray-700 flex flex-col gap-2 md:gap-3 flex-shrink-0 relative">
        <div className="max-w-4xl mx-auto w-full flex gap-2">
          <button onClick={() => setChatMode("fast")} className={`flex-1 py-1.5 md:py-2 text-[10px] md:text-xs font-bold uppercase rounded-lg border transition-colors ${chatMode === "fast" ? "bg-yellow-500/20 text-yellow-400 border-yellow-500/50" : "bg-gray-800 text-gray-500 border-gray-700 hover:bg-gray-700"}`}>⚡️ Chat Veloce</button>
          <button onClick={() => setChatMode("agent")} className={`flex-1 py-1.5 md:py-2 text-[10px] md:text-xs font-bold uppercase rounded-lg border transition-colors ${chatMode === "agent" ? "bg-blue-500/20 text-blue-400 border-blue-500/50" : "bg-gray-800 text-gray-500 border-gray-700 hover:bg-gray-700"}`}>🧠 Agente OS</button>
        </div>

        <form onSubmit={handleSubmit} className="max-w-4xl mx-auto w-full flex flex-row items-end gap-2 md:gap-3 relative">
          <label className="cursor-pointer p-2.5 md:p-3 bg-gray-700 hover:bg-gray-600 rounded-xl border border-gray-600 flex-shrink-0 transition-colors">
            <input type="file" className="hidden" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            <span className="text-lg md:text-xl">{file && file.type.startsWith("image/") ? "🖼️" : file ? "📎" : "📎"}</span>
          </label>
          
          <button type="button" onMouseDown={startRecording} onMouseUp={stopRecording} onMouseLeave={stopRecording} onTouchStart={startRecording} onTouchEnd={stopRecording} className={`p-2.5 md:p-3 rounded-xl border flex-shrink-0 transition-colors ${isRecording ? "bg-red-600 border-red-500 animate-pulse text-white" : "bg-gray-700 hover:bg-gray-600 border-gray-600 text-gray-300"}`}>
            <span className="text-lg md:text-xl">🎙️</span>
          </button>
          
          <div className="flex-1 relative">
             <textarea value={input} onChange={(e) => setInput(e.target.value)} placeholder="Scrivi un comando..." className="w-full bg-gray-700 border border-gray-600 text-white rounded-xl p-2.5 md:p-3 px-3 md:px-4 resize-none max-h-32 text-sm md:text-base focus:outline-none focus:ring-1 focus:ring-blue-500" rows={1} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSubmit(); } }} />
          </div>
          
          <button type="submit" disabled={isLoading || (!input.trim() && !file)} className="p-2.5 md:p-3 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-600 rounded-xl text-white flex-shrink-0 transition-colors flex items-center justify-center min-w-[2.5rem] md:min-w-[3rem]">
            {isLoading ? <span className="animate-spin text-lg md:text-xl">⏳</span> : <span className="text-lg md:text-xl">➤</span>}
          </button>
        </form>

        {/* BADGE ALLEGATO RECUPERATO */}
        {file && (
          <div className="max-w-4xl mx-auto w-full flex items-center gap-2 text-xs text-gray-400 animate-in slide-in-from-bottom-2 px-1">
            <span className="bg-gray-700/80 px-2.5 py-1.5 rounded-lg border border-gray-600 flex items-center gap-2 max-w-full overflow-hidden">
              <span>{file.type.startsWith("image/") ? "🖼️" : "📄"}</span>
              <span className="truncate text-gray-200">{file.name}</span>
            </span>
            <button 
              onClick={() => setFile(null)} 
              className="text-red-400 hover:text-red-300 bg-red-900/20 px-2 py-1 rounded-md transition-colors"
              type="button"
            >
              ✕ Rimuovi
            </button>
          </div>
        )}
      </footer>

      {/* MODALE IMPOSTAZIONI RESPONSIVO */}
      {isSettingsOpen && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 backdrop-blur-sm p-2 md:p-4">
          <div className="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-4xl shadow-2xl flex flex-col h-[90vh] md:h-[80vh] max-h-[850px] overflow-hidden">
            
            <div className="p-4 md:p-5 border-b border-gray-800 flex justify-between items-center bg-gray-800/50 flex-shrink-0">
              <div>
                <h2 className="text-base md:text-lg text-white font-bold">⚙️ Impostazioni di Sistema</h2>
                <p className="text-gray-400 text-xs mt-1 hidden sm:block">Gestisci configurazioni, permessi e API.</p>
              </div>
              <button onClick={() => setIsSettingsOpen(false)} className="text-gray-400 hover:text-white text-xl md:text-2xl px-2">✕</button>
            </div>
            
            <div className="flex flex-col md:flex-row flex-1 overflow-hidden">
              {/* BARRA LATERALE TABS (Diventa orizzontale su mobile) */}
              <div className="w-full md:w-64 bg-gray-800/30 border-b md:border-b-0 md:border-r border-gray-800 p-2 md:p-4 flex flex-row md:flex-col gap-1.5 md:gap-2 overflow-x-auto flex-shrink-0 custom-scrollbar">
                <button onClick={() => setSettingsTab("general")} className={`text-left px-3 md:px-4 py-2 md:py-2.5 rounded-lg text-xs md:text-sm font-medium transition-colors whitespace-nowrap ${settingsTab === "general" ? "bg-blue-600/20 text-blue-400 border border-blue-500/30" : "text-gray-400 hover:bg-gray-800 hover:text-gray-200"}`}>🛠️ Generale</button>
                <button onClick={() => setSettingsTab("auth")} className={`text-left px-3 md:px-4 py-2 md:py-2.5 rounded-lg text-xs md:text-sm font-medium transition-colors whitespace-nowrap ${settingsTab === "auth" ? "bg-blue-600/20 text-blue-400 border border-blue-500/30" : "text-gray-400 hover:bg-gray-800 hover:text-gray-200"}`}>📨 Credenziali</button>
                <button onClick={() => setSettingsTab("ollama")} className={`text-left px-3 md:px-4 py-2 md:py-2.5 rounded-lg text-xs md:text-sm font-medium transition-colors whitespace-nowrap ${settingsTab === "ollama" ? "bg-green-600/20 text-green-400 border border-green-500/30" : "text-gray-400 hover:bg-gray-800 hover:text-gray-200"}`}>🦙 Ollama</button>
                <button onClick={() => setSettingsTab("mlx")} className={`text-left px-3 md:px-4 py-2 md:py-2.5 rounded-lg text-xs md:text-sm font-medium transition-colors whitespace-nowrap ${settingsTab === "mlx" ? "bg-purple-600/20 text-purple-400 border border-purple-500/30" : "text-gray-400 hover:bg-gray-800 hover:text-gray-200"}`}>🍎 Apple MLX</button>
                <button onClick={() => setSettingsTab("images")} className={`text-left px-3 md:px-4 py-2 md:py-2.5 rounded-lg text-xs md:text-sm font-medium transition-colors whitespace-nowrap ${settingsTab === "images" ? "bg-pink-600/20 text-pink-400 border border-pink-500/30" : "text-gray-400 hover:bg-gray-800 hover:text-gray-200"}`}>🎨 Immagini</button>
              </div>

              {/* AREA CONTENUTO */}
              <div className="flex-1 p-4 md:p-6 overflow-y-auto custom-scrollbar">
                
                {settingsTab === "general" && (
                  <div className="space-y-6 animate-in fade-in">
                    <div>
                      <h3 className="text-white font-semibold mb-3 border-b border-gray-800 pb-2 text-sm md:text-base">Sicurezza e Permessi</h3>
                      <label className="flex items-start md:items-center gap-3 md:gap-4 p-3 md:p-4 bg-black/40 border border-gray-800 rounded-lg cursor-pointer hover:border-gray-600 transition-colors">
                        <div className="relative mt-1 md:mt-0 flex-shrink-0">
                          <input type="checkbox" className="sr-only" checked={allowGlobalWrite} onChange={(e) => toggleGlobalWrite(e.target.checked)} />
                          <div className={`block w-10 md:w-12 h-6 md:h-7 rounded-full transition-colors ${allowGlobalWrite ? 'bg-red-500' : 'bg-gray-600'}`}></div>
                          <div className={`absolute left-1 top-1 bg-white w-4 md:w-5 h-4 md:h-5 rounded-full transition-transform ${allowGlobalWrite ? 'translate-x-4 md:translate-x-5' : ''}`}></div>
                        </div>
                        <div>
                          <p className={`font-bold text-sm md:text-base ${allowGlobalWrite ? 'text-red-400' : 'text-gray-300'}`}>{allowGlobalWrite ? "Scrittura Globale ATTIVA" : "Confinato in Sandbox"}</p>
                          <p className="text-[10px] md:text-xs text-gray-500 mt-1">{allowGlobalWrite ? "⚠️ L'Agente può modificare o cancellare file ovunque." : "Sicuro. Scrive solo nella cartella Sandbox specificata."}</p>
                        </div>
                      </label>
                    </div>
                    
                    <div>
                      <h3 className="text-white font-semibold mb-3 border-b border-gray-800 pb-2 text-sm md:text-base">Parametri di Base</h3>
                      <div className="grid gap-4">
                        <div>
                          <label className="block text-xs text-gray-500 mb-1">Limite Parole (MAX_TOKENS)</label>
                          <div className="flex items-center gap-3 md:gap-4">
                            <input type="range" min="512" max="8192" step="512" value={envSettings.MAX_TOKENS} onChange={e => setEnvSettings({...envSettings, MAX_TOKENS: e.target.value})} className="flex-1 accent-blue-500" />
                            <span className="bg-black border border-gray-700 px-2 md:px-3 py-1 rounded text-blue-400 text-xs md:text-sm min-w-[3rem] text-center">{envSettings.MAX_TOKENS}</span>
                          </div>
                        </div>
                        <div>
                          <label className="block text-xs text-gray-500 mb-1">Directory Sandbox</label>
                          <input type="text" value={envSettings.SANDBOX_DIR} onChange={e => setEnvSettings({...envSettings, SANDBOX_DIR: e.target.value})} className="w-full bg-black border border-gray-700 rounded p-2 md:p-2.5 text-white text-sm focus:border-blue-500 outline-none" />
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {settingsTab === "auth" && (
                  <div className="space-y-5 md:space-y-6 animate-in fade-in">
                    <div>
                      <h3 className="text-white font-semibold border-b border-gray-800 pb-2 mb-3 text-sm md:text-base">Telegram Bot API</h3>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 md:gap-4">
                        <div className="md:col-span-2">
                          <label className="block text-xs text-gray-500 mb-1">Telegram Bot Token</label>
                          <input type="password" value={envSettings.TELEGRAM_TOKEN} onChange={e => setEnvSettings({...envSettings, TELEGRAM_TOKEN: e.target.value})} className="w-full bg-black border border-gray-700 rounded p-2 md:p-2.5 text-white text-sm" />
                        </div>
                        <div>
                          <label className="block text-xs text-gray-500 mb-1">API ID</label>
                          <input type="text" value={envSettings.TG_API_ID} onChange={e => setEnvSettings({...envSettings, TG_API_ID: e.target.value})} className="w-full bg-black border border-gray-700 rounded p-2 md:p-2.5 text-white text-sm" />
                        </div>
                        <div>
                          <label className="block text-xs text-gray-500 mb-1">API Hash</label>
                          <input type="password" value={envSettings.TG_API_HASH} onChange={e => setEnvSettings({...envSettings, TG_API_HASH: e.target.value})} className="w-full bg-black border border-gray-700 rounded p-2 md:p-2.5 text-white text-sm" />
                        </div>
                      </div>
                    </div>

                    <div>
                      <h3 className="text-white font-semibold border-b border-gray-800 pb-2 mb-3 text-sm md:text-base">Email SMTP / IMAP</h3>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 md:gap-4">
                        <div>
                          <label className="block text-xs text-gray-500 mb-1">Gmail (User)</label>
                          <input type="text" value={envSettings.EMAIL_USER} onChange={e => setEnvSettings({...envSettings, EMAIL_USER: e.target.value})} className="w-full bg-black border border-gray-700 rounded p-2 md:p-2.5 text-white text-sm" />
                        </div>
                        <div>
                          <label className="block text-xs text-gray-500 mb-1">Gmail (App Password)</label>
                          <input type="password" value={envSettings.EMAIL_PASSWORD} onChange={e => setEnvSettings({...envSettings, EMAIL_PASSWORD: e.target.value})} className="w-full bg-black border border-gray-700 rounded p-2 md:p-2.5 text-white text-sm" />
                        </div>
                        <div>
                          <label className="block text-xs text-gray-500 mb-1">iCloud (Email)</label>
                          <input type="text" value={envSettings.ICLOUD_EMAIL} onChange={e => setEnvSettings({...envSettings, ICLOUD_EMAIL: e.target.value})} className="w-full bg-black border border-gray-700 rounded p-2 md:p-2.5 text-white text-sm" />
                        </div>
                        <div>
                          <label className="block text-xs text-gray-500 mb-1">iCloud (App Password)</label>
                          <input type="password" value={envSettings.ICLOUD_APP_PASSWORD} onChange={e => setEnvSettings({...envSettings, ICLOUD_APP_PASSWORD: e.target.value})} className="w-full bg-black border border-gray-700 rounded p-2 md:p-2.5 text-white text-sm" />
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {settingsTab === "ollama" && (
                  <div className="space-y-4 animate-in fade-in">
                    <h3 className="text-green-400 font-semibold border-b border-gray-800 pb-2 text-sm md:text-base">Impostazioni Ollama</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 md:gap-4">
                      <div className="md:col-span-2">
                        <label className="block text-xs text-gray-500 mb-1">Motore Attivo (ACTIVE_ENGINE)</label>
                        <select value={envSettings.ACTIVE_ENGINE} onChange={e => setEnvSettings({...envSettings, ACTIVE_ENGINE: e.target.value})} className="w-full bg-black border border-gray-700 rounded p-2 md:p-2.5 text-white text-sm">
                          <option value="ollama">Ollama</option>
                          <option value="mlx">Apple MLX</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs text-gray-500 mb-1">Text Model Name</label>
                        <input type="text" value={envSettings.TEXT_MODEL_NAME} onChange={e => setEnvSettings({...envSettings, TEXT_MODEL_NAME: e.target.value})} className="w-full bg-black border border-gray-700 rounded p-2 md:p-2.5 text-white text-sm" />
                      </div>
                      <div>
                        <label className="block text-xs text-gray-500 mb-1">Base URL (Text)</label>
                        <input type="text" value={envSettings.BASE_URL_TEXT} onChange={e => setEnvSettings({...envSettings, BASE_URL_TEXT: e.target.value})} className="w-full bg-black border border-gray-700 rounded p-2 md:p-2.5 text-white text-sm" />
                      </div>
                      <div className="md:col-span-2">
                        <label className="block text-xs text-gray-500 mb-1">Fast Model Name (Chat Veloce)</label>
                        <input type="text" value={envSettings.FAST_MODEL_NAME} onChange={e => setEnvSettings({...envSettings, FAST_MODEL_NAME: e.target.value})} className="w-full bg-black border border-gray-700 rounded p-2 md:p-2.5 text-white text-sm" />
                      </div>
                      <div>
                        <label className="block text-xs text-gray-500 mb-1">Vision Model Name</label>
                        <input type="text" value={envSettings.VISION_MODEL_NAME} onChange={e => setEnvSettings({...envSettings, VISION_MODEL_NAME: e.target.value})} className="w-full bg-black border border-gray-700 rounded p-2 md:p-2.5 text-white text-sm" />
                      </div>
                      <div>
                        <label className="block text-xs text-gray-500 mb-1">Base URL (Vision)</label>
                        <input type="text" value={envSettings.BASE_URL_VISION} onChange={e => setEnvSettings({...envSettings, BASE_URL_VISION: e.target.value})} className="w-full bg-black border border-gray-700 rounded p-2 md:p-2.5 text-white text-sm" />
                      </div>
                    </div>
                  </div>
                )}

                {settingsTab === "mlx" && (
                  <div className="space-y-4 animate-in fade-in">
                    <h3 className="text-purple-400 font-semibold border-b border-gray-800 pb-2 text-sm md:text-base">Impostazioni Apple MLX</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 md:gap-4">
                      <div className="md:col-span-2">
                        <label className="block text-xs text-gray-500 mb-1">MLX Base URL</label>
                        <input type="text" value={envSettings.MLX_BASE_URL} onChange={e => setEnvSettings({...envSettings, MLX_BASE_URL: e.target.value})} className="w-full bg-black border border-gray-700 rounded p-2 md:p-2.5 text-white text-sm" />
                      </div>
                      <div>
                        <label className="block text-xs text-gray-500 mb-1">MLX Text Model</label>
                        <input type="text" value={envSettings.MLX_TEXT_MODEL_NAME} onChange={e => setEnvSettings({...envSettings, MLX_TEXT_MODEL_NAME: e.target.value})} className="w-full bg-black border border-gray-700 rounded p-2 md:p-2.5 text-white text-sm" />
                      </div>
                      <div>
                        <label className="block text-xs text-gray-500 mb-1">MLX Fast Model</label>
                        <input type="text" value={envSettings.MLX_FAST_MODEL_NAME} onChange={e => setEnvSettings({...envSettings, MLX_FAST_MODEL_NAME: e.target.value})} className="w-full bg-black border border-gray-700 rounded p-2 md:p-2.5 text-white text-sm" />
                      </div>
                      <div className="md:col-span-2">
                        <label className="block text-xs text-gray-500 mb-1">MLX Vision Model</label>
                        <input type="text" value={envSettings.MLX_VISION_MODEL_NAME} onChange={e => setEnvSettings({...envSettings, MLX_VISION_MODEL_NAME: e.target.value})} className="w-full bg-black border border-gray-700 rounded p-2 md:p-2.5 text-white text-sm" />
                      </div>
                    </div>
                  </div>
                )}

                {settingsTab === "images" && (
                  <div className="space-y-4 animate-in fade-in">
                    <h3 className="text-pink-400 font-semibold border-b border-gray-800 pb-2 text-sm md:text-base">Pipeline SDXL / Flux</h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 md:gap-4">
                      <div>
                        <label className="block text-xs text-gray-500 mb-1">Image Gen API URL</label>
                        <input type="text" value={envSettings.IMAGE_GEN_API_URL} onChange={e => setEnvSettings({...envSettings, IMAGE_GEN_API_URL: e.target.value})} className="w-full bg-black border border-gray-700 rounded p-2 md:p-2.5 text-white text-sm" />
                      </div>
                      <div>
                        <label className="block text-xs text-gray-500 mb-1">Image Model Name</label>
                        <input type="text" value={envSettings.IMAGE_MODEL_NAME} onChange={e => setEnvSettings({...envSettings, IMAGE_MODEL_NAME: e.target.value})} className="w-full bg-black border border-gray-700 rounded p-2 md:p-2.5 text-white text-sm" />
                      </div>
                    </div>
                  </div>
                )}

              </div>
            </div>

            {/* BOTTONI IN BASSO */}
            <div className="p-3 md:p-4 border-t border-gray-800 flex justify-end gap-2 md:gap-3 bg-gray-800/50 flex-shrink-0">
              <button onClick={() => setIsSettingsOpen(false)} className="px-4 md:px-5 py-2 text-xs md:text-sm text-gray-400 hover:text-white transition-colors">Annulla</button>
              <button onClick={saveSettings} className="px-4 md:px-6 py-2 text-xs md:text-sm bg-blue-600 hover:bg-blue-500 text-white rounded-lg transition-colors font-medium shadow-lg shadow-blue-900/20">Salva e Applica</button>
            </div>

          </div>
        </div>
      )}
    </div>
  );
}