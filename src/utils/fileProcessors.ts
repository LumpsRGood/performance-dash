import Papa from 'papaparse';
import * as XLSX from 'xlsx';
import { ServerMetricRow } from '../types';
import {
  cleanName,
  normalizeStoreNumber,
  isSupportStaff,
  STORE_MAP,
} from './calculations';

function pickCol(columns: string[], keywords: string[]): string | null {
  for (const col of columns) {
    const colLower = String(col).toLowerCase().trim();
    for (const key of keywords) {
      if (colLower.includes(key)) return col;
    }
  }
  return null;
}

function extractStoreNumber(text?: string | number | null): string {
  if (!text) return 'Unknown';
  const str = String(text).trim();
  const match = str.match(/IHOP\s*#\s*(\d{3,4})\b/i) ||
    str.match(/^\s*(\d{3,4})\s*[-–:]/) ||
    str.match(/^\s*(\d{3,4})(?:\.0)?\s*$/) ||
    str.match(/(?:site|id site|store)\D{0,10}(\d{3,4})\b/i);
  if (match) return normalizeStoreNumber(match[1]);

  const lower = str.toLowerCase();
  if (lower.includes('prattville')) return '3231';
  if (lower.includes('eastern') || lower.includes('montgomery')) return '4445';
  if (lower.includes('oxford')) return '4456';
  if (lower.includes('decatur')) return '4463';

  return normalizeStoreNumber(str);
}

// Parse Tray Orders (Tablet %)
export async function parseTrayOrders(file: File): Promise<ServerMetricRow[]> {
  return new Promise((resolve, reject) => {
    Papa.parse(file, {
      header: true,
      skipEmptyLines: true,
      complete: (results) => {
        try {
          const data = results.data as Record<string, any>[];
          if (!data.length) {
            resolve([]);
            return;
          }
          const headers = Object.keys(data[0]);
          const colDevice = pickCol(headers, ['device orders report', 'device orders', 'device']);
          const colServer = pickCol(headers, ['staff customer', 'server', 'employee', 'cashier']);
          const colBase = pickCol(headers, ['base (including disc.)', 'base', 'sales', 'amount']);
          const colStore = pickCol(headers, ['id site', 'site', 'store', 'location']);

          const aggMap = new Map<string, { store: string; server: string; handheld: number; pos: number }>();

          for (const row of data) {
            const rawServer = colServer ? row[colServer] : '';
            const server = cleanName(rawServer);
            if (!server || server.toLowerCase().includes('total')) continue;

            const store = colStore ? extractStoreNumber(row[colStore]) : extractStoreNumber(file.name);
            const dev = colDevice ? String(row[colDevice] || '').toLowerCase() : '';
            const isHandheld = dev.includes('handheld') || dev.includes('hand held');
            const isPos = dev.includes('pos');
            const baseVal = colBase ? parseFloat(String(row[colBase]).replace(/[$,]/g, '')) || 0 : 0;

            const key = `${store}_${server}`;
            if (!aggMap.has(key)) {
              aggMap.set(key, { store, server, handheld: 0, pos: 0 });
            }
            const cur = aggMap.get(key)!;
            if (isHandheld) cur.handheld += baseVal;
            else if (isPos) cur.pos += baseVal;
            else cur.pos += baseVal;
          }

          const rows: ServerMetricRow[] = [];
          for (const item of aggMap.values()) {
            const total = item.handheld + item.pos;
            const tabletPct = total > 0 ? item.handheld / total : 0;
            rows.push({
              store: item.store,
              server: item.server,
              tabletPct,
              tabletWeight: total,
              supportStaff: isSupportStaff(item.server),
            });
          }
          resolve(rows);
        } catch (err) {
          reject(err);
        }
      },
      error: (err) => reject(err),
    });
  });
}

// Parse Tray Checks (Turn Time)
export async function parseTrayChecks(file: File): Promise<ServerMetricRow[]> {
  const isExcel = file.name.endsWith('.xlsx') || file.name.endsWith('.xls');

  let rowsData: Record<string, any>[] = [];
  if (isExcel) {
    const arrayBuffer = await file.arrayBuffer();
    const workbook = XLSX.read(arrayBuffer, { type: 'array' });
    const firstSheet = workbook.Sheets[workbook.SheetNames[0]];
    rowsData = XLSX.utils.sheet_to_json(firstSheet);
  } else {
    rowsData = await new Promise((resolve, reject) => {
      Papa.parse(file, {
        header: true,
        skipEmptyLines: true,
        complete: (res) => resolve(res.data as Record<string, any>[]),
        error: (err) => reject(err),
      });
    });
  }

  if (!rowsData.length) return [];

  const headers = Object.keys(rowsData[0]);
  const colStore = pickCol(headers, ['id site', 'site', 'store', 'location']);
  const colOpen = pickCol(headers, ['opened', 'open', 'order start', 'start time', 'opened at']);
  const colClose = pickCol(headers, ['closed', 'close', 'order end', 'end time', 'closed at']);
  const colService = pickCol(headers, ['service', 'service type', 'order type']);
  const colServer = pickCol(headers, ['created by', 'server', 'server name', 'employee', 'cashier']);

  const aggMap = new Map<string, { store: string; server: string; totalTurnMinutes: number; count: number }>();

  for (const row of rowsData) {
    if (colService) {
      const sType = String(row[colService] || '').toLowerCase();
      if (!sType.includes('eat in') && !sType.includes('dine in')) {
        continue;
      }
    }

    const rawServer = colServer ? row[colServer] : '';
    const server = cleanName(rawServer);
    if (!server || server.toLowerCase().includes('total')) continue;

    const store = colStore ? extractStoreNumber(row[colStore]) : extractStoreNumber(file.name);

    if (!colOpen || !colClose) continue;
    const openTime = new Date(row[colOpen]).getTime();
    const closeTime = new Date(row[colClose]).getTime();
    if (isNaN(openTime) || isNaN(closeTime) || closeTime < openTime) continue;

    const diffMinutes = (closeTime - openTime) / (1000 * 60);
    if (diffMinutes < 0 || diffMinutes > 300) continue; // Skip anomalies

    const key = `${store}_${server}`;
    if (!aggMap.has(key)) {
      aggMap.set(key, { store, server, totalTurnMinutes: 0, count: 0 });
    }
    const cur = aggMap.get(key)!;
    cur.totalTurnMinutes += diffMinutes;
    cur.count += 1;
  }

  const result: ServerMetricRow[] = [];
  for (const item of aggMap.values()) {
    result.push({
      store: item.store,
      server: item.server,
      turnTime: Number((item.totalTurnMinutes / item.count).toFixed(2)),
      turnCheckCount: item.count,
      supportStaff: isSupportStaff(item.server),
    });
  }

  return result;
}

// Parse Rosnet Beverage
export async function parseRosnetBeverage(file: File): Promise<ServerMetricRow[]> {
  let rowsData: Record<string, any>[] = [];
  if (file.name.endsWith('.xlsx') || file.name.endsWith('.xls')) {
    const arrayBuffer = await file.arrayBuffer();
    const workbook = XLSX.read(arrayBuffer, { type: 'array' });
    const sheetName = workbook.SheetNames.includes('Employee Summary')
      ? 'Employee Summary'
      : workbook.SheetNames[0];
    const sheet = workbook.Sheets[sheetName];
    const rawMatrix = XLSX.utils.sheet_to_json(sheet, { header: 1 }) as any[][];
    // Find header row with required terms
    let headerIdx = 0;
    for (let i = 0; i < Math.min(10, rawMatrix.length); i++) {
      const rowStr = JSON.stringify(rawMatrix[i]).toLowerCase();
      if (rowStr.includes('location') && rowStr.includes('employee') && rowStr.includes('%')) {
        headerIdx = i;
        break;
      }
    }
    const headers = (rawMatrix[headerIdx] as string[]).map((h) => String(h).trim());
    const dataRows = rawMatrix.slice(headerIdx + 1);
    rowsData = dataRows.map((r: any[]) => {
      const obj: Record<string, any> = {};
      headers.forEach((h, idx) => {
        obj[h] = r[idx];
      });
      return obj;
    });
  } else {
    rowsData = await new Promise((resolve, reject) => {
      Papa.parse(file, {
        header: true,
        skipEmptyLines: true,
        complete: (res) => resolve(res.data as Record<string, any>[]),
        error: (err) => reject(err),
      });
    });
  }

  if (!rowsData.length) return [];

  const headers = Object.keys(rowsData[0]);
  const colStore = pickCol(headers, ['location']);
  const colServer = pickCol(headers, ['employee']);
  const colBev = pickCol(headers, ['% of net sales', '% net sales', 'bev %', 'beverage %']);
  const colNetSales = pickCol(headers, ['net sales', 'net sls', 'sales']);

  const result: ServerMetricRow[] = [];
  for (const row of rowsData) {
    const rawServer = colServer ? String(row[colServer] || '') : '';
    // Strip employee id like "123 - John Doe"
    const cleanedIdServer = rawServer.replace(/^\d+\s*-\s*/, '');
    const server = cleanName(cleanedIdServer);
    if (!server || server.toLowerCase().includes('total')) continue;

    const store = colStore ? extractStoreNumber(row[colStore]) : extractStoreNumber(file.name);
    let rawBev = colBev ? parseFloat(String(row[colBev]).replace(/[%$,]/g, '')) : null;
    if (rawBev != null && !isNaN(rawBev)) {
      if (rawBev > 1) rawBev = rawBev / 100;
    }
    const netSales = colNetSales
      ? parseFloat(String(row[colNetSales]).replace(/[$,]/g, '')) || 0
      : 0;

    result.push({
      store,
      server,
      dineInBevPct: rawBev,
      bevWeight: netSales,
      supportStaff: isSupportStaff(server),
    });
  }

  return result;
}

// Parse PPA File
export async function parseEmployeePpa(file: File): Promise<ServerMetricRow[]> {
  let rowsData: Record<string, any>[] = [];
  if (file.name.endsWith('.xlsx') || file.name.endsWith('.xls')) {
    const arrayBuffer = await file.arrayBuffer();
    const workbook = XLSX.read(arrayBuffer, { type: 'array' });
    const sheet = workbook.Sheets[workbook.SheetNames[0]];
    const rawMatrix = XLSX.utils.sheet_to_json(sheet, { header: 1 }) as any[][];
    let headerIdx = 0;
    for (let i = 0; i < Math.min(10, rawMatrix.length); i++) {
      const rowStr = JSON.stringify(rawMatrix[i]).toLowerCase();
      if (rowStr.includes('location') && rowStr.includes('employee') && (rowStr.includes('ppa') || rowStr.includes('covers'))) {
        headerIdx = i;
        break;
      }
    }
    const headers = (rawMatrix[headerIdx] as string[]).map((h) => String(h).trim());
    const dataRows = rawMatrix.slice(headerIdx + 1);
    rowsData = dataRows.map((r: any[]) => {
      const obj: Record<string, any> = {};
      headers.forEach((h, idx) => {
        obj[h] = r[idx];
      });
      return obj;
    });
  } else {
    rowsData = await new Promise((resolve, reject) => {
      Papa.parse(file, {
        header: true,
        skipEmptyLines: true,
        complete: (res) => resolve(res.data as Record<string, any>[]),
        error: (err) => reject(err),
      });
    });
  }

  if (!rowsData.length) return [];

  const headers = Object.keys(rowsData[0]);
  const colStore = pickCol(headers, ['location']);
  const colServer = pickCol(headers, ['employee name', 'employee']);
  const colNetSales = pickCol(headers, ['net sales', 'sales']);
  const colCovers = pickCol(headers, ['covers', 'guest count', 'guests']);
  const colPpa = pickCol(headers, ['ppa']);

  const result: ServerMetricRow[] = [];
  for (const row of rowsData) {
    const rawServer = colServer ? String(row[colServer] || '') : '';
    const cleanedIdServer = rawServer.replace(/^\d+\s*-\s*/, '');
    const server = cleanName(cleanedIdServer);
    if (!server || server.toLowerCase().includes('total')) continue;

    const store = colStore ? extractStoreNumber(row[colStore]) : extractStoreNumber(file.name);
    const netSales = colNetSales ? parseFloat(String(row[colNetSales]).replace(/[$,]/g, '')) || 0 : 0;
    const covers = colCovers ? parseFloat(String(row[colCovers]).replace(/[,]/g, '')) || 0 : 0;
    let ppa = colPpa ? parseFloat(String(row[colPpa]).replace(/[$,]/g, '')) : null;
    if ((ppa == null || isNaN(ppa)) && covers > 0) {
      ppa = netSales / covers;
    }

    result.push({
      store,
      server,
      ppa: ppa != null && !isNaN(ppa) ? Number(ppa.toFixed(2)) : null,
      ppaWeight: covers,
      netSales,
      supportStaff: isSupportStaff(server),
    });
  }

  return result;
}

// Merge multiple uploaded metric datasets
export function mergeUploadedDatasets(
  tabletRows: ServerMetricRow[],
  turnRows: ServerMetricRow[],
  bevRows: ServerMetricRow[],
  ppaRows: ServerMetricRow[]
): ServerMetricRow[] {
  const mergedMap = new Map<string, ServerMetricRow>();

  function addOrMerge(row: ServerMetricRow) {
    const key = `${row.store}_${row.server}`;
    if (!mergedMap.has(key)) {
      mergedMap.set(key, { ...row });
    } else {
      const existing = mergedMap.get(key)!;
      if (row.tabletPct != null) {
        existing.tabletPct = row.tabletPct;
        existing.tabletWeight = row.tabletWeight;
      }
      if (row.turnTime != null) {
        existing.turnTime = row.turnTime;
        existing.turnCheckCount = row.turnCheckCount;
      }
      if (row.dineInBevPct != null) {
        existing.dineInBevPct = row.dineInBevPct;
        existing.bevWeight = row.bevWeight;
      }
      if (row.ppa != null) {
        existing.ppa = row.ppa;
        existing.ppaWeight = row.ppaWeight;
        existing.netSales = row.netSales;
      }
      if (row.supportStaff != null) {
        existing.supportStaff = existing.supportStaff || row.supportStaff;
      }
    }
  }

  tabletRows.forEach(addOrMerge);
  turnRows.forEach(addOrMerge);
  bevRows.forEach(addOrMerge);
  ppaRows.forEach(addOrMerge);

  return Array.from(mergedMap.values());
}
