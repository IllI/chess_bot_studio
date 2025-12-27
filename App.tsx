
import React, { useState, useEffect } from 'react';
import { Brain, Cpu, BookOpen, ChevronRight, Info, Save, Play, RefreshCcw, Sparkles } from 'lucide-react';
import TuningLab from './components/TuningLab';
import LearningCenter from './components/LearningCenter';
import EngineArena from './components/EngineArena';

export type BotConfig = {
  piece_values: { [key: string]: number };
  mobility_weight: number;
  pawn_structure_bonus: { [key: string]: number };
  king_safety_penalty: { [key: string]: number };
  search_depth: number;
};

const INITIAL_CONFIG: BotConfig = {
  piece_values: { pawn: 100, knight: 320, bishop: 330, rook: 500, queen: 900 },
  mobility_weight: 10.0,
  pawn_structure_bonus: { passed_pawn: 50, doubled_pawn: -20, isolated_pawn: -15 },
  king_safety_penalty: { open_file: -30, king_in_center: -40 },
  search_depth: 4
};

const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'learn' | 'tune' | 'arena'>('learn');
  const [config, setConfig] = useState<BotConfig>(INITIAL_CONFIG);

  const handleUpdateConfig = (newConfig: BotConfig) => {
    setConfig(newConfig);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-900/50 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-600 rounded-lg">
              <Brain className="text-white w-6 h-6" />
            </div>
            <h1 className="text-xl font-bold tracking-tight bg-gradient-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent">
              ChessMaster AI Architect
            </h1>
          </div>
          <nav className="flex gap-1 bg-slate-800/50 p-1 rounded-xl border border-slate-700">
            <TabButton active={activeTab === 'learn'} onClick={() => setActiveTab('learn')} icon={<BookOpen size={18} />} label="Curriculum" />
            <TabButton active={activeTab === 'tune'} onClick={() => setActiveTab('tune')} icon={<Cpu size={18} />} label="Tuning Lab" />
            <TabButton active={activeTab === 'arena'} onClick={() => setActiveTab('arena')} icon={<Play size={18} />} label="Arena" />
          </nav>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 max-w-7xl mx-auto w-full p-6">
        {activeTab === 'learn' && <LearningCenter onStartTuning={() => setActiveTab('tune')} />}
        {activeTab === 'tune' && <TuningLab config={config} setConfig={handleUpdateConfig} />}
        {activeTab === 'arena' && <EngineArena config={config} />}
      </main>

      {/* Footer Status */}
      <footer className="border-t border-slate-800 p-4 bg-slate-900/80 text-xs text-slate-500 flex justify-between px-8">
        <div className="flex gap-4">
          <span>Model: Gemini 3 Flash (Tutor)</span>
          <span>Engine: Custom Heuristic V1.2</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
          Lichess API Connected
        </div>
      </footer>
    </div>
  );
};

const TabButton: React.FC<{ active: boolean, onClick: () => void, icon: React.ReactNode, label: string }> = ({ active, onClick, icon, label }) => (
  <button
    onClick={onClick}
    className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-all duration-200 ${
      active 
        ? 'bg-slate-700 text-white shadow-lg border border-slate-600' 
        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
    }`}
  >
    {icon}
    <span className="font-medium">{label}</span>
  </button>
);

export default App;
