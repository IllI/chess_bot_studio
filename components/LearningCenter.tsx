import React from 'react';
import { BookOpen, Brain, Zap, Target, ArrowRight, ShieldCheck, Cpu, Code2, Sparkles, Network } from 'lucide-react';
import { motion } from 'framer-motion';

interface LearningCenterProps {
  onContinue: () => void;
}

const LearningCenter: React.FC<LearningCenterProps> = ({ onContinue }) => {
  return (
    <div className="max-w-5xl mx-auto py-12 space-y-20">
      <div className="text-center space-y-8">
        <motion.div 
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-bold uppercase tracking-widest mb-4"
        >
          <Sparkles size={14} /> The Architect Lab Beta
        </motion.div>
        <h1 className="text-6xl md:text-7xl font-black tracking-tight leading-none bg-clip-text text-transparent bg-gradient-to-b from-white to-slate-500">
          Decode the <span className="text-indigo-500">Logic</span> <br/> of a Chess AI.
        </h1>
        <p className="text-xl text-slate-400 max-w-2xl mx-auto leading-relaxed">
          Before Deep Blue and AlphaZero, chess engines were tuned by hand. 
          Discover the mathematical heuristics that made digital grandmasters possible.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <ConceptCard 
          icon={<Cpu className="text-indigo-400" />}
          title="Heuristics"
          description="How to turn a 64-square board into a single mathematical score."
        />
        <ConceptCard 
          icon={<Network className="text-emerald-400" />}
          title="Search Depth"
          description="Explore the exponential growth of the Minimax search tree."
        />
        <ConceptCard 
          icon={<Target className="text-red-400" />}
          title="Tuning"
          description="Find the perfect balance between piece value and positional safety."
        />
      </div>

      <div className="glass rounded-[40px] p-12 flex flex-col md:flex-row items-center justify-between gap-12 border-indigo-500/20 shadow-2xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-600/10 blur-[80px] -z-10" />
        <div className="space-y-4">
          <h3 className="text-3xl font-bold">Ready to Build?</h3>
          <p className="text-slate-400 text-lg">Initialize your bot and prepare for the Arena.</p>
          <ul className="space-y-2">
            <li className="flex items-center gap-2 text-sm text-slate-300">
              <div className="w-1.5 h-1.5 rounded-full bg-indigo-500" /> Configure Piece Values
            </li>
            <li className="flex items-center gap-2 text-sm text-slate-300">
              <div className="w-1.5 h-1.5 rounded-full bg-indigo-500" /> Define Search Horizon
            </li>
          </ul>
        </div>
        <button 
          onClick={onContinue}
          className="px-10 py-5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-3xl font-bold text-xl shadow-2xl shadow-indigo-600/40 transition-all flex items-center gap-4 group active:scale-95"
        >
          Enter Tuning Lab <ArrowRight className="group-hover:translate-x-2 transition-transform" />
        </button>
      </div>
    </div>
  );
};

const ConceptCard: React.FC<{ icon: React.ReactNode, title: string, description: string }> = ({ icon, title, description }) => (
  <div className="glass p-8 rounded-[36px] hover:bg-white/5 transition-all group">
    <div className="p-4 bg-slate-900/80 rounded-2xl w-fit mb-6 shadow-inner">
      {icon}
    </div>
    <h4 className="text-lg font-bold mb-3">{title}</h4>
    <p className="text-slate-400 text-sm leading-relaxed">{description}</p>
  </div>
);

export default LearningCenter;