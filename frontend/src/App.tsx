import React from 'react';
import { CesiumBase } from './components/CesiumBase';
import { OverlayRoot } from './components/OverlayRoot';
import { UIChrome } from './components/UIChrome';
import { ResearchPack } from './components/ResearchPack';
import { useSiteStore } from './store/useSiteStore';
import { ShieldAlert, Cpu, MessageSquare } from 'lucide-react';

export default function App() {
  const { mode, selectedSite, chatOpen, setChatOpen } = useSiteStore();

  return (
    <div className="relative w-full min-h-screen bg-slate-50 flex flex-col text-slate-800 font-sans selection:bg-cyan-500/20">
      
      {/* ==================================================== */}
      {/* PERSISTENT TOP BAR                                   */}
      {/* ==================================================== */}
      <header className="fixed top-0 left-0 right-0 h-14 bg-white/95 backdrop-blur-md border-b border-slate-200 z-50 px-6 flex items-center justify-between shadow-xs">
        <div className="flex items-center gap-2.5">
          {/* Logo Icon */}
          <div className="w-8 h-8 rounded-lg bg-cyan-500 flex items-center justify-center shadow-md shadow-cyan-500/20">
            <Cpu className="w-4.5 h-4.5 text-white" />
          </div>
          <div>
            <span className="font-bold tracking-tight text-slate-900 text-sm">3D-RAMS</span>
            <span className="text-[10px] font-mono text-cyan-600 block leading-none font-semibold uppercase tracking-wider">
              ASI:One Review Console v3.0
            </span>
          </div>
        </div>

        {/* Dynamic Session Pill */}
        <div className="hidden sm:flex items-center gap-2 px-3 py-1 bg-slate-100 rounded-full border border-slate-200/60">
          <span className={`w-2 h-2 rounded-full ${
            mode === 'EXPLORATION' 
              ? 'bg-emerald-500 animate-pulse' 
              : mode === 'DESCENT' 
              ? 'bg-amber-500 animate-bounce' 
              : 'bg-cyan-500'
          }`} />
          <span className="text-xs font-mono font-bold text-slate-600 uppercase tracking-wide">
            {mode === 'EXPLORATION' 
              ? `REVIEW PACK // ${selectedSite.name.toUpperCase()}` 
              : mode === 'DESCENT' 
              ? '3D SITE MODEL BUILDING' 
              : 'READY // ASI:ONE INTAKE'}
          </span>
        </div>

        {/* Toggle Chatbot Button */}
        <button
          onClick={() => setChatOpen(!chatOpen)}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-medium transition cursor-pointer hover:shadow-xs ${
            chatOpen 
              ? 'bg-cyan-50 border-cyan-300 text-cyan-700 font-bold shadow-sm shadow-cyan-500/5' 
              : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'
          }`}
          title={chatOpen ? "Minimize Chat" : "Open ASI Chatbot"}
        >
          <MessageSquare className="w-4 h-4 text-cyan-500 shrink-0" />
          <span className="font-bold uppercase tracking-wide">ASI:One Chat</span>
        </button>

        {/* Auth / Dispatch ID */}
        <div className="flex items-center gap-3">
          <div className="text-right">
            <span className="text-xs font-mono text-slate-500 font-bold block">HUMAN REVIEW MODE</span>
            <span className="text-[9px] font-mono text-slate-400 block uppercase">No work approval issued</span>
          </div>
          <div className="w-8 h-8 rounded-full bg-slate-100 border border-slate-200 flex items-center justify-center font-bold text-slate-700 text-xs">
            OP
          </div>
        </div>
      </header>

      {/* Main Page scrollable container with padding-top to account for fixed header */}
      <div className="w-full pt-14 flex flex-col flex-grow pb-10">
        
        {/* ==================================================== */}
        {/* HERO WORKSPACE: 3D CANVASES & FLOATING HUD            */}
        {/* ==================================================== */}
        <section className="relative w-full h-[70vh] min-h-[520px] bg-slate-950 overflow-hidden border-b border-slate-200 shadow-sm flex select-none">
          {/* Layer 1 (Bottom): Cesium WGS84 Terrain Globe */}
          <CesiumBase />
          
          {/* Layer 2 (Middle): Three.js ENU local coordinate overlay */}
          <OverlayRoot />
          
          {/* Layer 3 (Top): UI HUD (Chat panel, right widgets, overlays) */}
          <UIChrome />
        </section>

        {/* ==================================================== */}
        {/* BELOW HERO: RESEARCH PACK DOCUMENT VIEW             */}
        {/* ==================================================== */}
        <ResearchPack />
        
      </div>

      {/* ==================================================== */}
      {/* PERSISTENT SAFETY & LIABILITY BANNER (Fixed Bottom) */}
      {/* ==================================================== */}
      <footer className="fixed bottom-0 left-0 right-0 h-10 bg-red-600 text-white font-mono text-[10px] md:text-xs z-50 flex items-center justify-between px-6 shadow-2xl select-none uppercase tracking-wide border-t border-red-500/45">
        <div className="flex items-center gap-2">
          <ShieldAlert className="w-4 h-4 shrink-0 text-white animate-pulse" />
          <span className="font-extrabold">HUMAN REVIEW REQUIRED</span>
        </div>
        <div className="hidden md:block text-slate-100 text-center text-[10px]">
          3D-RAMS IS A PRE-VISIT RESEARCH AID. NOT CERTIFIED RAMS, WORK APPROVAL, OR EMERGENCY RESPONSE. VERIFY EVIDENCE AND SITE CONDITIONS BEFORE DISPATCH.
        </div>
        <div className="font-bold text-slate-200 font-mono">
          SEC_ID: RX-4420
        </div>
      </footer>

    </div>
  );
}

