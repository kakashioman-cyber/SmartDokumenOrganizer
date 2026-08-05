'use client';

import React, { useState, useEffect } from 'react';
import { Database, Search, Filter, Trash2, Download, RefreshCw, FileSpreadsheet, ChevronDown, ChevronUp, Eye, EyeOff, FileText, Code, CheckCircle2 } from 'lucide-react';

export default function ArchiveManager({ refreshTrigger }) {
  const [documents, setDocuments] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [isLoading, setIsLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState('');
  const [expandedDocId, setExpandedDocId] = useState(null);

  const fetchDocuments = async () => {
    setIsLoading(true);
    try {
      let url = 'http://localhost:8000/api/documents';
      const params = new URLSearchParams();
      if (searchQuery) params.append('search', searchQuery);
      if (selectedCategory && selectedCategory !== 'All') params.append('doc_type', selectedCategory);
      if (params.toString()) url += `?${params.toString()}`;

      const res = await fetch(url);
      const data = await res.json();
      setDocuments(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Error fetching documents:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, [searchQuery, selectedCategory, refreshTrigger]);

  const handleDeleteDoc = async (id, e) => {
    if (e) e.stopPropagation();
    if (!confirm(`Hapus dokumen #${id}?`)) return;
    try {
      const res = await fetch(`http://localhost:8000/api/documents/${id}`, { method: 'DELETE' });
      if (res.ok) {
        setStatusMessage(`Dokumen #${id} berhasil dihapus.`);
        if (expandedDocId === id) setExpandedDocId(null);
        fetchDocuments();
      }
    } catch (err) {
      console.error('Error deleting document:', err);
    }
  };

  const handleClearAll = async () => {
    if (!confirm('⚠️ Apakah Anda yakin ingin menghapus SEMUA data dokumen tersimpan dan me-reset ID dari #1?')) return;
    try {
      const res = await fetch('http://localhost:8000/api/documents/clear-all', { method: 'DELETE' });
      if (res.ok) {
        setStatusMessage('🗑️ Semua data dokumen berhasil dibersihkan & ID di-reset ke #1.');
        setExpandedDocId(null);
        fetchDocuments();
      }
    } catch (err) {
      console.error('Error clearing documents:', err);
    }
  };

  const handleDownloadExcel = () => {
    const downloadUrl = `http://localhost:8000/api/export/excel?doc_type=${selectedCategory}`;
    window.open(downloadUrl, '_blank');
  };

  const toggleExpandDoc = (id) => {
    setExpandedDocId(expandedDocId === id ? null : id);
  };

  const categoryBadges = {
    ktp: { label: '🪪 KTP', color: 'bg-sky-950/60 text-sky-300 border-sky-500/40' },
    id_card: { label: '🪪 KTP', color: 'bg-sky-950/60 text-sky-300 border-sky-500/40' },
    passport: { label: 'Passport', color: 'bg-indigo-950/60 text-indigo-300 border-indigo-500/40' },
    business_card: { label: '🪪 Kartu Nama', color: 'bg-emerald-950/60 text-emerald-300 border-emerald-500/40' },
    invoice: { label: '🧾 Invoice / Struk', color: 'bg-amber-950/60 text-amber-300 border-amber-500/40' },
    vendor: { label: '📦 Vendor / PO', color: 'bg-purple-950/60 text-purple-300 border-purple-500/40' },
    vendor_doc: { label: '📦 Vendor / PO', color: 'bg-purple-950/60 text-purple-300 border-purple-500/40' },
    po: { label: '📦 Vendor / PO', color: 'bg-purple-950/60 text-purple-300 border-purple-500/40' },
    general: { label: '📄 Bisnis / Pajak', color: 'bg-pink-950/60 text-pink-300 border-pink-500/40' }
  };

  return (
    <div className="bg-[#0b1120] border border-slate-800 rounded-2xl p-6 shadow-xl space-y-6">
      {/* Header & Main Controls */}
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <Database className="w-5 h-5 text-emerald-400" />
            <h3 className="text-lg font-bold text-slate-100">Data Tersimpan & Manajemen Arsip Document</h3>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Database SQLite Local (`data/organizer.db`) | Total Dokumen: <span className="text-emerald-400 font-bold">{documents.length}</span>
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <button
            onClick={handleDownloadExcel}
            className="flex items-center gap-2 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs px-4 py-2.5 rounded-xl transition-all shadow-[0_0_15px_rgba(52,211,153,0.3)]"
          >
            <FileSpreadsheet className="w-4 h-4" />
            Download Excel Multi-Sheet (.xlsx)
          </button>

          <button
            onClick={handleClearAll}
            className="flex items-center gap-2 bg-rose-950/60 hover:bg-rose-900 border border-rose-600/50 text-rose-300 font-semibold text-xs px-4 py-2.5 rounded-xl transition-all"
          >
            <Trash2 className="w-4 h-4 text-rose-400" />
            Hapus Semua Data (Reset ke #1)
          </button>
        </div>
      </div>

      {statusMessage && (
        <div className="p-3 bg-emerald-950/60 border border-emerald-500/40 rounded-xl text-xs text-emerald-300">
          {statusMessage}
        </div>
      )}

      {/* Filter & Search Controls */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="relative">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
          <input
            type="text"
            placeholder="Cari berdasarkan nama, NIK, PO, vendor..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-[#070c18] border border-slate-800 rounded-xl pl-9 pr-3 py-2 text-xs text-slate-200 focus:border-emerald-500 focus:outline-none"
          />
        </div>

        <div>
          <select
            value={selectedCategory}
            onChange={(e) => setSelectedCategory(e.target.value)}
            className="w-full bg-[#070c18] border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:border-emerald-500 focus:outline-none"
          >
            <option value="All">🌐 Semua Kategori Dokumen</option>
            <option value="ktp">🪪 Kartu Tanda Penduduk (KTP)</option>
            <option value="passport">🛂 Paspor (Passport)</option>
            <option value="business_card">🪪 Kartu Nama (Business Card)</option>
            <option value="invoice">🧾 Struk / Invoice Pembayaran</option>
            <option value="vendor">📦 Dokumen Vendor & Pengadaan</option>
            <option value="general">📄 Dokumen Bisnis / Pajak / Sertifikat</option>
          </select>
        </div>

        <div className="flex justify-end">
          <button
            onClick={fetchDocuments}
            className="flex items-center gap-2 bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 font-medium text-xs px-4 py-2 rounded-xl transition-all"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh Data
          </button>
        </div>
      </div>

      {/* Table of Documents */}
      <div className="border border-slate-800 rounded-xl overflow-hidden">
        <table className="w-full text-left text-xs text-slate-300">
          <thead className="bg-[#070c18] text-slate-400 uppercase font-semibold text-[10px] tracking-wider border-b border-slate-800">
            <tr>
              <th className="p-3">ID</th>
              <th className="p-3">Nama File</th>
              <th className="p-3">Kategori</th>
              <th className="p-3">Entitas Utama (NIK / No. Inv / PO / Vendor)</th>
              <th className="p-3">Tanggal Unggah</th>
              <th className="p-3 text-right">Aksi / Detail</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 bg-[#0b1120]">
            {documents.length === 0 ? (
              <tr>
                <td colSpan="6" className="p-8 text-center text-slate-500 italic">
                  Belum ada dokumen tersimpan di kategori ini.
                </td>
              </tr>
            ) : (
              documents.map((doc) => {
                const j = doc.json_data || {};
                const dtType = doc.type.toLowerCase();
                const isExpanded = expandedDocId === doc.id;

                let mainEntity = 'N/A';
                if (dtType === 'ktp' || dtType === 'id_card') {
                  mainEntity = `NIK: ${j.id_number || 'N/A'} — ${j.full_name || ''}`;
                } else if (dtType === 'passport' || dtType === 'paspor') {
                  mainEntity = `Paspor: ${j.id_number || 'N/A'} (${j.full_name || ''})`;
                } else if (dtType === 'vendor' || dtType === 'vendor_doc' || dtType === 'po') {
                  const poNo = j.po_number && j.po_number !== 'N/A' ? `PO: ${j.po_number}` : (j.invoice_number && j.invoice_number !== 'N/A' ? `INV: ${j.invoice_number}` : 'Dokumen Vendor');
                  const vName = j.vendor_name && j.vendor_name !== 'N/A' ? j.vendor_name : (j.customer_name || 'N/A');
                  mainEntity = `${poNo} — ${vName}`;
                } else if (dtType === 'invoice' || dtType === 'receipt') {
                  const invNo = j.invoice_number && j.invoice_number !== 'N/A' ? `INV: ${j.invoice_number}` : (j.po_number && j.po_number !== 'N/A' ? `PO: ${j.po_number}` : 'Invoice');
                  const vName = j.vendor_name && j.vendor_name !== 'N/A' ? j.vendor_name : (j.customer_name || 'N/A');
                  mainEntity = `${invNo} — ${vName}`;
                } else if (dtType === 'business_card') {
                  mainEntity = `${j.contact_name || 'N/A'} — ${j.company_name || ''}`;
                } else {
                  const invNo = j.invoice_number;
                  const custName = j.customer_name || j.vendor_name;
                  if (invNo || custName) {
                    mainEntity = `${invNo || 'N/A'} - ${custName || 'N/A'}`;
                  } else {
                    const title = j.document_title && !j.document_title.includes('--- Page') ? j.document_title : '';
                    mainEntity = title || j.tax_id_npwp || j.business_license_nib || 'Dokumen Bisnis';
                  }
                }

                const badge = categoryBadges[dtType] || {
                  label: `📄 ${doc.type.toUpperCase()}`,
                  color: 'bg-slate-800 text-slate-300 border-slate-700'
                };

                return (
                  <React.Fragment key={doc.id}>
                    <tr
                      onClick={() => toggleExpandDoc(doc.id)}
                      className={`cursor-pointer transition-colors ${isExpanded ? 'bg-emerald-950/30' : 'hover:bg-slate-900/50'
                        }`}
                    >
                      <td className="p-3 font-mono text-emerald-400 font-bold">#{doc.id}</td>
                      <td className="p-3 font-medium text-slate-200">
                        <div>{doc.name}</div>
                        <div className="flex flex-wrap items-center gap-1.5 mt-1">
                          <span className={`px-1.5 py-0.5 rounded text-[9px] font-semibold border ${doc.is_confidential !== false || doc.llm_engine === 'ollama' ? 'bg-emerald-950/80 text-emerald-400 border-emerald-600/40' : 'bg-amber-950/80 text-amber-400 border-amber-600/40'}`}>
                            {doc.is_confidential !== false || doc.llm_engine === 'ollama' ? '🔒 Mode A (Offline Rahasia)' : '🌐 Mode B (Cloud Vision)'}
                          </span>
                          {doc.process_time_seconds !== undefined && doc.process_time_seconds !== null && Number(doc.process_time_seconds) > 0 ? (
                            <span className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-sky-950/80 text-sky-300 border border-sky-600/40">
                              ⏱️ {Number(doc.process_time_seconds).toFixed(2)}s
                            </span>
                          ) : null}
                          <span className="px-1.5 py-0.5 rounded text-[9px] font-semibold bg-slate-800 text-slate-300 border border-slate-700">
                            🤖 {doc.llm_engine || 'Local Rule Parser'}
                          </span>
                        </div>
                      </td>
                      <td className="p-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${badge.color}`}>
                          {badge.label}
                        </span>
                      </td>
                      <td className="p-3 text-emerald-300 font-semibold">{mainEntity}</td>
                      <td className="p-3 text-slate-400 text-[11px]">{doc.created_at}</td>
                      <td className="p-3 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              toggleExpandDoc(doc.id);
                            }}
                            className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-medium border transition-all ${isExpanded
                              ? 'bg-emerald-900/50 border-emerald-500 text-emerald-300'
                              : 'bg-slate-800 border-slate-700 text-slate-300 hover:border-slate-600'
                              }`}
                          >
                            {isExpanded ? (
                              <>
                                <ChevronUp className="w-3.5 h-3.5" />
                                Sembunyikan
                              </>
                            ) : (
                              <>
                                <Eye className="w-3.5 h-3.5" />
                                Lihat Detail
                              </>
                            )}
                          </button>

                          <button
                            onClick={(e) => handleDeleteDoc(doc.id, e)}
                            className="p-1.5 text-rose-400 hover:text-rose-300 hover:bg-rose-950/40 rounded-lg transition-all"
                            title="Hapus Dokumen"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>

                    {/* Expandable Accordion View */}
                    {isExpanded && (
                      <tr className="bg-[#070c18]/90 border-t border-b border-emerald-500/20">
                        <td colSpan="6" className="p-5">
                          <div className="space-y-4">
                            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                              <div className="flex items-center gap-3">
                                <span className="text-xs font-bold text-emerald-400 flex items-center gap-1.5">
                                  <CheckCircle2 className="w-4 h-4" /> Hasil Rekap Unmasked Final Dokumen #{doc.id}
                                </span>
                                <span className="text-[10px] font-semibold text-slate-300 bg-slate-900 border border-slate-700 px-2 py-0.5 rounded-md">
                                  Modus: {doc.is_confidential !== false ? '🔒 Rahasia (Masked PII)' : '🔓 Umum (Direct)'}
                                </span>
                                <span className="text-[10px] font-semibold text-slate-300 bg-slate-900 border border-slate-700 px-2 py-0.5 rounded-md">
                                  LLM Engine: {doc.llm_engine || 'Local Rule Parser'}
                                </span>
                              </div>
                              <span className="text-[11px] text-slate-400 italic">Klik baris ini kembali untuk meminimize</span>
                            </div>

                            {/* Cards Grid */}
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                              {Object.entries(j).map(([k, v]) => {
                                if (k === 'items' || v === null || v === undefined) return null;
                                const displayVal = typeof v === 'object' ? JSON.stringify(v) : String(v);
                                return (
                                  <div key={k} className="bg-slate-900/80 border border-slate-800 p-2.5 rounded-xl">
                                    <div className="text-[10px] text-slate-400 uppercase font-semibold">{k === 'quantity' ? 'JUMLAH BARANG' : k.replace(/_/g, ' ')}</div>
                                    <div className="text-xs font-medium text-slate-200 mt-0.5 break-words">{displayVal}</div>
                                  </div>
                                );
                              })}
                            </div>

                            {/* Render Items Table in Detail View if present */}
                            {Array.isArray(j.items) && j.items.length > 0 && (
                              <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-3 space-y-2 mt-2">
                                <div className="text-[11px] font-bold text-emerald-400 uppercase tracking-wider">
                                  Tabel Rincian Barang / Supply Chain ({j.items.length} Item)
                                </div>
                                <div className="overflow-x-auto">
                                  <table className="w-full text-left text-[11px] text-slate-300">
                                    <thead className="bg-slate-950 text-slate-400 font-semibold border-b border-slate-800">
                                      <tr>
                                        <th className="p-2">No</th>
                                        <th className="p-2">SKU</th>
                                        <th className="p-2">Deskripsi Item</th>
                                        <th className="p-2">Qty</th>
                                        <th className="p-2">Satuan</th>
                                        <th className="p-2">Harga</th>
                                        <th className="p-2 text-right">Total</th>
                                      </tr>
                                    </thead>
                                    <tbody className="divide-y divide-slate-800/40">
                                      {j.items.map((it, idx) => (
                                        <tr key={idx}>
                                          <td className="p-2 font-bold text-emerald-400">{it.no || idx + 1}</td>
                                          <td className="p-2 font-mono text-slate-400">{it.sku || '-'}</td>
                                          <td className="p-2 font-medium text-slate-200">{it.description || it.item_name || '-'}</td>
                                          <td className="p-2">{it.qty || '1'}</td>
                                          <td className="p-2">{it.unit || 'pcs'}</td>
                                          <td className="p-2 font-mono">{it.unit_price || '0'}</td>
                                          <td className="p-2 text-right font-mono font-bold text-emerald-300">{it.total || '0'}</td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </div>
                              </div>
                            )}

                            {/* Raw Text, Masked Preview, & Unmasked Final JSON */}
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-2">
                              <div>
                                <span className="text-[11px] font-semibold text-slate-400 mb-1 block">📄 Teks Mentah (Raw OCR):</span>
                                <textarea
                                  readOnly
                                  rows={5}
                                  value={doc.raw_text || ''}
                                  className="w-full bg-[#030712] border border-slate-800 rounded-xl p-2.5 text-[11px] font-mono text-slate-300 resize-none focus:outline-none"
                                />
                              </div>
                              <div>
                                <span className="text-[11px] font-semibold text-slate-400 mb-1 block">🔐 Teks Tersensor (PII Masked):</span>
                                <textarea
                                  readOnly
                                  rows={5}
                                  value={doc.masked_text || ''}
                                  className="w-full bg-[#030712] border border-slate-800 rounded-xl p-2.5 text-[11px] font-mono text-emerald-300 resize-none focus:outline-none"
                                />
                              </div>
                              <div>
                                <span className="text-[11px] font-semibold text-slate-400 mb-1 block">✨ Hasil Ekstraksi (Unmasked Final JSON):</span>
                                <textarea
                                  readOnly
                                  rows={5}
                                  value={JSON.stringify(doc.json_data, null, 2)}
                                  className="w-full bg-[#030712] border border-slate-800 rounded-xl p-2.5 text-[11px] font-mono text-amber-300 resize-none focus:outline-none"
                                />
                              </div>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
