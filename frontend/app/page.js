'use client';
import { useEffect, useState, useMemo } from 'react';
import Link from 'next/link';

import { API } from '@/lib/api';
import { HouseDivider, HouseButton } from '@/components/HouseDecor';

/* ─── SVG Icons ─── */
function IconSearch({ className = "w-5 h-5" }) {
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" /></svg>;
}
function IconTrendingUp({ className = "w-4 h-4" }) {
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17" /><polyline points="16 7 22 7 22 13" /></svg>;
}
function IconArrowRight({ className = "w-4 h-4" }) {
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" /></svg>;
}
function IconBuilding({ className = "w-4 h-4" }) {
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="4" y="2" width="16" height="20" rx="2" /><path d="M9 22v-4h6v4" /><line x1="8" y1="6" x2="8" y2="6" /><line x1="12" y1="6" x2="12" y2="6" /><line x1="16" y1="6" x2="16" y2="6" /><line x1="8" y1="10" x2="8" y2="10" /><line x1="12" y1="10" x2="12" y2="10" /><line x1="16" y1="10" x2="16" y2="10" /><line x1="8" y1="14" x2="8" y2="14" /><line x1="12" y1="14" x2="12" y2="14" /><line x1="16" y1="14" x2="16" y2="14" /></svg>;
}
function IconMapPin({ className = "w-4 h-4" }) {
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" /><circle cx="12" cy="10" r="3" /></svg>;
}
function IconHome({ className = "w-4 h-4" }) {
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /><polyline points="9 22 9 12 15 12 15 22" /></svg>;
}
function IconCalendar({ className = "w-4 h-4" }) {
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" /><line x1="16" y1="2" x2="16" y2="6" /><line x1="8" y1="2" x2="8" y2="6" /><line x1="3" y1="10" x2="21" y2="10" /></svg>;
}
function IconTrendingUpBig({ className = "w-5 h-5" }) {
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18" /><polyline points="17 6 23 6 23 12" /></svg>;
}
function IconTrendingDown({ className = "w-5 h-5" }) {
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="23 18 13.5 8.5 8.5 13.5 1 6" /><polyline points="17 18 23 18 23 12" /></svg>;
}
function IconTag({ className = "w-5 h-5" }) {
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z" /><line x1="7" y1="7" x2="7.01" y2="7" /></svg>;
}

/* ─── Format Helpers ─── */
function formatPrice(val) {
  if (val == null || isNaN(val)) return '-';
  return Number(val).toFixed(1) + ' 萬/坪';
}
function formatNum(val) {
  if (val == null) return '-';
  return Number(val).toLocaleString('zh-TW');
}
function formatTotal(val) {
  if (val == null || isNaN(val)) return '-';
  const num = Number(val);
  if (num >= 10000) return (num / 10000).toFixed(0) + ' 億';
  return num.toFixed(0) + ' 萬';
}

/* ─── Fetch with timeout ─── */
function fetchTimeout(url, timeout = 8000) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeout);
  return fetch(url, { signal: ctrl.signal }).finally(() => clearTimeout(timer));
}

/* ═══════════════════════════════════════════
   CHART: Price Trend Line (clean single-axis)
   ═══════════════════════════════════════════ */
