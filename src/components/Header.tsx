import React from 'react';
import { AlertTriangle, Database, UploadCloud } from 'lucide-react';
import { DataSource } from '../types';

interface HeaderProps {
  dataSource: DataSource;
  setDataSource: (source: DataSource) => void;
}

export const Header: React.FC<HeaderProps> = ({ dataSource, setDataSource }) => {
  return (
    <header className="mb-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">
            FOH Performance Dashboard
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Use the FOH database for the priority stores, or fall back to uploads when needed.
          </p>
        </div>

        <div className="inline-flex rounded-lg bg-slate-100 p-1 border border-slate-200 text-sm font-medium self-start sm:self-center">
          <button
            type="button"
            onClick={() => setDataSource('FOH Database')}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-md transition-all ${
              dataSource === 'FOH Database'
                ? 'bg-white text-blue-700 shadow-sm font-semibold'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Database className="w-4 h-4" />
            FOH Database
          </button>
          <button
            type="button"
            onClick={() => setDataSource('Manual Uploads')}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-md transition-all ${
              dataSource === 'Manual Uploads'
                ? 'bg-white text-blue-700 shadow-sm font-semibold'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <UploadCloud className="w-4 h-4" />
            Manual Uploads
          </button>
        </div>
      </div>

      <div className="mt-4 flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 p-3.5 text-sm text-amber-900">
        <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
        <div>
          <strong className="font-semibold text-amber-800">Automation Warning:</strong>{' '}
          Automated refresh is currently configured only for the Alabama market (Stores 3231, 4445, 4456, 4463).
          If you are outside the Alabama market, please use Manual Uploads for now.
        </div>
      </div>
    </header>
  );
};
