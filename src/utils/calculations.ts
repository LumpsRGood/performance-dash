import { ServerMetricRow, ServerDisplayRow, BadgeType, StoreKPIs } from '../types';

export const STORE_MAP: Record<string, string> = {
  '3231': 'Prattville',
  '4445': 'Montgomery',
  '4456': 'Oxford',
  '4463': 'Decatur',
};

export const PRIORITY_STORES = ['3231', '4445', '4456', '4463'];

export function getStoreLabel(store: string): string {
  const norm = normalizeStoreNumber(store);
  if (!norm || norm === 'Unknown') return 'Unknown';
  if (STORE_MAP[norm]) {
    return `${norm} - ${STORE_MAP[norm]}`;
  }
  return `${norm} - Store`;
}

export function normalizeStoreNumber(store?: string | number | null): string {
  if (!store) return 'Unknown';
  const s = String(store).trim();
  const match = s.match(/(\d{3,4})/);
  return match ? String(parseInt(match[1], 10)) : s;
}

export function cleanName(name?: string | null): string {
  if (!name) return '';
  let str = String(name).trim();
  if (str.includes(',')) {
    const parts = str.split(',').map((p) => p.trim()).filter(Boolean);
    if (parts.length >= 2) {
      str = `${parts.slice(1).join(' ')} ${parts[0]}`;
    }
  }
  str = str.replace(/,/g, ' ');
  const tokens: string[] = [];
  for (const token of str.split(/\s+/)) {
    if (!tokens.length || tokens[tokens.length - 1].toLowerCase() !== token.toLowerCase()) {
      tokens.push(token);
    }
  }
  return tokens
    .map((t) => t.charAt(0).toUpperCase() + t.slice(1).toLowerCase())
    .join(' ');
}

export function isSupportStaff(name?: string | null): boolean {
  const lower = String(name || '').trim().toLowerCase();
  if (!lower) return false;
  return lower.includes('olo') || lower.includes('online ordering');
}

export function isTabletGreen(x?: number | null): boolean {
  return x != null && !isNaN(x) && x >= 0.90;
}

export function isTurnGreen(x?: number | null): boolean {
  return x != null && !isNaN(x) && x <= 40;
}

export function isBevGreen(x?: number | null): boolean {
  return x != null && !isNaN(x) && x >= 0.19;
}

export function isPpaGreen(x?: number | null): boolean {
  return x != null && !isNaN(x) && x >= 21;
}

export function isTurnRed(x?: number | null): boolean {
  return x != null && !isNaN(x) && x > 45;
}

export function isBevRed(x?: number | null): boolean {
  return x != null && !isNaN(x) && x < 0.18;
}

export function isPpaRed(x?: number | null): boolean {
  return x != null && !isNaN(x) && x < 20;
}

export function getTabletColor(x?: number | null): { bg: string; text: string; icon: string } {
  if (x == null || isNaN(x)) return { bg: '#f1f5f9', text: '#64748b', icon: '' };
  if (x >= 0.90) return { bg: '#6fdc8c', text: '#111827', icon: '🟢' };
  if (x >= 0.80) return { bg: '#ffe066', text: '#111827', icon: '🟡' };
  return { bg: '#ff6b6b', text: '#ffffff', icon: '🔴' };
}

export function getTurnColor(x?: number | null): { bg: string; text: string; icon: string } {
  if (x == null || isNaN(x)) return { bg: '#f1f5f9', text: '#64748b', icon: '' };
  if (x <= 40) return { bg: '#6fdc8c', text: '#111827', icon: '🟢' };
  if (x <= 45) return { bg: '#ffe066', text: '#111827', icon: '🟡' };
  return { bg: '#ff6b6b', text: '#ffffff', icon: '🔴' };
}

export function getBevColor(x?: number | null): { bg: string; text: string; icon: string } {
  if (x == null || isNaN(x)) return { bg: '#f1f5f9', text: '#64748b', icon: '' };
  if (x >= 0.19) return { bg: '#6fdc8c', text: '#111827', icon: '🟢' };
  if (x >= 0.18) return { bg: '#ffe066', text: '#111827', icon: '🟡' };
  return { bg: '#ff6b6b', text: '#ffffff', icon: '🔴' };
}

