'use client';
import { useEffect, useRef, useState, useCallback } from 'react';
import { formatFloor } from '../lib/floor';

const cityCenters = {
  '臺北市': [25.0330, 121.5654],
  '新北市': [25.0300, 121.4680],
  '桃園市': [24.9941, 121.3060],
  '新竹市': [24.7894, 121.0094],
  '新竹縣': [24.8069, 121.0267],
  '臺中市': [24.1477, 120.6736],
  '台南市': [22.9963, 120.2131],
  '高雄市': [22.6273, 120.3014],
  '基隆市': [25.1370, 121.7450],
  '宜蘭縣': [24.7526, 121.7580],
  '苗栗縣': [24.5600, 120.8320],
  '彰化縣': [24.0800, 120.5400],
  '南投縣': [23.8960, 120.7780],
  '雲林縣': [23.7200, 120.5500],
  '嘉義縣': [23.4600, 120.3800],
  '嘉義市': [23.4770, 120.4430],
  '屏東縣': [22.6750, 120.4850],
  '花蓮縣': [23.9760, 121.6030],
  '台東縣': [22.7500, 121.1450],
};

// 通勤目的地（與後端 OFFICE_LOCATIONS 對應）
const OFFICE_LOCATIONS = {
  '臺北市': [{ name: '信義計畫區', lat: 25.0338, lon: 121.5645 }, { name: '南港軟體園區', lat: 25.0529, lon: 121.6068 }, { name: '內湖科技園區', lat: 25.0742, lon: 121.5750 }],
  '新北市': [{ name: '板橋車站', lat: 25.0140, lon: 121.4602 }, { name: '新莊副都心', lat: 25.0405, lon: 121.4538 }],
  '桃園市': [{ name: '中壢站前', lat: 24.9536, lon: 121.2295 }, { name: '桃園高鐵站', lat: 25.0153, lon: 121.2193 }],
  '新竹市': [{ name: '竹科', lat: 24.7894, lon: 121.0094 }],
  '新竹縣': [{ name: '竹科', lat: 24.7894, lon: 121.0094 }, { name: '竹北交流道', lat: 24.8069, lon: 121.0267 }],
  '臺中市': [{ name: '中科', lat: 24.1586, lon: 120.6667 }, { name: '台中七期', lat: 24.1477, lon: 120.6737 }],
  '台南市': [{ name: '台南火車站', lat: 22.9963, lon: 120.2131 }],
  '高雄市': [{ name: '高雄捷運紅線', lat: 22.6376, lon: 120.3137 }],
};

function getScoreColor(score) {
  if (score == null) return '#94a3b8';
  if (score >= 80) return '#16a34a';
  if (score >= 60) return '#2563eb';
  if (score >= 40) return '#d97706';
  return '#dc2626';
}

function getPriceColor(unitPrice) {
  if (unitPrice == null) return '#94a3b8';
  const num = Number(unitPrice);
  if (num > 80) return '#dc2626';
  if (num > 60) return '#b91c1c';
  if (num > 40) return '#d97706';
  if (num > 25) return '#92400e';
  return '#637d56';
}

