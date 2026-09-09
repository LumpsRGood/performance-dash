export type StoreNumber = '3231' | '4445' | '4456' | '4463' | string;

export interface ServerMetricRow {
  store: string;
  server: string;
  tabletPct?: number | null;
  tabletWeight?: number | null;
  turnTime?: number | null;
  turnCheckCount?: number | null;
  dineInBevPct?: number | null;
  bevWeight?: number | null;
  ppa?: number | null;
  ppaWeight?: number | null;
  netSales?: number | null;
  supportStaff?: boolean;
}

export type BadgeType = 'TOP PERFORMER' | 'ALL GREEN' | 'COACH' | 'SLOWEST TURN';

export interface ServerDisplayRow extends ServerMetricRow {
  badge?: BadgeType | null;
  isAllGreen: boolean;
  greensCount: number;
  tabletTrendMarker?: { symbol: string; color: string } | null;
  turnTrendMarker?: { symbol: string; color: string } | null;
  bevTrendMarker?: { symbol: string; color: string } | null;
  ppaTrendMarker?: { symbol: string; color: string } | null;
}

export interface StoreKPIs {
  storeNumber: string;
  storeLabel: string;
  avgTablet: number | null;
  avgTurn: number | null;
  avgBev: number | null;
  avgPpa: number | null;
  topTabletServer?: string;
  bottomTabletServer?: string;
  bestTurnServer?: string;
  slowestTurnServer?: string;
  topBevServer?: string;
  bottomBevServer?: string;
  topPpaServer?: string;
  bottomPpaServer?: string;
  tabletTrend?: { text: string; color: string } | null;
  turnTrend?: { text: string; color: string } | null;
  bevTrend?: { text: string; color: string } | null;
  ppaTrend?: { text: string; color: string } | null;
}

export interface ImportRun {
  id?: number;
  businessDate: string;
  sourceSystem: 'tray' | 'rosnet' | 'pipeline';
  reportType: string;
  status: 'loaded' | 'processed' | 'failed' | 'skipped';
  startedAt: string;
  completedAt: string;
}

export type PeriodMode = 'Yesterday' | 'WTD' | 'MTD';
export type DataSource = 'FOH Database' | 'Manual Uploads';
