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
      n += Math.floor(Math.random() * 50000);
      setNodes(n);
      if (Math.random() > 0.8) addLog(`info depth ${config.search_depth} nodes ${n} score cp 15 pv g1f3`);
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
        <div className="glass rounded-[48px] p-10 aspect-square flex flex-col items-center justify-center relative overflow-hidden">
          <div className="text-center space-y-8 relative z-10">
            {isSimulating ? (
              <div className="flex flex-col items-center gap-6">
                <div className="w-24 h-24 rounded-full border-4 border-indigo-500/20 border-t-indigo-500 animate-spin" />
                <div className="mono text-4xl font-bold text-white">{(nodes/1000).toFixed(1)}k Nodes</div>
              </div>
            ) : (
              <button
                onClick={startTest}
                className="px-12 py-5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-[24px] font-bold text-xl flex items-center gap-3"
              >
                <Play size={20} fill="currentColor" /> Start Test
              </button>
            )}
          </div>
        </div>
      </div>
      <div className="lg:col-span-5 space-y-6">
        <div className="glass rounded-[32px] p-8 h-[400px] flex flex-col">
          <h3 className="font-bold text-sm uppercase tracking-widest mb-6 flex items-center gap-3 text-slate-400">
            <Terminal size={16} /> UCI Output
          </h3>
          <div className="flex-1 overflow-y-auto space-y-1 mono text-[10px] text-slate-400">
            {logs.map((log, i) => <div key={i}>> {log}</div>)}
            <div ref={logEndRef} />
          </div>
        </div>
      </div>
    </div>
  );
};

export default EngineArena;