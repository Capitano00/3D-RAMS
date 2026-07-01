import React from 'react';
import { useSiteStore } from '../store/useSiteStore';
import { 
  ShieldAlert, 
  CheckCircle2, 
  AlertTriangle, 
  Clock, 
  FileText, 
  Terminal, 
  Compass, 
  Layers, 
  ExternalLink,
  PlusCircle,
  Check
} from 'lucide-react';

export const ResearchPack: React.FC = () => {
  const {
    selectedSite,
    annotations,
    agents,
    selectedAnnotation,
    setSelectedAnnotation,
    observationPack,
    toggleInObservationPack
  } = useSiteStore();

  // Dynamic Content based on selected site
  const getImpactSummary = () => {
    switch(selectedSite.name) {
      case 'Birmingham Rail Corridor':
        return {
          text: 'Complex railway corridor intersection with active high-voltage pylon cables, sub-station exposure, and wind-drift moisture dispersion concerns.',
          stakes: 'HIGH RISK CONFLICT ZONE',
          category: 'Rail Transit Corridor',
          weather: 'Weather signal available'
        };
      case 'London Thameslink Hub':
        return {
          text: 'High-density urban rail network with low-clearance catenary wire sag variance and substation terminal flux anomalies.',
          stakes: 'THERMAL EXPANSION WARNING',
          category: 'Urban Rail Terminal',
          weather: 'Weather signal available'
        };
      case 'Snowdon Grid Interconnect':
        return {
          text: 'Elevated grid interconnect with severe weather, access, and infrastructure context requiring competent-person review.',
          stakes: 'EXTREME WEATHER ZONE',
          category: 'High-Altitude Power Grid',
          weather: 'Weather signal available'
        };
      case 'Edinburgh Tram Extension':
        return {
          text: 'Urban tram network extension with temporary work platform encroachment on active power lines and feeder cable clearance buffers.',
          stakes: 'TEMPORARY WORKS CONFLICT',
          category: 'Municipal Light Rail',
          weather: 'Weather signal available'
        };
      default:
        return {
          text: `Autonomous spatial scan completed over coordinates ${selectedSite.lat.toFixed(5)}°N, ${selectedSite.lng.toFixed(5)}°W. Basic terrain, flight obstacles, and cadastral datasets resolved.`,
          stakes: 'STANDARD BASELINE SCAN',
          category: 'Custom Location',
          weather: 'Weather pending verification'
        };
    }
  };

  const getMissionBriefBullets = () => {
    switch(selectedSite.name) {
      case 'Birmingham Rail Corridor':
        return [
          'Recommended access point: Cable St Access Gate B. Maintain 3.0m lateral distance from transformer compound perimeter fence.',
          'Overhead line clearance context under OHL-B11 is flagged for competent-person verification before equipment or access planning.',
          'Surface moisture drainage context is flagged near Trench Sector 4. Verify ground conditions and temporary works controls before dispatch.',
        ];
      case 'London Thameslink Hub':
        return [
          'Access restricted to scheduled maintenance windows. High magnetic flux (1.8 mG) detected at node J-109; use non-ferromagnetic tools for adjacent work.',
          'Ambient thermal expansion has sagged catenary wires by an estimated 0.45m. Ensure all tall vehicles or machinery keep below 4.5m.',
          'Verify earthing connections across all metal structures in Zone A before manual touch.',
        ];
      case 'Snowdon Grid Interconnect':
        return [
          'High altitude weather context requires review before crane, cable tensioning, or high-level platform planning.',
          'Review wind exposure, loose-material controls, and access constraints against current site procedures.',
          'Confirm access and muster arrangements from authorised site documentation before dispatch.',
        ];
      case 'Edinburgh Tram Extension':
        return [
          'Temporary platform WP-4 appears near the OHL feeder buffer zone. Verify geometry and controls before work planning.',
          'Urban traffic crossing adjacent to construction corridor: high density pedestrians and local vehicles require active marshalling.',
          'Ensure tram conductor alignment is confirmed against local CAD coordinates prior to final structural pouring.',
        ];
      default:
        return [
          'Treat any overhead line, power cable, or exposed utility marker in the 3D viewport as a prompt for human verification.',
          'Conduct a physical ground scan for buried cables or unknown substructure lines before driving stakes or breaking ground.',
          'Inspect the local topography for steep slope gradients or soil erosion indicators not fully resolved in low-resolution terrain maps.',
        ];
    }
  };

  const summary = getImpactSummary();
  const bullets = getMissionBriefBullets();

  return (
    <section id="research-pack" className="w-full bg-white py-12 px-6 md:px-12 border-t border-slate-200 text-slate-700">
      <div className="max-w-5xl mx-auto space-y-10">
        
        {/* Pack Header */}
        <div className="border-b border-slate-200 pb-5">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-2">
            <span className="text-xs font-bold font-mono text-cyan-600 tracking-wider uppercase flex items-center gap-1.5">
              <FileText className="w-4 h-4 text-cyan-500" /> Research Pack // Human-Review Dossier
            </span>
            <span className="text-xs text-slate-400 font-mono">
              GENERATED: 2026-06-30 // ID: PRE-RAMS-7C9F
            </span>
          </div>
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">
            Pre-Visit Spatial Risk Review Pack
          </h1>
          <p className="text-sm text-slate-500 mt-1 max-w-2xl font-sans leading-relaxed">
            Every annotation and hazard layer mapped in the 3D interface is cross-referenced here with agent confidence scores, source timelines, and evidence-backed registers.
          </p>
        </div>

        {/* Card 1: Impact Summary & Stakes */}
        <div id="card-impact-summary" className="bg-slate-50 border border-slate-200 rounded-xl p-6 shadow-sm transition hover:shadow-md">
          <div className="flex flex-col md:flex-row md:items-start justify-between gap-4 mb-4">
            <div>
              <span className="text-[10px] font-mono font-extrabold bg-red-100 text-red-700 px-2 py-0.5 rounded border border-red-200 tracking-wider">
                {summary.stakes}
              </span>
              <h2 className="text-base font-bold text-slate-900 mt-2">
                Impact Summary
              </h2>
            </div>
            <div className="flex flex-wrap gap-2">
              <span className="text-xs bg-slate-200/70 text-slate-600 px-2.5 py-1 rounded-md font-medium border border-slate-300/50">
                {summary.category}
              </span>
              <span className="text-xs bg-cyan-50 text-cyan-700 px-2.5 py-1 rounded-md font-medium border border-cyan-200/50">
                {summary.weather}
              </span>
            </div>
          </div>
          <p className="text-sm text-slate-600 leading-relaxed max-w-4xl">
            {summary.text} This dossier helps surveyors and field teams reduce manual research time and expose review items earlier. Human review is still required before dispatch or work planning.
          </p>
        </div>

        {/* Card 2: Research Coverage Grid */}
        <div id="card-coverage-grid" className="space-y-3">
          <h3 className="text-xs font-mono font-bold uppercase text-slate-400 tracking-wider">
            Agent Research Coverage Matrix
          </h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            {[
              { label: 'Terrain Geometry', status: 'ready', source: 'Cesium / scene layer' },
              { label: 'Weather Dynamics', status: 'ready', source: 'Backend weather signal' },
              { label: 'OSM Infrastructure', status: 'ready', source: 'Open-source context' },
              { label: 'Utility Records', status: selectedSite.name === 'Snowdon Grid Interconnect' || selectedSite.name.includes('Custom') ? 'fallback' : 'ready', source: selectedSite.name === 'Snowdon Grid Interconnect' || selectedSite.name.includes('Custom') ? 'Cached / fallback' : 'Backend evidence' },
              { label: 'Flood Zones', status: 'ready', source: 'Water context layer' },
              { label: 'Access Routes', status: 'ready', source: 'Access context' },
            ].map((cell, index) => (
              <div 
                key={index} 
                className={`p-3 rounded-lg border flex flex-col justify-between h-20 transition shadow-sm ${
                  cell.status === 'ready' 
                    ? 'bg-emerald-50/40 border-emerald-200/80' 
                    : 'bg-amber-50/40 border-amber-200/80'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-semibold text-slate-800 leading-tight truncate mr-1">
                    {cell.label}
                  </span>
                  {cell.status === 'ready' ? (
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                  ) : (
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-500 shrink-0" />
                  )}
                </div>
                <div className="space-y-0.5">
                  <span className="text-[9px] font-mono block text-slate-400 uppercase">
                    Source:
                  </span>
                  <span className={`text-[10px] font-semibold block truncate ${
                    cell.status === 'ready' ? 'text-emerald-700' : 'text-amber-700'
                  }`}>
                    {cell.source}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Card 3: Mission Brief */}
        <div id="card-mission-brief" className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
          <h2 className="text-base font-bold text-slate-900 mb-3 flex items-center gap-2">
            <Compass className="w-4 h-4 text-cyan-600" /> Mission Brief & Access Guidelines
          </h2>
          <div className="space-y-3 pl-4 border-l-2 border-cyan-500">
            {bullets.map((bullet, idx) => (
              <div key={idx} className="text-sm text-slate-600 leading-relaxed flex items-start gap-2">
                <span className="text-cyan-500 font-mono mt-0.5 shrink-0 select-none">•</span>
                <span>{bullet}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Card 4: Grouped Risk Review */}
        <div id="card-risk-review" className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold text-slate-900">
              Active Advisory Registry
            </h2>
            <span className="text-xs font-mono text-slate-400">
              {annotations.length} Observations Identified
            </span>
          </div>

          <div className="grid md:grid-cols-2 gap-4">
            
            {/* Left Col: High-Priority & Hazards */}
            <div className="space-y-3">
              <h3 className="text-xs font-bold font-mono text-red-500 uppercase tracking-widest flex items-center gap-1">
                <ShieldAlert className="w-3.5 h-3.5" /> High-Priority Hazards
              </h3>
              
              {annotations.filter(a => a.level === 'hazard').length === 0 ? (
                <div className="p-4 rounded-lg border border-slate-200 bg-slate-50 text-slate-400 text-xs italic text-center">
                  No high-priority hazards active on this coordinate frame.
                </div>
              ) : (
                annotations.filter(a => a.level === 'hazard').map(anno => {
                  const isSelected = selectedAnnotation?.id === anno.id;
                  return (
                    <div 
                      key={anno.id} 
                      onClick={() => setSelectedAnnotation(anno)}
                      className={`p-4 rounded-lg border transition-all text-left cursor-pointer ${
                        isSelected 
                          ? 'bg-red-50/50 border-red-500 ring-1 ring-red-500' 
                          : 'bg-white border-slate-200 hover:border-red-200 hover:bg-slate-50/30'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2 mb-1">
                        <h4 className="text-sm font-bold text-slate-900 leading-snug">{anno.title}</h4>
                        <span className="text-[10px] font-mono bg-red-100 text-red-700 px-2 py-0.5 rounded-full border border-red-200 uppercase font-semibold shrink-0">
                          {anno.id}
                        </span>
                      </div>
                      <p className="text-xs text-slate-500 mb-2.5 font-mono">
                        Source: {anno.type} Sub-Agent | Confidence: {(anno.confidence * 100).toFixed(0)}%
                      </p>
                      <p className="text-xs text-slate-600 leading-relaxed truncate-2-lines">
                        {anno.description}
                      </p>
                    </div>
                  );
                })
              )}
            </div>

            {/* Right Col: Warnings & Environmental Buffers */}
            <div className="space-y-3">
              <h3 className="text-xs font-bold font-mono text-amber-500 uppercase tracking-widest flex items-center gap-1">
                <AlertTriangle className="w-3.5 h-3.5" /> Warnings & Contextual Buffers
              </h3>

              {annotations.filter(a => a.level !== 'hazard').length === 0 ? (
                <div className="p-4 rounded-lg border border-slate-200 bg-slate-50 text-slate-400 text-xs italic text-center">
                  No warning buffers active.
                </div>
              ) : (
                annotations.filter(a => a.level !== 'hazard').map(anno => {
                  const isSelected = selectedAnnotation?.id === anno.id;
                  const isWarning = anno.level === 'warning';
                  return (
                    <div 
                      key={anno.id} 
                      onClick={() => setSelectedAnnotation(anno)}
                      className={`p-4 rounded-lg border transition-all text-left cursor-pointer ${
                        isSelected 
                          ? isWarning 
                            ? 'bg-amber-50/50 border-amber-500 ring-1 ring-amber-500' 
                            : 'bg-cyan-50/50 border-cyan-500 ring-1 ring-cyan-500'
                          : 'bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50/30'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2 mb-1">
                        <h4 className="text-sm font-bold text-slate-900 leading-snug">{anno.title}</h4>
                        <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border uppercase font-semibold shrink-0 ${
                          isWarning 
                            ? 'bg-amber-100 text-amber-700 border-amber-200' 
                            : 'bg-cyan-50 text-cyan-700 border-cyan-200'
                        }`}>
                          {anno.id}
                        </span>
                      </div>
                      <p className="text-xs text-slate-500 mb-2.5 font-mono">
                        Source: {anno.type} Sub-Agent | Confidence: {(anno.confidence * 100).toFixed(0)}%
                      </p>
                      <p className="text-xs text-slate-600 leading-relaxed truncate-2-lines">
                        {anno.description}
                      </p>
                    </div>
                  );
                })
              )}
            </div>

          </div>
        </div>

        {/* Card 5: Evidence Register */}
        <div id="card-evidence-register" className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-4">
          <div>
            <h2 className="text-base font-bold text-slate-900">
              Evidence & Telemetry Register
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Source telemetry sets used by autonomous sub-agents to calculate 3D boundaries. Select rows to locate them on the map.
            </p>
          </div>

          <div className="border border-slate-200 rounded-lg overflow-hidden">
            {/* Header row */}
            <div className="grid grid-cols-12 gap-2 bg-slate-50 px-4 py-2 border-b border-slate-200 text-[10px] font-mono uppercase text-slate-400 tracking-wider">
              <div className="col-span-2">Marker ID</div>
              <div className="col-span-3">Assigned Source</div>
              <div className="col-span-2">Telemetry Vintage</div>
              <div className="col-span-2 text-center">Confidence</div>
              <div className="col-span-3 text-right">Advisory Actions</div>
            </div>

            {/* Rows */}
            <div className="divide-y divide-slate-100">
              {annotations.map((anno) => {
                const isSelected = selectedAnnotation?.id === anno.id;
                const inPack = observationPack.includes(anno.id);
                return (
                  <div 
                    key={anno.id}
                    onClick={() => setSelectedAnnotation(anno)}
                    className={`grid grid-cols-12 gap-2 px-4 py-3 items-center text-xs transition cursor-pointer ${
                      isSelected ? 'bg-cyan-50/20' : 'hover:bg-slate-50/50'
                    }`}
                  >
                    <div className="col-span-2 font-mono font-bold text-slate-900 flex items-center gap-1.5">
                      <span className={`w-1.5 h-1.5 rounded-full ${
                        anno.level === 'hazard' ? 'bg-red-500' : anno.level === 'warning' ? 'bg-amber-500' : 'bg-cyan-500'
                      }`} />
                      {anno.id}
                    </div>
                    <div className="col-span-3 font-medium text-slate-700 truncate">{anno.title}</div>
                    <div className="col-span-2 text-slate-500 font-mono text-[11px]">{anno.vintage}</div>
                    <div className="col-span-2 text-center font-mono">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        anno.confidence >= 0.9 
                          ? 'bg-emerald-50 text-emerald-700 border border-emerald-200/50' 
                          : anno.confidence >= 0.8 
                          ? 'bg-blue-50 text-blue-700 border border-blue-200/50'
                          : 'bg-amber-50 text-amber-700 border border-amber-200/50 font-bold animate-pulse'
                      }`}>
                        {(anno.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div className="col-span-3 text-right flex items-center justify-end gap-2">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleInObservationPack(anno.id);
                        }}
                        className={`px-2 py-1 rounded text-[10px] font-bold flex items-center gap-1 transition ${
                          inPack 
                            ? 'bg-emerald-100 text-emerald-800 border border-emerald-200' 
                            : 'bg-slate-100 text-slate-600 border border-slate-200 hover:bg-slate-200'
                        }`}
                      >
                        {inPack ? <Check className="w-3 h-3" /> : <PlusCircle className="w-3 h-3" />}
                        {inPack ? 'In Pack' : 'Add to Pack'}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Card 6: Tool Trace / Agent Timeline */}
        <div id="card-tool-trace" className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-base font-bold text-slate-900 flex items-center gap-1.5">
              <Terminal className="w-4 h-4 text-slate-500" /> Multi-Agent Swarm Tool Trace
            </h2>
            <span className="text-xs font-mono text-slate-400">Total overhead: 460 ms</span>
          </div>

          <div className="relative border-l border-slate-200 pl-6 ml-3 space-y-6 text-xs text-slate-600">
            {[
              { title: 'Extraction & Entity Resolution', timestamp: '11:00:15 AM', duration: '120ms', detail: 'Coordinates parsed; matching known buffer databases and OHL vector segments.', status: 'COMPLETED' },
              { title: 'Elevation Baseline Matching', timestamp: '11:00:15 AM', duration: '85ms', detail: `ENU projection initialized at lat ${selectedSite.lat.toFixed(4)}, lon ${selectedSite.lng.toFixed(4)} with base elevation calculated at ${selectedSite.elevation}m.`, status: 'COMPLETED' },
              { title: 'Weather Context Sync', timestamp: '11:00:16 AM', duration: '110ms', detail: 'Collected weather, water, and access context where available; fallback status is disclosed when sources are incomplete.', status: 'COMPLETED' },
              { title: 'Sub-Agent Spatial Alignment', timestamp: '11:00:16 AM', duration: '145ms', detail: 'Drawn 3D bounding rings, sag catenaries, and electrostatic discharge risk fields directly on Three.js local overlay.', status: 'COMPLETED' }
            ].map((step, idx) => (
              <div key={idx} className="relative">
                {/* Node icon */}
                <div className="absolute -left-[31px] top-0.5 bg-white p-0.5">
                  <div className="w-3 h-3 rounded-full bg-cyan-500 border-2 border-white ring-1 ring-cyan-500 animate-pulse" />
                </div>
                
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h4 className="font-bold text-slate-800 flex items-center gap-2">
                      {step.title}
                      <span className="text-[9px] font-mono text-slate-400 font-normal">
                        ({step.duration})
                      </span>
                    </h4>
                    <p className="text-slate-500 mt-0.5 leading-relaxed font-sans">{step.detail}</p>
                  </div>
                  <div className="text-right shrink-0">
                    <span className="text-[10px] font-mono text-cyan-600 bg-cyan-50 border border-cyan-100 px-1.5 py-0.5 rounded font-bold">
                      {step.status}
                    </span>
                    <p className="text-[9px] font-mono text-slate-400 mt-1 flex items-center gap-1">
                      <Clock className="w-3 h-3" /> {step.timestamp}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Card 7: Runtime / Fallback Status */}
        <div id="card-runtime-status" className="bg-slate-50 border border-slate-200 rounded-xl p-6 shadow-sm flex flex-col md:flex-row items-center justify-between gap-4">
          <div>
            <h3 className="text-sm font-bold text-slate-900">
              Telemetry Cache Integration Notice
            </h3>
            <p className="text-xs text-slate-500 mt-1 leading-relaxed max-w-2xl font-sans">
              The UI distinguishes backend-returned, cached, fallback, and locally visualized layers for review. 
              {selectedSite.name === 'Snowdon Grid Interconnect' || selectedSite.name.includes('Custom') 
                ? ' Snowdon or custom queries may use cached planning records or local visual fixtures where backend evidence is incomplete.' 
                : ' Infrastructure and utility layers should be verified against source evidence before dispatch.'}
            </p>
          </div>
          <button 
            onClick={() => {
              const element = document.getElementById('research-pack');
              if (element) {
                element.scrollIntoView({ behavior: 'smooth' });
              }
            }}
            className="px-5 py-2.5 bg-white hover:bg-slate-100 text-slate-800 font-bold text-xs uppercase tracking-wider rounded-lg border border-slate-300 shadow-sm transition shrink-0 flex items-center gap-1.5 cursor-pointer"
          >
            <Layers className="w-4 h-4 text-cyan-500" /> Save to Observation Pack
          </button>
        </div>

      </div>
    </section>
  );
};