export function getPpaColor(x?: number | null): { bg: string; text: string; icon: string } {
  if (x == null || isNaN(x)) return { bg: '#f1f5f9', text: '#64748b', icon: '' };
  if (x >= 21) return { bg: '#6fdc8c', text: '#111827', icon: '🟢' };
  if (x >= 20) return { bg: '#ffe066', text: '#111827', icon: '🟡' };
  return { bg: '#ff6b6b', text: '#ffffff', icon: '🔴' };
}

export function safeMean(values: (number | null | undefined)[]): number | null {
  const valid = values.filter((v): v is number => v != null && !isNaN(v));
  if (!valid.length) return null;
  return valid.reduce((acc, c) => acc + c, 0) / valid.length;
}

export function weightedMean(
  items: { val?: number | null; weight?: number | null }[]
): number | null {
  const valid = items.filter(
    (i) => i.val != null && !isNaN(i.val) && i.weight != null && !isNaN(i.weight) && i.weight > 0
  );
  if (!valid.length) return null;
  const totalWeight = valid.reduce((sum, i) => sum + (i.weight || 0), 0);
  if (totalWeight <= 0) return null;
  const totalVal = valid.reduce((sum, i) => sum + (i.val || 0) * (i.weight || 0), 0);
  return totalVal / totalWeight;
}

export const TREND_GUARDS = {
  tablet: { rowMinWeight: 100, storeMinWeight: 400, flatThreshold: 0.01 },
  turn: { rowMinWeight: 3, storeMinWeight: 12, flatThreshold: 1.0 },
  bev: { rowMinWeight: 100, storeMinWeight: 400, flatThreshold: 0.003 },
  ppa: { rowMinWeight: 8, storeMinWeight: 30, flatThreshold: 0.25 },
};

export function getTrendMarker(
  current: number | null | undefined,
  previous: number | null | undefined,
  prevWeight: number | null | undefined,
  type: 'tablet' | 'turn' | 'bev' | 'ppa'
): { symbol: string; color: string; text?: string } | null {
  if (current == null || previous == null || prevWeight == null) return null;
  const guard = TREND_GUARDS[type];
  if (prevWeight < guard.rowMinWeight) return null;

  let delta: number;
  if (type === 'turn') {
    delta = previous - current; // for turn time, decrease is good
  } else {
    delta = current - previous;
  }

  if (Math.abs(delta) <= guard.flatThreshold) {
    return { symbol: '•', color: '#64748b' };
  }
  if (delta > 0) {
    return { symbol: '▲', color: '#16a34a' };
  }
  return { symbol: '▼', color: '#dc2626' };
}

export function getStoreKpiDelta(
  current: number | null | undefined,
  previous: number | null | undefined,
  prevWeight: number | null | undefined,
  type: 'tablet' | 'turn' | 'bev' | 'ppa',
  comparisonLabel: string = 'vs LW'
): { text: string; color: string } | null {
  if (current == null || previous == null || prevWeight == null) return null;
  const guard = TREND_GUARDS[type];
  if (prevWeight < guard.storeMinWeight) return null;

  let delta: number;
  if (type === 'turn') {
    delta = previous - current;
  } else {
    delta = current - previous;
  }

  const absDelta = Math.abs(delta);
  if (absDelta <= guard.flatThreshold) {
    return { text: `• Flat ${comparisonLabel}`, color: '#64748b' };
  }

  let formattedDelta: string;
  if (type === 'bev' || type === 'tablet') {
    formattedDelta = `${(absDelta * 100).toFixed(1)}%`;
  } else if (type === 'ppa') {
    formattedDelta = `$${absDelta.toFixed(2)}`;
  } else {
    formattedDelta = `${absDelta.toFixed(1)}m`;
  }

  if (delta > 0) {
    const symbol = type === 'turn' ? '▼' : '▲';
    return { text: `${symbol} ${formattedDelta} ${comparisonLabel}`, color: '#16a34a' };
  } else {
    const symbol = type === 'turn' ? '▲' : '▼';
    return { text: `${symbol} ${formattedDelta} ${comparisonLabel}`, color: '#dc2626' };
  }
}

