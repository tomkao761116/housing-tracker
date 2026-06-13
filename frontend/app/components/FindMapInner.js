/**
 * 成交地圖元件 — 重構版
 * 
 * 核心功能：
 * 1. MarkerCluster 聚類標記（大量點不卡頓）
 * 2. 點擊 marker → 飛到該點 + 開啟 Popup + 顯示詳細 Modal + 高亮列表
 * 3. 點擊列表卡片 → 地圖飛到對應 marker + 開啟 Popup + 顯示 Modal
 * 4. 框選篩選：畫矩形過濾範圍內成交
 * 5. 著色模式：score / price
 */
'use client';

import { useEffect, useRef, useCallback, useState } from 'react';
import 'leaflet/dist/leaflet.css';
import 'leaflet.markercluster/dist/MarkerCluster.css';
import 'leaflet.markercluster/dist/MarkerCluster.Default.css';
import 'leaflet-draw/dist/leaflet.draw.css';
import { TrainFront, GraduationCap, HeartPulse, ShoppingCart, Trees, UtensilsCrossed, Square, MapPin } from 'lucide-react';

const DEFAULT_CENTER = [23.97, 120.96];
const DEFAULT_ZOOM = 8;
const MIN_ZOOM = 8;

const CITY_BOUNDS = {
  '基隆市':   [[25.04, 121.49], [25.31, 121.70]],
  '臺北市':   [[24.99, 121.42], [25.21, 121.58]],
  '新北市':   [[24.88, 121.06], [25.31, 121.61]],
  '桃園市':   [[24.80, 121.07], [25.06, 121.42]],
  '新竹市':   [[24.76, 120.93], [24.89, 121.04]],
  '新竹縣':   [[24.54, 120.81], [24.85, 121.20]],
  '苗栗縣':   [[24.30, 120.67], [24.67, 121.20]],
  '臺中市':   [[24.06, 120.42], [24.39, 120.82]],
  '彰化縣':   [[23.77, 120.28], [24.06, 120.62]],
  '南投縣':   [[23.69, 120.40], [23.96, 120.87]],
  '雲林縣':   [[23.42, 120.14], [23.84, 120.56]],
  '嘉義市':   [[23.45, 120.38], [23.52, 120.47]],
  '嘉義縣':   [[23.27, 120.18], [23.64, 120.62]],
  '臺南市':   [[22.86, 120.00], [23.31, 120.38]],
  '高雄市':   [[22.47, 120.00], [22.90, 120.45]],
  '屏東縣':   [[22.19, 120.24], [22.71, 120.67]],
  '宜蘭縣':   [[24.58, 121.41], [24.94, 121.89]],
  '花蓮縣':   [[23.33, 121.23], [24.18, 121.70]],
  '臺東縣':   [[22.40, 120.72], [23.48, 121.48]],
  '澎湖縣':   [[23.38, 119.47], [23.78, 119.80]],
  '金門縣':   [[24.33, 118.20], [24.52, 118.52]],
  '連江縣':   [[25.88, 119.78], [26.28, 120.08]],
};

/* ─── SVG Icons ─────────────────────────────────────── */
function IconBuilding2({ className = "w-5 h-5" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 22v-10"/><path d="M16 22v-14"/><path d="M10 22v-4"/><path d="M4 22V10"/><path d="M9 6h8"/><path d="M12 6V2"/><path d="M8 12h2"/><path d="M14 12h2"/><path d="M8 16h2"/><path d="M14 16h2"/>
    </svg>
  );
}

function IconBed({ className = "w-5 h-5" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 4v16"/><path d="M2 8h18a2 2 0 0 1 2 2v10"/><path d="M2 17h20"/><path d="M6 8v9"/>
    </svg>
  );
}

function IconRuler({ className = "w-5 h-5" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21.8 10.9C21.47 10.72 21.15 10.56 20.8 10.46A11.16 11.16 0 0 0 12 2a11.16 11.16 0 0 0-8.8 4.46c-.35.1-.67.26-1 .44"/><path d="M12 2v20"/><path d="m5.6 5.6 1.4 1.4"/><path d="m17 17 1.4 1.4"/><path d="m17 7 1.4-1.4"/><path d="m5.6 18.4 1.4-1.4"/>
    </svg>
  );
}

