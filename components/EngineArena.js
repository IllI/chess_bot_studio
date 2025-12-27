import React, { useState, useEffect, useRef } from 'react';
import { Play, RotateCcw, Swords, Activity, Monitor, Zap, Cpu, Terminal, ChevronRight } from 'lucide-react';

const EngineArena = ({ config }) => {
  const [isSimulating, setIsSimulating] = useState(false);
  const [nodes, setNodes] = useState(0);
  const [logs, setLogs] = useState([]);
  const logEndRef = useRef(null);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const addLog = (msg) => {
    setLogs(prev => [...prev.slice(-15), msg]);
  };

  const startTest = () => {
    setIsSimulating(true);
    setLogs([]);
    setNodes(0);
    addLog("> UCI ok");
    addLog("> position startpos moves e2e4 e7e5");
    
    let n = 0;
    const interval = setInterval(() => {
      const increment = Math.floor(Math.random() * 50000);
      n += increment;
      setNodes(n);
      if (Math.random() > 0.8) {
        addLog(`info depth ${config.search_depth} nodes ${n} score cp 15 pv g1f3`);
      }
    }, 200);

    setTimeout(() => {
      clearInterval(interval);
      setIsSimulating(false);
      addLog("bestmove g1f3");
    }, 4000);
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
      <div className="lg:col-span-7">
        <div className="glass rounded-[48px] p-10 aspect-square flex flex-col items-center justify-center relative overflow-hidden bg-slate-900/40">
          <div className="text-center space-y-8 relative z-10">
            {isSimulating ? (
              <div className="flex flex-col items-center gap-6">
                <div className="relative">
                  <div className="w-32 h-32 rounded-full border-4 border-indigo-500/10 border-t-indigo-500 animate-spin" />
                  <Cpu className="absolute inset-0 m-auto text-indigo-400 opacity-50" size={40} />
                </div>
                <div className="mono text-4xl font-bold text-white tracking-tighter">{(nodes/1000).toFixed(1)}k Nodes</div>
                <p className="text-xs uppercase tracking-[0.2em] text-slate-500 font-bold">Search Horizon: Depth {config.search_depth}</p>
              </div>
            ) : (
              <div className="space-y-8">
                <Swords size={64} className="text-slate-700 mx-auto" />
                <button
                  onClick={startTest}
                  className="px-12 py-5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-[24px] font-bold text-xl flex items-center gap-3 shadow-xl shadow-indigo-600/20 transition-all active:scale-95"
                >
                  <Play size={20} fill="currentColor" /> Start Simulation
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
      <div className="lg:col-span-5 space-y-6">
        <div className="glass rounded-[32px] p-8 h-[400px] flex flex-col bg-black/20">
          <h3 className="font-bold text-sm uppercase tracking-widest mb-6 flex items-center gap-3 text-slate-400">
            <Terminal size={16} className="text-indigo-400" /> UCI Engine Output
          </h3>
          <div className="flex-1 overflow-y-auto space-y-1 mono text-[11px] text-slate-400 custom-scrollbar">
            {logs.length === 0 && <div className="italic text-slate-600">Waiting for engine start...</div>}
            {logs.map((log, i) => (
              <div key={i} className="flex gap-2">
                <span className="text-indigo-500 shrink-0 opacity-50">›</span>
                <span>{log}</span>
              </div>
            ))}
            <div ref={logEndRef} />
          </div>
        </div>
        
        <div className="glass rounded-[32px] p-6 bg-indigo-500/5 border-indigo-500/10">
           <div className="flex justify-between items-center">
              <span className="text-xs font-bold uppercase tracking-widest text-slate-500">Live Evaluation</span>
              <span className={`mono text-sm font-bold ${isSimulating ? 'text-indigo-400' : 'text-slate-600'}`}>
                {isSimulating ? '+0.15' : '0.00'}
              </span>
           </div>
        </div>
      </div>
    </div>
  );
};

export default EngineArena;