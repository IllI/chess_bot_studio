import React, { useState, useEffect, useRef } from 'react';
import { Play, RotateCcw, Swords, Info, Activity, Monitor, ShieldCheck, Zap, Cpu, Terminal, ChevronRight } from 'lucide-react';
import { BotConfig } from '../App';
import { motion, AnimatePresence } from 'framer-motion';

interface EngineArenaProps {
  config: BotConfig;
}

const EngineArena: React.FC<EngineArenaProps> = ({ config }) => {
  const [isSimulating, setIsSimulating] = useState(false);
  const [nodes, setNodes] = useState(0);
  const [evalScore, setEvalScore] = useState(0.0);
  const [logs, setLogs] = useState<string[]>([]);
  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const addLog = (msg: string) => {
    setLogs(prev => [...prev.slice(-15), msg]);
  };

  const startTest = () => {
    setIsSimulating(true);
    setLogs([]);
    setNodes(0);
    setEvalScore(0.0);
    
    addLog("> UCI ok");
    addLog("> position startpos moves e2e4 e7e5");
    
    let n = 0;
    const interval = setInterval(() => {
      const increment = Math.floor(Math.random() * 80000);
      n += increment;
      setNodes(n);
      setEvalScore(prev => prev + (Math.random() - 0.5) * 0.15);
      
      if (Math.random() > 0.7) {
        addLog(`info depth ${config.search_depth} nodes ${n} score cp ${Math.floor(evalScore * 100)} pv g1f3 b8c6`);
      }
    }, 150);

    setTimeout(() => {
      clearInterval(interval);
      setIsSimulating(false);
      addLog(`bestmove g1f3 ponder b8c6`);
    }, 5000);
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
      <div className="lg:col-span-7">
        <div className="glass rounded-[48px] p-10 aspect-square flex flex-col items-center justify-center relative overflow-hidden group">
          <div className="absolute inset-0 shimmer opacity-30" />
          
          <div className="absolute top-10 left-10 flex gap-4">
             <div className="glass px-5 py-2 rounded-2xl flex items-center gap-3">
                <Monitor size={14} className="text-indigo-400" />
                <span className="text-xs font-black uppercase tracking-widest text-slate-400">Search: D{config.search_depth}</span>
             </div>
             <div className="glass px-5 py-2 rounded-2xl flex items-center gap-3">
                <Zap size={14} className="text-yellow-400" />
                <span className="text-xs font-black uppercase tracking-widest text-slate-400">{isSimulating ? 'Active' : 'Standby'}</span>
             </div>
          </div>

          <div className="relative z-10 text-center space-y-8">
            <AnimatePresence mode="wait">
              {isSimulating ? (
                <motion.div
                  key="sim"
                  initial={{ scale: 0.95, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  exit={{ scale: 1.05, opacity: 0 }}
                  className="flex flex-col items-center gap-8"
                >
                  <div className="relative">
                    <div className="w-40 h-40 rounded-full border-[6px] border-indigo-500/20 border-t-indigo-500 animate-spin" />
                    <Cpu className="absolute inset-0 m-auto text-indigo-400" size={56} />
                  </div>
                  <div className="space-y-1">
                    <p className="text-5xl font-black mono text-white tracking-tighter">{(nodes / 1000).toFixed(1)}k</p>
                    <p className="text-xs font-bold text-slate-500 uppercase tracking-[0.3em]">Evaluation Nodes</p>
                  </div>
                </motion.div>
              ) : (
                <motion.div
                  key="idle"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="space-y-8"
                >
                  <div className="p-12 rounded-[48px] bg-slate-900/30 border border-white/5 backdrop-blur-sm">
                    <Swords size={72} className="text-slate-800 mx-auto mb-6" />
                    <h3 className="text-3xl font-black mb-2">Arena Link</h3>
                    <p className="text-slate-500 text-sm max-w-xs mx-auto leading-relaxed">
                      Deploy your weights to a diagnostic game. See the heuristic scoring in real-time.
                    </p>
                  </div>
                  <button
                    onClick={startTest}
                    className="px-12 py-5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-[24px] font-bold text-xl shadow-2xl shadow-indigo-600/40 transition-all transform hover:scale-105 active:scale-95 flex items-center gap-3 mx-auto"
                  >
                    <Play size={20} fill="currentColor" /> Initialize Game
                  </button>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          <div className="absolute right-10 top-1/2 -translate-y-1/2 w-6 h-[60%] bg-slate-950/80 rounded-full overflow-hidden border border-white/10 p-1 shadow-inner">
            <motion.div
              animate={{ height: `${50 + (evalScore * 10)}%` }}
              className={`w-full rounded-full shadow-[0_0_15px_rgba(99,102,241,0.3)] transition-all duration-700 ${evalScore >= 0 ? 'bg-indigo-500' : 'bg-red-500'}`}
            />
          </div>
        </div>
      </div>

      <div className="lg:col-span-5 space-y-6">
        <div className="glass rounded-[32px] p-8 border-indigo-500/10 flex flex-col h-[400px]">
          <h3 className="font-bold text-sm uppercase tracking-widest mb-6 flex items-center gap-3 text-slate-400">
            <Terminal size={16} className="text-indigo-400" />
            UCI Thinking Console
          </h3>
          <div className="flex-1 overflow-y-auto space-y-2 mono text-[11px] leading-relaxed text-slate-400 custom-scrollbar">
            {logs.map((log, i) => (
              <div key={i} className={`flex items-start gap-2 ${log.startsWith('bestmove') ? 'text-emerald-400 font-bold' : ''}`}>
                <ChevronRight size={12} className="mt-0.5 opacity-50 shrink-0" />
                <span>{log}</span>
              </div>
            ))}
            <div ref={logEndRef} />
          </div>
        </div>

        <div className="glass rounded-[32px] p-8">
          <h3 className="font-bold mb-6 flex items-center gap-3">
            <Activity className="text-indigo-400" size={18} />
            Engine Performance
          </h3>
          <div className="space-y-4">
             <StatBox label="Search Velocity" value={`${isSimulating ? '512k' : '0'} NPS`} />
             <StatBox label="Eval Confidence" value={`${(94 - Math.abs(evalScore * 6)).toFixed(1)}%`} />
             <StatBox label="Memory Utilization" value="124MB" />
          </div>
        </div>

        <button 
          onClick={() => setLogs([])} 
          className="w-full py-4 glass hover:bg-white/5 text-slate-500 rounded-2xl font-bold flex items-center justify-center gap-3 transition-all border-dashed border-white/10 border-2 text-xs uppercase tracking-widest"
        >
          <RotateCcw size={14} /> Clear Diagnostic Logs
        </button>
      </div>
    </div>
  );
};

const StatBox: React.FC<{ label: string, value: string }> = ({ label, value }) => (
  <div className="flex justify-between items-center p-4 rounded-2xl bg-white/5 border border-white/5">
    <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">{label}</span>
    <span className="mono text-indigo-400 font-black text-sm">{value}</span>
  </div>
);

export default EngineArena;