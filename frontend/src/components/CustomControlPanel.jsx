'use client';

import React from 'react';
import { FileText, Shield, Cpu, Lock, Unlock, Zap, CreditCard, User, Receipt, Package, FileCode, Sparkles } from 'lucide-react';

export default function CustomControlPanel({
  docType,
  setDocType,
  isConfidential,
  setIsConfidential,
  llmEngine,
  setLlmEngine,
  apiKey,
  setApiKey,
  onOpenSettings
}) {
  const docCategories = [
    { id: 'auto', name: '✨ Deteksi Otomatis oleh AI (Auto-Detect)', icon: Sparkles, color: 'text-emerald-400 font-bold' },
    { id: 'ktp', name: 'Kartu Tanda Penduduk (KTP)', icon: User, color: 'text-sky-400' },
    { id: 'passport', name: 'Paspor (Passport)', icon: CreditCard, color: 'text-indigo-400' },
    { id: 'business_card', name: 'Kartu Nama (Business Card)', icon: FileText, color: 'text-emerald-400' },
    { id: 'invoice', name: 'Struk / Invoice Pembayaran', icon: Receipt, color: 'text-amber-400' },
    { id: 'vendor', name: 'Dokumen Vendor & Pengadaan', icon: Package, color: 'text-purple-400' },
    { id: 'general', name: 'Dokumen Bisnis / Pajak / Sertifikat', icon: FileCode, color: 'text-pink-400' }
  ];

  return (
    <div className="bg-[#0b1120] border border-slate-800/80 rounded-2xl p-6 mb-6 shadow-xl">
      <div className="flex items-center justify-between gap-2 mb-4 border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <Cpu className="w-5 h-5 text-emerald-400" />
          <h2 className="text-base font-semibold text-slate-100">Panel Pengaturan Ekstraksi Smart Document Organizer</h2>
        </div>
        {onOpenSettings && (
          <button
            type="button"
            onClick={onOpenSettings}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-200 rounded-xl text-xs font-semibold transition-all"
          >
            <Sparkles className="w-3.5 h-3.5 text-emerald-400" />
            <span>⚙️ Pengaturan API Key</span>
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Category Selection */}
        <div>
          <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
            📁 Target Kategori Dokumen
          </label>
          <div className="grid grid-cols-1 gap-2">
            {docCategories.map((cat) => {
              const Icon = cat.icon;
              const isSelected = docType === cat.id;
              return (
                <button
                  key={cat.id}
                  type="button"
                  onClick={() => setDocType(cat.id)}
                  className={`flex items-center gap-3 p-3 rounded-xl border text-left text-xs font-medium transition-all ${isSelected
                    ? 'bg-emerald-950/40 border-emerald-500/80 text-emerald-300 shadow-[0_0_15px_rgba(16,185,129,0.15)]'
                    : 'bg-slate-900/60 border-slate-800 text-slate-400 hover:border-slate-700 hover:text-slate-200'
                    }`}
                >
                  <Icon className={`w-4 h-4 ${cat.color}`} />
                  <span>{cat.name}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Confidentiality & LLM Engine Settings */}
        <div className="flex flex-col justify-between">
          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
              🛡️ Mode Pemrosesan & Kerahasiaan Data
            </label>
            <div className="grid grid-cols-2 gap-3 mb-5">
              <button
                type="button"
                onClick={() => {
                  setIsConfidential(true);
                  setLlmEngine('local');
                }}
                className={`flex flex-col items-center p-3.5 rounded-xl border text-center transition-all ${(isConfidential || llmEngine === 'local' || llmEngine === 'ollama')
                  ? 'bg-emerald-950/60 border-emerald-400 text-emerald-300 shadow-[0_0_15px_rgba(52,211,153,0.2)]'
                  : 'bg-slate-900/60 border-slate-800 text-slate-400 hover:border-slate-700'
                  }`}
              >
                <Lock className="w-5 h-5 text-emerald-400 mb-1" />
                <span className="text-xs font-bold">🔒 Mode A: Rahasia & Privacy</span>
                <span className="text-[10px] text-slate-400 mt-0.5">100% Offline + PII Vault Protection</span>
              </button>

              <button
                type="button"
                onClick={() => {
                  setIsConfidential(false);
                  setLlmEngine('gemini');
                }}
                className={`flex flex-col items-center p-3.5 rounded-xl border text-center transition-all ${(!isConfidential && llmEngine !== 'local' && llmEngine !== 'ollama')
                  ? 'bg-amber-950/50 border-amber-400 text-amber-300 shadow-[0_0_15px_rgba(251,191,36,0.2)]'
                  : 'bg-slate-900/60 border-slate-800 text-slate-400 hover:border-slate-700'
                  }`}
              >
                <Zap className="w-5 h-5 text-amber-400 mb-1" />
                <span className="text-xs font-bold">⚡ Mode B: Direct Cloud Vision</span>
                <span className="text-[10px] text-slate-400 mt-0.5">Maksimal (Gemini / OpenAI / Claude)</span>
              </button>
            </div>

            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
              🧠 Pilihan Provider Vision AI Engine
            </label>

            {/* Mode A: Local Offline Engines (Row 1 Side-by-Side) */}
            <div className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider mb-1 flex items-center gap-1">
              <span>🔒 100% Local Offline Engines (Mode A)</span>
            </div>
            <div className="grid grid-cols-2 gap-2.5 mb-3">
              <button
                type="button"
                onClick={() => {
                  setLlmEngine('local');
                  setIsConfidential(true);
                }}
                className={`flex items-center gap-2 p-2.5 rounded-xl border text-xs font-medium transition-all ${llmEngine === 'local'
                  ? 'bg-emerald-950/60 border-emerald-400 text-emerald-300 shadow-[0_0_12px_rgba(52,211,153,0.2)]'
                  : 'bg-slate-900/60 border-slate-800 text-slate-400 hover:border-slate-700'
                  }`}
              >
                <Shield className="w-4 h-4 text-emerald-400 shrink-0" />
                <div className="text-left">
                  <div className="font-bold">Local Offline Parser</div>
                  <div className="text-[9px] text-slate-400">Rule-based (Super Cepat)</div>
                </div>
              </button>

              <button
                type="button"
                onClick={() => {
                  setLlmEngine('ollama');
                  setIsConfidential(true);
                }}
                className={`flex items-center gap-2 p-2.5 rounded-xl border text-xs font-medium transition-all ${llmEngine === 'ollama' || llmEngine === 'moondream'
                  ? 'bg-purple-950/60 border-purple-400 text-purple-300 shadow-[0_0_12px_rgba(192,132,252,0.2)]'
                  : 'bg-slate-900/60 border-slate-800 text-slate-400 hover:border-slate-700'
                  }`}
              >
                <Cpu className="w-4 h-4 text-purple-400 shrink-0" />
                <div className="text-left">
                  <div className="font-bold">Ollama Qwen2-VL</div>
                  <div className="text-[9px] text-purple-400 font-semibold">Local Vision AI (Detail & Slow)</div>
                </div>
              </button>
            </div>

            {/* Mode B: Cloud Vision AI Engines */}
            <div className="text-[10px] font-bold text-amber-400 uppercase tracking-wider mb-1 flex items-center gap-1">
              <span>🌐 Cloud Vision AI Engines (Mode B)</span>
            </div>
            <div className="grid grid-cols-3 gap-2">
              <button
                type="button"
                onClick={() => {
                  setLlmEngine('gemini');
                  setIsConfidential(false);
                }}
                className={`flex flex-col items-center p-2 rounded-xl border text-xs font-medium text-center transition-all ${llmEngine === 'gemini' || llmEngine === 'cloud_vision'
                  ? 'bg-indigo-950/60 border-indigo-400 text-indigo-300'
                  : 'bg-slate-900/60 border-slate-800 text-slate-400 hover:border-slate-700'
                  }`}
              >
                <Sparkles className="w-4 h-4 text-indigo-400 mb-0.5" />
                <div className="font-bold text-[11px]">Google Gemini</div>
                <div className="text-[9px] text-slate-400">Rekomendasi</div>
              </button>

              <button
                type="button"
                onClick={() => {
                  setLlmEngine('openai');
                  setIsConfidential(false);
                }}
                className={`flex flex-col items-center p-2 rounded-xl border text-xs font-medium text-center transition-all ${llmEngine === 'openai'
                  ? 'bg-sky-950/60 border-sky-400 text-sky-300'
                  : 'bg-slate-900/60 border-slate-800 text-slate-400 hover:border-slate-700'
                  }`}
              >
                <Zap className="w-4 h-4 text-sky-400 mb-0.5" />
                <div className="font-bold text-[11px]">OpenAI GPT-4o</div>
                <div className="text-[9px] text-slate-400">Presisi Tinggi</div>
              </button>

              <button
                type="button"
                onClick={() => {
                  setLlmEngine('claude');
                  setIsConfidential(false);
                }}
                className={`flex flex-col items-center p-2 rounded-xl border text-xs font-medium text-center transition-all ${llmEngine === 'claude'
                  ? 'bg-amber-950/60 border-amber-400 text-amber-300'
                  : 'bg-slate-900/60 border-slate-800 text-slate-400 hover:border-slate-700'
                  }`}
              >
                <Sparkles className="w-4 h-4 text-amber-400 mb-0.5" />
                <div className="font-bold text-[11px]">Claude 3.5</div>
                <div className="text-[9px] text-slate-400">Akurasi Visual</div>
              </button>
            </div>

            {/* Inline API Key Bar */}
            {llmEngine !== 'local' && llmEngine !== 'ollama' && llmEngine !== 'moondream' && (
              <div className="mt-3.5 pt-3 border-t border-slate-800/80 animate-in fade-in duration-200">
                <div className="flex items-center gap-2.5 bg-slate-900/90 border border-slate-800 focus-within:border-emerald-500/80 rounded-xl px-3 py-2 transition-all">
                  <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5 shrink-0">
                    🔑 API Key
                  </span>
                  <input
                    type="password"
                    value={apiKey || ''}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder="kosongkan untuk memakai key default server"
                    className="w-full bg-transparent text-xs text-slate-200 placeholder-slate-500 focus:outline-none font-mono tracking-tight"
                  />
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
