import React, { useState, useEffect, useMemo } from 'react';
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
import { Calendar, Filter, Sparkles, Loader2 } from 'lucide-react';

export const App: React.FC = () => {
  const [dataSource, setDataSource] = useState<DataSource>('FOH Database');
  const [periodMode, setPeriodMode] = useState<PeriodMode>('Yesterday');
  const [businessDate, setBusinessDate] = useState<string>('2026-09-07');
  const [availableDates, setAvailableDates] = useState<string[]>(['2026-09-07', ...AVAILABLE_BUSINESS_DATES]);
  const [selectedStoreFilter, setSelectedStoreFilter] = useState<string>('ALL');

  const [dbStatus, setDbStatus] = useState<{
    connected: boolean;
    totalRecords?: number;
    host?: string;
  }>({ connected: false });

  const [dbMetrics, setDbMetrics] = useState<ServerMetricRow[]>([]);
  const [dbPrevMetrics, setDbPrevMetrics] = useState<ServerMetricRow[]>([]);
  const [importRuns, setImportRuns] = useState<ImportRun[]>(MOCK_IMPORT_RUNS);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [isLoadingMetrics, setIsLoadingMetrics] = useState<boolean>(false);

  // Manual Upload data state
  const [uploadedMetrics, setUploadedMetrics] = useState<ServerMetricRow[]>([]);

  // 1. Initial Health and Metadata Check
  useEffect(() => {
    // Check DB health
    fetch('/api/health')
      .then((r) => r.json())
      .then((data) => {
        if (data.status === 'ok') {
          setDbStatus({
            connected: true,
            totalRecords: data.totalRecords,
            host: data.dbHost,
          });
        }
      })
      .catch((err) => console.warn('Backend /api/health not reachable, using fallback mode:', err));

    // Fetch dates from DB
    fetch('/api/dates')
      .then((r) => r.json())
      .then((data) => {
        if (data.dates && data.dates.length > 0) {
          setAvailableDates(data.dates);
          setBusinessDate(data.dates[0]);
        }
      })
      .catch(() => {});

    // Fetch import runs
    fetch('/api/import-runs')
      .then((r) => r.json())
      .then((data) => {
        if (data.runs && data.runs.length > 0) {
          setImportRuns(data.runs);
        }
      })
      .catch(() => {});
  }, []);

  // 2. Fetch Live Metrics on Date / Period Change
  useEffect(() => {
    if (dataSource !== 'FOH Database') return;

    let isSubscribed = true;
    setIsLoadingMetrics(true);

    const targetDate = new Date(`${businessDate}T00:00:00`);
    let mainUrl = `/api/metrics?date=${businessDate}`;
    let prevUrl: string | null = null;

    if (periodMode === 'Yesterday') {
      const prevDateObj = new Date(targetDate);
      prevDateObj.setDate(prevDateObj.getDate() - 7);
      const prevDateIso = prevDateObj.toISOString().slice(0, 10);
      prevUrl = `/api/metrics?date=${prevDateIso}`;
    } else if (periodMode === 'WTD') {
      // Find Monday of the current week
      const day = targetDate.getDay();
      const diffToMonday = targetDate.getDate() - day + (day === 0 ? -6 : 1);
      const monday = new Date(targetDate.setDate(diffToMonday));
      const mondayIso = monday.toISOString().slice(0, 10);
      mainUrl = `/api/metrics?startDate=${mondayIso}&endDate=${businessDate}`;

      // Prior week Monday to same day
      const priorMon = new Date(monday);
      priorMon.setDate(priorMon.getDate() - 7);
      const priorEnd = new Date(new Date(`${businessDate}T00:00:00`));
      priorEnd.setDate(priorEnd.getDate() - 7);
      prevUrl = `/api/metrics?startDate=${priorMon.toISOString().slice(0, 10)}&endDate=${priorEnd.toISOString().slice(0, 10)}`;
    } else if (periodMode === 'MTD') {
      const firstOfMonth = new Date(targetDate.getFullYear(), targetDate.getMonth(), 1).toISOString().slice(0, 10);
      mainUrl = `/api/metrics?startDate=${firstOfMonth}&endDate=${businessDate}`;
      const firstOfPriorMonth = new Date(targetDate.getFullYear(), targetDate.getMonth() - 1, 1).toISOString().slice(0, 10);
      const endOfPriorMonth = new Date(targetDate.getFullYear(), targetDate.getMonth(), 0).toISOString().slice(0, 10);
      prevUrl = `/api/metrics?startDate=${firstOfPriorMonth}&endDate=${endOfPriorMonth}`;
    }

    Promise.all([
      fetch(mainUrl)
        .then((r) => r.json())
        .catch(() => ({ rows: [] })),
      prevUrl
        ? fetch(prevUrl)
            .then((r) => r.json())
            .catch(() => ({ rows: [] }))
        : Promise.resolve({ rows: [] }),
    ])
      .then(([mainRes, prevRes]) => {
        if (!isSubscribed) return;
        if (mainRes.rows && mainRes.rows.length > 0) {
          setDbMetrics(mainRes.rows);
        } else {
          // Fallback to mock data if empty for that particular date
          const fallback = MOCK_DAILY_METRICS[businessDate] || MOCK_DAILY_METRICS['2026-04-18'];
          setDbMetrics(fallback);
        }

        if (prevRes.rows && prevRes.rows.length > 0) {
          setDbPrevMetrics(prevRes.rows);
        } else {
          setDbPrevMetrics(MOCK_PREVIOUS_PERIOD_METRICS);
        }
      })
      .finally(() => {
        if (isSubscribed) setIsLoadingMetrics(false);
      });

    return () => {
      isSubscribed = false;
    };
  }, [businessDate, periodMode, dataSource]);

  // Current active raw dataset
  const activeMetrics: ServerMetricRow[] = useMemo(() => {
    if (dataSource === 'Manual Uploads') {
      return uploadedMetrics;
    }
    return dbMetrics.length > 0 ? dbMetrics : MOCK_DAILY_METRICS['2026-04-18'];
  }, [dataSource, uploadedMetrics, dbMetrics]);

  // Baseline previous dataset for trends
  const prevRowsMap = useMemo(() => {
    const map = new Map<string, ServerMetricRow>();
    const source = dbPrevMetrics.length > 0 ? dbPrevMetrics : MOCK_PREVIOUS_PERIOD_METRICS;
    source.forEach((row) => {
      map.set(row.server, row);
    });
    return map;
  }, [dbPrevMetrics]);

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

  // Handle automated refresh trigger via API
  const handleTriggerRefresh = async (
    jobType: 'rosnet' | 'tray' | 'full',
    date: string,
    targetStores: string[]
  ): Promise<{ ok: boolean; label: string; stdout: string; stderr: string }> => {
    setIsRefreshing(true);

    try {
      const r = await fetch('/api/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          jobType,
          businessDate: date,
          stores: targetStores,
        }),
      });
      const res = await r.json();
      if (res.run) {
        setImportRuns((prev) => [res.run, ...prev]);
      }
      return {
        ok: Boolean(res.ok),
        label: res.label || `${jobType.toUpperCase()} Refresh`,
        stdout: res.stdout || '',
        stderr: res.stderr || '',
      };
    } catch (err: any) {
      console.error('Refresh API failed:', err);
      return {
        ok: false,
        label: `${jobType.toUpperCase()} Refresh`,
        stdout: '',
        stderr: err.message || 'Error triggering refresh',
      };
    } finally {
      setIsRefreshing(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#f8fafc] text-slate-900 pb-20">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-6">
        <Header
          dataSource={dataSource}
          setDataSource={setDataSource}
          dbStatus={dbStatus}
        />

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
              {availableDates.map((dt) => (
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

        {/* Store Dashboards or Loading Indicator */}
        {isLoadingMetrics ? (
          <div className="rounded-xl border border-slate-200 bg-white p-12 text-center flex flex-col items-center justify-center">
            <Loader2 className="w-8 h-8 text-blue-600 animate-spin mb-3" />
            <p className="text-sm font-semibold text-slate-700">Loading FOH metrics from database...</p>
          </div>
        ) : displayStores.length === 0 ? (
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
            const prevStoreRows = (dbPrevMetrics.length > 0 ? dbPrevMetrics : MOCK_PREVIOUS_PERIOD_METRICS).filter(
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
