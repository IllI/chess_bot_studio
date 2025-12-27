import React, { useState } from 'react';
import { Brain, Settings2, PlayCircle, BookOpen, Layers, Sparkles, ChevronRight, Github } from 'lucide-react';
import TuningLab from './components/TuningLab.js';
import EngineArena from './components/EngineArena.js';
import LearningCenter from './components/LearningCenter.js';

const DEFAULT_CONFIG = {
  name: "New Recruit",
  piece_values: { pawn: 100, knight: 320, bishop: 330, rook: 500, queen: 900 },
  mobility_weight: 10,
  king_safety: 20,
  search_depth: 4
};

const App = () => {
  const [activeView, setActiveView] = useState('learn');
  const [config, setConfig] = useState(DEFAULT_CONFIG);

  return (
    <div className="min-h-screen flex flex-col bg-[#020617] text-slate-100">
      <nav className="glass sticky top-0 z-50 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="bg-indigo-600 p-2 rounded-xl shadow-lg shadow-indigo-600/30">
            <Brain className="text-white w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-white">ChessMaster <span className="text-indigo-400">Architect</span></h1>
            <p className="text-[10px] uppercase tracking-widest text-slate-500 font-bold">AI Training Environment</p>
          </div>
        </div>

        <div className="flex gap-2 bg-slate-900/50 p-1 rounded-2xl border border-white/5">
          <NavButton active={activeView === 'learn'} onClick={() => setActiveView('learn')} icon={<BookOpen size={18} />} label="Academy" />
          <NavButton active={activeView === 'tune'} onClick={() => setActiveView('tune')} icon={<Settings2 size={18} />} label="Lab" />
          <NavButton active={activeView === 'arena'} onClick={() => setActiveView('arena')} icon={<PlayCircle size={18} />} label="Arena" />
        </div>

        <div className="hidden md:flex items-center gap-4">
          <a href="https://github.com/IllI/chess_bot" target="_blank" className="text-slate-400 hover:text-white transition-colors">
            <Github size={20} />
          </a>
          <div className="h-8 w-[1px] bg-white/10" />
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-green-500/10 border border-green-500/20">
            <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
            <span className="text-[10px] font-bold text-green-500 uppercase">Engine Online</span>
          </div>
        </div>
      </nav>

      <main className="flex-1 p-6 max-w-7xl mx-auto w-full">
        {activeView === 'learn' && <LearningCenter onContinue={() => setActiveView('tune')} />}
        {activeView === 'tune' && <TuningLab config={config} setConfig={setConfig} />}
        {activeView === 'arena' && <EngineArena config={config} />}
      </main>

      <footer className="py-6 px-8 border-t border-white/5 bg-slate-950/50 text-slate-500 text-xs flex justify-between">
        <p>© 2024 Chess Bot Instructional Platform</p>
        <div className="flex gap-6">
          <button className="hover:text-slate-300">Privacy</button>
          <button className="hover:text-slate-300">Docs</button>
          <button className="hover:text-slate-300">API Status</button>
        </div>
      </footer>
    </div>
  );
};

const NavButton = ({ active, onClick, icon, label }) => (
  <button
    onClick={onClick}
    className={`flex items-center gap-2 px-4 py-2 rounded-xl transition-all duration-300 ${
      active 
        ? 'bg-indigo-600 text-white shadow-xl shadow-indigo-600/20' 
        : 'text-slate-400 hover:text-white hover:bg-white/5'
    }`}
  >
    {icon}
    <span className="text-sm font-semibold">{label}</span>
  </button>
);

export default App;