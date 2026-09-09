import { ServerDisplayRow, StoreKPIs } from '../types';
import { getTabletColor, getTurnColor, getBevColor, getPpaColor } from './calculations';

export async function generateWhatsAppCardPng(
  storeLabel: string,
  displayRows: ServerDisplayRow[],
  kpis: StoreKPIs,
  subtitle?: string,
  trendNote?: string
): Promise<string> {
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('Cannot get canvas context');

  const width = 850;
  const rowHeight = 36;
  const visibleRows = displayRows.filter((r) => r.turnTime != null || r.dineInBevPct != null);
  const rowCount = Math.max(visibleRows.length, 1);
  const tableHeight = 44 + rowCount * rowHeight;
  const height = Math.max(920, 360 + tableHeight + 110 + (trendNote ? 40 : 0));

  canvas.width = width;
  canvas.height = height;

  // Background
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, width, height);

  // Outer border
  ctx.strokeStyle = '#d7dee8';
  ctx.lineWidth = 2;
  ctx.strokeRect(10, 10, width - 20, height - 20);

  // Header banner
  const headerHeight = 84;
  ctx.fillStyle = '#1d4f91';
  ctx.fillRect(10, 10, width - 20, headerHeight);

  // Header text
  ctx.fillStyle = '#ffffff';
  ctx.font = 'bold 24px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText(storeLabel, width / 2, subtitle ? 45 : 55);

  if (subtitle) {
    ctx.fillStyle = '#dbeafe';
    ctx.font = 'italic bold 13px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
    ctx.fillText(subtitle, width / 2, 72);
  }

  // 4 KPI Summary Boxes
  const boxY = 112;
  const boxW = 185;
  const boxH = 100;
  const boxGap = 16;
  const startX = 32;

  const boxes = [
    {
      title: 'TABLET USE',
      value: kpis.avgTablet != null ? `${(kpis.avgTablet * 100).toFixed(2)}%` : 'No data',
      color: getTabletColor(kpis.avgTablet),
      trend: kpis.tabletTrend,
    },
    {
      title: 'TURN',
      value: kpis.avgTurn != null ? kpis.avgTurn.toFixed(2) : 'No data',
      color: getTurnColor(kpis.avgTurn),
      trend: kpis.turnTrend,
    },
    {
      title: 'BEVERAGE',
      value: kpis.avgBev != null ? `${(kpis.avgBev * 100).toFixed(2)}%` : 'No data',
      color: getBevColor(kpis.avgBev),
      trend: kpis.bevTrend,
    },
    {
      title: 'PPA',
      value: kpis.avgPpa != null ? `$${kpis.avgPpa.toFixed(2)}` : 'No data',
      color: getPpaColor(kpis.avgPpa),
      trend: kpis.ppaTrend,
    },
  ];

  boxes.forEach((box, i) => {
    const x = startX + i * (boxW + boxGap);
    // Box background
    ctx.fillStyle = box.color.bg;
    ctx.fillRect(x, boxY, boxW, boxH);
    ctx.strokeStyle = '#cfd9e6';
    ctx.lineWidth = 1;
    ctx.strokeRect(x, boxY, boxW, boxH);

    // Box title
    ctx.fillStyle = box.color.bg === '#ff6b6b' ? '#ffffff' : '#ffffff';
    // Draw small title header strip or top title
    ctx.fillStyle = '#1d4f91';
    ctx.fillRect(x, boxY, boxW, 26);
    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 12px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(box.title, x + boxW / 2, boxY + 18);

    // Metric value
    ctx.fillStyle = box.color.text;
    ctx.font = 'bold 22px sans-serif';
    ctx.fillText(box.value, x + boxW / 2, boxY + 62);

    // Delta / Trend text
    if (box.trend) {
      ctx.fillStyle = box.trend.color;
      ctx.font = 'bold 11px sans-serif';
      ctx.fillText(box.trend.text, x + boxW / 2, boxY + 86);
    }
  });

  // Table
  const tableY = 236;
  const tableX = 32;
  const tableW = width - 64;
  const colWidths = [tableW * 0.32, tableW * 0.17, tableW * 0.17, tableW * 0.17, tableW * 0.17];
  const colX = [
    tableX,
    tableX + colWidths[0],
    tableX + colWidths[0] + colWidths[1],
    tableX + colWidths[0] + colWidths[1] + colWidths[2],
    tableX + colWidths[0] + colWidths[1] + colWidths[2] + colWidths[3],
  ];

  // Table Header
  ctx.fillStyle = '#2d6cb5';
  ctx.fillRect(tableX, tableY, tableW, 38);
  ctx.strokeStyle = '#d7dee8';
  ctx.strokeRect(tableX, tableY, tableW, 38);

  const headers = ['Server', 'Tablet %', 'Turn Time', 'Dine In Bev %', 'PPA'];
  ctx.fillStyle = '#ffffff';
  ctx.font = 'bold 13px sans-serif';
  headers.forEach((h, i) => {
    ctx.textAlign = i === 0 ? 'left' : 'center';
    const textX = i === 0 ? colX[i] + 16 : colX[i] + colWidths[i] / 2;
    ctx.fillText(h, textX, tableY + 24);
  });

  // Load badge images if needed
  const iconImages: Record<string, HTMLImageElement> = {};
  const badgeTypes = ['TOP PERFORMER', 'ALL GREEN', 'COACH', 'SLOWEST TURN'];
  await Promise.all(
    badgeTypes.map((type) => {
      return new Promise<void>((resolve) => {
        const img = new Image();
        const fileMap: Record<string, string> = {
          'TOP PERFORMER': '/assets/icons/top_performer.png',
          'ALL GREEN': '/assets/icons/all_green.png',
          'COACH': '/assets/icons/coach.png',
          'SLOWEST TURN': '/assets/icons/slowest_turn.png',
        };
        img.src = fileMap[type];
        img.onload = () => {
          iconImages[type] = img;
          resolve();
        };
        img.onerror = () => resolve();
      });
    })
  );

  // Table Rows
  let curY = tableY + 38;
  if (visibleRows.length === 0) {
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(tableX, curY, tableW, rowHeight);
    ctx.strokeStyle = '#dfe5ec';
    ctx.strokeRect(tableX, curY, tableW, rowHeight);
    ctx.fillStyle = '#64748b';
    ctx.font = '13px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('No dine-in server rows', tableX + tableW / 2, curY + 23);
    curY += rowHeight;
  } else {
    visibleRows.forEach((row, rIdx) => {
      // Background alternating
      const isEven = rIdx % 2 === 0;
      ctx.fillStyle = row.isAllGreen ? '#e8f5e9' : isEven ? '#ffffff' : '#fbfcfe';
      ctx.fillRect(tableX, curY, tableW, rowHeight);

      // Server Cell
      ctx.strokeStyle = '#dfe5ec';
      ctx.strokeRect(colX[0], curY, colWidths[0], rowHeight);

      ctx.fillStyle = '#111827';
      ctx.font = 'bold 12.5px sans-serif';
      ctx.textAlign = 'left';
      ctx.fillText(row.server, colX[0] + 14, curY + 23);

      // Badge Icon next to server name
      if (row.badge && iconImages[row.badge]) {
        const icon = iconImages[row.badge];
        const iconSize = 22;
        ctx.drawImage(
          icon,
          colX[0] + colWidths[0] - iconSize - 10,
          curY + (rowHeight - iconSize) / 2,
          iconSize,
          iconSize
        );
      }

      // Tablet Cell
      const tabCol = getTabletColor(row.tabletPct);
      ctx.fillStyle = tabCol.bg;
      ctx.fillRect(colX[1], curY, colWidths[1], rowHeight);
      ctx.strokeRect(colX[1], curY, colWidths[1], rowHeight);
      ctx.fillStyle = tabCol.text;
      ctx.font = 'bold 12.5px sans-serif';
      ctx.textAlign = 'center';
      const tabText = row.tabletPct != null ? `${(row.tabletPct * 100).toFixed(2)}%` : '-';
      ctx.fillText(tabText, colX[1] + colWidths[1] / 2, curY + 23);
      if (row.tabletTrendMarker) {
        ctx.fillStyle = row.tabletTrendMarker.color;
        ctx.fillText(row.tabletTrendMarker.symbol, colX[1] + colWidths[1] - 12, curY + 23);
      }

      // Turn Cell
      const turnCol = getTurnColor(row.turnTime);
      ctx.fillStyle = turnCol.bg;
      ctx.fillRect(colX[2], curY, colWidths[2], rowHeight);
      ctx.strokeRect(colX[2], curY, colWidths[2], rowHeight);
      ctx.fillStyle = turnCol.text;
      ctx.font = 'bold 12.5px sans-serif';
      ctx.textAlign = 'center';
      const turnText = row.turnTime != null ? row.turnTime.toFixed(2) : '-';
      ctx.fillText(turnText, colX[2] + colWidths[2] / 2, curY + 23);
      if (row.turnTrendMarker) {
        ctx.fillStyle = row.turnTrendMarker.color;
        ctx.fillText(row.turnTrendMarker.symbol, colX[2] + colWidths[2] - 12, curY + 23);
      }

      // Beverage Cell
      const bevCol = getBevColor(row.dineInBevPct);
      ctx.fillStyle = bevCol.bg;
      ctx.fillRect(colX[3], curY, colWidths[3], rowHeight);
      ctx.strokeRect(colX[3], curY, colWidths[3], rowHeight);
      ctx.fillStyle = bevCol.text;
      ctx.font = 'bold 12.5px sans-serif';
      ctx.textAlign = 'center';
      const bevText = row.dineInBevPct != null ? `${(row.dineInBevPct * 100).toFixed(2)}%` : '-';
      ctx.fillText(bevText, colX[3] + colWidths[3] / 2, curY + 23);
      if (row.bevTrendMarker) {
        ctx.fillStyle = row.bevTrendMarker.color;
        ctx.fillText(row.bevTrendMarker.symbol, colX[3] + colWidths[3] - 12, curY + 23);
      }

      // PPA Cell
      const ppaCol = getPpaColor(row.ppa);
      ctx.fillStyle = ppaCol.bg;
      ctx.fillRect(colX[4], curY, colWidths[4], rowHeight);
      ctx.strokeRect(colX[4], curY, colWidths[4], rowHeight);
      ctx.fillStyle = ppaCol.text;
      ctx.font = 'bold 12.5px sans-serif';
      ctx.textAlign = 'center';
      const ppaText = row.ppa != null ? `$${row.ppa.toFixed(2)}` : '-';
      ctx.fillText(ppaText, colX[4] + colWidths[4] / 2, curY + 23);
      if (row.ppaTrendMarker) {
        ctx.fillStyle = row.ppaTrendMarker.color;
        ctx.fillText(row.ppaTrendMarker.symbol, colX[4] + colWidths[4] - 12, curY + 23);
      }

      curY += rowHeight;
    });
  }

  // Legend Area
  let legendY = curY + 28;
  const legendItems = [
    { label: 'Top Performer', type: 'TOP PERFORMER' },
    { label: 'All Green', type: 'ALL GREEN' },
    { label: 'Slowest Turn', type: 'SLOWEST TURN' },
    { label: 'Needs Coaching (missed Turn, Bev %, and PPA)', type: 'COACH' },
  ];

  // First 3 items
  const leg1 = legendItems.slice(0, 3);
  const leg1X = [tableX + 40, tableX + 280, tableX + 520];
  leg1.forEach((item, i) => {
    const x = leg1X[i];
    if (iconImages[item.type]) {
      ctx.drawImage(iconImages[item.type], x, legendY - 14, 20, 20);
    }
    ctx.fillStyle = '#334155';
    ctx.font = '12px sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText(item.label, x + 26, legendY);
  });

  // Second row (Coach)
  legendY += 26;
  const coachItem = legendItems[3];
  const coachX = tableX + 200;
  if (iconImages[coachItem.type]) {
    ctx.drawImage(iconImages[coachItem.type], coachX, legendY - 14, 20, 20);
  }
  ctx.fillStyle = '#334155';
  ctx.font = '12px sans-serif';
  ctx.textAlign = 'left';
  ctx.fillText(coachItem.label, coachX + 26, legendY);

  // Trend note
  if (trendNote) {
    legendY += 30;
    ctx.fillStyle = '#64748b';
    ctx.font = '11.5px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(trendNote, width / 2, legendY);
  }

  return canvas.toDataURL('image/png');
}
