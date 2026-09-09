import React, { useState, useMemo } from 'react';
import {
  StoreNumber,
  PeriodMode,
  DataSource,
  ServerMetricRow,
  ImportRun,
} from './types';
import {
  MOCK_DAILY_METRICS,
  MOCK_PREVIOUS_PERIOD_METRICS,
  MOCK_IMPORT_RUNS,
  AVAILABLE_BUSINESS_DATES,
} from './data/mockData';
import {
  PRIORITY_STORES,
  normalizeStoreNumber,
  processStoreRows,
  getStoreKpiDelta,
  getStoreLabel,
} from './utils/calculations';
import { Header } from './components/Header';
import { AdminRefreshModal } from './components/AdminRefreshModal';
import { StoreSection } from './components/StoreSection';
import { ManualUploadSection } from './components/ManualUploadSection';
import { Calendar, Filter, Sparkles, RefreshCw } from 'lucide-react';

export const App: React.FC = () => {
  const [dataSource, setDataSource] = useState<DataSource>('FOH Database');
  const [periodMode, setPeriodMode] = useState<PeriodMode>('Yesterday');
  const [businessDate, setBusinessDate] = useState<string>('2026-04-18');
  const [selectedStoreFilter, setSelectedStoreFilter] = useState<string>('ALL');

  const [importRuns, setImportRuns] = useState<ImportRun[]>(MOCK_IMPORT_RUNS);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  // Manual Upload data state
  const [uploadedMetrics, setUploadedMetrics] = useState<ServerMetricRow[]>([]);

  // Current active raw dataset
  const activeMetrics: ServerMetricRow[] = useMemo(() => {
    if (dataSource === 'Manual Uploads') {
      return uploadedMetrics;
    }
    // FOH Database mode
    const dateMetrics = MOCK_DAILY_METRICS[businessDate] || MOCK_DAILY_METRICS['2026-04-18'];
    return dateMetrics;
  }, [dataSource, uploadedMetrics, businessDate]);

  // Baseline previous dataset for trends
  const prevRowsMap = useMemo(() => {
    const map = new Map<string, ServerMetricRow>();
    MOCK_PREVIOUS_PERIOD_METRICS.forEach((row) => {
      map.set(row.server, row);
    });
    return map;
  }, []);

  // Subtitle & Trend Note calculation
  const { subtitle, trendNote, comparisonLabel } = useMemo(() => {
    const d = new Date(`${businessDate}T00:00:00`);
    const dateStr = d.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });

    if (periodMode === 'Yesterday') {
      const prevDate = new Date(d);
      prevDate.setDate(prevDate.getDate() - 7);
      const prevDateStr = prevDate.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      });
      return {
        subtitle: `Yesterday (${dateStr})`,
        trendNote: `All arrows vs LW (${prevDateStr})`,
        comparisonLabel: 'vs LW',
      };
    } else if (periodMode === 'WTD') {
      return {
        subtitle: `Week to Date through ${dateStr}`,
        trendNote: `All arrows vs Prior Week-to-Date`,
        comparisonLabel: 'vs Prior WTD',
      };
    } else {
      return {
        subtitle: `Month to Date through ${dateStr}`,
        trendNote: `All arrows vs Prior Month baseline`,
        comparisonLabel: 'vs Prior Month',
      };
    }
  }, [periodMode, businessDate]);

  // Group metrics by store
  const storeGroups = useMemo(() => {
    const map = new Map<string, ServerMetricRow[]>();
    activeMetrics.forEach((row) => {
      const storeNorm = normalizeStoreNumber(row.store);
      if (!map.has(storeNorm)) {
        map.set(storeNorm, []);
      }
      map.get(storeNorm)!.push(row);
    });

    // Ensure priority stores exist in FOH Database mode
    if (dataSource === 'FOH Database') {
      PRIORITY_STORES.forEach((ps) => {
        if (!map.has(ps)) {
          map.set(ps, []);
        }
      });
    }

    return map;
  }, [activeMetrics, dataSource]);

  // Ordered stores list
  const availableStores = useMemo(() => {
    const list = Array.from(storeGroups.keys());
    list.sort((a, b) => {
      const idxA = PRIORITY_STORES.indexOf(a);
      const idxB = PRIORITY_STORES.indexOf(b);
      if (idxA !== -1 && idxB !== -1) return idxA - idxB;
      if (idxA !== -1) return -1;
      if (idxB !== -1) return 1;
      return a.localeCompare(b);
    });
    return list;
  }, [storeGroups]);

  // Filtered stores
  const displayStores = useMemo(() => {
    if (selectedStoreFilter === 'ALL') {
      return availableStores;
    }
    return availableStores.filter((s) => s === selectedStoreFilter);
  }, [availableStores, selectedStoreFilter]);

  // Handle automated refresh trigger
  const handleTriggerRefresh = (
    jobType: 'rosnet' | 'tray' | 'full',
    date: string,
    targetStores: string[]
  ) => {
    setIsRefreshing(true);
    setTimeout(() => {
      setIsRefreshing(false);
      const newRun: ImportRun = {
        id: Date.now(),
        businessDate: date,
        sourceSystem: jobType === 'rosnet' ? 'rosnet' : jobType === 'tray' ? 'tray' : 'pipeline',
        reportType:
          jobType === 'full'
            ? 'daily_full_pipeline'
            : jobType === 'rosnet'
            ? 'rosnet_auto_import'
            : 'tray_auto_import',
        status: 'processed',
        startedAt: new Date().toISOString(),
        completedAt: new Date(Date.now() + 4000).toISOString(),
      };
      setImportRuns((prev) => [newRun, ...prev]);
    }, 1200);
  };

  return (
    <div className="min-h-screen bg-[#f8fafc] text-slate-900 pb-20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-6">
        <Header dataSource={dataSource} setDataSource={setDataSource} />

        {/* Admin Automated Refresh Banner */}
        {dataSource === 'FOH Database' && (
          <AdminRefreshModal
            importRuns={importRuns}
            onTriggerRefresh={handleTriggerRefresh}
            isRefreshing={isRefreshing}
          />
        )}

        {/* Manual Uploads Dropzone Section */}
        {dataSource === 'Manual Uploads' && (
          <ManualUploadSection
            onDataParsed={(data) => setUploadedMetrics(data)}
          />
        )}

        {/* Controls Toolbar: Period Mode, Date Picker, Store Filter */}
        <div className="mb-8 rounded-xl border border-slate-200 bg-white p-4 shadow-xs flex flex-wrap items-center justify-between gap-4">
          {/* Period Mode Selector */}
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
              Period:
            </span>
            <div className="inline-flex rounded-lg bg-slate-100 p-0.5 border border-slate-200 text-xs font-semibold">
              {(['Yesterday', 'WTD', 'MTD'] as PeriodMode[]).map((mode) => (
                <button
                  key={mode}
                  type="button"
                  onClick={() => setPeriodMode(mode)}
                  className={`px-3 py-1.5 rounded-md transition-all ${
                    periodMode === mode
                      ? 'bg-white text-blue-700 shadow-xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  {mode}
                </button>
              ))}
            </div>
          </div>

          {/* Business Date Picker */}
          <div className="flex items-center gap-2">
            <Calendar className="w-4 h-4 text-slate-500" />
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
              Date:
            </span>
            <select
              value={businessDate}
              onChange={(e) => setBusinessDate(e.target.value)}
              className="px-3 py-1.5 border border-slate-300 rounded-md text-xs font-medium text-slate-800 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {AVAILABLE_BUSINESS_DATES.map((dt) => (
                <option key={dt} value={dt}>
                  {dt}
                </option>
              ))}
            </select>
          </div>

          {/* Store Filter Selector */}
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-slate-500" />
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
              Filter Store:
            </span>
            <select
              value={selectedStoreFilter}
              onChange={(e) => setSelectedStoreFilter(e.target.value)}
              className="px-3 py-1.5 border border-slate-300 rounded-md text-xs font-medium text-slate-800 bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="ALL">All Stores</option>
              {availableStores.map((st) => (
                <option key={st} value={st}>
                  {getStoreLabel(st)}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Store Dashboards */}
        {displayStores.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-300 bg-white p-12 text-center">
            <Sparkles className="w-8 h-8 text-slate-400 mx-auto mb-3" />
            <h3 className="text-base font-semibold text-slate-800">
              No store data found for this selection
            </h3>
            <p className="text-xs text-slate-500 mt-1">
              Please choose another date or upload report files in Manual Uploads mode.
            </p>
          </div>
        ) : (
          displayStores.map((st) => {
            const rawRows = storeGroups.get(st) || [];
            const { displayRows, kpis } = processStoreRows(rawRows, prevRowsMap);

            // Compute store level deltas
            const prevStoreRows = MOCK_PREVIOUS_PERIOD_METRICS.filter(
              (r) => normalizeStoreNumber(r.store) === st
            );
            const { kpis: prevKpis } = processStoreRows(prevStoreRows);

            kpis.tabletTrend = getStoreKpiDelta(
              kpis.avgTablet,
              prevKpis.avgTablet,
              450,
              'tablet',
              comparisonLabel
            );
            kpis.turnTrend = getStoreKpiDelta(
              kpis.avgTurn,
              prevKpis.avgTurn,
              20,
              'turn',
              comparisonLabel
            );
            kpis.bevTrend = getStoreKpiDelta(
              kpis.avgBev,
              prevKpis.avgBev,
              450,
              'bev',
              comparisonLabel
            );
            kpis.ppaTrend = getStoreKpiDelta(
              kpis.avgPpa,
              prevKpis.avgPpa,
              40,
              'ppa',
              comparisonLabel
            );

            return (
              <StoreSection
                key={st}
                kpis={kpis}
                displayRows={displayRows}
                subtitle={subtitle}
                trendNote={trendNote}
              />
            );
          })
        )}
      </div>
    </div>
  );
};
