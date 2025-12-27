
import React from 'react';
import { BookOpen, Brain, Zap, Target, ArrowRight, ShieldCheck } from 'lucide-react';

interface LearningCenterProps {
  onStartTuning: () => void;
}

const LearningCenter: React.FC<LearningCenterProps> = ({ onStartTuning }) => {
  return (
    <div className="max-w-4xl mx-auto space-y-12 py-8 animate-in slide-in-from-bottom-4 duration-700">
      <div className="text-center space-y-4">
        <h2 className="text-4xl font-extrabold tracking-tight sm:text-5xl">
          Mastering the <span className="text-blue-500">Digital Gambit</span>
        </h2>
        <p className="text-xl text-slate-400 max-w-2xl mx-auto leading-relaxed">
          Learn how AI thinks about 64 squares. From hand-tuned math to deep neural networks, 
          discover the architecture of the world's strongest chess engines.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <LessonCard 
          icon={<Zap className="text-yellow-400" />}
          title="The Evaluation Function"
          description="The 'soul' of the engine. Learn how we convert a chess position into a single numerical score like +1.5 or -0.8."
          tags={["Heuristics", "Math"]}
        />
        <LessonCard 
          icon={<Target className="text-red-400" />}
          title="Search Trees & Minimax"
          description="How AI looks into the future. Discover why deeper isn't always better and how 'pruning' saves billions of calculations."
          tags={["Algorithms", "Efficiency"]}
        />
        <LessonCard 
          icon={<Brain className="text-indigo-400" />}
          title="Traditional vs Neural"
          description="Understand the shift from Stockfish (manual logic) to AlphaZero (deep learning). The evolution of digital intuition."
          tags={["Machine Learning", "History"]}
        />
        <LessonCard 
          icon={<ShieldCheck className="text-emerald-400" />}
          title="The Tuning Loop"
          description="Learn the process of A/B testing configurations to find the most efficient parameters for winning games."
          tags={["Optimization", "Data"]}
        />
      </div>

      <div className="bg-slate-900 border border-slate-800 p-8 rounded-3xl flex flex-col md:flex-row items-center justify-between gap-8 shadow-2xl relative overflow-hidden">
        <div className="absolute -left-12 top-0 bottom-0 w-24 bg-gradient-to-r from-blue-600/20 to-transparent blur-2xl"></div>
        <div className="space-y-2 relative">
          <h3 className="text-2xl font-bold">Ready to architect your own bot?</h3>
          <p className="text-slate-400">Step into the lab and start tuning weights for a Lichess-compatible engine.</p>
        </div>
        <button 
          onClick={onStartTuning}
          className="px-8 py-4 bg-blue-600 hover:bg-blue-500 text-white rounded-2xl font-bold transition-all transform hover:scale-105 flex items-center gap-3 shadow-xl shadow-blue-600/30 whitespace-nowrap"
        >
          Initialize Lab <ArrowRight size={20} />
        </button>
      </div>
    </div>
  );
};

const LessonCard: React.FC<{ icon: React.ReactNode, title: string, description: string, tags: string[] }> = ({ icon, title, description, tags }) => (
  <div className="bg-slate-900/50 border border-slate-800 p-6 rounded-2xl hover:border-slate-700 transition-all group hover:bg-slate-800/50">
    <div className="p-3 bg-slate-800 rounded-xl w-fit mb-4 group-hover:scale-110 transition-transform">
      {icon}
    </div>
    <h4 className="text-lg font-bold mb-2">{title}</h4>
    <p className="text-slate-400 text-sm leading-relaxed mb-4">{description}</p>
    <div className="flex gap-2">
      {tags.map(t => (
        <span key={t} className="text-[10px] uppercase font-bold tracking-wider text-slate-500 px-2 py-1 bg-slate-800 rounded-md border border-slate-700">
          {t}
        </span>
      ))}
    </div>
  </div>
);

export default LearningCenter;
