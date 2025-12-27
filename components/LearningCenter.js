import React from 'react';
import { BookOpen, Target, ArrowRight, Cpu, Network } from 'lucide-react';
import { motion } from 'framer-motion';

const LearningCenter = ({ onContinue }) => {
  return (
    <div className="max-w-5xl mx-auto py-12 space-y-20">
      <div className="text-center space-y-8">
        <h1 className="text-6xl font-black tracking-tight text-white">
          Build a <span className="text-indigo-500">Chess AI</span>.
        </h1>
        <p className="text-xl text-slate-400 max-w-2xl mx-auto">
          Learn how chess engines process positions using mathematical heuristics and deep search trees.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <ConceptCard icon={<Cpu className="text-indigo-400" />} title="Heuristics" description="Position evaluation logic." />
        <ConceptCard icon={<Network className="text-emerald-400" />} title="Search" description="Explaining the search tree." />
        <ConceptCard icon={<Target className="text-red-400" />} title="Tuning" description="Balancing priorities." />
      </div>

      <div className="glass rounded-[40px] p-12 flex flex-col md:flex-row items-center justify-between gap-12">
        <div className="space-y-4">
          <h3 className="text-3xl font-bold text-white">Ready to Architect?</h3>
          <p className="text-slate-400">Configure your engine's brain in the Lab.</p>
        </div>
        <button 
          onClick={onContinue}
          className="px-10 py-5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-3xl font-bold text-xl flex items-center gap-4"
        >
          Enter Lab <ArrowRight />
        </button>
      </div>
    </div>
  );
};

const ConceptCard = ({ icon, title, description }) => (
  <div className="glass p-8 rounded-[36px]">
    <div className="p-4 bg-slate-900 rounded-2xl w-fit mb-6">{icon}</div>
    <h4 className="text-lg font-bold mb-3 text-white">{title}</h4>
    <p className="text-slate-400 text-sm">{description}</p>
  </div>
);

export default LearningCenter;