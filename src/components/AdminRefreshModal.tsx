import React, { useState } from 'react';
import {
  ChevronDown,
  ChevronRight,
  Play,
  RefreshCw,
  Server,
  CheckCircle2,
  AlertCircle,
  Terminal,
  Info,
  ShieldCheck,
} from 'lucide-react';
import { ImportRun, StoreNumber } from '../types';
import { PRIORITY_STORES, getStoreLabel } from '../utils/calculations';

interface AdminRefreshProps {
  importRuns: ImportRun[];
  onTriggerRefresh: (
    jobType: 'rosnet' | 'tray' | 'full',
    date: string,
    stores: string[]
  ) => Promise<{
    ok: boolean;
    label: string;
    stdout: string;
    stderr: string;
  }>;
  isRefreshing: boolean;
}

export const AdminRefreshModal: React.FC<AdminRefreshProps> = ({
  importRuns,
  onTriggerRefresh,
  isRefreshing,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [showArchNotes, setShowArchNotes] = useState(false);
  const [refreshDate, setRefreshDate] = useState('2026-09-07');
  const [scope, setScope] = useState<'All stores' | 'Single store'>('All stores');
  const [singleStore, setSingleStore] = useState<StoreNumber>('3231');
  const [lastLog, setLastLog] = useState<{
    ok: boolean;
    label: string;
    stdout: string;
    stderr: string;
  } | null>(null);

  const handleRun = async (type: 'rosnet' | 'tray' | 'full') => {
    const stores = scope === 'All stores' ? PRIORITY_STORES : [singleStore];
    const result = await onTriggerRefresh(type, refreshDate, stores);
    setLastLog(result);
  };

  return (
    <div className="mb-6 rounded-xl border border-slate-200 bg-white shadow-xs overflow-hidden transition-all">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-5 py-3.5 flex items-center justify-between text-left bg-slate-50 hover:bg-slate-100 transition-colors"
      >
        <div className="flex items-center gap-2.5">
          <Server className="w-4 h-4 text-blue-600" />
          <span className="font-semibold text-sm text-slate-800">
            Admin: Refresh Alabama Data
          </span>
          <span className="text-xs bg-blue-100 text-blue-800 px-2 py-0.5 rounded-full font-medium">
            Stores: 3231, 4445, 4456, 4463
          </span>
        </div>
        {isOpen ? (
          <ChevronDown className="w-4 h-4 text-slate-500" />
        ) : (
          <ChevronRight className="w-4 h-4 text-slate-500" />
        )}
      </button>

      {isOpen && (
        <div className="p-5 border-t border-slate-200 space-y-4">
          <p className="text-xs text-slate-500">
            Runs the Alabama priority-store automated import jobs for Prattville, Montgomery, Oxford, and Decatur.
          </p>

          {/* Architecture & Debian Browser Resolution Info Box */}
          <div className="rounded-lg border border-blue-100 bg-blue-50/70 p-3.5 text-xs text-blue-900">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 font-semibold text-blue-950">
                <Info className="w-4 h-4 text-blue-600 flex-shrink-0" />
                <span>Headless Browser & Tray Architecture Status</span>
              </div>
              <button
                type="button"
                onClick={() => setShowArchNotes(!showArchNotes)}
                className="text-xs text-blue-700 hover:text-blue-900 underline font-medium"
              >
                {showArchNotes ? 'Hide Details' : 'Why did Streamlit/Debian fail?'}
              </button>
            </div>

            {showArchNotes && (
              <div className="mt-3 pt-3 border-t border-blue-200/60 space-y-2 text-slate-700">
                <p>
                  <strong>Root Cause on Streamlit:</strong> Streamlit Cloud runs on a minimal Debian Linux image without the required Chromium GUI/headless libraries (<code>libglib-2.0</code>, <code>libnss3</code>, <code>libnspr4</code>) or where Debian package repositories expired. This prevented running browser automation directly on the Streamlit host.
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mt-2 pt-1 font-medium">
                  <div className="bg-white p-2.5 rounded border border-blue-100">
                    <span className="text-blue-700 font-bold block mb-1">1. Direct Database</span>
                    Metrics query live directly from Supabase PostgreSQL (8,320+ rows).
                  </div>
                  <div className="bg-white p-2.5 rounded border border-blue-100">
                    <span className="text-blue-700 font-bold block mb-1">2. Remote Collector</span>
                    Offloads headless Chrome scraping to the dedicated Render worker.
                  </div>
                  <div className="bg-white p-2.5 rounded border border-blue-100">
                    <span className="text-blue-700 font-bold block mb-1">3. Zero-Dependency Uploads</span>
                    Drag-and-drop CSV parsing runs in-browser with no Debian or OS dependencies.
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-1">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Refresh business date
              </label>
              <input
                type="date"
                value={refreshDate}
                onChange={(e) => setRefreshDate(e.target.value)}
                className="w-full px-3 py-1.5 border border-slate-300 rounded-md text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Refresh scope
              </label>
              <div className="flex items-center gap-3 mt-1.5">
                <label className="inline-flex items-center text-xs text-slate-700 cursor-pointer">
                  <input
                    type="radio"
                    name="admin_scope"
                    checked={scope === 'All stores'}
                    onChange={() => setScope('All stores')}
                    className="mr-1.5 text-blue-600"
                  />
                  All stores
                </label>
                <label className="inline-flex items-center text-xs text-slate-700 cursor-pointer">
                  <input
                    type="radio"
                    name="admin_scope"
                    checked={scope === 'Single store'}
                    onChange={() => setScope('Single store')}
                    className="mr-1.5 text-blue-600"
                  />
                  Single store
                </label>
              </div>
            </div>

            {scope === 'Single store' && (
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Store to refresh
                </label>
                <select
                  value={singleStore}
                  onChange={(e) => setSingleStore(e.target.value as StoreNumber)}
                  className="w-full px-3 py-1.5 border border-slate-300 rounded-md text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {PRIORITY_STORES.map((s) => (
                    <option key={s} value={s}>
                      {getStoreLabel(s)}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>

          <div className="flex flex-wrap gap-2.5 pt-2">
            <button
              type="button"
              disabled={isRefreshing}
              onClick={() => handleRun('rosnet')}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-800 text-xs font-medium rounded-md border border-slate-300 transition-colors disabled:opacity-50"
            >
              <Play className="w-3 h-3 text-slate-600" />
              Run Rosnet Import (Inactive)
            </button>
            <button
              type="button"
              disabled={isRefreshing}
              onClick={() => handleRun('tray')}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium rounded-md shadow-xs transition-colors disabled:opacity-50"
            >
              {isRefreshing ? (
                <RefreshCw className="w-3 h-3 animate-spin" />
              ) : (
                <Play className="w-3 h-3" />
              )}
              Run Tray Import
            </button>
            <button
              type="button"
              disabled={isRefreshing}
              onClick={() => handleRun('full')}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-slate-900 hover:bg-slate-800 text-white text-xs font-medium rounded-md shadow-xs transition-colors disabled:opacity-50"
            >
              {isRefreshing ? (
                <RefreshCw className="w-3 h-3 animate-spin" />
              ) : (
                <Play className="w-3 h-3" />
              )}
              Run Full Refresh
            </button>
          </div>

          {/* Execution Output Console */}
          {lastLog && (
            <div className="mt-4 rounded-lg border border-slate-800 bg-slate-950 p-4 text-xs font-mono text-slate-100 overflow-x-auto shadow-inner">
              <div className="flex items-center justify-between pb-2 border-b border-slate-800 mb-2.5">
                <div className="flex items-center gap-2">
                  <Terminal className="w-3.5 h-3.5 text-slate-400" />
                  <span className="font-semibold text-slate-300">{lastLog.label}</span>
                </div>
                {lastLog.ok ? (
                  <span className="inline-flex items-center gap-1 text-emerald-400 font-semibold">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    Success
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 text-rose-400 font-semibold">
                    <AlertCircle className="w-3.5 h-3.5" />
                    Skipped / Notice
                  </span>
                )}
              </div>
              {lastLog.stdout && (
                <pre className="whitespace-pre-wrap text-slate-300 leading-relaxed">
                  {lastLog.stdout}
                </pre>
              )}
              {lastLog.stderr && (
                <pre className="whitespace-pre-wrap text-amber-300 mt-2 font-semibold">
                  {lastLog.stderr}
                </pre>
              )}
            </div>
          )}

          {/* Recent Runs Table */}
          <div className="pt-2">
            <h4 className="text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2">
              Recent Ingestion Runs
            </h4>
            <div className="border border-slate-200 rounded-lg overflow-hidden max-h-48 overflow-y-auto">
              <table className="w-full text-left text-xs text-slate-600">
                <thead className="bg-slate-50 text-slate-700 font-semibold border-b border-slate-200 sticky top-0">
                  <tr>
                    <th className="px-3 py-2">Date</th>
                    <th className="px-3 py-2">Source</th>
                    <th className="px-3 py-2">Report Type</th>
                    <th className="px-3 py-2">Status</th>
                    <th className="px-3 py-2">Started</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {importRuns.map((run) => (
                    <tr key={run.id} className="hover:bg-slate-50/80">
                      <td className="px-3 py-1.5 font-medium text-slate-900">{run.businessDate}</td>
                      <td className="px-3 py-1.5 capitalize">{run.sourceSystem}</td>
                      <td className="px-3 py-1.5 text-slate-500">{run.reportType}</td>
                      <td className="px-3 py-1.5">
                        <span
                          className={`inline-block px-2 py-0.5 rounded text-[11px] font-semibold ${
                            run.status === 'processed'
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : 'bg-amber-50 text-amber-700 border border-amber-200'
                          }`}
                        >
                          {run.status}
                        </span>
                      </td>
                      <td className="px-3 py-1.5 text-slate-500 font-mono text-[11px]">
                        {run.startedAt ? new Date(run.startedAt).toLocaleString() : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
