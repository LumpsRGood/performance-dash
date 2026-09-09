import React, { useState } from 'react';
import { Download, Eye, X, Image as ImageIcon } from 'lucide-react';
import { ServerDisplayRow, StoreKPIs } from '../types';
import { getTabletColor, getTurnColor, getBevColor, getPpaColor } from '../utils/calculations';
import { generateWhatsAppCardPng } from '../utils/cardGenerator';

interface StoreSectionProps {
  kpis: StoreKPIs;
  displayRows: ServerDisplayRow[];
  subtitle?: string;
  trendNote?: string;
}

const BADGE_CONFIG = {
  'TOP PERFORMER': {
    label: 'Top Performer',
    icon: '/assets/icons/top_performer.png',
    bg: 'bg-purple-100 text-purple-800 border-purple-300',
  },
  'ALL GREEN': {
    label: 'All Green',
    icon: '/assets/icons/all_green.png',
    bg: 'bg-emerald-100 text-emerald-800 border-emerald-300',
  },
  'COACH': {
    label: 'Needs Coaching',
    icon: '/assets/icons/coach.png',
    bg: 'bg-amber-100 text-amber-900 border-amber-300',
  },
  'SLOWEST TURN': {
    label: 'Slowest Turn',
    icon: '/assets/icons/slowest_turn.png',
    bg: 'bg-rose-100 text-rose-800 border-rose-300',
  },
};