export default function FindMap({ trades, selectedId, onSelect, colorMode = 'score', commuteCity, maxCommuteTime }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const LRef = useRef(null);
  const markersRef = useRef([]);
  const commuteCircleRef = useRef(null);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(null);

  // Load Leaflet
  useEffect(() => {
    if (window.L) {
      LRef.current = window.L;
      setLoaded(true);
      return;
    }
    let loadedFlag = false;
    const loadScript = () => {
      return new Promise((resolve, reject) => {
        if (document.querySelector('link[href*="leaflet"]')) resolve(true);
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
        link.crossOrigin = '';
        document.head.appendChild(link);
        const script = document.createElement('script');
        script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
        script.crossOrigin = '';
        script.onload = () => { if (!loadedFlag) { loadedFlag = true; resolve(true); } };
        script.onerror = () => reject(new Error('Failed to load Leaflet'));
        document.head.appendChild(script);
      });
    };
    loadScript().then(() => { LRef.current = window.L; setLoaded(true); }).catch(setError);
  }, []);

  // Init map
  useEffect(() => {
    if (!loaded || !containerRef.current || mapRef.current) return;
    const L = LRef.current;
    if (!L) return;
    try {
      const center = trades.length > 0 && trades[0].lat
        ? [trades[0].lat, trades[0].lon]
        : [25.0330, 121.5654];
      const map = L.map(containerRef.current).setView(center, 10);
      delete L.Icon.Default.prototype._getIconUrl;
      L.Icon.Default.mergeOptions({
        iconRetinaUrl: '/leaflet/marker-icon-2x.png',
        iconUrl: '/leaflet/marker-icon.png',
        shadowUrl: '/leaflet/marker-shadow.png',
      });
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors',
        maxZoom: 19,
      }).addTo(map);
      mapRef.current = map;
    } catch (err) { setError(err.message); }
  }, [loaded]);

  // Update markers
  const updateMarkers = useCallback(() => {
    if (!mapRef.current || !LRef.current || !trades?.length) return;
    const L = LRef.current;
    const map = mapRef.current;

    // Remove old circle markers
    markersRef.current.forEach(m => map.removeLayer(m));
    markersRef.current = [];

    const bounds = [];

    trades.forEach((trade) => {
      const lat = trade.lat;
      const lng = trade.lon;
      if (!lat || !lng) return;
      bounds.push([lat, lng]);

      const score = trade.score_overall;
      const unitPrice = trade.unit_price_tping;
      const color = colorMode === 'score' ? getScoreColor(score) : getPriceColor(unitPrice);
      const isSelected = selectedId === trade.id;

      const marker = L.circleMarker([lat, lng], {
        radius: isSelected ? 14 : 9,
        fillColor: color,
        color: isSelected ? '#fbbf24' : '#fff',
        weight: isSelected ? 3 : 2,
        fillOpacity: 0.85,
      });

      const totalPriceWan = trade.total_price_wan?.toLocaleString() || '—';
      const unitPriceStr = unitPrice ? `${Number(unitPrice).toFixed(1)}萬/坪` : '—';
      const areaPing = trade.building_area_tping ? `${trade.building_area_tping}坪` : '—';
      const layoutStr = trade.rooms != null ? `${trade.rooms || '?'}房${trade.living_rooms || '?'}廳${trade.bathrooms || '?'}衛` : '—';
      const ageStr = trade.building_age != null ? (trade.building_age === 0 ? '新成屋' : `${trade.building_age}年`) : '—';
      const floorStr = trade.floor ? formatFloor(trade.floor, trade.total_floors) : '—';
      const scoreStr = score != null ? `${score}分` : '—';

      marker.bindPopup(`
        <div style="min-width: 220px; font-family: system-ui;">
          <p><strong>${trade.city}${trade.district}</strong></p>
          <p style="font-size:12px;color:#64748b">${trade.address}</p>
          <hr style="margin:6px 0;border:none;border-top:1px solid #eee">
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px 12px;font-size:13px;">
            <span>總價</span><strong style="color:#637d56">${totalPriceWan}萬</strong>
            <span>單價</span><strong>${unitPriceStr}</strong>
            <span>面積</span><span>${areaPing}</span>
            <span>屋齡</span><span>${ageStr}</span>
            <span>格局</span><span>${layoutStr}</span>
            <span>樓層</span><span>${floorStr}</span>
            <span>型態</span><span>${trade.building_type || '—'}</span>
            <span>生活圈</span><strong style="color:${color}">${scoreStr}</strong>
            ${trade.commute_time != null ? `<span>通勤</span><span>${trade.commute_time}分</span>` : ''}
          </div>
        </div>
      `);

      marker.on('click', () => {
        if (onSelect) onSelect(trade.id);
      });

      marker.addTo(map);
      markersRef.current.push(marker);
    });

    if (bounds.length > 0) {
      map.fitBounds(bounds, { padding: [40, 40] });
    } else if (bounds.length === 0 && trades.length > 0) {
      // Some trades but no coords — use first city center found
      const firstCity = trades.find(t => t.city)?.city;
      if (firstCity && cityCenters[firstCity]) {
        map.setView(cityCenters[firstCity], 11);
      }
    }

    // ── 通勤距離圈 ──
    if (commuteCircleRef.current) {
      map.removeLayer(commuteCircleRef.current);
      commuteCircleRef.current = null;
    }
    if (commuteCity && maxCommuteTime && OFFICE_LOCATIONS[commuteCity]) {
      const offices = OFFICE_LOCATIONS[commuteCity];
      // 車程估算：30km/h 市區速度
      const radiusKm = (Number(maxCommuteTime) / 60) * 30;
      const radiusM = radiusKm * 1000;

      // 以最近標記的座標為中心畫圈（或用第一個辦公室）
      const centerOffice = offices[0];
      const allCircles = offices.map(o =>
        L.circle([o.lat, o.lon], {
          radius: radiusM,
          fillColor: '#3b82f6',
          color: '#3b82f6',
          fillOpacity: 0.08,
          weight: 1.5,
          dashArray: '6,4',
        }).bindTooltip(`${o.name}（${maxCommuteTime}分鐘車程圈）`, { sticky: true })
      );
      const group = L.layerGroup(allCircles).addTo(map);
      commuteCircleRef.current = group;

      // 確保圈和標記都在視野內
      if (bounds.length > 0) {
        const extendedBounds = [...bounds];
        offices.forEach(o => extendedBounds.push([o.lat, o.lon]));
        map.fitBounds(extendedBounds, { padding: [40, 40] });
      }
    }
  }, [trades, selectedId, colorMode, onSelect, commuteCity, maxCommuteTime]);

  useEffect(() => {
    if (loaded && mapRef.current) updateMarkers();
  }, [loaded, updateMarkers]);

  if (error) {
    return (
      <div className="w-full h-[500px] flex items-center justify-center bg-stone-100 text-red-600 rounded-xl">
        地圖載入失敗: {error}
      </div>
    );
  }

  if (!loaded) {
    return (
      <div className="w-full h-[500px] flex items-center justify-center bg-stone-100 text-stone-400 rounded-xl">
        地圖載入中...
      </div>
    );
  }

  return (
    <div className="rounded-xl overflow-hidden border border-stone-200 shadow-sm">
      <div ref={containerRef} className="w-full h-[500px]" />
    </div>
  );
}
