'use client';

import React, { useState } from 'react';
import { Database, CheckCircle, Eye, FileText, Lock, Code, Sparkles, Save } from 'lucide-react';

export default function ExtractionResult({ data, fileObj, onSaveSuccess }) {
  const [activeInspectorTab, setActiveInspectorTab] = useState('final');
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState('');

  if (!data) return null;

  const finalData = data.final_data || {};
  const isConfidential = data.is_confidential;

  const handleSaveToDb = async () => {
    if (!fileObj) {
      setSaveMessage('File tidak tersedia untuk disimpan');
      return;
    }
    setIsSaving(true);
    setSaveMessage('');

    try {
      const formData = new FormData();
      formData.append('file', fileObj);
      formData.append('doc_type', data.doc_type || 'general');
      formData.append('raw_text', data.raw_ocr || '');
      formData.append('masked_text', data.masked_text || '');
      formData.append('json_data', JSON.stringify(finalData));
      formData.append('is_confidential', data.is_confidential !== undefined ? data.is_confidential : true);
      formData.append('llm_engine', data.llm_engine || 'Local Rule Parser');
      formData.append('process_time_seconds', data.process_time_seconds || 0);

      const res = await fetch('http://localhost:8000/api/documents/save', {
        method: 'POST',
        body: formData
      });

      const result = await res.json();
      if (result.status === 'success') {
        setSaveMessage(`✅ Dokumen berhasil disimpan ke SQLite dengan ID #${result.id}!`);
        if (onSaveSuccess) onSaveSuccess();
      } else {
        setSaveMessage('❌ Gagal menyimpan dokumen');
      }
    } catch (err) {
      console.error('Error saving document:', err);
      setSaveMessage('❌ Terjadi kesalahan saat menyimpan ke database');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="bg-[#0b1120] border border-slate-800 rounded-2xl p-6 my-6 shadow-2xl space-y-6">
      {/* Header Result */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-emerald-400" />
            <h3 className="text-lg font-bold text-slate-100">Hasil Rekap Ekstraksi IDP Dokumen</h3>
          </div>
          <div className="flex flex-wrap items-center gap-2 mt-1 text-xs text-slate-400">
            <span>Dokumen: <strong className="text-emerald-300">{data.file_name}</strong></span>
            <span>| Kategori: <strong className="text-slate-200 uppercase">{data.doc_type}</strong></span>
            <span>| Modus: <strong className={data.llm_engine === 'ollama' || isConfidential ? 'text-emerald-400' : 'text-amber-400'}>
              {data.llm_engine === 'ollama' || isConfidential ? '🔒 Mode A (Offline Rahasia)' : '🌐 Mode B (Cloud Vision)'}
            </strong></span>
            {data.process_time_seconds !== undefined && (
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-sky-950/80 text-sky-300 border border-sky-600/40 shadow-[0_0_10px_rgba(56,189,248,0.2)]">
                ⏱️ Waktu Ekstraksi: <span className="font-mono text-sky-200">{data.process_time_seconds}s</span>
              </span>
            )}
          </div>
        </div>

        <button
          onClick={handleSaveToDb}
          disabled={isSaving}
          className="flex items-center gap-2 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs px-5 py-2.5 rounded-xl transition-all shadow-[0_0_15px_rgba(52,211,153,0.3)] disabled:opacity-50"
        >
          <Save className="w-4 h-4" />
          {isSaving ? 'Menyimpan...' : 'Simpan Dokumen ke Database'}
        </button>
      </div>

      {saveMessage && (
        <div className="p-3 bg-emerald-950/60 border border-emerald-500/40 rounded-xl text-xs text-emerald-300 font-medium">
          {saveMessage}
        </div>
      )}

      {/* Visual Structured Cards for Scalar Fields */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {Object.entries(finalData)
          .filter(([key]) => key !== 'items' && key !== 'item_name' && key !== 'unit_price')
          .map(([key, val]) => (
            <div key={key} className="bg-[#0f172a] border border-slate-800 p-3.5 rounded-xl">
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
                {key === 'quantity' ? 'JUMLAH BARANG' : key.replace(/_/g, ' ')}
              </span>
              <span className="text-xs font-semibold text-slate-100 break-words">
                {typeof val === 'object' ? JSON.stringify(val) : String(val || 'N/A')}
              </span>
            </div>
          ))}
      </div>

      {/* Render Items Table if present */}
      {Array.isArray(finalData.items) && finalData.items.length > 0 && (
        <div className="bg-[#0f172a] border border-slate-800 rounded-xl p-4 space-y-3">
          <h4 className="text-xs font-bold text-emerald-400 uppercase tracking-wider flex items-center gap-2">
            <Database className="w-4 h-4" />
            Tabel Rincian Barang / Supply Chain ({finalData.items.length} Item)
          </h4>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-900/80 text-slate-400 font-semibold border-b border-slate-800">
                <tr>
                  <th className="p-2.5">No</th>
                  <th className="p-2.5">SKU / Kode</th>
                  <th className="p-2.5">Deskripsi Item</th>
                  <th className="p-2.5">Qty</th>
                  <th className="p-2.5">Satuan</th>
                  <th className="p-2.5">Harga Satuan</th>
                  <th className="p-2.5 text-right">Total</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/50">
                {finalData.items.map((it, idx) => (
                  <tr key={idx} className="hover:bg-slate-900/40">
                    <td className="p-2.5 font-bold text-emerald-400">{it.no || idx + 1}</td>
                    <td className="p-2.5 font-mono text-slate-300">{it.sku || '-'}</td>
                    <td className="p-2.5 font-medium text-slate-100">{it.description || it.item_name || '-'}</td>
                    <td className="p-2.5">{it.qty || '1'}</td>
                    <td className="p-2.5">{it.unit || 'pcs'}</td>
                    <td className="p-2.5 font-mono">{it.unit_price || '0'}</td>
                    <td className="p-2.5 text-right font-mono font-bold text-emerald-300">{it.total || '0'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Interactive Step Inspector */}
      <div className="bg-[#070c18] border border-slate-800/80 rounded-xl p-4">
        <div className="flex items-center justify-between mb-3 border-b border-slate-800/80 pb-2">
          <span className="text-xs font-bold text-slate-300 flex items-center gap-2">
            <Eye className="w-4 h-4 text-emerald-400" />
            Inspect Payload Intermediate Data per Langkah:
          </span>
          <div className="flex gap-1">
            <button
              onClick={() => setActiveInspectorTab('ocr')}
              className={`px-3 py-1 text-[11px] font-medium rounded-lg transition-all ${activeInspectorTab === 'ocr' ? 'bg-emerald-500 text-slate-950 font-bold' : 'text-slate-400 hover:text-slate-200'
                }`}
            >
              1. Raw OCR
            </button>
            <button
              onClick={() => setActiveInspectorTab('mask')}
              className={`px-3 py-1 text-[11px] font-medium rounded-lg transition-all ${activeInspectorTab === 'mask' ? 'bg-emerald-500 text-slate-950 font-bold' : 'text-slate-400 hover:text-slate-200'
                }`}
            >
              2. Masked Text
            </button>
            <button
              onClick={() => setActiveInspectorTab('llm')}
              className={`px-3 py-1 text-[11px] font-medium rounded-lg transition-all ${activeInspectorTab === 'llm' ? 'bg-emerald-500 text-slate-950 font-bold' : 'text-slate-400 hover:text-slate-200'
                }`}
            >
              3. LLM JSON
            </button>
            <button
              onClick={() => setActiveInspectorTab('final')}
              className={`px-3 py-1 text-[11px] font-medium rounded-lg transition-all ${activeInspectorTab === 'final' ? 'bg-emerald-500 text-slate-950 font-bold' : 'text-slate-400 hover:text-slate-200'
                }`}
            >
              4. Unmasked Final
            </button>
          </div>
        </div>

        {/* Inspector Box Output */}
        {activeInspectorTab === 'ocr' && (
          <textarea
            readOnly
            className="w-full h-36 bg-[#0b1120] text-slate-300 font-mono text-xs p-3 rounded-lg border border-slate-800 resize-none focus:outline-none"
            value={data.raw_ocr || ''}
          />
        )}
        {activeInspectorTab === 'mask' && (
          <textarea
            readOnly
            className="w-full h-36 bg-[#0b1120] text-emerald-300 font-mono text-xs p-3 rounded-lg border border-slate-800 resize-none focus:outline-none"
            value={isConfidential ? data.masked_text || '' : '🔓 Dokumen Non-Rahasia: Tahap PII Masking dilewati (Bypassed).'}
          />
        )}
        {activeInspectorTab === 'llm' && (
          <pre className="w-full h-36 bg-[#0b1120] text-amber-300 font-mono text-xs p-3 rounded-lg border border-slate-800 overflow-auto">
            {JSON.stringify(data.llm_json, null, 2)}
          </pre>
        )}
        {activeInspectorTab === 'final' && (
          <pre className="w-full h-36 bg-[#0b1120] text-emerald-400 font-mono text-xs p-3 rounded-lg border border-slate-800 overflow-auto">
            {JSON.stringify(finalData, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}