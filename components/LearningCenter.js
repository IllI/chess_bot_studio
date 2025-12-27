import React from 'react';
import { BookOpen, Target, ArrowRight, Cpu, Network, Sparkles } from 'lucide-react';
import { motion } from 'framer-motion';

const LearningCenter = ({ onContinue }) => {
  return (
    <div className="max-w-5xl mx-auto py-12 space-y-20">
      <div className="text-center space-y-8">
        <motion.div 
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-bold uppercase tracking-widest mb-4"
        >
          <Sparkles size={14} /> AI Fundamentals 101
        </motion.div>
        <h1 className="text-6xl md:text-7xl font-black tracking-tight text-white leading-tight">
          Master the <span className="text-indigo-500">Logic</span> <br/> behind the Bot.
        </h1>
        <p className="text-xl text-slate-400 max-w-2xl mx-auto leading-relaxed">
          Chess AI is a perfect sandbox to understand how machines "see" complexity through mathematical scoring and tree search.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <ConceptCard icon={<Cpu className="text-indigo-400" />} title="Heuristics" description="Position evaluation logic: transforming a board state into a single numeric score." />
        <ConceptCard icon={<Network className="text-emerald-400" />} title="Search Tree" description="Minimax and Alpha-Beta: how computers look ahead into millions of future possibilities." />
        <ConceptCard icon={<Target className="text-red-400" />} title="Weight Tuning" description="Balancing priorities: Should the bot value raw material or positional mobility more?" />
      </div>

      <div className="glass rounded-[40px] p-12 flex flex-col md:flex-row items-center justify-between gap-12 bg-indigo-600/5 border-indigo-600/10 relative overflow-hidden">
        <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-500/5 blur-[100px] pointer-events-none" />
        <div className="space-y-4">
          <h3 className="text-3xl font-bold text-white">Ready to Architect?</h3>
          <p className="text-slate-400 text-lg">Initialize your configuration and enter the Tuning Lab.</p>
        </div>
        <button 
          onClick={onContinue}
          className="px-10 py-5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-3xl font-bold text-xl flex items-center gap-4 shadow-2xl shadow-indigo-600/30 transition-all active:scale-95 group"
        >
          Enter Lab <ArrowRight className="group-hover:translate-x-1 transition-transform" />
        </button>
      </div>
    </div>
  );
};

const ConceptCard = ({ icon, title, description }) => (
  <div className="glass p-8 rounded-[36px] bg-slate-900/30 border-white/5 hover:border-white/10 transition-all">
    <div className="p-4 bg-slate-950 rounded-2xl w-fit mb-6 shadow-inner">{icon}</div>
    <h4 className="text-lg font-bold mb-3 text-white">{title}</h4>
    <p className="text-slate-400 text-sm leading-relaxed">{description}</p>
  </div>
);

export default LearningCenter;