function PriceTrendChart({ data, height = 200 }) {
  if (!data || data.length === 0) return null;

  const w = 800;
  const pad = { top: 20, right: 20, bottom: 36, left: 56 };
  const cw = w - pad.left - pad.right;
  const ch = height - pad.top - pad.bottom;

  const prices = data.map(d => d.avg_unit_price).filter(v => v != null && v > 0);
  if (prices.length === 0) return null;

  const minP = Math.floor(Math.min(...prices) * 0.9);
  const maxP = Math.ceil(Math.max(...prices) * 1.05);
  const pRange = maxP - minP || 1;

  const xScale = (i) => pad.left + (i / (data.length - 1 || 1)) * cw;
  const yScale = (v) => pad.top + ch - ((v - minP) / pRange) * ch;

  const validPoints = data.map((d, i) => ({ i, v: d.avg_unit_price })).filter(p => p.v != null && p.v > 0);
  if (validPoints.length < 2) return null;

  const linePath = validPoints.map((p, idx) => {
    const x = xScale(p.i);
    const y = yScale(p.v);
    return `${idx === 0 ? 'M' : 'L'} ${x} ${y}`;
  }).join(' ');

  const areaPath = linePath + ` L ${xScale(validPoints[validPoints.length - 1].i)} ${pad.top + ch} L ${xScale(validPoints[0].i)} ${pad.top + ch} Z`;

  const step = Math.max(1, Math.floor(data.length / 8));
  const xLabels = [];
  for (let i = 0; i < data.length; i += step) {
    const label = data[i].month?.slice(0, 7) || '';
    xLabels.push(
      <text key={`x-${i}`} x={xScale(i)} y={height - 6} textAnchor="middle" fontSize={11} fill="#78716c">
        {label}
      </text>
    );
  }

  const yTicks = 5;
  const yLabels = Array.from({ length: yTicks }, (_, i) => {
    const val = minP + (maxP - minP) * (i / (yTicks - 1));
    const y = pad.top + ch - (i / (yTicks - 1)) * ch;
    return (
      <g key={`y-${i}`}>
        <line x1={pad.left} y1={y} x2={w - pad.right} y2={y} stroke="#f0eeeb" strokeWidth={1} />
        <text x={pad.left - 10} y={y + 4} textAnchor="end" fontSize={11} fill="#78716c">
          {val.toFixed(0)}
        </text>
      </g>
    );
  });

  const lastPt = validPoints[validPoints.length - 1];

  return (
    <div className="w-full overflow-x-auto">
      <svg viewBox={`0 0 ${w} ${height}`} className="w-full min-w-[500px]" preserveAspectRatio="xMidYMid meet">
        {yLabels}
        <defs>
          <linearGradient id="priceGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#5a6b4e" stopOpacity={0.1} />
            <stop offset="100%" stopColor="#5a6b4e" stopOpacity={0} />
          </linearGradient>
        </defs>
        <path d={areaPath} fill="url(#priceGrad)" />
        <path d={linePath} fill="none" stroke="#5a6b4e" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
        {lastPt && (
          <circle cx={xScale(lastPt.i)} cy={yScale(lastPt.v)} r={4} fill="#5a6b4e" stroke="white" strokeWidth={2} />
        )}
        <line x1={pad.left} y1={pad.top + ch} x2={w - pad.right} y2={pad.top + ch} stroke="#e0ddd8" strokeWidth={1} />
        {xLabels}
        <text x={14} y={pad.top + ch / 2} textAnchor="middle" fontSize={11} fill="#a8a29e" transform={`rotate(-90, 14, ${pad.top + ch / 2})`}>
          均價（萬/坪）
        </text>
      </svg>
    </div>
  );
}

/* ═══════════════════════════════════════════
   CHART: Volume Bars (simple horizontal bars)
   ═══════════════════════════════════════════ */
function VolumeBarChart({ data, height = 160 }) {
  if (!data || data.length === 0) return null;

  const w = 800;
  const pad = { top: 16, right: 20, bottom: 36, left: 56 };
  const cw = w - pad.left - pad.right;
  const ch = height - pad.top - pad.bottom;

  const volumes = data.map(d => d.count).filter(v => v > 0);
  if (volumes.length === 0) return null;

  const maxV = Math.ceil(Math.max(...volumes) * 1.15);
  const barWidth = Math.max(2, Math.min(12, (cw / data.length) * 0.6));

  const xScale = (i) => pad.left + (i / (data.length - 1 || 1)) * cw;
  const yScale = (v) => pad.top + ch - (v / maxV) * ch;

  const step = Math.max(1, Math.floor(data.length / 8));
  const xLabels = [];
  for (let i = 0; i < data.length; i += step) {
    const label = data[i].month?.slice(0, 7) || '';
    xLabels.push(
      <text key={`x-${i}`} x={xScale(i)} y={height - 6} textAnchor="middle" fontSize={11} fill="#78716c">
        {label}
      </text>
    );
  }

  const yTicks = 4;
  const yLabels = Array.from({ length: yTicks }, (_, i) => {
    const val = (maxV * i) / (yTicks - 1);
    const y = pad.top + ch - (i / (yTicks - 1)) * ch;
    return (
      <g key={`y-${i}`}>
        <line x1={pad.left} y1={y} x2={w - pad.right} y2={y} stroke="#f0eeeb" strokeWidth={1} />
        <text x={pad.left - 10} y={y + 4} textAnchor="end" fontSize={11} fill="#78716c">
          {Math.round(val)}
        </text>
      </g>
    );
  });

  return (
    <div className="w-full overflow-x-auto">
      <svg viewBox={`0 0 ${w} ${height}`} className="w-full min-w-[500px]" preserveAspectRatio="xMidYMid meet">
        {yLabels}
        {data.map((d, i) => (
          <rect
            key={i}
            x={xScale(i) - barWidth / 2}
            y={yScale(d.count)}
            width={barWidth}
            height={Math.max(0, pad.top + ch - yScale(d.count))}
            fill="#5a6b4e"
            opacity={0.45}
            rx={1}
          />
        ))}
        <line x1={pad.left} y1={pad.top + ch} x2={w - pad.right} y2={pad.top + ch} stroke="#e0ddd8" strokeWidth={1} />
        {xLabels}
        <text x={14} y={pad.top + ch / 2} textAnchor="middle" fontSize={11} fill="#a8a29e" transform={`rotate(-90, 14, ${pad.top + ch / 2})`}>
          筆數
        </text>
      </svg>
    </div>
  );
}

