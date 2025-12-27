import React, { useState, useEffect } from 'react';
import { Sliders, Sparkles, Brain, Info, ChevronRight, Zap, RefreshCcw, Activity } from 'lucide-react';
import { BotConfig } from '../App';
import { GoogleGenAI } from "@google/genai";
import { motion } from 'framer-motion';

interface TuningLabProps {
  config: BotConfig;
  setConfig: (config: BotConfig) => void;
}

const TuningLab: React.FC<TuningLabProps> = ({ config, setConfig }) => {
  const [explanation, setExplanation] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const updateWeight = (category: keyof BotConfig, key: string, value: number) => {
    const newConfig = { ...config };
    if (typeof newConfig[category] === 'object') {
      (newConfig[category] as any)[key] = value;
    } else {
      (newConfig[category] as any) = value;
    }
    setConfig(newConfig);
  };

  const askCoach = async () => {
    setLoading(true);
    // Mandatory named parameter initialization using exclusively process.env.API_KEY
    const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });
    try {
      const response = await ai.models.generateContent({
        model: 'gemini-3-flash-preview',
        contents: `I am tuning my chess bot. Here are my current parameters: ${JSON.stringify(config)}. 
        Explain the "personality" of this bot in 3 bullet points. Focus on how it evaluates material vs positional advantages.`
      });
      // Correct property access for text response
      setExplanation(response.text);
    } catch (e) {
      setExplanation("Could not connect to the coach. Check your network.");
    } finally {
      setLoading(false);
    }
  };

  const getStyle = () => {
    const mobility = config.mobility_weight;
    if (mobility > 30) return "Hyper-Aggressive";
    if (mobility < 5) return "Solid & Defensive";
    return "Balanced";
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      {/* Left: Parameter Tuning */}
      <div className="lg:col-span-8 space-y-6">
        <div className="bg-slate-900 border border-slate-800 rounded-3xl p-8 shadow-xl">
          <div className="flex items-center justify-between mb-10">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-600/20 rounded-xl">
                <Sliders className="text-blue-400" size={24} />
              </div>
              <div>
                <h2 className="text-xl font-bold text-white">Neural Parameters</h2>
                <p className="text-xs text-slate-500 font-medium">Configure the core evaluation logic</p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-[10px] text-slate-500 uppercase font-bold mb-1">Inferred Style</p>
              <span className="px-3 py-1 bg-blue-500/10 text-blue-400 rounded-full text-xs font-bold border border-blue-500/20">
                {getStyle()}
              </span>
            </div>
          </div>

          <div className="space-y-12">
            {/* Piece Values */}
            <section>
              <div className="flex items-center gap-2 mb-6">
                <div className="w-1 h-4 bg-blue-500 rounded-full" />
                <h3 className="text-sm font-bold text-slate-300 uppercase tracking-widest">Material Values</h3>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-x-12 gap-y-8">
                {Object.entries(config.piece_values).map(([piece, value]) => (
                  <div key={piece} className="space-y-3 group">
                    <div className="flex justify-between items-end">
                      <span className="capitalize text-sm font-bold text-slate-200">{piece}</span>
                      <div className="flex items-baseline gap-1">
                        <span className="text-lg font-mono font-bold text-blue-400">{value}</span>
                        <span className="text-[10px] text-slate-600 font-bold uppercase tracking-tighter">pts</span>
                      </div>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="1200"
                      step="10"
                      value={value}
                      onChange={(e) => updateWeight('piece_values', piece, parseInt(e.target.value))}
                      className="w-full"
                    />
                  </div>
                ))}
              </div>
            </section>

            {/* Positional Values */}
            <section>
              <div className="flex items-center gap-2 mb-6">
                <div className="w-1 h-4 bg-indigo-500 rounded-full" />
                <h3 className="text-sm font-bold text-slate-300 uppercase tracking-widest">Positional Weights</h3>
              </div>
              <div className="space-y-10">
                <div className="space-y-3">
                  <div className="flex justify-between items-end">
                    <div className="space-y-0.5">
                      <p className="text-sm font-bold text-slate-200">Mobility Multiplier</p>
                      <p className="text-[10px] text-slate-500 font-medium">Prioritize square control and attacking potential.</p>
                    </div>
                    <span className="text-lg font-mono font-bold text-indigo-400">{config.mobility_weight}x</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="50"
                    step="0.5"
                    value={config.mobility_weight}
                    onChange={(e) => updateWeight('mobility_weight', '', parseFloat(e.target.value))}
                    className="w-full"
                  />
                </div>

                <div className="space-y-3">
                  <div className="flex justify-between items-end">
                    <div className="space-y-0.5">
                      <p className="text-sm font-bold text-slate-200">Search Horizon (Depth)</p>
                      <p className="text-[10px] text-slate-500 font-medium">Calculation depth. Higher depth is stronger but slower.</p>
                    </div>
                    <span className="text-lg font-mono font-bold text-emerald-400">{config.search_depth} plies</span>
                  </div>
                  <input
                    type="range"
                    min="1"
                    max="12"
                    step="1"
                    value={config.search_depth}
                    onChange={(e) => updateWeight('search_depth', '', parseInt(e.target.value))}
                    className="w-full"
                  />
                </div>
              </div>
            </section>
          </div>
        </div>
      </div>

      {/* Right: Insights & AI Coach */}
      <div className="lg:col-span-4 space-y-6">
        <div className="bg-gradient-to-br from-blue-900/20 to-slate-900 border border-blue-500/20 rounded-3xl p-6 shadow-2xl">
          <div className="flex items-center gap-3 mb-6">
            <Sparkles className="text-blue-400" />
            <h2 className="text-xl font-bold">AI Architect</h2>
          </div>

          <div className="space-y-4">
            <button
              onClick={askCoach}
              disabled={loading}
              className="w-full py-4 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 rounded-2xl font-bold transition-all flex items-center justify-center gap-3 shadow-xl shadow-blue-600/20"
            >
              {loading ? (
                <RefreshCcw className="animate-spin" size={18} />
              ) : (
                <>Analyze Configuration <ChevronRight size={18} /></>
              )}
            </button>

            {explanation ? (
              <motion.div 
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="p-5 bg-slate-950/80 border border-blue-500/20 rounded-2xl max-h-[400px] overflow-y-auto"
              >
                <div className="text-slate-200 text-sm leading-relaxed whitespace-pre-wrap">{explanation}</div>
              </motion.div>
            ) : (
              <div className="text-center p-8 bg-slate-950/50 rounded-2xl border border-dashed border-slate-800">
                <Brain className="mx-auto text-slate-700 mb-4" size={32} />
                <p className="text-xs text-slate-500 font-medium">Launch the AI Architect to see how your weight changes affect strategy.</p>
              </div>
            )}
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6">
          <div className="flex items-center gap-3 mb-6">
            <Activity className="text-emerald-400" />
            <h3 className="text-sm font-bold text-slate-300 uppercase tracking-widest text-white">System Analogy</h3>
          </div>
          <div className="space-y-4">
            <div className="bg-slate-950 p-4 rounded-2xl border border-slate-800">
               <div className="flex justify-between items-center mb-2">
                 <span className="text-[10px] font-bold text-slate-500 uppercase">Input Layer</span>
                 <span className="text-[10px] font-mono text-emerald-400">READY</span>
               </div>
               <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
                 <motion.div initial={{ width: 0 }} animate={{ width: '100%' }} className="h-full bg-emerald-500" />
               </div>
               <p className="text-[10px] text-slate-500 mt-2">Board squares and piece positions act as raw neurons.</p>
            </div>
            <div className="bg-slate-950 p-4 rounded-2xl border border-slate-800">
               <div className="flex justify-between items-center mb-2">
                 <span className="text-[10px] font-bold text-slate-500 uppercase">Weight Tuning</span>
                 <span className="text-[10px] font-mono text-blue-400">ACTIVE</span>
               </div>
               <div className="h-1 bg-slate-800 rounded-full overflow-hidden">
                 <motion.div initial={{ width: 0 }} animate={{ width: '70%' }} className="h-full bg-blue-500" />
               </div>
               <p className="text-[10px] text-slate-500 mt-2">Your sliders represent learned weights in a trained model.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TuningLab;