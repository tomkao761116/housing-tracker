/**
 * 成交地圖元件 — v3
 * 
 * 互動邏輯：
 * 1. 點擊 marker → flyTo + 通知父元件 onSelect（列表滾動+高亮）
 * 2. 收到 selectedId → flyTo（從列表點擊）
 * 3. 無 popup/modal，純視覺 focus
 * 4. cluster 展開後不自動收合
 */
'use client';

import { useEffect, useRef, useCallback, useState } from 'react';
import 'leaflet/dist/leaflet.css';
import 'leaflet.markercluster/dist/MarkerCluster.css';
import 'leaflet.markercluster/dist/MarkerCluster.Default.css';
import 'leaflet-draw/dist/leaflet.draw.css';
import { Square } from 'lucide-react';

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
export default function FindMap({ trades, selectedId, onSelect, hoveredId, onMarkerHover, colorMode, filters, onBoxSelect, onMapReady }) {
  const mapRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const LRef = useRef(null);
  
  // marker cache: id -> marker
  const allMarkersCache = useRef(new Map());
  
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

    // 點擊 marker → 通知父元件（由父元件驅動列表滾動+高亮）
    marker.on('click', () => {
      onSelectRef.current?.(trade.id);
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

    const currentTrades = trades;
    if (!currentTrades || currentTrades.length === 0) return;

    currentTrades
      .filter(t => t.lat != null && t.lon != null)
      .forEach(trade => {
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
        disableClusteringAtZoom: 17,
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

      // 防止 cluster 自動收合：展開後保持 spiderfy 狀態
      let lastSpiderfiedCluster = null;
      clusterGroup.on('spiderfied', (e) => {
        lastSpiderfiedCluster = e.cluster;
      });
      clusterGroup.on('unspiderfied', (e) => {
        // 阻止自動收合，重新展開
        if (lastSpiderfiedCluster && lastSpiderfiedCluster !== e.cluster) {
          setTimeout(() => {
            try {
              clusterGroup.spiderfy(lastSpiderfiedCluster.getLatLng());
            } catch(err) {
              // 如果座標已失效，清除記錄
              lastSpiderfiedCluster = null;
            }
          }, 0);
        }
      });

      map.addLayer(clusterGroup);
      mapInstanceRef.current = map;
      mapInstanceRef.current._clusterGroup = clusterGroup;

      // 通知父元件地圖已就緒，並暴露 resetView 方法
      if (onMapReady) {
        onMapReady({
          resetView: () => {
            map.flyTo(DEFAULT_CENTER, DEFAULT_ZOOM, { duration: 0.8 });
          },
          flyToTrade: (tradeId) => {
            const marker = allMarkersCache.current.get(tradeId);
            if (marker) {
              const latlng = marker.getLatLng();
              map.flyTo(latlng, Math.max(map.getZoom(), 16), { duration: 0.8 });
            }
          },
        });
      }

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
          
          const inBounds = [];
          allMarkersCache.current.forEach((marker, id) => {
            if (bounds.contains(marker.getLatLng())) {
              const trade = trades.find(t => t.id === id);
              if (trade) inBounds.push(trade);
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

      // 自動縮放到縣市範圍
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

  /* ── selectedId 改變 → flyTo + 高亮 marker ── */
  useEffect(() => {
    if (!selectedId || !mapInstanceRef.current) return;

    const map = mapInstanceRef.current;
    const marker = allMarkersCache.current.get(selectedId);

    if (marker) {
      const latlng = marker.getLatLng();
      const targetZoom = Math.max(map.getZoom(), 16);
      map.flyTo(latlng, targetZoom, { duration: 0.8, noMoveStart: true });
      
      // 高亮選中的 marker
      marker.setStyle({ radius: 9, fillOpacity: 1, weight: 3, color: '#5a6b4e' });
    } else {
      // Fallback: 從 trades 找座標
      const trade = trades.find(t => t.id === selectedId);
      if (trade && trade.lat != null && trade.lon != null) {
        map.flyTo([trade.lat, trade.lon], 16, { duration: 0.8, noMoveStart: true });
      }
    }
  }, [selectedId, trades]);

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
    </div>
  );
}