/* ═══════════════════════════════════════════
   CHART: Donut Chart (larger, cleaner legend)
   ═══════════════════════════════════════════ */
function DonutChart({ data, size = 160 }) {
  if (!data || data.length === 0) return null;
  const total = data.reduce((s, d) => s + (d.count || 0), 0);
  if (total === 0) return null;

  const colors = ['#5a6b4e', '#6b7fa3', '#c4956a', '#a36b6b', '#7d6ba3', '#a36b8a', '#6b7da3'];
  const cx = size / 2, cy = size / 2, r = size / 2 - 8;
  const innerR = r * 0.62;
  let cumAngle = -Math.PI / 2;

  const withPct = data.map(d => ({
    ...d,
    percentage: d.percentage ?? ((d.count || 0) / total * 100),
  }));

  const slices = withPct.map((d, i) => {
    const angle = (d.percentage / 100) * 2 * Math.PI;
    const startAngle = cumAngle;
    cumAngle += angle;
    const endAngle = cumAngle;
    if (angle < 0.01) return null;

    const x1 = cx + r * Math.cos(startAngle);
    const y1 = cy + r * Math.sin(startAngle);
    const x2 = cx + r * Math.cos(endAngle);
    const y2 = cy + r * Math.sin(endAngle);
    const ix1 = cx + innerR * Math.cos(endAngle);
    const iy1 = cy + innerR * Math.sin(endAngle);
    const ix2 = cx + innerR * Math.cos(startAngle);
    const iy2 = cy + innerR * Math.sin(startAngle);
    const largeArc = angle > Math.PI ? 1 : 0;

    const path = `M ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2} L ${ix1} ${iy1} A ${innerR} ${innerR} 0 ${largeArc} 0 ${ix2} ${iy2} Z`;

    return <path key={i} d={path} fill={colors[i % colors.length]} stroke="white" strokeWidth={2} />;
  }).filter(Boolean);

  return (
    <div className="flex flex-col sm:flex-row items-center gap-5">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {slices}
        <text x={cx} y={cy - 6} textAnchor="middle" fontSize={18} fontWeight="bold" fill="#1c1917">{formatNum(total)}</text>
        <text x={cx} y={cy + 12} textAnchor="middle" fontSize={11} fill="#78716c">筆成交</text>
      </svg>
      <div className="grid grid-cols-2 gap-x-6 gap-y-2">
        {withPct.filter(d => d.percentage > 3).map((d, i) => (
          <div key={i} className="flex items-center gap-2.5">
            <span className="w-2.5 h-2.5 rounded-sm flex-shrink-0" style={{ backgroundColor: colors[i % colors.length] }} />
            <span className="text-sm text-stone-600">{d.label}</span>
            <span className="text-sm font-semibold text-stone-800 ml-auto">{d.percentage}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════
   CHART: Horizontal Bar Ranking
   ═══════════════════════════════════════════ */
function HBarRanking({ items, valueKey, labelKey, color = "#5a6b4e", valueFormat = (v) => v, unit = '' }) {
  if (!items || items.length === 0) return null;
  const maxVal = Math.max(...items.map(i => i[valueKey] || 0), 1);
  return (
    <div className="space-y-3">
      {items.map((item, i) => {
        const pct = ((item[valueKey] || 0) / maxVal) * 100;
        return (
          <div key={i} className="flex items-center gap-3">
            <span className="w-6 text-right text-xs font-bold text-stone-400 tabular-nums">{i + 1}</span>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium text-stone-700 truncate pr-2">{item[labelKey]}</span>
                <span className="text-sm font-bold text-stone-800 tabular-nums whitespace-nowrap ml-2">
                  {valueFormat(item[valueKey])}{unit}
                </span>
              </div>
              <div className="h-2 bg-stone-100 rounded-sm overflow-hidden">
                <div
                  className="h-full rounded-sm transition-all duration-500"
                  style={{ width: `${pct}%`, backgroundColor: color, opacity: 0.65 - (i * 0.07) }}
                />
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ═══════════════════════════════════════════
   CHART: Age Distribution (vertical bars)
   ═══════════════════════════════════════════ */
function AgeDistChart({ data, avgAge, height = 170 }) {
  if (!data || data.length === 0) return null;

  const w = 400;
  const pad = { top: 16, right: 10, bottom: 44, left: 36 };
  const cw = w - pad.left - pad.right;
  const ch = height - pad.top - pad.bottom;

  const maxPct = Math.max(...data.map(d => d.percentage), 1);
  const barGap = 6;
  const barW = Math.max(6, (cw / data.length) - barGap);

  const xScale = (i) => pad.left + i * (barW + barGap) + barGap / 2;
  const yScale = (v) => pad.top + ch - (v / maxPct) * ch;

  const ageColors = ['#5a6b4e', '#6b7a5e', '#7d8a6e', '#b8956a', '#a3855a', '#8a754a', '#7a6540'];

  return (
    <div className="w-full">
      <svg viewBox={`0 0 ${w} ${height}`} className="w-full" preserveAspectRatio="xMidYMid meet">
        {[0, 0.25, 0.5, 0.75, 1].map((frac, i) => {
          const y = pad.top + ch * (1 - frac);
          const val = Math.round(maxPct * frac);
          return (
            <g key={i}>
              <line x1={pad.left} y1={y} x2={w - pad.right} y2={y} stroke="#f0eeeb" strokeWidth={1} />
              {val > 0 && (
                <text x={pad.left - 8} y={y + 4} textAnchor="end" fontSize={10} fill="#a8a29e">{val}%</text>
              )}
            </g>
          );
        })}
        {data.map((d, i) => {
          const colorIdx = Math.min(i, ageColors.length - 1);
          return (
            <g key={i}>
              <rect
                x={xScale(i)}
                y={yScale(d.percentage)}
                width={barW}
                height={Math.max(0, pad.top + ch - yScale(d.percentage))}
                fill={ageColors[colorIdx]}
                opacity={0.6}
                rx={1}
              />
              {d.percentage >= 3 && (
                <text x={xScale(i) + barW / 2} y={yScale(d.percentage) - 8} textAnchor="middle" fontSize={12} fill="#57534e" fontWeight="600">
                  {d.percentage}%
                </text>
              )}
              <text x={xScale(i) + barW / 2} y={height - 8} textAnchor="middle" fontSize={12} fill="#57534e" fontWeight="500">
                {d.label.replace('-', '~')}
              </text>
            </g>
          );
        })}
        <line x1={pad.left} y1={pad.top + ch} x2={w - pad.right} y2={pad.top + ch} stroke="#e0ddd8" strokeWidth={1} />
      </svg>
    </div>
  );
}

/* ═══════════════════════════════════════════
   MAIN PAGE
   ═══════════════════════════════════════════ */
export default function HomePage() {
  const [city, setCity] = useState('所有縣市');
  const [year, setYear] = useState(2025);
  const [districts, setDistricts] = useState(null);
  const [trends, setTrends] = useState(null);
  const [buildingTypes, setBuildingTypes] = useState(null);
  const [priceDist, setPriceDist] = useState(null);
  const [ageDist, setAgeDist] = useState(null);
  const [citiesOverview, setCitiesOverview] = useState(null);
  const [highlights, setHighlights] = useState(null);
  const [highlightYear, setHighlightYear] = useState(2025);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const years = [2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018, 2017, 2016, 2015, 2014, 2013, 2012, 2011];

  const allCitiesList = useMemo(() => {
    if (citiesOverview?.data) {
      return ['所有縣市', ...citiesOverview.data.map(c => c.city)];
    }
    return ['所有縣市', '臺北市', '新北市', '桃園市', '臺中市', '高雄市', '臺南市', '宜蘭縣', '彰化縣', '屏東縣', '新竹縣', '基隆市', '新竹市', '苗栗縣', '雲林縣', '嘉義縣', '南投縣', '嘉義市', '花蓮縣', '臺東縣', '金門縣', '澎湖縣', '連江縣'];
  }, [citiesOverview]);

  useEffect(() => {
    setLoading(true);
    setError(null);
    const cityParam = city === '所有縣市' ? '' : `city=${encodeURIComponent(city)}`;
    fetchTimeout(`${API}/api/stats/districts/lightweight?${cityParam}&year=${year}`, 10000)
      .then(res => res.json())
      .then(data => { setDistricts(data); setLoading(false); })
      .catch(() => { setLoading(false); setError('timeout'); });
  }, [city, year]);

  useEffect(() => {
    const cityParam = city === '所有縣市' ? '' : `city=${encodeURIComponent(city)}`;
    const startYear = Math.max(year - 2, 2011);
    fetchTimeout(`${API}/api/stats/trends/monthly?${cityParam}&start_year=${startYear}&end_year=${year}`, 10000)
      .then(res => res.json())
      .then(data => setTrends(data))
      .catch(() => {});
  }, [city, year]);

  useEffect(() => {
    const cityParam = city === '所有縣市' ? '' : `city=${encodeURIComponent(city)}`;
    fetchTimeout(`${API}/api/stats/building_types?${cityParam}&year=${year}`, 8000)
      .then(res => res.json())
      .then(data => setBuildingTypes(data))
      .catch(() => {});
  }, [city, year]);

  useEffect(() => {
    const cityParam = city === '所有縣市' ? '' : `city=${encodeURIComponent(city)}`;
    fetchTimeout(`${API}/api/stats/price_distribution?${cityParam}&year=${year}`, 8000)
      .then(res => res.json())
      .then(data => setPriceDist(data))
      .catch(() => {});
  }, [city, year]);

  useEffect(() => {
    const cityParam = city === '所有縣市' ? '' : `city=${encodeURIComponent(city)}`;
    fetchTimeout(`${API}/api/stats/building_age_distribution?${cityParam}&year=${year}`, 8000)
      .then(res => res.json())
      .then(data => setAgeDist(data))
      .catch(() => {});
  }, [city, year]);

  useEffect(() => {
    fetchTimeout(`${API}/api/stats/cities/overview?year=${year}`, 8000)
      .then(res => res.json())
      .then(data => setCitiesOverview(data))
      .catch(() => {});
  }, [year]);

  useEffect(() => {
    fetchTimeout(`${API}/api/stats/highlights?year=${highlightYear}`, 8000)
      .then(res => res.json())
      .then(data => setHighlights(data))
      .catch(() => {});
  }, [highlightYear]);

  const totalTx = districts?.data?.reduce((s, r) => s + (r.count || 0), 0) || 0;
  const weightedAvg = districts?.data?.reduce((s, r) => s + ((r.avg_unit_price || 0) * (r.count || 0)), 0) || 0;
  const avgUnitPrice = totalTx > 0 ? weightedAvg / totalTx : 0;
  const displayCity = city === '所有縣市' ? '全臺灣' : city;

  const validDistricts = [...(districts?.data || [])].filter(d => d.avg_unit_price != null);
  const top5Price = validDistricts.sort((a, b) => (b.avg_unit_price || 0) - (a.avg_unit_price || 0)).slice(0, 5);
  const top5Volume = [...(districts?.data || [])].sort((a, b) => (b.count || 0) - (a.count || 0)).slice(0, 5);

  const yoyChange = trends?.data?.length > 12 ? (() => {
    const current = trends.data[trends.data.length - 1]?.avg_unit_price;
    const lastYear = trends.data[trends.data.length - 13]?.avg_unit_price;
    if (current && lastYear) return ((current - lastYear) / lastYear * 100).toFixed(1);
    return null;
  })() : null;

  /* ── Shared select styling ── */
  const selectClass = 'appearance-none bg-white border border-[#ddd8d2] rounded-sm px-3 py-2 pr-8 text-sm text-stone-800 focus:outline-none focus:ring-1 focus:ring-[#5a6b4e]/30 focus:border-[#5a6b4e] cursor-pointer';

  return (
    <div className="space-y-12 animate-fade-in">
      {/* ═══ Hero ═══ */}
      <section className="text-center py-8 sm:py-12">
        <div className="inline-flex items-center gap-2 px-3 py-1.5 text-xs font-medium text-zinc-500 mb-6">
          資料來源：內政部地政司實價登錄
        </div>
        <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold text-[#1a1a1a] leading-tight tracking-tight">
          全台房屋成交紀錄，<br />
          <span className="text-[#5a6b4e]">一查就懂</span>
        </h1>
        <p className="mt-4 text-base sm:text-lg text-stone-500 max-w-xl mx-auto leading-relaxed">
          輸入城市、區域或地址，立即查看該地區的成交行情與生活機能評估。
        </p>
        <HouseButton as={Link} href="/find" className="mt-8 inline-flex items-center gap-2.5 px-8 py-3 text-base border-[#5a6b4e] text-[#5a6b4e] hover:bg-[#5a6b4e] hover:text-white">
          <IconSearch className="w-5 h-5" />
          開始找房
        </HouseButton>
      </section>

      {/* House divider */}
      <HouseDivider className="max-w-5xl mx-auto" />

      {/* ═══ 全台年度亮點 ═══ */}
      {highlights?.data && (() => {
        const d = highlights.data;
        const hasData = d.price_up_city || d.price_down_city || d.cheapest_city;
        if (!hasData) return null;

        const Card = ({ label, name, city: subCity, curPrice, prevPrice, pct, color }) => {
          const isUp   = color === 'emerald';
          const isDown = color === 'rose';
          const isCheap = color === 'violet';

          const bgMap = { emerald: 'bg-[#f2f5f0] border-[#dde0d8]', rose: 'bg-[#f8f0f0] border-[#e8d8d8]', violet: 'bg-[#f0eff5] border-[#d8d8e8]' };
          const badgeBg = { emerald: 'bg-[#dde0d8] text-[#5a6b4e]', rose: 'bg-[#e8d8d8] text-[#a36b6b]', violet: 'bg-[#d8d8e8] text-[#7d6ba3]' };
          const iconColor = { emerald: 'text-[#5a6b4e]', rose: 'text-[#a36b6b]', violet: 'text-[#7d6ba3]' };

          return (
            <div className={`${bgMap[color]} border rounded-sm p-4 flex flex-col justify-between min-h-[120px]`}>
              <div className="flex items-start justify-between gap-2">
                <span className="text-xs font-medium text-stone-500">{label}</span>
                {!isCheap && (
                  <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-sm text-xs font-bold ${badgeBg[color]}`}>
                    {isUp ? <IconTrendingUpBig className="w-3.5 h-3.5" /> : <IconTrendingDown className="w-3.5 h-3.5" />}
                    {pct > 0 ? '+' : ''}{pct}%
                  </span>
                )}
                {isCheap && (
                  <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-sm text-xs font-bold ${badgeBg[color]}`}>
                    <IconTag className="w-3.5 h-3.5" />
                    最低
                  </span>
                )}
              </div>
              <div className="mt-2">
                <div className="text-lg font-bold text-[#1a1a1a] leading-tight truncate">{name}</div>
                {subCity && (
                  <div className="text-xs text-stone-500 mt-0.5">{subCity}</div>
                )}
              </div>
              <div className="mt-auto pt-3 flex items-baseline gap-2">
                <span className="text-2xl font-bold text-[#1a1a1a] tabular-nums">{curPrice.toFixed(1)}</span>
                <span className="text-xs text-stone-500">萬/坪</span>
                {prevPrice != null && (
                  <span className="text-sm text-stone-400 line-through ml-1 tabular-nums">{prevPrice.toFixed(1)}萬</span>
                )}
              </div>
            </div>
          );
        };

        return (
          <section className="max-w-5xl mx-auto">
            <div className="bg-white border border-[#e0ddd8] rounded-sm shadow-sm overflow-hidden">
              <div className="px-5 py-4 border-b border-[#edeae5] flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <IconTrendingUp className="w-5 h-5 text-[#5a6b4e]" />
                  <h2 className="text-base font-bold text-[#1a1a1a]">全台年度亮點</h2>
                </div>
                <div className="relative">
                  <select value={highlightYear} onChange={(e) => setHighlightYear(parseInt(e.target.value))}
                    className={`${selectClass} w-20`}>
                    {years.slice(0, 5).map(y => <option key={y} value={y}>{y}</option>)}
                  </select>
                  <IconCalendar className="w-3.5 h-3.5 absolute right-2 top-1/2 -translate-y-1/2 text-stone-400 pointer-events-none" />
                </div>
              </div>
              <div className="p-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {d.price_up_city && <Card label="縣市漲最多" name={d.price_up_city.city} curPrice={d.price_up_city.avg_unit_price} prevPrice={d.price_up_city.prev_price} pct={d.price_up_city.yoy_pct} color="emerald" />}
                {d.price_down_city && <Card label="縣市跌最多" name={d.price_down_city.city} curPrice={d.price_down_city.avg_unit_price} prevPrice={d.price_down_city.prev_price} pct={d.price_down_city.yoy_pct} color="rose" />}
                {d.cheapest_city && <Card label="最便宜縣市" name={d.cheapest_city.city} curPrice={d.cheapest_city.avg_unit_price} color="violet" />}
                {d.price_up_district && <Card label="行政區漲最多" name={d.price_up_district.district} city={d.price_up_district.city} curPrice={d.price_up_district.avg_unit_price} prevPrice={d.price_up_district.prev_price} pct={d.price_up_district.yoy_pct} color="emerald" />}
                {d.price_down_district && <Card label="行政區跌最多" name={d.price_down_district.district} city={d.price_down_district.city} curPrice={d.price_down_district.avg_unit_price} prevPrice={d.price_down_district.prev_price} pct={d.price_down_district.yoy_pct} color="rose" />}
                {d.cheapest_district && <Card label="最便宜行政區" name={d.cheapest_district.district} city={d.cheapest_district.city} curPrice={d.cheapest_district.avg_unit_price} color="violet" />}
              </div>
            </div>
          </section>
        );
      })()}

      {/* ═══ 即時房市儀表板 ═══ */}
      <section className="max-w-5xl mx-auto">
        <div className="bg-white border border-[#e0ddd8] rounded-sm shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-[#edeae5]">
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <div className="flex items-center gap-2">
                <IconTrendingUp className="w-5 h-5 text-[#5a6b4e]" />
                <h2 className="text-base font-bold text-[#1a1a1a]">即時房市行情</h2>
              </div>
              <div className="flex items-center gap-3">
                <div className="relative">
                  <select value={city} onChange={(e) => setCity(e.target.value)}
                    className={selectClass}>
                    {allCitiesList.map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                  <IconMapPin className="w-3.5 h-3.5 absolute right-2 top-1/2 -translate-y-1/2 text-stone-400 pointer-events-none" />
                </div>
                <div className="relative">
                  <select value={year} onChange={(e) => setYear(parseInt(e.target.value))}
                    className={`${selectClass} w-20`}>
                    {years.map(y => <option key={y} value={y}>{y}</option>)}
                  </select>
                  <IconCalendar className="w-3.5 h-3.5 absolute right-2 top-1/2 -translate-y-1/2 text-stone-400 pointer-events-none" />
                </div>
              </div>
            </div>
            <p className="text-xs text-stone-500 mt-2">{displayCity} · {year}年成交數據</p>
          </div>

          {loading ? (
            <div className="p-8 flex items-center justify-center">
              <div className="animate-pulse space-y-3 w-full max-w-md">
                <div className="h-4 bg-stone-200 rounded w-1/3" />
                <div className="h-32 bg-stone-100 rounded-sm" />
              </div>
            </div>
          ) : error ? (
            <div className="p-8 text-center">
              <div className="text-sm text-stone-500">即時數據正在維護中，請稍後再試。</div>
              <Link href="/find" className="mt-4 inline-flex items-center gap-2 px-5 py-2.5 border border-[#5a6b4e] text-[#5a6b4e] text-sm font-medium rounded-sm hover:bg-[#5a6b4e] hover:text-white transition-colors">
                <IconSearch className="w-4 h-4" />
                前往找房
              </Link>
            </div>
          ) : districts?.data?.length === 0 ? (
            <div className="p-8 text-center">
              <div className="text-sm text-stone-500">{displayCity} {year}年暫無成交統計資料</div>
              <Link href="/find" className="mt-4 inline-flex items-center gap-2 px-5 py-2.5 border border-[#5a6b4e] text-[#5a6b4e] text-sm font-medium rounded-sm hover:bg-[#5a6b4e] hover:text-white transition-colors">
                <IconSearch className="w-4 h-4" />
                前往找房
              </Link>
            </div>
          ) : (
            <div>
              {/* ── Section 1: KPI Cards ── */}
              <div className="px-5 pt-5 pb-2">
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                  {[
                    { icon: <IconHome className="w-5 h-5" />, label: '總成交量', value: formatNum(totalTx), sub: '筆', color: 'text-[#5a6b4e]', bgColor: 'bg-[#f5f7f3]' },
                    { icon: <IconTrendingUp className="w-5 h-5" />, label: '平均單價', value: avgUnitPrice.toFixed(1), sub: yoyChange ? `${yoyChange > 0 ? '+' : ''}${yoyChange}% YoY` : '萬/坪', color: 'text-[#5a6b4e]', bgColor: 'bg-[#f5f7f3]' },
                    { icon: <IconMapPin className="w-5 h-5" />, label: '涵蓋區域', value: districts?.data?.length || 0, sub: '個行政區', color: 'text-[#6b7fa3]', bgColor: 'bg-[#f3f5f7]' },
                    { icon: <IconBuilding className="w-5 h-5" />, label: '平均總價', value: formatTotal(districts?.data?.reduce((s, r) => s + ((r.avg_total_price || 0) * (r.count || 0)), 0) / totalTx), sub: '', color: 'text-[#b8956a]', bgColor: 'bg-[#f7f5f3]' },
                  ].map((kpi, i) => (
                    <div key={i} className={`${kpi.bgColor} rounded-sm p-4`}>
                      <div className="flex items-center gap-1.5 text-stone-500 mb-2">
                        {kpi.icon}
                        <span className="text-xs font-medium">{kpi.label}</span>
                      </div>
                      <div className={`text-2xl font-bold ${kpi.color} tabular-nums`}>{kpi.value}</div>
                      {kpi.sub && <div className="text-xs text-stone-500 mt-1">{kpi.sub}</div>}
                    </div>
                  ))}
                </div>
              </div>

              {/* ── Section 2: Trend Charts ── */}
              <div className="px-5 py-4">
                <div className="text-sm font-semibold text-stone-700 mb-3">近月均價走勢</div>
                <PriceTrendChart data={trends?.data || []} />
              </div>

              <div className="px-5 py-4 border-t border-[#edeae5]">
                <div className="text-sm font-semibold text-stone-700 mb-3">近月成交量</div>
                <VolumeBarChart data={trends?.data || []} />
              </div>

              {/* ── Section 3: Rankings & Distributions ── */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-0 divide-y md:divide-y-0 md:divide-x divide-[#edeae5]">
                <div className="p-5 space-y-6">
                  <div>
                    <div className="text-sm font-semibold text-stone-700 mb-3">單價最高前 5 區</div>
                    <HBarRanking
                      items={top5Price}
                      valueKey="avg_unit_price"
                      labelKey="district"
                      color="#5a6b4e"
                      valueFormat={(v) => v.toFixed(1) + ' 萬/坪'}
                    />
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-stone-700 mb-3">成交量最高前 5 區</div>
                    <HBarRanking
                      items={top5Volume}
                      valueKey="count"
                      labelKey="district"
                      color="#6b7fa3"
                      valueFormat={(v) => formatNum(v)}
                      unit=" 筆"
                    />
                  </div>
                </div>

                <div className="p-5 space-y-6">
                  <div>
                    <div className="text-sm font-semibold text-stone-700 mb-3">總價區間分佈</div>
                    <DonutChart data={(priceDist?.data || []).map(d => ({ label: d.label, count: d.value }))} size={160} />
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-stone-700 mb-3">建物型態 TOP 5</div>
                    <HBarRanking
                      items={buildingTypes?.data?.slice(0, 5) || []}
                      valueKey="count"
                      labelKey="type"
                      color="#7d6ba3"
                      valueFormat={(v) => formatNum(v)}
                      unit=" 筆"
                    />
                  </div>
                  <div>
                    <div className="text-sm font-semibold text-stone-700 mb-3 flex items-center gap-2">
                      屋齡分佈
                      {ageDist?.avg_building_age != null && (
                        <span className="text-xs font-normal text-stone-400">（平均 {ageDist.avg_building_age} 年）</span>
                      )}
                    </div>
                    <AgeDistChart data={ageDist?.data || []} avgAge={ageDist?.avg_building_age} />
                  </div>
                </div>
              </div>

              {/* CTA */}
              <div className="px-5 py-4 border-t border-[#edeae5]">
                <Link href="/find" className="flex items-center justify-center gap-2 w-full py-3 rounded-sm bg-stone-50 border border-[#e0ddd8] text-sm font-medium text-stone-700 hover:bg-stone-100 hover:border-[#d0cdc8] transition-all">
                  瀏覽更多成交紀錄
                  <IconArrowRight className="w-4 h-4" />
                </Link>
              </div>
            </div>
          )}
        </div>
      </section>

      {/* ═══ Footer ═══ */}
      <footer className="text-center py-6 border-t border-[#e0ddd8]">
        <p className="text-xs text-stone-400">資料僅供參考，實際交易條件以內政部實價登錄為準。</p>
      </footer>
    </div>
  );
}
