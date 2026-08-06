'use client';

import React, { useState } from 'react';
import { Activity, Upload, Database, Layers, Sparkles, FileText, CheckCircle2 } from 'lucide-react';
import StepTracker from '@/components/StepTracker';
import CustomControlPanel from '@/components/CustomControlPanel';
import ExtractionResult from '@/components/ExtractionResult';
import ArchiveManager from '@/components/ArchiveManager';
import { API_BASE_URL } from '@/config';

export default function Home() {
  const [activeMainTab, setActiveMainTab] = useState('scan'); // 'scan' | 'archive'

  // Form & Settings State
  const [docType, setDocType] = useState('auto');
  const [isConfidential, setIsConfidential] = useState(false);
  const [llmEngine, setLlmEngine] = useState('gemini');
  const [apiKey, setApiKey] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);

  // Streaming State
  const [currentStep, setCurrentStep] = useState(-1);
  const [isProcessing, setIsProcessing] = useState(false);
  const [resultData, setResultData] = useState(null);
  const [statusMessage, setStatusMessage] = useState('');
  const [refreshArchiveCount, setRefreshArchiveCount] = useState(0);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const handleStartProcess = async () => {
    if (!selectedFile) return;

    setIsProcessing(true);
    setCurrentStep(0);
    setResultData(null);
    setStatusMessage('Menginisialisasi upload dokumen...');

    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('doc_type', docType);
    formData.append('is_confidential', isConfidential ? 'true' : 'false');
    formData.append('llm_engine', llmEngine);
    formData.append('custom_api_key', apiKey);

    try {
      const response = await fetch(`${API_BASE_URL}/api/idp/process-stream`, {
        method: 'POST',
        body: formData,
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const jsonStr = line.replace('data: ', '').trim();
            if (jsonStr) {
              const eventData = JSON.parse(jsonStr);
              if (eventData.step !== undefined) {
                setCurrentStep(eventData.step);
                if (eventData.status) setStatusMessage(eventData.status);
              }

              if (eventData.step === 6 && eventData.data) {
                setResultData(eventData.data);
                setIsProcessing(false);
              }
            }
          }
        }
      }
    } catch (error) {
      console.error('Error streaming IDP process:', error);
      setIsProcessing(false);
      setStatusMessage('❌ Gagal memproses dokumen');
    }
  };

  return (
    <main className="min-h-screen bg-[#070c18] text-slate-100 p-6 font-sans">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header Dashboard */}
        <header className="flex flex-col md:flex-row items-start md:items-center justify-between border-b border-slate-800/80 pb-5">
          <div className="flex items-center gap-3">
            <div className="bg-emerald-500/10 p-2.5 rounded-xl border border-emerald-500/20">
              <Activity className="w-6 h-6 text-emerald-400" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-slate-100 flex items-center gap-2">
                Smart Document Organizer <span className="text-emerald-400 text-xs px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20">FastAPI + Next.js</span>
              </h1>
              <p className="text-xs text-slate-400">Digitalisasi Dokumen, PII Vault Protection & Ekstraksi Data Berbasis AI</p>
            </div>
          </div>

          {/* Navigation Tabs */}
          <div className="flex items-center gap-2 mt-4 md:mt-0 bg-[#0b1120] border border-slate-800 p-1.5 rounded-xl">
            <button
              onClick={() => setActiveMainTab('scan')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all ${activeMainTab === 'scan'
                ? 'bg-emerald-500 text-slate-950 shadow-[0_0_15px_rgba(52,211,153,0.3)]'
                : 'text-slate-400 hover:text-slate-200'
                }`}
            >
              <Layers className="w-4 h-4" />
              Tab 1: Scan & Ekstraksi
            </button>
            <button
              onClick={() => setActiveMainTab('archive')}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all ${activeMainTab === 'archive'
                ? 'bg-emerald-500 text-slate-950 shadow-[0_0_15px_rgba(52,211,153,0.3)]'
                : 'text-slate-400 hover:text-slate-200'
                }`}
            >
              <Database className="w-4 h-4" />
              Tab 2: Data Tersimpan & Excel
            </button>
          </div>
        </header>

        {activeMainTab === 'scan' ? (
          <>
            {/* Custom Control Panel */}
            <CustomControlPanel
              docType={docType}
              setDocType={setDocType}
              isConfidential={isConfidential}
              setIsConfidential={setIsConfidential}
              llmEngine={llmEngine}
              setLlmEngine={setLlmEngine}
              apiKey={apiKey}
              setApiKey={setApiKey}
            />

            {/* Drag & Drop Upload Zone */}
            <div className="border-2 border-dashed border-slate-800 hover:border-emerald-500/50 bg-[#0a101d] rounded-2xl p-8 text-center transition-all my-6">
              <input
                type="file"
                id="fileInput"
                className="hidden"
                onChange={handleFileChange}
                accept=".pdf,.png,.jpg,.jpeg,.webp"
              />
              <label htmlFor="fileInput" className="cursor-pointer flex flex-col items-center">
                <div className="w-14 h-14 bg-slate-900 border border-slate-800 rounded-2xl flex items-center justify-center text-slate-400 mb-3">
                  <Upload className="w-7 h-7 text-emerald-400" />
                </div>
                <p className="text-sm font-medium text-slate-200">
                  {selectedFile ? selectedFile.name : 'Tarik file ke sini, atau klik untuk pilih dokumendata'}
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  Mendukung PDF digital, scan PDF, JPG, PNG, WEBP (KTP, Paspor, Kartu Nama, Invoice, PO, NIB/NPWP)
                </p>
              </label>

              {selectedFile && !isProcessing && (
                <button
                  onClick={handleStartProcess}
                  className="mt-5 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs px-6 py-2.5 rounded-xl transition-all shadow-[0_0_20px_rgba(52,211,153,0.4)]"
                >
                  🚀 Mulai Ekstraksi IDP Dokumen
                </button>
              )}
            </div>

            {/* Stepper Progress Animation (Real-time stream lighting) */}
            {currentStep >= 0 && (
              <div className="space-y-2">
                <StepTracker currentStep={currentStep} isProcessing={isProcessing} />
                {statusMessage && (
                  <p className="text-center text-xs font-semibold text-emerald-400 animate-pulse">
                    Status: {statusMessage}
                  </p>
                )}
              </div>
            )}

            {/* Component Hasil Ekstraksi */}
            <ExtractionResult
              data={resultData}
              fileObj={selectedFile}
              onSaveSuccess={() => setRefreshArchiveCount((prev) => prev + 1)}
            />
          </>
        ) : (
          <ArchiveManager refreshTrigger={refreshArchiveCount} />
        )}
      </div>
    </main>
  );
}
