import React, { useState } from 'react';
import { Sliders, Sparkles, Brain, Info, ChevronRight, Zap, RefreshCcw, Activity, ShieldAlert, Target, InfoIcon } from 'lucide-react';
import { BotConfig } from '../App';
import { GoogleGenAI } from "@google/genai";
import { motion, AnimatePresence } from 'framer-motion';

interface TuningLabProps {
  config: BotConfig;
  setConfig: (config: BotConfig) => void;
}

const TuningLab: React.FC<TuningLabProps> = ({ config, setConfig }) => {
  const [aiReport, setAiReport] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  const updateWeight = (category: keyof BotConfig, key: string | null, value: number) => {
    const next = { ...config };
    if (key && typeof next[category] === 'object') {
      (next[category] as any)[key] = value;
    } else {
      (next[category] as any) = value;
    }
    setConfig(next);
  };

  const getAIAnalysis = async () => {
    setIsAnalyzing(true);
    const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });
    try {
      const prompt = `Act as a senior chess engine architect. Analyze this configuration: ${JSON.stringify(config)}. 
      - What is the bot's "personality"?
      - What are its likely tactical weaknesses?
      - Provide 3 short bullet points. Be technical but accessible.`;
      const response = await ai.models.generateContent({
        model: 'gemini-3-flash-preview',
        contents: prompt
      });
      setAiReport(response.text);
    } catch (e) {
      setAiReport("Consultation failed. Check architect uplink.");
    } finally {
      setIsAnalyzing(false);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
      <div className="lg:col-span-8 space-y-6">
        <div className="glass rounded-[40px] p-10 shadow-2xl relative overflow-hidden">
          <div className="absolute top-0 right-0 w-80 h-80 bg-indigo-600/5 blur-[120px] pointer-events-none" />
          
          <div className="flex items-center justify-between mb-12">
            <div className="space-y-1">
              <h2 className="text-3xl font-black">Heuristic Calibration</h2>
              <p className="text-slate-500 font-medium">Define the mathematical worth of every position.</p>
            </div>
            <div className="hidden md:block glass px-4 py-2 rounded-2xl border-indigo-500/20">
               <span className="text-[10px] font-bold uppercase tracking-[0.2em] text-indigo-400">V1.4 Stable</span>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-16">
            <section className="space-y-10">
              <div className="flex items-center gap-3 border-b border-white/5 pb-4">
                <Target className="text-indigo-400" size={18} />
                <h3 className="text-xs font-black uppercase tracking-widest text-slate-400">Static Piece Values</h3>
              </div>
              
              <div className="space-y-8">
                {Object.entries(config.piece_values).map(([piece, val]) => (
                  <div key={piece} className="space-y-3">
                    <div className="flex justify-between items-end">
                      <span className="text-sm font-bold text-slate-300 capitalize flex items-center gap-2">
                        {piece}
                      </span>
                      <span className="mono text-indigo-400 text-sm font-bold bg-indigo-500/10 px-2 py-0.5 rounded-lg">{val}</span>
                    </div>
                    <input
                      type="range" min="0" max="1500" step="10" value={val}
                      onChange={(e) => updateWeight('piece_values', piece, parseInt(e.target.value))}
                      className="w-full"
                    />
                  </div>
                ))}
              </div>
            </section>

            <section className="space-y-10">
              <div className="flex items-center gap-3 border-b border-white/5 pb-4">
                <ShieldAlert className="text-emerald-400" size={18} />
                <h3 className="text-xs font-black uppercase tracking-widest text-slate-400">Strategic Weighting</h3>
              </div>

              <div className="space-y-8">
                <div className="space-y-4">
                  <div className="flex justify-between text-sm font-bold text-slate-300">
                    <span className="flex items-center gap-2">Mobility <InfoIcon size={12} className="text-slate-600" /></span>
                    <span className="mono text-emerald-400">+{config.mobility_weight}%</span>
                  </div>
                  <input
                    type="range" min="0" max="100" step="1" value={config.mobility_weight}
                    onChange={(e) => updateWeight('mobility_weight', null, parseInt(e.target.value))}
                    className="w-full"
                  />
                </div>

                <div className="space-y-4">
                  <div className="flex justify-between text-sm font-bold text-slate-300">
                    <span>King Safety Penalty</span>
                    <span className="mono text-red-400">-{config.king_safety}</span>
                  </div>
                  <input
                    type="range" min="0" max="200" step="5" value={config.king_safety}
                    onChange={(e) => updateWeight('king_safety', null, parseInt(e.target.value))}
                    className="w-full accent-red-500"
                  />
                </div>

                <div className="p-6 bg-slate-900/50 rounded-3xl border border-white/5 mt-8">
                   <div className="flex justify-between text-sm font-bold text-slate-300 mb-4">
                    <span className="flex items-center gap-2">Search Depth <Zap size={12} className="text-yellow-400" /></span>
                    <span className="mono text-indigo-400">{config.search_depth} Layers</span>
                  </div>
                  <input
                    type="range" min="1" max="10" step="1" value={config.search_depth}
                    onChange={(e) => updateWeight('search_depth', null, parseInt(e.target.value))}
                    className="w-full"
                  />
                  <p className="text-[10px] text-slate-500 mt-4 leading-relaxed italic">
                    Higher values dramatically increase CPU load. Depth 4-6 is optimal for real-time play.
                  </p>
                </div>
              </div>
            </section>
          </div>
        </div>
      </div>

      <div className="lg:col-span-4 space-y-6">
        <div className="glass rounded-[32px] p-8 shadow-xl border-indigo-500/20 bg-indigo-500/5 flex flex-col h-fit">
          <div className="flex items-center gap-3 mb-6">
            <Sparkles className="text-indigo-400" size={20} />
            <h3 className="font-bold text-xl">Architect Insight</h3>
          </div>
          
          <p className="text-sm text-slate-400 leading-relaxed mb-8">
            The architect uses LLM reasoning to predict how your mathematical weights will manifest in actual chess tactics.
          </p>

          <button
            onClick={getAIAnalysis}
            disabled={isAnalyzing}
            className="w-full py-4 bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 rounded-2xl font-bold transition-all flex items-center justify-center gap-3 shadow-xl shadow-indigo-600/20"
          >
            {isAnalyzing ? <RefreshCcw className="animate-spin" size={18} /> : <>Generate Report <ChevronRight size={18} /></>}
          </button>

          <AnimatePresence>
            {aiReport && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                className="mt-8 overflow-hidden"
              >
                <div className="p-5 bg-slate-950/80 rounded-[24px] border border-white/5 text-sm leading-relaxed text-slate-300 prose prose-invert prose-sm">
                  {aiReport}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <div className="glass rounded-[32px] p-8">
          <h4 className="text-xs font-bold uppercase tracking-widest text-slate-500 mb-6 flex items-center gap-2">
            <Activity size={14} className="text-indigo-400" />
            Evaluation Pipeline
          </h4>
          <div className="space-y-6">
            <AnalogyStep label="Input Features" description="Fills UCI board buffers" progress={100} color="bg-indigo-500" />
            <AnalogyStep label="Weighting" description="Current calibration active" progress={100} color="bg-emerald-500" />
            <AnalogyStep label="Alpha-Beta" description="Pruning search branches" progress={40} color="bg-red-500" />
          </div>
        </div>
      </div>
    </div>
  );
};

const AnalogyStep: React.FC<{ label: string, description: string, progress: number, color: string }> = ({ label, description, progress, color }) => (
  <div className="space-y-2">
    <div className="flex justify-between items-end">
      <span className="text-xs font-bold text-slate-200">{label}</span>
      <span className="text-[10px] text-slate-500">{description}</span>
    </div>
    <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
      <motion.div
        initial={{ width: 0 }}
        animate={{ width: `${progress}%` }}
        className={`h-full ${color} shadow-[0_0_10px_rgba(255,255,255,0.1)]`}
      />
    </div>
  </div>
);

export default TuningLab;