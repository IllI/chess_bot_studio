import React, { useState } from 'react';
import { Sparkles, ChevronRight, Zap, RefreshCcw, Activity, ShieldAlert, Target, InfoIcon } from 'lucide-react';
import { GoogleGenAI } from "@google/genai";
import { motion, AnimatePresence } from 'framer-motion';

const TuningLab = ({ config, setConfig }) => {
  const [aiReport, setAiReport] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  const updateWeight = (category, key, value) => {
    const next = { ...config };
    if (key && typeof next[category] === 'object') {
      next[category][key] = value;
    } else {
      next[category] = value;
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
      console.error(e);
      setAiReport("Consultation failed. Check architect uplink.");
    } finally {
      setIsAnalyzing(false);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
      <div className="lg:col-span-8 space-y-6">
        <div className="glass rounded-[40px] p-10 shadow-2xl relative overflow-hidden bg-slate-900/40">
          <div className="absolute top-0 right-0 w-80 h-80 bg-indigo-600/5 blur-[120px] pointer-events-none" />
          
          <div className="flex items-center justify-between mb-12">
            <div className="space-y-1">
              <h2 className="text-3xl font-black text-white">Heuristic Calibration</h2>
              <p className="text-slate-500 font-medium">Define the mathematical worth of every position.</p>
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
                      <span className="text-sm font-bold text-slate-300 capitalize">
                        {piece}
                      </span>
                      <span className="mono text-indigo-400 text-sm font-bold bg-indigo-500/10 px-2 py-0.5 rounded-lg">{val}</span>
                    </div>
                    <input
                      type="range" min="0" max="1500" step="10" value={val}
                      onChange={(e) => updateWeight('piece_values', piece, parseInt(e.target.value))}
                      className="w-full accent-indigo-500"
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
                    <span>Mobility</span>
                    <span className="mono text-emerald-400">+{config.mobility_weight}%</span>
                  </div>
                  <input
                    type="range" min="0" max="100" step="1" value={config.mobility_weight}
                    onChange={(e) => updateWeight('mobility_weight', null, parseInt(e.target.value))}
                    className="w-full accent-emerald-500"
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

                <div className="p-6 bg-slate-950/50 rounded-3xl border border-white/5 mt-8">
                  <div className="flex justify-between text-sm font-bold text-slate-300 mb-4">
                    <span>Search Depth</span>
                    <span className="mono text-indigo-400">{config.search_depth} Layers</span>
                  </div>
                  <input
                    type="range" min="1" max="10" step="1" value={config.search_depth}
                    onChange={(e) => updateWeight('search_depth', null, parseInt(e.target.value))}
                    className="w-full accent-indigo-400"
                  />
                </div>
              </div>
            </section>
          </div>
        </div>
      </div>

      <div className="lg:col-span-4 space-y-6">
        <div className="glass rounded-[32px] p-8 shadow-xl border-indigo-500/20 bg-indigo-500/5 flex flex-col h-fit">
          <div className="flex items-center gap-3 mb-6 text-white">
            <Sparkles className="text-indigo-400" size={20} />
            <h3 className="font-bold text-xl">Architect Insight</h3>
          </div>
          <button
            onClick={getAIAnalysis}
            disabled={isAnalyzing}
            className="w-full py-4 bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 rounded-2xl font-bold transition-all text-white flex items-center justify-center gap-3"
          >
            {isAnalyzing ? <RefreshCcw className="animate-spin" size={18} /> : <>Generate Report <ChevronRight size={18} /></>}
          </button>
          <AnimatePresence>
            {aiReport && (
              <motion.div 
                initial={{ opacity: 0, y: 10 }} 
                animate={{ opacity: 1, y: 0 }} 
                className="mt-6 text-sm text-slate-300 bg-black/30 p-4 rounded-xl border border-white/5"
              >
                {aiReport}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
};

export default TuningLab;