export const StoreSection: React.FC<StoreSectionProps> = ({
  kpis,
  displayRows,
  subtitle,
  trendNote,
}) => {
  const [isGenerating, setIsGenerating] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  const handleDownloadCard = async () => {
    try {
      setIsGenerating(true);
      const dataUrl = await generateWhatsAppCardPng(
        kpis.storeLabel,
        displayRows,
        kpis,
        subtitle,
        trendNote
      );
      const safeName = kpis.storeLabel.replace(/\s+/g, '_').replace(/-/g, '_');
      const link = document.createElement('a');
      link.href = dataUrl;
      link.download = `${safeName}_whatsapp_card.png`;
      link.click();
    } catch (err) {
      console.error('Failed to generate card:', err);
    } finally {
      setIsGenerating(false);
    }
  };

  const handlePreviewCard = async () => {
    try {
      setIsGenerating(true);
      const dataUrl = await generateWhatsAppCardPng(
        kpis.storeLabel,
        displayRows,
        kpis,
        subtitle,
        trendNote
      );
      setPreviewUrl(dataUrl);
    } catch (err) {
      console.error('Failed to preview card:', err);
    } finally {
      setIsGenerating(false);
    }
  };

  const tabletColor = getTabletColor(kpis.avgTablet);
  const turnColor = getTurnColor(kpis.avgTurn);
  const bevColor = getBevColor(kpis.avgBev);
  const ppaColor = getPpaColor(kpis.avgPpa);

  return (
    <section className="mb-12 bg-white rounded-xl border border-slate-200 shadow-sm p-5 sm:p-6">
      {/* Store Title */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between pb-4 border-b border-slate-200 gap-3">
        <div>
          <h2 className="text-xl sm:text-2xl font-bold text-slate-900 flex items-center gap-2">
            <span>📍</span>
            <span>{kpis.storeLabel}</span>
          </h2>
          {subtitle && <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>}
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handlePreviewCard}
            disabled={isGenerating}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-50 text-slate-700 text-xs font-semibold shadow-xs transition-colors disabled:opacity-50"
          >
            <Eye className="w-3.5 h-3.5 text-slate-500" />
            Preview Card
          </button>
          <button
            type="button"
            onClick={handleDownloadCard}
            disabled={isGenerating}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-[#1d4f91] hover:bg-[#153e73] text-white text-xs font-semibold shadow-xs transition-colors disabled:opacity-50"
          >
            <Download className="w-3.5 h-3.5" />
            {isGenerating ? 'Generating...' : `Download ${kpis.storeLabel.split(' - ')[0]} WhatsApp Card`}
          </button>
        </div>
      </div>

      {/* 4 KPI Columns */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 my-6">
        {/* Tablet KPI */}
        <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-4">
          <span className="text-xs font-semibold text-slate-500 tracking-wide uppercase">
            Avg Tablet %
          </span>
          <div className="mt-1 flex items-baseline gap-2">
            <span
              className="text-2xl font-bold px-2 py-0.5 rounded-md"
              style={{ backgroundColor: tabletColor.bg, color: tabletColor.text }}
            >
              {kpis.avgTablet != null ? `${(kpis.avgTablet * 100).toFixed(2)}%` : 'No data'}
            </span>
            {kpis.tabletTrend && (
              <span className="text-xs font-semibold" style={{ color: kpis.tabletTrend.color }}>
                {kpis.tabletTrend.text}
              </span>
            )}
          </div>
          <div className="mt-3 text-xs text-slate-600 space-y-0.5">
            <div>
              <strong className="text-slate-800">Top:</strong> {kpis.topTabletServer || 'No data'}
            </div>
            <div>
              <strong className="text-slate-800">Bottom:</strong> {kpis.bottomTabletServer || 'No data'}
            </div>
          </div>
        </div>

        {/* Turn KPI */}
        <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-4">
          <span className="text-xs font-semibold text-slate-500 tracking-wide uppercase">
            Avg Turn
          </span>
          <div className="mt-1 flex items-baseline gap-2">
            <span
              className="text-2xl font-bold px-2 py-0.5 rounded-md"
              style={{ backgroundColor: turnColor.bg, color: turnColor.text }}
            >
              {kpis.avgTurn != null ? kpis.avgTurn.toFixed(2) : 'No data'}
            </span>
            {kpis.turnTrend && (
              <span className="text-xs font-semibold" style={{ color: kpis.turnTrend.color }}>
                {kpis.turnTrend.text}
              </span>
            )}
          </div>
          <div className="mt-3 text-xs text-slate-600 space-y-0.5">
            <div>
              <strong className="text-slate-800">Best:</strong> {kpis.bestTurnServer || 'No data'}
            </div>
            <div>
              <strong className="text-slate-800">Slowest:</strong> {kpis.slowestTurnServer || 'No data'}
            </div>
          </div>
        </div>

        {/* Dine In Bev % KPI */}
        <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-4">
          <span className="text-xs font-semibold text-slate-500 tracking-wide uppercase">
            Avg Dine In Bev %
          </span>
          <div className="mt-1 flex items-baseline gap-2">
            <span
              className="text-2xl font-bold px-2 py-0.5 rounded-md"
              style={{ backgroundColor: bevColor.bg, color: bevColor.text }}
            >
              {kpis.avgBev != null ? `${(kpis.avgBev * 100).toFixed(2)}%` : 'No data'}
            </span>
            {kpis.bevTrend && (
              <span className="text-xs font-semibold" style={{ color: kpis.bevTrend.color }}>
                {kpis.bevTrend.text}
              </span>
            )}
          </div>
          <div className="mt-3 text-xs text-slate-600 space-y-0.5">
            <div>
              <strong className="text-slate-800">Top:</strong> {kpis.topBevServer || 'No data'}
            </div>
            <div>
              <strong className="text-slate-800">Bottom:</strong> {kpis.bottomBevServer || 'No data'}
            </div>
          </div>
        </div>

        {/* PPA KPI */}
        <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-4">
          <span className="text-xs font-semibold text-slate-500 tracking-wide uppercase">
            Avg PPA
          </span>
          <div className="mt-1 flex items-baseline gap-2">
            <span
              className="text-2xl font-bold px-2 py-0.5 rounded-md"
              style={{ backgroundColor: ppaColor.bg, color: ppaColor.text }}
            >
              {kpis.avgPpa != null ? `$${kpis.avgPpa.toFixed(2)}` : 'No data'}
            </span>
            {kpis.ppaTrend && (
              <span className="text-xs font-semibold" style={{ color: kpis.ppaTrend.color }}>
                {kpis.ppaTrend.text}
              </span>
            )}
          </div>
          <div className="mt-3 text-xs text-slate-600 space-y-0.5">
            <div>
              <strong className="text-slate-800">Top:</strong> {kpis.topPpaServer || 'No data'}
            </div>
            <div>
              <strong className="text-slate-800">Bottom:</strong> {kpis.bottomPpaServer || 'No data'}
            </div>
          </div>
        </div>
      </div>

      {/* Server Performance Table */}
      <div className="overflow-x-auto rounded-lg border border-slate-200">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-[#2d6cb5] text-white">
            <tr>
              <th className="px-4 py-3 text-left font-bold text-xs uppercase tracking-wider">
                Server
              </th>
              <th className="px-4 py-3 text-center font-bold text-xs uppercase tracking-wider">
                Tablet %
              </th>
              <th className="px-4 py-3 text-center font-bold text-xs uppercase tracking-wider">
                Turn Time
              </th>
              <th className="px-4 py-3 text-center font-bold text-xs uppercase tracking-wider">
                Dine In Bev %
              </th>
              <th className="px-4 py-3 text-center font-bold text-xs uppercase tracking-wider">
                PPA
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 bg-white">
            {displayRows.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-slate-400">
                  No server data available
                </td>
              </tr>
            ) : (
              displayRows.map((row, idx) => {
                const tabC = getTabletColor(row.tabletPct);
                const turnC = getTurnColor(row.turnTime);
                const bevC = getBevColor(row.dineInBevPct);
                const ppaC = getPpaColor(row.ppa);

                return (
                  <tr
                    key={idx}
                    className={`transition-colors ${
                      row.isAllGreen ? 'bg-[#e8f5e9] hover:bg-[#dcedc8]' : 'hover:bg-slate-50'
                    }`}
                  >
                    {/* Server Name + Badges */}
                    <td className="px-4 py-2.5 font-medium text-slate-900 flex items-center justify-between gap-2">
                      <span className="truncate">{row.server}</span>
                      {row.badge && BADGE_CONFIG[row.badge] && (
                        <div
                          className="flex items-center gap-1.5 flex-shrink-0"
                          title={BADGE_CONFIG[row.badge].label}
                        >
                          <img
                            src={BADGE_CONFIG[row.badge].icon}
                            alt={row.badge}
                            className="w-5 h-5 object-contain"
                          />
                          <span
                            className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${
                              BADGE_CONFIG[row.badge].bg
                            }`}
                          >
                            {BADGE_CONFIG[row.badge].label}
                          </span>
                        </div>
                      )}
                    </td>

                    {/* Tablet % */}
                    <td className="px-4 py-2.5 text-center">
                      <div className="inline-flex items-center justify-center gap-1 min-w-[72px]">
                        <span
                          className="font-bold text-xs px-2.5 py-1 rounded-md"
                          style={{ backgroundColor: tabC.bg, color: tabC.text }}
                        >
                          {row.tabletPct != null
                            ? `${(row.tabletPct * 100).toFixed(2)}%`
                            : '-'}
                        </span>
                        {row.tabletTrendMarker && (
                          <span
                            className="text-xs font-bold"
                            style={{ color: row.tabletTrendMarker.color }}
                          >
                            {row.tabletTrendMarker.symbol}
                          </span>
                        )}
                      </div>
                    </td>

                    {/* Turn Time */}
                    <td className="px-4 py-2.5 text-center">
                      <div className="inline-flex items-center justify-center gap-1 min-w-[64px]">
                        <span
                          className="font-bold text-xs px-2.5 py-1 rounded-md"
                          style={{ backgroundColor: turnC.bg, color: turnC.text }}
                        >
                          {row.turnTime != null ? row.turnTime.toFixed(2) : '-'}
                        </span>
                        {row.turnTrendMarker && (
                          <span
                            className="text-xs font-bold"
                            style={{ color: row.turnTrendMarker.color }}
                          >
                            {row.turnTrendMarker.symbol}
                          </span>
                        )}
                      </div>
                    </td>

                    {/* Dine In Bev % */}
                    <td className="px-4 py-2.5 text-center">
                      <div className="inline-flex items-center justify-center gap-1 min-w-[72px]">
                        <span
                          className="font-bold text-xs px-2.5 py-1 rounded-md"
                          style={{ backgroundColor: bevC.bg, color: bevC.text }}
                        >
                          {row.dineInBevPct != null
                            ? `${(row.dineInBevPct * 100).toFixed(2)}%`
                            : '-'}
                        </span>
                        {row.bevTrendMarker && (
                          <span
                            className="text-xs font-bold"
                            style={{ color: row.bevTrendMarker.color }}
                          >
                            {row.bevTrendMarker.symbol}
                          </span>
                        )}
                      </div>
                    </td>

                    {/* PPA */}
                    <td className="px-4 py-2.5 text-center">
                      <div className="inline-flex items-center justify-center gap-1 min-w-[68px]">
                        <span
                          className="font-bold text-xs px-2.5 py-1 rounded-md"
                          style={{ backgroundColor: ppaC.bg, color: ppaC.text }}
                        >
                          {row.ppa != null ? `$${row.ppa.toFixed(2)}` : '-'}
                        </span>
                        {row.ppaTrendMarker && (
                          <span
                            className="text-xs font-bold"
                            style={{ color: row.ppaTrendMarker.color }}
                          >
                            {row.ppaTrendMarker.symbol}
                          </span>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* WhatsApp Card Preview Modal */}
      {previewUrl && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full max-h-[90vh] flex flex-col overflow-hidden border border-slate-200">
            <div className="p-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <div className="flex items-center gap-2">
                <ImageIcon className="w-5 h-5 text-blue-600" />
                <h3 className="font-bold text-sm text-slate-900">
                  {kpis.storeLabel} - WhatsApp Store Card
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setPreviewUrl(null)}
                className="p-1 rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-200 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-4 overflow-y-auto flex justify-center bg-slate-100">
              <img
                src={previewUrl}
                alt="WhatsApp Card Preview"
                className="max-w-full rounded-lg shadow-md border border-slate-300"
              />
            </div>

            <div className="p-4 border-t border-slate-200 flex justify-end gap-2 bg-white">
              <button
                type="button"
                onClick={() => setPreviewUrl(null)}
                className="px-3.5 py-1.5 text-xs font-medium text-slate-600 hover:text-slate-800 rounded-md"
              >
                Close
              </button>
              <button
                type="button"
                onClick={handleDownloadCard}
                className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg bg-[#1d4f91] hover:bg-[#153e73] text-white text-xs font-semibold shadow-xs"
              >
                <Download className="w-3.5 h-3.5" />
                Download PNG
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
};
