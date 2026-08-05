'use client';

import React from 'react';
import {
  Upload,
  Scan,
  Shield,
  Bot,
  CheckCircle,
  FileSpreadsheet,
  Check,
  Loader2
} from 'lucide-react';

const STEPS = [
  { id: 0, label: 'Upload', icon: Upload },
  { id: 1, label: 'OCR Reading', icon: Scan },
  { id: 2, label: 'PII Masking', icon: Shield },
  { id: 3, label: 'LLM AI Parsing', icon: Bot },
  { id: 4, label: 'Validasi Vault', icon: CheckCircle },
  { id: 5, label: 'Format Excel', icon: FileSpreadsheet },
  { id: 6, label: 'Hasil Rekap', icon: Check },
];

export default function StepTracker({ currentStep, isProcessing }) {
  return (
    <div className="w-full bg-[#0b1120] border border-slate-800 rounded-2xl p-5 my-6 shadow-2xl">
      <div className="flex items-center justify-between relative px-2">
        {STEPS.map((step, index) => {
          const Icon = step.icon;

          const isCompleted = currentStep > index;
          const isCurrent = currentStep === index && isProcessing;
          const isPending = currentStep < index;

          return (
            <React.Fragment key={step.id}>
              {/* Step Node */}
              <div className="flex flex-col items-center z-10">
                <div
                  className={`
                    w-12 h-12 rounded-xl flex items-center justify-center transition-all duration-500 border
                    ${isCompleted
                      ? 'bg-emerald-950/90 border-emerald-400 text-emerald-400 shadow-[0_0_15px_rgba(52,211,153,0.3)]'
                      : isCurrent
                        ? 'bg-emerald-950 border-2 border-emerald-300 text-emerald-300 scale-110 shadow-[0_0_25px_rgba(52,211,153,0.6)] animate-pulse'
                        : 'bg-slate-900/80 border-slate-800 text-slate-600 opacity-40'
                    }
                  `}
                >
                  {isCurrent ? (
                    <Loader2 className="w-5 h-5 animate-spin text-emerald-300" />
                  ) : isCompleted ? (
                    <Check className="w-5 h-5 text-emerald-400 font-bold" />
                  ) : (
                    <Icon className="w-5 h-5 text-slate-500" />
                  )}
                </div>

                <span
                  className={`text-[11px] mt-2 font-medium transition-colors ${isCompleted || isCurrent ? 'text-emerald-400 font-bold' : 'text-slate-600 opacity-50'
                    }`}
                >
                  {step.label}
                </span>
              </div>

              {/* Connecting Progress Line */}
              {index < STEPS.length - 1 && (
                <div className="flex-1 h-[2px] mx-2 bg-slate-800/80 relative -mt-5">
                  <div
                    className="h-full bg-emerald-400 transition-all duration-500 ease-out shadow-[0_0_10px_rgba(52,211,153,0.8)]"
                    style={{
                      width: currentStep > index ? '100%' : '0%'
                    }}
                  />
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}