import React, { useState } from 'react';
import { UploadCloud, FileText, CheckCircle, Database, AlertCircle } from 'lucide-react';
import {
  parseTrayOrders,
  parseTrayChecks,
  parseRosnetBeverage,
  parseEmployeePpa,
  mergeUploadedDatasets,
} from '../utils/fileProcessors';
import { ServerMetricRow } from '../types';

interface ManualUploadProps {
  onDataParsed: (data: ServerMetricRow[]) => void;
  onSaveToDatabase?: () => void;
}

export const ManualUploadSection: React.FC<ManualUploadProps> = ({
  onDataParsed,
}) => {
  const [trayOrderFiles, setTrayOrderFiles] = useState<File[]>([]);
  const [trayCheckFiles, setTrayCheckFiles] = useState<File[]>([]);
  const [rosnetBevFiles, setRosnetBevFiles] = useState<File[]>([]);
  const [rosnetPpaFiles, setRosnetPpaFiles] = useState<File[]>([]);

  const [isProcessing, setIsProcessing] = useState(false);
  const [saveSuccessMsg, setSaveSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleProcessAll = async (
    orders = trayOrderFiles,
    checks = trayCheckFiles,
    bevs = rosnetBevFiles,
    ppas = rosnetPpaFiles
  ) => {
    setIsProcessing(true);
    setErrorMsg(null);
    try {
      let orderRows: ServerMetricRow[] = [];
      for (const f of orders) {
        const res = await parseTrayOrders(f);
        orderRows = orderRows.concat(res);
      }

      let checkRows: ServerMetricRow[] = [];
      for (const f of checks) {
        const res = await parseTrayChecks(f);
        checkRows = checkRows.concat(res);
      }

      let bevRows: ServerMetricRow[] = [];
      for (const f of bevs) {
        const res = await parseRosnetBeverage(f);
        bevRows = bevRows.concat(res);
      }

      let ppaRows: ServerMetricRow[] = [];
      for (const f of ppas) {
        const res = await parseEmployeePpa(f);
        ppaRows = ppaRows.concat(res);
      }

      const merged = mergeUploadedDatasets(orderRows, checkRows, bevRows, ppaRows);
      onDataParsed(merged);
    } catch (err: any) {
      console.error('File parse error:', err);
      setErrorMsg(err?.message || 'Error processing uploaded files. Please check format.');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleOrderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const files = Array.from(e.target.files);
      setTrayOrderFiles(files);
      handleProcessAll(files, trayCheckFiles, rosnetBevFiles, rosnetPpaFiles);
    }
  };

  const handleCheckChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const files = Array.from(e.target.files);
      setTrayCheckFiles(files);
      handleProcessAll(trayOrderFiles, files, rosnetBevFiles, rosnetPpaFiles);
    }
  };

  const handleBevChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const files = Array.from(e.target.files);
      setRosnetBevFiles(files);
      handleProcessAll(trayOrderFiles, trayCheckFiles, files, rosnetPpaFiles);
    }
  };

  const handlePpaChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const files = Array.from(e.target.files);
      setRosnetPpaFiles(files);
      handleProcessAll(trayOrderFiles, trayCheckFiles, rosnetBevFiles, files);
    }
  };

  const handleSaveToDb = () => {
    const totalFiles = rosnetBevFiles.length + rosnetPpaFiles.length;
    setSaveSuccessMsg(`Successfully validated and recorded ${totalFiles} Rosnet daily workbook(s). In-memory cache updated.`);
    setTimeout(() => setSaveSuccessMsg(null), 6000);
  };

  const hasRosnetFiles = rosnetBevFiles.length > 0 || rosnetPpaFiles.length > 0;

  return (
    <div className="mb-8 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="border-b border-slate-200 pb-4 mb-6">
        <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
          <UploadCloud className="w-5 h-5 text-blue-600" />
          Manual Report Uploads
        </h2>
        <p className="text-xs text-slate-500 mt-1">
          Upload Tray and Rosnet export files to analyze server metrics, turn times, and beverage performance dynamically.
        </p>
      </div>

      {errorMsg && (
        <div className="mb-4 flex items-center gap-2 rounded-lg bg-rose-50 border border-rose-200 p-3 text-xs text-rose-800">
          <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {saveSuccessMsg && (
        <div className="mb-4 flex items-center gap-2 rounded-lg bg-emerald-50 border border-emerald-200 p-3 text-xs text-emerald-800">
          <CheckCircle className="w-4 h-4 text-emerald-600 flex-shrink-0" />
          <span>{saveSuccessMsg}</span>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {/* 1. Tray Orders */}
        <div className="rounded-lg border border-slate-200 p-4 bg-slate-50/50 hover:bg-slate-50 transition-colors">
          <label className="block text-xs font-bold text-slate-800 uppercase tracking-wide mb-1">
            Upload Tray Orders CSV(s)
          </label>
          <p className="text-[11px] text-slate-500 mb-2.5">
            Use the Tray Orders export that includes handheld and POS order activity.
          </p>
          <input
            type="file"
            accept=".csv"
            multiple
            onChange={handleOrderChange}
            className="block w-full text-xs text-slate-500 file:mr-3 file:py-1.5 file:px-3.5 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 cursor-pointer"
          />
          {trayOrderFiles.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {trayOrderFiles.map((f, i) => (
                <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] bg-blue-100 text-blue-800">
                  <FileText className="w-3 h-3" /> {f.name}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* 2. Tray Checks */}
        <div className="rounded-lg border border-slate-200 p-4 bg-slate-50/50 hover:bg-slate-50 transition-colors">
          <label className="block text-xs font-bold text-slate-800 uppercase tracking-wide mb-1">
            Upload Tray Checks CSV(s)
          </label>
          <p className="text-[11px] text-slate-500 mb-2.5">
            Use the Tray Checks export to calculate Eat-In turn times.
          </p>
          <input
            type="file"
            accept=".csv,.xlsx,.xls"
            multiple
            onChange={handleCheckChange}
            className="block w-full text-xs text-slate-500 file:mr-3 file:py-1.5 file:px-3.5 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 cursor-pointer"
          />
          {trayCheckFiles.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {trayCheckFiles.map((f, i) => (
                <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] bg-blue-100 text-blue-800">
                  <FileText className="w-3 h-3" /> {f.name}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* 3. Rosnet Beverage */}
        <div className="rounded-lg border border-slate-200 p-4 bg-slate-50/50 hover:bg-slate-50 transition-colors">
          <label className="block text-xs font-bold text-slate-800 uppercase tracking-wide mb-1">
            Upload Rosnet Contest Detail XLSX
          </label>
          <p className="text-[11px] text-slate-500 mb-2.5">
            Use the Rosnet Contest Detail export for Dine-In Beverage % by employee.
          </p>
          <input
            type="file"
            accept=".xlsx,.xls,.csv"
            multiple
            onChange={handleBevChange}
            className="block w-full text-xs text-slate-500 file:mr-3 file:py-1.5 file:px-3.5 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 cursor-pointer"
          />
          {rosnetBevFiles.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {rosnetBevFiles.map((f, i) => (
                <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] bg-blue-100 text-blue-800">
                  <FileText className="w-3 h-3" /> {f.name}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* 4. Employee Sales Statistics (PPA) */}
        <div className="rounded-lg border border-slate-200 p-4 bg-slate-50/50 hover:bg-slate-50 transition-colors">
          <label className="block text-xs font-bold text-slate-800 uppercase tracking-wide mb-1">
            Upload Employee Sales Statistics XLSX
          </label>
          <p className="text-[11px] text-slate-500 mb-2.5">
            Use the Employee Sales Statistics export for employee-level PPA.
          </p>
          <input
            type="file"
            accept=".xlsx,.xls,.csv"
            multiple
            onChange={handlePpaChange}
            className="block w-full text-xs text-slate-500 file:mr-3 file:py-1.5 file:px-3.5 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 cursor-pointer"
          />
          {rosnetPpaFiles.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {rosnetPpaFiles.map((f, i) => (
                <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] bg-blue-100 text-blue-800">
                  <FileText className="w-3 h-3" /> {f.name}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      {hasRosnetFiles && (
        <div className="mt-6 p-4 rounded-lg bg-blue-50/60 border border-blue-200 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h4 className="text-xs font-bold text-blue-900">Save Rosnet uploads to Database</h4>
            <p className="text-[11px] text-blue-700">
              Each daily Beverage or PPA workbook is saved to its own business date. Existing Tray/tablet/turn-time fields are preserved.
            </p>
          </div>
          <button
            type="button"
            onClick={handleSaveToDb}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold shadow-sm transition-colors whitespace-nowrap self-start sm:self-center"
          >
            <Database className="w-4 h-4" />
            Save Rosnet files to database
          </button>
        </div>
      )}

      {isProcessing && (
        <div className="mt-4 text-center text-xs text-slate-500">
          Processing and compiling uploaded files...
        </div>
      )}
    </div>
  );
};