/* ─── Shared Components ─────────────────────────────── */
function Tag({ color = 'stone', children }) {
  const colorMap = {
    emerald: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    amber: 'bg-amber-50 text-amber-700 border-amber-200',
    rose: 'bg-rose-50 text-rose-700 border-rose-200',
    stone: 'bg-stone-100 text-stone-600 border-stone-200',
    blue: 'bg-blue-50 text-blue-700 border-blue-200',
  };
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-lg text-xs font-medium border ${colorMap[color] || colorMap.stone}`}>
      {children}
    </span>
  );
}

const DIMENSIONS = [
  { key: 'transit', label: '交通', icon: TrainFront, color: '#7b6ba5' },
  { key: 'education', label: '教育', icon: GraduationCap, color: '#3b7ab5' },
  { key: 'medical', label: '醫療', icon: HeartPulse, color: '#b54a3a' },
  { key: 'shopping', label: '購物', icon: ShoppingCart, color: '#c45a7a' },
  { key: 'leisure', label: '休閒', icon: Trees, color: '#5a8a5a' },
  { key: 'dining', label: '餐飲', icon: UtensilsCrossed, color: '#c47a3a' },
];

function parseFloorNum(val) {
  if (val == null) return null;
  if (typeof val === 'number') return val;
  const match = String(val).match(/(\d+)/);
  return match ? parseInt(match[1], 10) : null;
}

const CHINESE_DIGITS = { '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10, '十一': 11, '十二': 12, '十三': 13, '十四': 14, '十五': 15, '十六': 16, '十七': 17, '十八': 18, '十九': 19, '二十': 20, '二十一': 21, '二十二': 22, '二十三': 23, '二十四': 24, '二十五': 25, '二十六': 26, '二十七': 27, '二十八': 28, '二十九': 29, '三十': 30 };

function parseChineseFloor(str) {
  if (str == null) return null;
  const s = String(str).replace('層', '').trim();
  return CHINESE_DIGITS[s] || null;
}

function formatFloor(floor, totalFloors, buildingType) {
  if (floor == null) return '';
  const floorStr = String(floor).trim();
  const totalStr = String(totalFloors ?? '').trim();
  const isEntireBuilding = floorStr.includes('全');
  if ((buildingType?.includes('透天') || buildingType?.includes('別墅') || isEntireBuilding) && totalStr) {
    const num = parseFloorNum(totalStr) ?? parseChineseFloor(totalStr);
    return num != null ? `共${num}層` : totalStr;
  }
  const floorNum = parseFloorNum(floorStr) ?? parseChineseFloor(floorStr);
  const totalNum = parseFloorNum(totalStr) ?? parseChineseFloor(totalStr);
  if (totalNum != null && floorNum != null) return `${floorNum}F / ${totalNum}F`;
  if (floorNum != null) return `${floorNum}F`;
  return floorStr;
}

function PriceBadge({ price }) {
  return (
    <div className="text-sm md:text-lg font-bold text-stone-900 tabular-nums leading-tight">
      {price}
    </div>
  );
}

/* ─── Trade Detail Modal ────────────────────────────── */
function TradeDetailModal({ trade, onClose }) {
  if (!trade) return null;

  const formatDate = (dateStr, season) => {
    if (dateStr) {
      const d = new Date(dateStr);
      if (d.getFullYear() > 2028 || d.getFullYear() < 1950) {
      } else {
        return `${d.getFullYear()}/${String(d.getMonth() + 1).padStart(2, '0')}/${String(d.getDate()).padStart(2, '0')}`;
      }
    }
    if (season) {
      const match = String(season).match(/^(\d{3})S(\d)$/);
      if (match) {
        const rocYear = parseInt(match[1], 10);
        const quarter = parseInt(match[2], 10);
        const westYear = rocYear + 1911;
        if (westYear > 2028 || westYear < 1950) return '—';
        const month = (quarter - 1) * 3 + 2;
        return `${westYear}/${String(month).padStart(2, '0')}/—`;
      }
    }
    return '—';
  };

  const formatPrice = (val) => {
    if (val == null) return '—';
    const num = Number(val);
    if (num >= 100000000) {
      const yi = (num / 100000000).toFixed(2);
      return `${parseFloat(yi)} 億`;
    }
    const wan = Math.round(num / 10000);
    return `${wan.toLocaleString()} 萬`;
  };

  const formatUnitPrice = (val) => {
    if (val == null) return '—';
    const num = Number(val);
    return `${num.toFixed(2)} 萬/坪`;
  };

  const formatArea = (area) => {
    if (area == null) return '—';
    const tping = Number(area) / 3.3058;
    return `${tping.toFixed(2)} 坪`;
  };

  const isLandOnly = trade.is_land_only || (trade.building_type === '其他' && (!trade.building_area || trade.building_area === 0));
  const displayArea = isLandOnly ? trade.land_area : trade.building_area;
  const areaLabel = isLandOnly ? '地積' : '面積';
  const unitPriceLabel = isLandOnly ? '地價' : '單價';

  const buildingTypeColor = {
    '住宅大樓': 'emerald',
    '華廈': 'emerald',
    '公寓': 'emerald',
    '透天厝': 'amber',
    '別墅': 'rose',
  };

  return (
    <div className="fixed inset-0 z-[10000] flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
      
      <div
        className="relative bg-white rounded-2xl shadow-2xl max-w-lg w-full max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onClose}
          className="absolute top-3 right-3 z-10 w-8 h-8 flex items-center justify-center rounded-full bg-white/80 hover:bg-white transition-colors text-stone-400 hover:text-stone-700 shadow-sm"
        >
          ✕
        </button>

        <div className="p-5 pb-4">
          <div className="flex items-start justify-between mb-3">
            <div className="flex-1 min-w-0 mr-4 max-w-[65%]">
              <div className="flex items-center gap-2 mb-1">
                <Tag color="emerald">{trade.city}</Tag>
                <Tag color="stone">{trade.district}</Tag>
              </div>
              <h3 className="font-semibold text-stone-900 truncate text-base">
                <MapPin className="w-4 h-4 inline" /> {trade.address}
              </h3>
            </div>
            <div className="text-right flex-shrink-0">
              <div className="text-xs text-stone-400">成交日期</div>
              <div className="text-sm font-medium text-stone-700 tabular-nums">{formatDate(trade.trade_date, trade.season)}</div>
            </div>
          </div>

          <div className="grid grid-cols-4 gap-2 mb-4 p-3 bg-stone-50 rounded-xl">
            <div>
              <div className="text-xs text-stone-400 mb-1">總價</div>
              <PriceBadge price={formatPrice(trade.total_price)} />
            </div>
            <div>
              <div className="text-xs text-stone-400 mb-1">{unitPriceLabel}</div>
              <div className="text-sm font-bold text-emerald-600 tabular-nums leading-tight">{formatUnitPrice(trade.unit_price_tping)}</div>
            </div>
            <div>
              <div className="text-xs text-stone-400 mb-1">{areaLabel}</div>
              <div className="text-sm font-bold text-stone-700 tabular-nums leading-tight">{formatArea(displayArea)}</div>
            </div>
            <div>
              <div className="text-xs text-stone-400 mb-1">屋齡</div>
              <div className="text-sm font-bold tabular-nums leading-tight">
                {trade.building_age != null ? (
                  trade.building_age === 0 ? (
                    <span className="text-emerald-600">新成屋</span>
                  ) : (
                    <span className={trade.building_age <= 5 ? 'text-emerald-600' : trade.building_age <= 15 ? 'text-blue-600' : 'text-orange-600'}>
                      {trade.building_age}年
                    </span>
                  )
                ) : (
                  <span className="text-stone-300">—</span>
                )}
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2 mb-3">
            {trade.building_type && (
              <Tag color={buildingTypeColor[trade.building_type] || 'stone'}>
                <IconBuilding2 className="w-4 h-4 inline" /> {trade.building_type}
              </Tag>
            )}
            {(trade.rooms != null || trade.living_rooms != null || trade.bathrooms != null) && (
              <Tag color="emerald">
                <IconBed className="w-4 h-4 inline" /> {trade.rooms || '?'}房{trade.living_rooms || '?'}廳{trade.bathrooms || '?'}衛
              </Tag>
            )}
            {trade.floor != null && (
              <Tag color="amber">
                <IconRuler className="w-4 h-4 inline" /> {formatFloor(trade.floor, trade.total_floors, trade.building_type)}
              </Tag>
            )}
          </div>

          {trade.score_overall != null && (
            <div className="mb-3 p-2.5 rounded-xl border" style={{
              borderColor: trade.score_overall >= 80 ? '#9ab57d' : trade.score_overall >= 60 ? '#94a3b8' : trade.score_overall >= 40 ? '#fcd34d' : '#fca5a5',
              backgroundColor: trade.score_overall >= 80 ? '#ecfdf5' : trade.score_overall >= 60 ? '#eff6ff' : trade.score_overall >= 40 ? '#fffbeb' : '#fef2f2'
            }}>
              <div className="flex items-center justify-between">
                <span className="text-xs text-stone-500 font-medium"><MapPin className="w-3 h-3 inline" /> 生活圈評分</span>
                <span className={`text-lg font-bold tabular-nums ${
                  trade.score_overall >= 80 ? 'text-emerald-600' :
                  trade.score_overall >= 60 ? 'text-blue-600' :
                  trade.score_overall >= 40 ? 'text-amber-600' : 'text-red-600'
                }`}>{trade.score_overall}</span>
              </div>
              <div className="flex gap-3 mt-1.5 flex-wrap">
                {DIMENSIONS.map(dim => {
                  const score = trade[`score_${dim.key}`];
                  const IconComp = dim.icon;
                  return (
                    <div key={dim.key} className="flex items-center gap-1">
                      <IconComp size={12} strokeWidth={2} style={{ color: score != null ? dim.color : '#d6d3d1' }} />
                      <span className={`text-xs tabular-nums ${score != null ? 'text-stone-600' : 'text-stone-300'}`}>
                        {score != null ? score : '-'}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ─── Color helpers ─────────────────────────────────── */
const scoreColorsCache = (() => {
  try {
    const s = getComputedStyle(document.documentElement);
    return {
      null: s.getPropertyValue('--score-null').trim() || '#999999',
      excellent: s.getPropertyValue('--score-excellent').trim() || '#2d7a5f',
      good: s.getPropertyValue('--score-good').trim() || '#4a5d8a',
      average: s.getPropertyValue('--score-average').trim() || '#b8943a',
      poor: s.getPropertyValue('--score-poor').trim() || '#a85555',
    };
  } catch {
    return { null: '#999', excellent: '#2d7a5f', good: '#4a5d8a', average: '#b8943a', poor: '#a85555' };
  }
})();

function getScoreColor(score) {
  if (score == null) return scoreColorsCache.null;
  if (score >= 80) return scoreColorsCache.excellent;
  if (score >= 60) return scoreColorsCache.good;
  if (score >= 40) return scoreColorsCache.average;
  return scoreColorsCache.poor;
}

function getPriceColor(totalPrice) {
  const priceWan = totalPrice / 10000;
  if (priceWan > 200) return '#dc2626';
  if (priceWan > 150) return '#ea580c';
  if (priceWan > 100) return '#ca8a04';
  if (priceWan > 50) return '#3b82f6';
  return '#16a34a';
}

function getMarkerColor(trade, colorMode) {
  if (colorMode === 'price') return getPriceColor(trade.total_price || 0);
  return getScoreColor(trade.score_overall || 0);
}

/* ─── Map Legend ────────────────────────────────────── */
function MapLegend({ colorMode }) {
  const scoreColors = [
    { min: 80, label: '80+ 優異', color: 'var(--score-excellent)' },
    { min: 60, label: '60-79 良好', color: 'var(--score-good)' },
    { min: 40, label: '40-59 普通', color: 'var(--score-average)' },
    { min: 0, label: '40- 待加強', color: 'var(--score-poor)' },
  ];
  const priceColors = [
    { min: 200, label: '200 萬以上', color: '#dc2626' },
    { min: 150, label: '150-200 萬', color: '#ea580c' },
    { min: 100, label: '100-150 萬', color: '#ca8a04' },
    { min: 50, label: '50-100 萬', color: '#3b82f6' },
    { min: 0, label: '50 萬以下', color: '#16a34a' },
  ];
  const items = colorMode === 'score' ? scoreColors : priceColors;
  return (
    <div className="absolute bottom-4 left-4 z-[400] bg-white/95 backdrop-blur-sm rounded-lg shadow-md border border-[#e8e4df] p-3 text-xs">
      <div className="font-medium text-[#2a2a2a] mb-2 flex items-center gap-1.5">
        <Square className="w-3.5 h-3.5" />
        {colorMode === 'score' ? '生活圈評分' : '總價區間'}
      </div>
      <div className="space-y-1.5">
        {items.map((item, i) => (
          <div key={i} className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: item.color }} />
            <span className="text-[#777]">{item.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ─── Main Component ────────────────────────────────── */
export default function FindMap({ trades, selectedId, onSelect, hoveredId, onMarkerHover, colorMode, filters, onBoxSelect }) {
  const mapRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const LRef = useRef(null);
  
  // 所有 trade 資料的快取 (id -> trade)
  const allTradesCache = useRef(new Map());
  // 所有 marker 的快取 (id -> marker)
  const allMarkersCache = useRef(new Map());
  
  const [detailTrade, setDetailTrade] = useState(null);
  const [boxCount, setBoxCount] = useState(null);

  // Stable refs for callbacks inside Leaflet handlers
  const onSelectRef = useRef(onSelect);
  const onMarkerHoverRef = useRef(onMarkerHover);
  const onBoxSelectRef = useRef(onBoxSelect);
  const colorModeRef = useRef(colorMode);
  const selectedIdRef = useRef(selectedId);

  useEffect(() => { onSelectRef.current = onSelect; }, [onSelect]);
  useEffect(() => { onMarkerHoverRef.current = onMarkerHover; }, [onMarkerHover]);
  useEffect(() => { onBoxSelectRef.current = onBoxSelect; }, [onBoxSelect]);
  useEffect(() => { colorModeRef.current = colorMode; }, [colorMode]);
  useEffect(() => { selectedIdRef.current = selectedId; }, [selectedId]);

  /* ── 建立單一 marker ── */
  const createMarker = useCallback((trade) => {
    const L = LRef.current;
    if (!L) return null;
    
    const color = getMarkerColor(trade, colorModeRef.current);
    
    const marker = L.circleMarker([trade.lat, trade.lon], {
      radius: 6,
      fillColor: color,
      color: '#fff',
      weight: 2,
      opacity: 1,
      fillOpacity: 0.75,
    });

    // Popup 內容（簡單摘要）
    const popupHtml = `
      <div style="min-width:180px;font-family:sans-serif;line-height:1.5;">
        <div style="font-weight:bold;margin-bottom:4px;">${trade.address || '—'}</div>
        ${trade.total_price ? `<div>總價: ${Math.round(trade.total_price / 10000).toLocaleString()} 萬</div>` : ''}
        ${trade.unit_price_tping ? `<div>單價: ${trade.unit_price_tping} 萬/坪</div>` : ''}
        ${trade.score_overall != null ? `<div>生活圈: ${trade.score_overall} 分</div>` : ''}
      </div>
    `;
    marker.bindPopup(popupHtml, { maxWidth: 280, closeOnClick: false, closeButton: true });

    // 點擊 marker → 通知父元件 + 開 popup + 開 modal
    marker.on('click', () => {
      const tid = trade.id;
      // 通知父元件高亮列表
      onSelectRef.current?.(tid);
      // 開啟 popup
      marker.openPopup();
      // 開啟詳細 modal
      setDetailTrade(trade);
    });

    // Hover 效果
    marker.on('mouseover', () => {
      onMarkerHoverRef.current?.(trade.id);
      marker.setStyle({ radius: 8, fillOpacity: 1 });
    });
    marker.on('mouseout', () => {
      onMarkerHoverRef.current?.(null);
      if (trade.id !== selectedIdRef.current) {
        marker.setStyle({ radius: 6, fillOpacity: 0.75 });
      }
    });

    return marker;
  }, []);

  /* ── 更新地圖上的所有 marker ── */
  const updateMarkers = useCallback(() => {
    const cg = mapInstanceRef.current?._clusterGroup;
    if (!cg) return;

    cg.clearLayers();
    allMarkersCache.current.clear();
    allTradesCache.current.clear();

    const currentTrades = trades;
    if (!currentTrades || currentTrades.length === 0) return;

    currentTrades
      .filter(t => t.lat != null && t.lon != null)
      .forEach(trade => {
        allTradesCache.current.set(trade.id, trade);
        const marker = createMarker(trade);
        if (marker) {
          allMarkersCache.current.set(trade.id, marker);
          cg.addLayer(marker);
        }
      });
  }, [trades, createMarker]);

  /* ── 初始化地圖 ── */
  useEffect(() => {
    let cancelled = false;

    async function init() {
      if (!mapRef.current) return;

      // Strict Mode 防護
      if (mapInstanceRef.current && mapInstanceRef.current._container === mapRef.current) {
        return;
      }
      if (mapInstanceRef.current) {
        try { mapInstanceRef.current.remove(); } catch(e) {}
        mapInstanceRef.current = null;
      }

      // 動態載入 Leaflet
      const LModule = await import('leaflet');
      const L = LModule.default;
      const MCModule = await import('leaflet.markercluster');
      const DrawModule = await import('leaflet-draw');

      if (MCModule.default) L.MarkerClusterGroup = MCModule.default;
      if (MCModule.MarkerClusterGroup) L.MarkerClusterGroup = MCModule.MarkerClusterGroup;
      for (const key of Object.keys(MCModule)) {
        if (!(key in L)) L[key] = MCModule[key];
      }
      for (const key of Object.keys(DrawModule)) {
        if (!(key in L) && key.startsWith('FeatureGroup')) L[key] = DrawModule[key];
      }

      if (cancelled || !mapRef.current) return;

      // 清除容器殘留
      while (mapRef.current.firstChild) {
        mapRef.current.removeChild(mapRef.current.firstChild);
      }
      delete mapRef.current._leaflet_id;
      delete mapRef.current._leaflet_disable;

      LRef.current = L;

      // 修正圖示路徑
      L.Icon.Default.mergeOptions({
        iconRetinaUrl: '/leaflet/marker-icon-2x.png',
        iconUrl: '/leaflet/marker-icon.png',
        shadowUrl: '/leaflet/marker-shadow.png',
      });

      const map = L.map(mapRef.current, {
        center: DEFAULT_CENTER,
        zoom: DEFAULT_ZOOM,
        minZoom: MIN_ZOOM,
        zoomControl: true,
        attributionControl: false,
      });

      L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
        maxZoom: 19,
      }).addTo(map);

      // 建立 cluster group
      const clusterGroup = new L.MarkerClusterGroup({
        maxClusterRadius: 50,
        spiderfyOnMaxZoom: true,
        showCoverageOnHover: false,
        zoomToBoundsOnClick: true,
        spiderfyDistanceMultiplier: 1.5,
        iconCreateFunction: (cluster) => {
          const childCount = cluster.getChildCount();
          let diameter = 40;
          let fontSize = 14;
          if (childCount > 100) { diameter = 58; fontSize = 16; }
          else if (childCount > 30) { diameter = 48; fontSize = 15; }

          return L.divIcon({
            html: `<div style="background:linear-gradient(135deg,#5a6b4e,#4a5d3e);color:#fff;border-radius:50%;width:${diameter}px;height:${diameter}px;display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:${fontSize}px;box-shadow:0 2px 8px rgba(0,0,0,.2);cursor:pointer;">${childCount}</div>`,
            className: 'marker-cluster housing-cluster',
            iconSize: L.point(diameter, diameter),
            iconAnchor: [diameter / 2, diameter / 2],
          });
        },
      });

      map.addLayer(clusterGroup);
      // 把 clusterGroup 掛到 mapInstance 上方便存取
      mapInstanceRef.current = map;
      mapInstanceRef.current._clusterGroup = clusterGroup;

      // Leaflet Draw 框選
      const drawLayer = new L.FeatureGroup();
      map.addLayer(drawLayer);

      const drawControl = new L.Control.Draw({
        draw: {
          polyline: false, circle: false, circlemarker: false, marker: false, polygon: false,
          rectangle: {
            shapeOptions: { color: '#5a6b4e', weight: 2, fillOpacity: 0.1, fillColor: '#5a6b4e' },
          },
        },
        edit: { featureGroup: drawLayer },
      });
      map.addControl(drawControl);

      map.on(L.Draw.Event.CREATED, (e) => {
        if (e.layerType === 'rectangle') {
          const bounds = e.layer.getBounds();
          drawLayer.addLayer(e.layer);
          
          // 從 allTradesCache 找框選範圍內的交易
          const inBounds = [];
          allTradesCache.current.forEach((trade) => {
            if (bounds.contains([trade.lat, trade.lon])) {
              inBounds.push(trade);
            }
          });
          
          setBoxCount(inBounds.length);
          if (inBounds.length > 0) {
            onBoxSelectRef.current?.(inBounds);
          }
        }
      });

      // 初始載入
      updateMarkers();

      // 自動縮放
      if (filters?.city && CITY_BOUNDS[filters.city]) {
        const [sw, ne] = CITY_BOUNDS[filters.city];
        map.fitBounds([[sw[0], sw[1]], [ne[0], ne[1]]]);
      }
    }

    init();

    return () => {
      cancelled = true;
      if (mapInstanceRef.current) {
        const map = mapInstanceRef.current;
        map.remove();
        if (mapRef.current) {
          delete mapRef.current._leaflet_id;
          delete mapRef.current._leaflet_disable;
        }
        mapInstanceRef.current = null;
      }
    };
  }, []); // 只跑一次

  /* ── trades 改變時更新 marker ── */
  useEffect(() => {
    if (mapInstanceRef.current) {
      updateMarkers();
      if (filters?.city && CITY_BOUNDS[filters.city]) {
        const [sw, ne] = CITY_BOUNDS[filters.city];
        mapInstanceRef.current.fitBounds([[sw[0], sw[1]], [ne[0], ne[1]]]);
      }
    }
  }, [trades, updateMarkers, filters]);

  /* ── selectedId 改變 → 飛到該點 + 開 popup + 開 modal ── */
  useEffect(() => {
    if (!selectedId || !mapInstanceRef.current) return;

    const map = mapInstanceRef.current;
    const marker = allMarkersCache.current.get(selectedId);
    const trade = allTradesCache.current.get(selectedId);

    if (marker) {
      const latlng = marker.getLatLng();
      const targetZoom = Math.max(map.getZoom(), 16);
      map.flyTo(latlng, targetZoom, { duration: 0.8, noMoveStart: true });
      
      // flyTo 結束後開 popup
      setTimeout(() => {
        if (allMarkersCache.current.has(selectedId)) {
          marker.openPopup();
        }
      }, 900);
      
      // 開 modal
      if (trade) setDetailTrade(trade);
    } else if (trade && trade.lat != null && trade.lon != null) {
      // Fallback: trade 不在目前頁面的 marker 中，直接飛到座標
      console.log('[FindMap] Fallback flyTo:', selectedId, trade.address);
      map.flyTo([trade.lat, trade.lon], 16, { duration: 0.8, noMoveStart: true });
      setDetailTrade(trade);
    }
  }, [selectedId]);

  /* ── hoveredId 同步高亮 ── */
  useEffect(() => {
    if (!hoveredId) return;
    const marker = allMarkersCache.current.get(hoveredId);
    if (marker) {
      marker.setStyle({ radius: 9, fillOpacity: 1, weight: 3 });
    }
    return () => {
      const m = allMarkersCache.current.get(hoveredId);
      if (m && hoveredId !== selectedId) {
        m.setStyle({ radius: 6, fillOpacity: 0.75, weight: 2 });
      }
    };
  }, [hoveredId, selectedId]);

  /* ── 框選結果提示自動消失 ── */
  useEffect(() => {
    if (boxCount !== null) {
      const timer = setTimeout(() => setBoxCount(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [boxCount]);

  return (
    <div className="relative">
      <div ref={mapRef} className="w-full h-[600px] rounded-xl border border-stone-200 overflow-hidden" />
      
      <MapLegend colorMode={colorMode} />

      {boxCount !== null && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-[500] bg-emerald-600 text-white px-4 py-2 rounded-lg shadow-lg text-sm font-medium animate-pulse">
          框選範圍內 {boxCount} 筆成交紀錄
        </div>
      )}
      
      {detailTrade && (
        <TradeDetailModal
          trade={detailTrade}
          onClose={() => setDetailTrade(null)}
        />
      )}
    </div>
  );
}
