import React, { useState, useEffect, useRef } from 'react';
import { useSiteStore } from '../store/useSiteStore';
import { ChatMessage, Site } from '../types';
import { extractSiteFromRun, invokeReviewWorkflow } from '../lib/agentRuntime';
import {
  MessageSquare,
  Send,
  MapPin,
  Compass,
  AlertTriangle,
  Layers,
  ChevronRight,
  Download,
  CheckCircle2,
  Cpu,
  Info,
  Layers3,
  X,
  Minimize2,
  Maximize2,
  ExternalLink,
  Briefcase,
  Zap,
  Activity,
  History,
  Check
} from 'lucide-react';

export const UIChrome: React.FC = () => {
  const {
    mode,
    setMode,
    selectedSite,
    setSelectedSite,
    agents,
    annotations,
    selectedAnnotation,
    setSelectedAnnotation,
    observationPack,
    toggleInObservationPack,
    resolutionProgress,
    weatherActive,
    chatHistory,
    addChatMessage,
    predefinedSites,
    triggerDescent,
    applyRunResult,
    chatOpen,
    setChatOpen,
  } = useSiteStore();

  // Internal component states
  const [chatInput, setChatInput] = useState('');
  const [isChatLoading, setIsChatLoading] = useState(false);
  const [showExportModal, setShowExportModal] = useState(false);
  const [exportNotification, setExportNotification] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  // Auto-scroll chat to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatHistory, isChatLoading]);

  // Execute download of the compiled observation pack
  const executeDownload = () => {
    const payload = {
      generator: "3D RAMs Core v3.0",
      exportUuid: "rams-7c9f-2026",
      timestamp: new Date().toISOString(),
      site: selectedSite,
      observations: observationPack.map(id => annotations.find(a => a.id === id)).filter(Boolean)
    };

    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(payload, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `3d-rams-pack-${selectedSite.name.toLowerCase().replace(/\s+/g, '-')}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();

    setExportNotification("Compilation download started successfully.");
    setTimeout(() => setExportNotification(null), 3000);
  };

  // Chat Submission Handler
  const handleSendMessage = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!chatInput.trim() || isChatLoading) return;

    const queryText = chatInput;
    setChatInput('');

    // 1. Add User Message to Chat History
    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: 'user',
      text: queryText,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };
    addChatMessage(userMsg);
    setIsChatLoading(true);

    const lowerText = queryText.toLowerCase();
    let purpose = "Pre-Visit Engineering Survey";
    if (lowerText.includes('excavat') || lowerText.includes('dig')) {
      purpose = "Excavation and Geotechnical Drilling";
    } else if (lowerText.includes('wire') || lowerText.includes('cable') || lowerText.includes('high voltage')) {
      purpose = "Catenary Wire Sag & High Voltage Review";
    } else if (lowerText.includes('substation') || lowerText.includes('grid')) {
      purpose = "Substation and Utility Context Review";
    }

    const matchedPredefined =
      predefinedSites.find((site) => lowerText.includes(site.name.toLowerCase().split(' ')[0])) ||
      predefinedSites.find((site) => lowerText.includes(site.name.toLowerCase().split(' ')[1] || ''));

    try {
      const run = await invokeReviewWorkflow({ query: queryText, site: matchedPredefined || null });
      const siteToTrigger = extractSiteFromRun(run, matchedPredefined || null);
      applyRunResult(run, siteToTrigger);

      const briefing = (run.uiState?.briefing || run.briefing || {}) as Record<string, unknown>;
      const hazards = (run.uiState?.hazards || run.hazards || []) as unknown[];
      const evidence = (run.uiState?.evidence || run.evidence || []) as unknown[];
      const trace = (run.uiState?.trace || run.trace || []) as unknown[];

      const agentMsg: ChatMessage = {
        id: `agent-${Date.now()}`,
        sender: 'agent',
        text: `${briefing.headline || `Location evidence gate resolved ${siteToTrigger.name}.`} Review pack is ready for human inspection: ${hazards.length} risk items, ${evidence.length} evidence entries, and ${trace.length} trace steps are available. This is not work approval.`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        extractionCard: {
          siteName: siteToTrigger.name,
          lat: siteToTrigger.lat,
          lng: siteToTrigger.lng,
          purpose,
          date: "Next Scheduled Shift (Jul 1, 2026)",
          resolved: true,
          rawSite: siteToTrigger,
          backendRun: run,
        }
      };

      addChatMessage(agentMsg);
    } catch (err) {
      console.warn('Agent workflow unavailable; using local visual fallback', err);
      const coordsMatch = queryText.match(/([-+]?\d{1,2}(?:\.\d+)?)\s*,\s*([-+]?\d{1,3}(?:\.\d+)?)/);
      let siteToTrigger: Site | null = matchedPredefined || null;
      if (!siteToTrigger && coordsMatch) {
        siteToTrigger = {
          name: `Coordinate candidate (${Number(coordsMatch[1]).toFixed(4)}, ${Number(coordsMatch[2]).toFixed(4)})`,
          lat: Number(coordsMatch[1]),
          lng: Number(coordsMatch[2]),
          elevation: 45,
        };
      }
      if (!siteToTrigger) {
        siteToTrigger = predefinedSites[0];
      }
      triggerDescent(siteToTrigger);
      addChatMessage({
        id: `agent-${Date.now()}`,
        sender: 'agent',
        text: `Backend workflow is unavailable in this browser session, so I loaded the local visual fixture for "${siteToTrigger.name}". Treat this as a fallback visualization only; human review and backend evidence are still required.`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        extractionCard: {
          siteName: siteToTrigger.name,
          lat: siteToTrigger.lat,
          lng: siteToTrigger.lng,
          purpose,
          date: "Next Scheduled Shift (Jul 1, 2026)",
          resolved: true,
          rawSite: siteToTrigger,
        }
      });
    } finally {
      setIsChatLoading(false);
    }
  };

  const isResolving = mode === 'DESCENT';

  return (
    <div className="absolute inset-0 pointer-events-none z-10 flex flex-col justify-between p-4 pt-4 select-none">
      
      {/* Toast Notification Container */}
      {exportNotification && (
        <div className="absolute top-4 left-1/2 transform -translate-x-1/2 bg-emerald-50 border border-emerald-300 text-emerald-800 font-bold px-4 py-2.5 rounded-lg shadow-xl flex items-center gap-2 text-xs tracking-wide pointer-events-auto z-40 animate-bounce">
          <CheckCircle2 className="w-4.5 h-4.5 text-emerald-500" />
          {exportNotification}
        </div>
      )}

      {/* ==================================================== */}
      {/* MAIN TOP OVERLAYS: HUD ROW                           */}
      {/* ==================================================== */}
      <div className="w-full flex-grow flex justify-between gap-4 overflow-hidden relative pb-10">
        
        {/* ==================================================== */}
        {/* LEFT COLLAPSIBLE CHAT INTERFACE & SIDEBAR            */}
        {/* ==================================================== */}
        <div className={`h-full flex flex-col pointer-events-auto transition-all duration-300 z-30 shrink-0 ${
          chatOpen ? 'w-96' : 'w-12'
        }`}>
          {!chatOpen ? (
            /* Collapsed Sidebar Tab */
            <div 
              onClick={() => setChatOpen(true)}
              className="w-full h-full bg-white/95 backdrop-blur-md border border-slate-200 rounded-xl shadow-lg flex flex-col items-center py-4 justify-between cursor-pointer hover:bg-slate-50 hover:border-cyan-300 group transition-all duration-200"
              title="Expand ASI:One Chat"
            >
              {/* Top: Pulsing Indicator / Icon */}
              <div className="flex flex-col items-center gap-1">
                <div className="relative">
                  <Cpu className="w-5 h-5 text-cyan-600 group-hover:scale-110 transition-transform" />
                  <div className="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-emerald-500 border border-white animate-pulse" />
                </div>
              </div>

              {/* Middle: Vertical Text */}
              <div className="flex-grow flex items-center justify-center select-none py-8">
                <span 
                  className="text-[10px] font-mono font-extrabold tracking-widest text-slate-400 group-hover:text-cyan-600 transition-colors uppercase whitespace-nowrap"
                  style={{ writingMode: 'vertical-rl', transform: 'rotate(180deg)' }}
                >
                  ASI:One Spatial Chat
                </span>
              </div>

              {/* Bottom: Expand Chevron Button */}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setChatOpen(true);
                }}
                className="p-1.5 rounded-lg bg-cyan-50 border border-cyan-200 text-cyan-700 hover:bg-cyan-600 hover:text-white transition shadow-xs flex items-center justify-center cursor-pointer"
                title="Expand Panel"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          ) : (
            /* Full Expanded Chat Card */
            <div className="w-full h-full bg-white/95 backdrop-blur-md border border-slate-200 rounded-xl shadow-lg flex flex-col overflow-hidden">
              {/* Chat Header */}
              <div className="px-4 py-3 border-b border-slate-100 bg-slate-50 flex items-center justify-between shrink-0">
                <div className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1">
                    <Cpu className="w-4 h-4 text-cyan-600" /> ASI:One Spatial Chatbot
                  </span>
                </div>
                <button
                  onClick={() => setChatOpen(false)}
                  className="text-slate-400 hover:text-slate-700 p-1 rounded hover:bg-slate-200/55 transition cursor-pointer"
                  title="Collapse Panel"
                >
                  <Minimize2 className="w-4.5 h-4.5" />
                </button>
              </div>

              {/* Message History */}
              <div className="flex-grow overflow-y-auto p-4 space-y-4 scrollbar-thin scrollbar-thumb-slate-200">
                {chatHistory.map((msg) => (
                  <div key={msg.id} className="space-y-1">
                    <div className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-[85%] rounded-2xl p-3 text-xs leading-relaxed shadow-xs ${
                        msg.sender === 'user'
                          ? 'bg-slate-100 text-slate-800 rounded-tr-none'
                          : 'bg-cyan-50/70 text-slate-800 rounded-tl-none border border-cyan-100/50'
                      }`}>
                        <p className="font-sans whitespace-pre-line">{msg.text}</p>
                        <span className="text-[9px] font-mono text-slate-400 block text-right mt-1.5 select-none uppercase">
                          {msg.timestamp}
                        </span>
                      </div>
                    </div>

                    {/* Extraction Confirmation Card inside chat */}
                    {msg.extractionCard && (
                      <div className="ml-1 mt-2 p-4 bg-white rounded-xl border border-slate-200/80 shadow-xs max-w-sm border-l-4 border-cyan-500 space-y-3">
                        <div className="flex items-center gap-1.5 border-b border-slate-100 pb-1.5">
                          <CheckCircle2 className="w-4.5 h-4.5 text-cyan-500 shrink-0" />
                          <span className="text-[11px] font-bold text-slate-800 uppercase tracking-wide">
                            Location Evidence Gate
                          </span>
                        </div>

                        <div className="grid grid-cols-12 gap-y-1.5 text-xs">
                          <span className="col-span-4 text-slate-400 font-mono text-[10px] uppercase">Site:</span>
                          <span className="col-span-8 font-bold text-slate-800 truncate">{msg.extractionCard.siteName}</span>

                          <span className="col-span-4 text-slate-400 font-mono text-[10px] uppercase">Coords:</span>
                          <span className="col-span-8 text-slate-500 font-mono font-semibold">
                            {msg.extractionCard.lat.toFixed(5)}°N, {msg.extractionCard.lng.toFixed(5)}°W
                          </span>

                          <span className="col-span-4 text-slate-400 font-mono text-[10px] uppercase">Purpose:</span>
                          <span className="col-span-8 text-slate-600 font-medium">{msg.extractionCard.purpose}</span>

                          <span className="col-span-4 text-slate-400 font-mono text-[10px] uppercase">Shift Date:</span>
                          <span className="col-span-8 text-slate-600 font-medium">{msg.extractionCard.date}</span>
                        </div>

                        <button
                          onClick={() => {
                            const siteObj = msg.extractionCard.rawSite || {
                              name: msg.extractionCard.siteName,
                              lat: msg.extractionCard.lat,
                              lng: msg.extractionCard.lng,
                              elevation: 45
                            };
                            if (msg.extractionCard.backendRun) {
                              applyRunResult(msg.extractionCard.backendRun, siteObj);
                            } else {
                              triggerDescent(siteObj);
                            }
                          }}
                          className="w-full py-2 bg-cyan-600 hover:bg-cyan-500 text-white font-bold text-xs uppercase tracking-wider rounded-lg border border-cyan-500 shadow-md shadow-cyan-600/10 transition flex items-center justify-center gap-1.5 cursor-pointer"
                        >
                          <Compass className="w-4.5 h-4.5" /> Confirm Candidate + Run Tools
                        </button>
                      </div>
                    )}
                  </div>
                ))}

                {isChatLoading && (
                  <div className="flex justify-start">
                    <div className="bg-cyan-50/50 rounded-2xl rounded-tl-none p-3 border border-cyan-100 max-w-[85%] text-xs shadow-xs text-slate-400 flex items-center gap-2">
                      <span className="w-1.5 h-1.5 rounded-full bg-cyan-500 animate-ping" />
                      <span>Preparing agent workflow, evidence gate, and review pack...</span>
                    </div>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>

              {/* Quick Hotzones Selector */}
              <div className="px-4 py-2 border-t border-slate-100 bg-slate-50/50">
                <span className="text-[10px] font-mono text-slate-400 font-bold block mb-1 uppercase tracking-wider">
                  Quick-Jump Coordinates / Hotzones:
                </span>
                <div className="flex flex-wrap gap-1.5 pb-1">
                  {predefinedSites.map((site) => (
                    <button
                      key={site.name}
                      onClick={async () => {
                        addChatMessage({
                          id: `site-${Date.now()}`,
                          sender: 'user',
                          text: `Reviewing ${site.name}`,
                          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                        });
                        setIsChatLoading(true);
                        try {
                          const run = await invokeReviewWorkflow({ query: `Prepare a pre-visit review pack for ${site.name}`, site });
                          const resolvedSite = extractSiteFromRun(run, site);
                          applyRunResult(run, resolvedSite);
                          addChatMessage({
                            id: `agent-site-${Date.now()}`,
                            sender: 'agent',
                            text: `Confirmed "${resolvedSite.name}" through the workflow adapter. Review pack layers are mapped for human inspection.`,
                            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                            extractionCard: {
                              siteName: resolvedSite.name,
                              lat: resolvedSite.lat,
                              lng: resolvedSite.lng,
                              purpose: "Pre-Visit Structural Engineering Review",
                              date: "Tomorrow (Jul 1, 2026)",
                              resolved: true,
                              rawSite: resolvedSite,
                              backendRun: run,
                            }
                          });
                        } catch (err) {
                          console.warn('Hotzone workflow unavailable; using fixture', err);
                          triggerDescent(site);
                          addChatMessage({
                            id: `agent-site-${Date.now()}`,
                            sender: 'agent',
                            text: `Loaded the local visual fixture for "${site.name}" because the backend workflow is unavailable. This remains a fallback visualization for human review.`,
                            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                            extractionCard: {
                              siteName: site.name,
                              lat: site.lat,
                              lng: site.lng,
                              purpose: "Pre-Visit Structural Engineering Review",
                              date: "Tomorrow (Jul 1, 2026)",
                              resolved: true,
                              rawSite: site,
                            }
                          });
                        } finally {
                          setIsChatLoading(false);
                        }
                      }}
                      className={`px-2 py-1 rounded text-[10px] font-medium border transition cursor-pointer ${
                        selectedSite.name === site.name
                          ? 'bg-cyan-50 border-cyan-300 text-cyan-700 font-bold'
                          : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-100'
                      }`}
                    >
                      {site.name.split(' ')[0]}
                    </button>
                  ))}
                </div>
              </div>

              {/* Chat Input form */}
              <form onSubmit={handleSendMessage} className="p-3 border-t border-slate-100 bg-white flex gap-2 shrink-0">
                <input
                  type="text"
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  placeholder="Ask ASI:One or type coordinates (lat,lng)..."
                  className="flex-grow px-3 py-2 bg-slate-50 border border-slate-200 text-slate-800 rounded-lg text-xs font-sans placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-cyan-500 focus:border-cyan-500 focus:bg-white"
                />
                <button
                  type="submit"
                  className="p-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white transition cursor-pointer flex items-center justify-center shrink-0 shadow-md shadow-cyan-600/10"
                >
                  <Send className="w-4 h-4" />
                </button>
              </form>
            </div>
          )}
        </div>

        {/* ==================================================== */}
        {/* CENTER SCENE OVERLAYS (Scan HUD / Descent)          */}
        {/* ==================================================== */}
        {isResolving && (
          <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-slate-950/40 backdrop-blur-xs transition">
            <div className="bg-white/95 border border-slate-200 p-6 rounded-2xl shadow-2xl w-full max-w-sm text-center space-y-4 scale-in duration-200">
              <div className="flex justify-center">
                <div className="w-12 h-12 rounded-full bg-cyan-100 flex items-center justify-center animate-spin">
                  <Compass className="w-6 h-6 text-cyan-600" />
                </div>
              </div>
              <div className="space-y-1">
                <h3 className="text-sm font-extrabold text-slate-900 tracking-tight uppercase">
                  Descent Scanning Triggered
                </h3>
                <p className="text-xs text-slate-500">
                  Flying to site origin at {selectedSite.lat.toFixed(4)}°N, {selectedSite.lng.toFixed(4)}°W
                </p>
              </div>

              <div className="space-y-1.5">
                <div className="flex justify-between text-[10px] font-mono text-slate-400 font-bold uppercase">
                  <span>Reconstructing Terrain</span>
                  <span>{resolutionProgress}%</span>
                </div>
                <div className="w-full bg-slate-100 h-1.5 rounded-full overflow-hidden border border-slate-200/50">
                  <div className="bg-cyan-500 h-full transition-all duration-100" style={{ width: `${resolutionProgress}%` }} />
                </div>
              </div>

              <div className="text-[9px] font-mono text-slate-400 uppercase tracking-widest bg-slate-50 py-1.5 rounded border border-slate-100">
                ACTIVE VECTOR ALIGNMENT
              </div>
            </div>
          </div>
        )}

        {/* ==================================================== */}
        {/* RIGHT FLOATING WIDGETS COLUMN                        */}
        {/* ==================================================== */}
        <div className="absolute top-0 bottom-0 right-0 w-80 flex flex-col gap-3 justify-start z-30 pointer-events-auto">
          
          {/* Site Context Card */}
          <div id="widget-site-context" className="bg-white/90 backdrop-blur-md border border-slate-200 p-4 rounded-xl shadow-sm space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5 border-b border-slate-100 pb-1.5">
              <MapPin className="w-4 h-4 text-cyan-600" /> Site Context Summary
            </h3>
            <div className="space-y-2 text-xs">
              <div className="flex justify-between items-center">
                <span className="text-slate-400 font-mono text-[10px] uppercase">Active Target:</span>
                <span className="font-bold text-slate-800 text-right max-w-[160px] truncate" title={selectedSite.name}>
                  {selectedSite.name}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-400 font-mono text-[10px] uppercase">WGS84 Lat/Lon:</span>
                <span className="font-mono text-slate-600 font-semibold text-right">
                  {selectedSite.lat.toFixed(5)}°N, {selectedSite.lng.toFixed(5)}°W
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-400 font-mono text-[10px] uppercase">Boundary Limit:</span>
                <span className="text-slate-700 font-medium text-right">500m Local ENU</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-400 font-mono text-[10px] uppercase">Base Elevation:</span>
                <span className="text-slate-700 font-mono font-semibold text-right">{selectedSite.elevation}m AGL</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-400 font-mono text-[10px] uppercase">Advisory Anomalies:</span>
                <span className="px-1.5 py-0.5 rounded bg-red-50 text-red-600 border border-red-100 font-bold font-mono text-[10px] text-right">
                  {annotations.length} Flags
                </span>
              </div>
            </div>
            {mode === 'EXPLORATION' && (
              <button
                onClick={() => {
                  const el = document.getElementById('research-pack');
                  if (el) el.scrollIntoView({ behavior: 'smooth' });
                }}
                className="w-full py-1.5 bg-slate-100 hover:bg-slate-200 border border-slate-300/60 rounded-lg font-bold text-[10px] uppercase tracking-wider text-slate-700 flex items-center justify-center gap-1 transition"
              >
                <span>Read Research Dossier</span> <ChevronRight className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {/* Active Overlay Legend Card */}
          <div id="widget-overlay-legend" className="bg-white/90 backdrop-blur-md border border-slate-200 p-4 rounded-xl shadow-sm space-y-2.5">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5 border-b border-slate-100 pb-1.5">
              <Layers className="w-4 h-4 text-cyan-600" /> Active 3D Overlays
            </h3>
            <div className="space-y-2 text-[11px] text-slate-600">
              <div className="flex items-center gap-2">
                <span className="w-3.5 h-2 rounded bg-blue-500 opacity-60 border border-blue-400" />
                <span className="font-semibold text-slate-700">Flooding Hydrology (Buffer)</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3.5 h-2 rounded bg-emerald-500 opacity-60 border border-emerald-400" />
                <span className="font-semibold text-slate-700">Recommended Egress Corridor</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3.5 h-2 rounded bg-amber-500 opacity-60 border border-amber-400" />
                <span className="font-semibold text-slate-700">Low-Confidence LiDAR Segment</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3.5 h-2 rounded bg-purple-500 opacity-60 border border-purple-400" />
                <span className="font-semibold text-slate-700">OHL Electric Shield Zone</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3.5 h-3.5 rounded-full bg-cyan-400 animate-pulse border border-cyan-300" />
                <span className="text-slate-500 italic text-[10px]">Interactions: Click pins to inspect</span>
              </div>
            </div>
          </div>

          {/* Sub-Agent Status Widget */}
          <div id="widget-subagents" className="bg-white/90 backdrop-blur-md border border-slate-200 p-4 rounded-xl shadow-sm space-y-3 flex-grow overflow-y-auto max-h-[220px]">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5 border-b border-slate-100 pb-1.5">
              <Activity className="w-4 h-4 text-cyan-600" /> Swarm Agent Statuses
            </h3>
            <div className="space-y-3">
              {agents.map((agent) => (
                <div key={agent.id} className="space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-bold text-slate-700">{agent.name}</span>
                    <span className={`px-1.5 py-0.5 rounded text-[9px] font-mono font-bold uppercase ${
                      agent.status === 'complete'
                        ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                        : agent.status === 'resolving'
                        ? 'bg-amber-50 text-amber-700 border border-amber-200 animate-pulse'
                        : 'bg-slate-50 text-slate-400 border border-slate-200'
                    }`}>
                      {agent.status}
                    </span>
                  </div>
                  {/* Confidence and vintage info */}
                  <div className="flex justify-between text-[9px] font-mono text-slate-400 uppercase leading-none">
                    <span>VINTAGE: {agent.vintage.substring(0, 18)}...</span>
                    <span>CONF: {(agent.confidence * 100).toFixed(0)}%</span>
                  </div>
                  {agent.status === 'resolving' && (
                    <div className="w-full bg-slate-100 h-1 rounded-full overflow-hidden border border-slate-200/50">
                      <div className="bg-cyan-500 h-full animate-pulse" style={{ width: `${resolutionProgress}%` }} />
                    </div>
                  )}
                  {agent.warning && (
                    <div className="text-[9px] font-mono text-amber-600 italic bg-amber-50 px-1 rounded">
                      ⚠ {agent.warning}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Compilation CTA Panel */}
          {observationPack.length > 0 && (
            <button
              onClick={() => setShowExportModal(true)}
              className="w-full py-3 bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs uppercase tracking-wider rounded-xl border border-emerald-500 shadow-md shadow-emerald-600/10 transition shrink-0 pointer-events-auto flex items-center justify-center gap-1.5 cursor-pointer"
            >
              <Layers3 className="w-4.5 h-4.5 text-white" /> Compile Pack ({observationPack.length})
            </button>
          )}

        </div>

      </div>

      {/* ==================================================== */}
      {/* SELECTION OVERLAY: ANNOTATION DETAIL CARD (Bottom Left) */}
      {/* ==================================================== */}
      {selectedAnnotation && (
        <div className="absolute bottom-12 left-4 w-96 bg-white border border-slate-200 rounded-xl shadow-xl z-30 p-4 pointer-events-auto space-y-3.5 scale-in duration-150">
          <div className="flex items-start justify-between border-b border-slate-100 pb-2">
            <div>
              <span className={`text-[9px] font-mono font-extrabold px-1.5 py-0.5 rounded border uppercase ${
                selectedAnnotation.level === 'hazard'
                  ? 'bg-red-50 text-red-700 border-red-200'
                  : selectedAnnotation.level === 'warning'
                  ? 'bg-amber-50 text-amber-700 border-amber-200'
                  : 'bg-cyan-50 text-cyan-700 border-cyan-200'
              }`}>
                {selectedAnnotation.level} // {selectedAnnotation.id}
              </span>
              <h4 className="text-sm font-bold text-slate-900 mt-1.5 leading-snug">
                {selectedAnnotation.title}
              </h4>
            </div>
            <button
              onClick={() => setSelectedAnnotation(null)}
              className="text-slate-400 hover:text-slate-600 p-0.5 rounded hover:bg-slate-100 transition cursor-pointer"
            >
              <X className="w-4.5 h-4.5" />
            </button>
          </div>

          <div className="text-xs text-slate-600 leading-relaxed font-sans space-y-1">
            <p>{selectedAnnotation.description}</p>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[10px] text-slate-400 uppercase pt-1.5">
              <span>Source: {selectedAnnotation.type}</span>
              <span>Confidence: {(selectedAnnotation.confidence * 100).toFixed(0)}%</span>
              <span>Vintage: {selectedAnnotation.vintage}</span>
            </div>
          </div>

          {/* Add to observation pack button */}
          <div className="flex gap-2.5 pt-1.5">
            <button
              onClick={() => setSelectedAnnotation(null)}
              className="flex-1 py-1.5 bg-slate-100 hover:bg-slate-200 border border-slate-300/40 rounded-lg text-slate-700 font-bold text-[10px] uppercase tracking-wider transition cursor-pointer text-center"
            >
              Dismiss
            </button>
            <button
              onClick={() => toggleInObservationPack(selectedAnnotation.id)}
              className={`flex-1 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider transition cursor-pointer flex items-center justify-center gap-1 border ${
                observationPack.includes(selectedAnnotation.id)
                  ? 'bg-emerald-50 text-emerald-700 border-emerald-300'
                  : 'bg-cyan-600 text-white border-cyan-600 hover:bg-cyan-500 shadow-md shadow-cyan-600/10'
              }`}
            >
              {observationPack.includes(selectedAnnotation.id) ? (
                <>
                  <Check className="w-3.5 h-3.5" /> Saved in Pack
                </>
              ) : (
                <>
                  <Layers3 className="w-3.5 h-3.5" /> Add to Advisory Pack
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* ==================================================== */}
      {/* EXPORT COMPILATION MODAL                             */}
      {/* ==================================================== */}
      {showExportModal && (
        <div className="fixed inset-0 bg-slate-950/40 backdrop-blur-xs z-50 flex items-center justify-center p-4 pointer-events-auto">
          <div className="bg-white border border-slate-200 w-full max-w-lg rounded-xl overflow-hidden shadow-2xl p-6 space-y-4 scale-in duration-150 text-slate-700">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <h3 className="text-sm font-bold tracking-wider text-slate-900 flex items-center gap-2 uppercase">
                <Layers3 className="w-5 h-5 text-cyan-600" /> Compiled Advisory Pack
              </h3>
              <button
                onClick={() => setShowExportModal(false)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded hover:bg-slate-100 cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="text-xs text-slate-500 font-mono space-y-1 bg-slate-50 p-3 rounded-lg border border-slate-150">
              <p>EXPORT_UUID: <span className="text-cyan-600 font-bold">rams-7c9f-2026</span></p>
              <p>SITE_CONTEXT: <span className="text-slate-800 font-semibold">{selectedSite.name}</span></p>
              <p>COORDINATES: <span className="text-slate-800 font-semibold">{selectedSite.lat.toFixed(5)}°N, {selectedSite.lng.toFixed(5)}°W</span></p>
            </div>

            <div className="space-y-2 max-h-[220px] overflow-y-auto pr-2 border-y border-slate-100 py-3">
              {observationPack.map((id, index) => {
                const match = annotations.find(a => a.id === id);
                if (!match) return null;
                return (
                  <div key={id} className="p-3 bg-slate-50/50 rounded-lg border border-slate-200/60 flex items-start gap-3">
                    <span className="w-5 h-5 rounded-full bg-slate-200 text-slate-600 text-xs font-mono font-bold flex items-center justify-center shrink-0 select-none">
                      {index + 1}
                    </span>
                    <div className="space-y-1">
                      <h4 className="text-[11px] font-bold text-slate-800 leading-none">{match.title}</h4>
                      <p className="text-[10px] text-slate-500 leading-normal">{match.description}</p>
                      <div className="flex items-center gap-3 text-[9px] font-mono text-slate-400 uppercase pt-1 font-semibold">
                        <span>Type: {match.type}</span>
                        <span>Level: {match.level}</span>
                        <span>Confidence: {(match.confidence * 100).toFixed(0)}%</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="flex items-center gap-2.5 p-3 rounded bg-amber-50 text-amber-800 border border-amber-200 text-[10px] leading-relaxed font-sans">
              <Info className="w-5 h-5 shrink-0 text-amber-600" />
              <div>
                <strong>Legal Disclaimer:</strong> This compilation contains spatial anomalies and warnings retrieved via autonomous agents. It does NOT constitute work authorization or formal RAMS clearance.
              </div>
            </div>

            <div className="flex gap-3 pt-2">
              <button
                onClick={() => setShowExportModal(false)}
                className="flex-1 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 border border-slate-300 text-slate-700 font-bold text-xs uppercase tracking-wider transition cursor-pointer text-center"
              >
                Close View
              </button>
              <button
                onClick={executeDownload}
                className="flex-1 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-bold text-xs uppercase tracking-wider transition cursor-pointer flex items-center justify-center gap-1.5 border border-cyan-500 shadow-lg shadow-cyan-600/10"
              >
                <Download className="w-4.5 h-4.5" /> Download payload
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
};