export function calculateGreensCount(row: ServerMetricRow): number {
  let count = 0;
  if (isTabletGreen(row.tabletPct)) count++;
  if (isTurnGreen(row.turnTime)) count++;
  if (isBevGreen(row.dineInBevPct)) count++;
  if (row.ppa != null && isPpaGreen(row.ppa)) count++;
  return count;
}

export function processStoreRows(
  rows: ServerMetricRow[],
  prevRowsMap?: Map<string, ServerMetricRow>
): { displayRows: ServerDisplayRow[]; kpis: StoreKPIs } {
  const visible = rows.filter((r) => !r.supportStaff && !isSupportStaff(r.server));
  const cardDf = visible.filter((r) => r.turnTime != null && r.dineInBevPct != null);
  const ppaAvailable = cardDf.some((r) => r.ppa != null);

  // Badge assignment
  const badgeMap = new Map<string, BadgeType>();

  if (cardDf.length > 0) {
    // Sort for top performer
    const sortedForTop = [...cardDf].sort((a, b) => {
      const passA =
        (isTurnGreen(a.turnTime) ? 1 : 0) +
        (isBevGreen(a.dineInBevPct) ? 1 : 0) +
        (ppaAvailable && isPpaGreen(a.ppa) ? 1 : 0);
      const passB =
        (isTurnGreen(b.turnTime) ? 1 : 0) +
        (isBevGreen(b.dineInBevPct) ? 1 : 0) +
        (ppaAvailable && isPpaGreen(b.ppa) ? 1 : 0);
      if (passB !== passA) return passB - passA;
      const ppaDiff = (b.ppa || 0) - (a.ppa || 0);
      if (ppaDiff !== 0) return ppaDiff;
      const bevDiff = (b.dineInBevPct || 0) - (a.dineInBevPct || 0);
      if (bevDiff !== 0) return bevDiff;
      const turnDiff = (a.turnTime || 999) - (b.turnTime || 999);
      if (turnDiff !== 0) return turnDiff;
      return a.server.localeCompare(b.server);
    });

    if (sortedForTop.length > 0) {
      badgeMap.set(sortedForTop[0].server, 'TOP PERFORMER');
    }

    // ALL GREEN
    for (const r of cardDf) {
      const allG =
        isTurnGreen(r.turnTime) &&
        isBevGreen(r.dineInBevPct) &&
        (ppaAvailable ? isPpaGreen(r.ppa) : true);
      if (allG && !badgeMap.has(r.server)) {
        badgeMap.set(r.server, 'ALL GREEN');
      }
    }

    // COACH
    for (const r of cardDf) {
      const coach =
        isTurnRed(r.turnTime) &&
        isBevRed(r.dineInBevPct) &&
        (ppaAvailable ? isPpaRed(r.ppa) : true);
      if (coach && !badgeMap.has(r.server)) {
        badgeMap.set(r.server, 'COACH');
      }
    }

    // SLOWEST TURN
    const turnTimes = cardDf.map((r) => r.turnTime).filter((t): t is number => t != null && !isNaN(t));
    if (turnTimes.length > 0) {
      const maxTurn = Math.max(...turnTimes);
      const slowest = cardDf.find((r) => r.turnTime === maxTurn);
      if (slowest && !badgeMap.has(slowest.server)) {
        badgeMap.set(slowest.server, 'SLOWEST TURN');
      }
    }
  }

  // Display rows
  const displayRows: ServerDisplayRow[] = visible.map((r) => {
    const isAllGreen =
      isTabletGreen(r.tabletPct) &&
      isTurnGreen(r.turnTime) &&
      isBevGreen(r.dineInBevPct) &&
      (ppaAvailable ? isPpaGreen(r.ppa) : true);
    const greensCount = calculateGreensCount(r);
    const badge = badgeMap.get(r.server) || null;

    let tabletTrendMarker = null;
    let turnTrendMarker = null;
    let bevTrendMarker = null;
    let ppaTrendMarker = null;

    if (prevRowsMap) {
      const prev = prevRowsMap.get(r.server);
      if (prev) {
        tabletTrendMarker = getTrendMarker(r.tabletPct, prev.tabletPct, prev.tabletWeight, 'tablet');
        turnTrendMarker = getTrendMarker(r.turnTime, prev.turnTime, prev.turnCheckCount, 'turn');
        bevTrendMarker = getTrendMarker(r.dineInBevPct, prev.dineInBevPct, prev.bevWeight, 'bev');
        ppaTrendMarker = getTrendMarker(r.ppa, prev.ppa, prev.ppaWeight, 'ppa');
      }
    }

    return {
      ...r,
      badge,
      isAllGreen,
      greensCount,
      tabletTrendMarker,
      turnTrendMarker,
      bevTrendMarker,
      ppaTrendMarker,
    };
  });

  // Sort rows: greens count desc, tablet desc, turn asc, bev desc, ppa desc, server asc
  displayRows.sort((a, b) => {
    if (b.greensCount !== a.greensCount) return b.greensCount - a.greensCount;
    const tabA = a.tabletPct ?? -1;
    const tabB = b.tabletPct ?? -1;
    if (tabB !== tabA) return tabB - tabA;
    const turnA = a.turnTime ?? 9999;
    const turnB = b.turnTime ?? 9999;
    if (turnA !== turnB) return turnA - turnB;
    const bevA = a.dineInBevPct ?? -1;
    const bevB = b.dineInBevPct ?? -1;
    if (bevB !== bevA) return bevB - bevA;
    const ppaA = a.ppa ?? -1;
    const ppaB = b.ppa ?? -1;
    if (ppaB !== ppaA) return ppaB - ppaA;
    return a.server.localeCompare(b.server);
  });

  // Calculate Store KPIs
  const avgTablet = weightedMean(rows.map((r) => ({ val: r.tabletPct, weight: r.tabletWeight }))) ??
    safeMean(rows.map((r) => r.tabletPct));
  const avgTurn = weightedMean(rows.map((r) => ({ val: r.turnTime, weight: r.turnCheckCount }))) ??
    safeMean(rows.map((r) => r.turnTime));
  const avgBev = weightedMean(rows.map((r) => ({ val: r.dineInBevPct, weight: r.bevWeight }))) ??
    safeMean(rows.map((r) => r.dineInBevPct));
  const avgPpa = weightedMean(rows.map((r) => ({ val: r.ppa, weight: r.ppaWeight }))) ??
    safeMean(rows.map((r) => r.ppa));

  // Rankings
  function getRank(
    accessor: (r: ServerDisplayRow) => number | null | undefined,
    ascending = false
  ): string {
    const valid = displayRows.filter((r) => accessor(r) != null && !isNaN(accessor(r)!));
    if (!valid.length) return 'No data';
    const sorted = [...valid].sort((a, b) => {
      const valA = accessor(a)!;
      const valB = accessor(b)!;
      return ascending ? valA - valB : valB - valA;
    });
    const bestVal = accessor(sorted[0])!;
    const tied = sorted.filter((r) => accessor(r) === bestVal);
    return tied.map((r) => r.server).join(' • ');
  }

  const topTabletServer = getRank((r) => r.tabletPct, false);
  const bottomTabletServer = getRank((r) => r.tabletPct, true);
  const bestTurnServer = getRank((r) => r.turnTime, true);
  const slowestTurnServer = getRank((r) => r.turnTime, false);
  const topBevServer = getRank((r) => r.dineInBevPct, false);
  const bottomBevServer = getRank((r) => r.dineInBevPct, true);
  const topPpaServer = getRank((r) => r.ppa, false);
  const bottomPpaServer = getRank((r) => r.ppa, true);

  const storeNumber = rows[0]?.store || '3231';

  return {
    displayRows,
    kpis: {
      storeNumber,
      storeLabel: getStoreLabel(storeNumber),
      avgTablet,
      avgTurn,
      avgBev,
      avgPpa,
      topTabletServer,
      bottomTabletServer,
      bestTurnServer,
      slowestTurnServer,
      topBevServer,
      bottomBevServer,
      topPpaServer,
      bottomPpaServer,
    },
  };
}
