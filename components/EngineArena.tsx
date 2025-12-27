import React, { useState, useEffect } from 'react';
import { Play, RotateCcw, Swords, Info, Activity, Monitor, Shield, Target, Zap } from 'lucide-react';
import { BotConfig } from '../App';
import { motion, AnimatePresence } from 'framer-motion';

interface EngineArenaProps {
  config: BotConfig;
}

const EngineArena: React.FC<EngineArenaProps> = ({ config }) => {
  const [isSimulating, setIsSimulating] = useState(false);
  const [evalScore, setEvalScore] = useState(0.0);
  const [activeLogic, setActiveLogic] = useState<string | null>(null);

  const startSimulation = () => {
    setIsSimulating(true);
    let current = 0;
    const interval = setInterval(() => {
      current += (Math.random() - 0.5) * 0.8;
      setEvalScore(current);
    }, 300);
    setTimeout(() => {
      clearInterval(interval);
      setIsSimulating(false);
      setEvalScore(Math.random() > 0.5 ? 1.2 : -0.8);
    }, 4000);
  };

  // Mock board data for visual instruction
  const squares = Array.from({ length: 64 });
  
  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      {/* Board Visualizer */}
      <div className="lg:col-span-7 space-y-6">
        <div className="bg-slate-900 rounded-3xl border border-slate-800 p-8 shadow-2xl relative overflow-hidden">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <Monitor className="text-blue-400" size={20} />
              <h2 className="text-lg font-bold">Neural Evaluation Layer</h2>
            </div>
            <div className="flex gap-2">
              <span className={`px-3 py-1 rounded-full text-[10px] font-bold tracking-widest border transition-colors ${isSimulating ? 'bg-blue-500/20 border-blue-500 text-blue-400 animate-pulse' : 'bg-slate-800 border-slate-700 text-slate-500'}`}>
                {isSimulating ? 'LIVE CALCULATION' : 'STANDBY'}
              </span>
            </div>
          </div>

          <div className="aspect-square w-full max-w-[500px] mx-auto grid grid-cols-8 grid-rows-8 gap-1 relative border-4 border-slate-800 rounded-lg p-1 bg-slate-950">
            {squares.map((_, i) => {
              const row = Math.floor(i / 8);
              const col = i % 8;
              const isDark = (row + col) % 2 === 1;
              const intensity = isSimulating ? Math.random() : 0.1;
              
              return (
                <div 
                  key={i} 
                  className={`relative flex items-center justify-center transition-colors duration-500 ${isDark ? 'bg-slate-900' : 'bg-slate-800'}`}
                >
                  <AnimatePresence>
                    {isSimulating && (
                      <motion.div 
                        initial={{ opacity: 0 }}
                        animate={{ opacity: intensity * 0.4 }}
                        exit={{ opacity: 0 }}
                        className="absolute inset-0 bg-blue-500"
                      />
                    )}
                  </AnimatePresence>
                </div>
              );
            })}
            
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
               <AnimatePresence>
                 {!isSimulating && evalScore === 0 && (
                   <motion.div 
                     initial={{ scale: 0.9, opacity: 0 }}
                     animate={{ scale: 1, opacity: 1 }}
                     className="bg-slate-900/90 backdrop-blur-md p-6 rounded-2xl border border-slate-700 text-center pointer-events-auto"
                   >
                     <Swords size={48} className="mx-auto text-slate-600 mb-4" />
                     <p className="text-slate-400 text-sm mb-4">The arena is ready. Test your tuned weights.</p>
                     <button 
                       onClick={startSimulation}
                       className="px-6 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-full font-bold transition-all"
                     >
                       Launch Simulation
                     </button>
                   </motion.div>
                 )}
               </AnimatePresence>
            </div>
          </div>

          <div className="mt-8 grid grid-cols-3 gap-4">
             <div className="bg-slate-950/50 p-4 rounded-2xl border border-slate-800">
                <p className="text-[10px] text-slate-500 uppercase font-bold mb-1">Current Advantage</p>
                <p className={`text-2xl font-mono font-bold ${evalScore >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                  {evalScore > 0 ? '+' : ''}{evalScore.toFixed(2)}
                </p>
             </div>
             <div className="bg-slate-950/50 p-4 rounded-2xl border border-slate-800 col-span-2">
                <p className="text-[10px] text-slate-500 uppercase font-bold mb-1">Bot Decision Path</p>
                <div className="flex gap-2 mt-2">
                   {['Center Control', 'King Safety', 'Material Win'].map((p, idx) => (
                     <span key={p} className={`text-[9px] px-2 py-1 rounded bg-slate-800 border border-slate-700 text-slate-300 transition-opacity ${isSimulating && idx !== (Math.floor(Date.now()/500)%3) ? 'opacity-30' : 'opacity-100'}`}>
                       {p}
                     </span>
                   ))}
                </div>
             </div>
          </div>
        </div>
      </div>

      {/* Engine Metrics & Instructional Feedback */}
      <div className="lg:col-span-5 space-y-6">
        <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 shadow-xl flex flex-col h-full">
          <div className="flex items-center gap-3 mb-8">
            <Activity className="text-blue-400" />
            <h2 className="text-xl font-bold">Heuristic Analytics</h2>
          </div>

          <div className="space-y-4 flex-1">
             <MetricRow 
                label="Nodes / Sec" 
                sub="Computational speed"
                value={isSimulating ? "1.2M" : "0"} 
                icon={<Zap size={16} className="text-yellow-500"/>} 
             />
             <MetricRow 
                label="Search Depth" 
                sub="Future moves analyzed"
                value={`${config.search_depth} plies`} 
                icon={<Target size={16} className="text-red-500"/>} 
             />
             <MetricRow 
                label="King Safety" 
                sub="Current vulnerability"
                value={isSimulating ? "EXCELLENT" : "CALCULATING"} 
                icon={<Shield size={16} className="text-emerald-500"/>} 
             />
          </div>

          <div className="mt-8 space-y-4">
             <div className="p-4 rounded-2xl bg-blue-500/5 border border-blue-500/10">
                <div className="flex items-start gap-3">
                   <Info className="text-blue-400 shrink-0 mt-0.5" size={16} />
                   <p className="text-xs text-slate-400 leading-relaxed">
                     <span className="text-blue-300 font-bold">Instruction:</span> The bot is currently using your 
                     <span className="text-white"> Mobility Weight ({config.mobility_weight})</span> to prioritize 
                     active squares over defensive positions.
                   </p>
                </div>
             </div>

             <div className="flex gap-3">
               <button 
                 onClick={() => setEvalScore(0)}
                 className="flex-1 py-3 bg-slate-800 hover:bg-slate-700 rounded-xl text-xs font-bold transition-colors flex items-center justify-center gap-2"
               >
                 <RotateCcw size={16} /> Reset State
               </button>
               <button 
                 onClick={startSimulation}
                 disabled={isSimulating}
                 className="flex-1 py-3 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-2 shadow-lg shadow-blue-600/20"
               >
                 <Play size={16} /> Run Test
               </button>
             </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const MetricRow: React.FC<{ label: string, sub: string, value: string, icon: React.ReactNode }> = ({ label, sub, value, icon }) => (
  <div className="p-4 rounded-2xl bg-slate-950 border border-slate-800 hover:border-slate-700 transition-colors">
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="p-2 bg-slate-900 rounded-lg">{icon}</div>
        <div>
          <p className="text-sm font-bold text-white leading-none mb-1">{label}</p>
          <p className="text-[10px] text-slate-500 font-medium">{sub}</p>
        </div>
      </div>
      <span className="font-mono text-blue-400 font-bold tracking-tight">{value}</span>
    </div>
  </div>
);

export default EngineArena;