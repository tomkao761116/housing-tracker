'use client';
import { useEffect, useRef, useState } from 'react';
/* ── SVG Icons ─────────────────────────────────────── */
function IconMapPin({ className = "w-5 h-5" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>
    </svg>
  );
}
const cityCenters = {
  '臺北市': [25.0330, 121.5654],
  '新北市': [25.0300, 121.4680],
  '桃園市': [24.9941, 121.3060],
  '臺中市': [24.1477, 120.6736],
  '高雄市': [22.6273, 120.3014],
};

export default function MapComponent({ trades, city }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const LRef = useRef(null);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(null);

  // Load Leaflet from CDN once
  useEffect(() => {
    if (window.L) {
      LRef.current = window.L;
      setLoaded(true);
      return;
    }

    let loadedFlag = false;

    const loadScript = () => {
      return new Promise((resolve, reject) => {
        // CSS
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
        link.integrity = 'sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=';
        link.crossOrigin = '';
        document.head.appendChild(link);

        // JS
        const script = document.createElement('script');
        script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
        script.integrity = 'sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=';
        script.crossOrigin = '';
        script.onload = () => {
          if (!loadedFlag) {
            loadedFlag = true;
            resolve(true);
          }
        };
        script.onerror = () => reject(new Error('Failed to load Leaflet'));
        document.head.appendChild(script);
      });
    };

    loadScript()
      .then(() => {
        LRef.current = window.L;
        setLoaded(true);
        console.log('[Map] Leaflet loaded from CDN');
      })
      .catch((err) => {
        setError(err.message);
        console.error('[Map]', err);
      });
  }, []);

  // Initialize map when Leaflet is ready
  useEffect(() => {
    if (!loaded || !containerRef.current || mapRef.current) return;

    const L = LRef.current;
    if (!L) return;

    try {
      const center = cityCenters[city] || [25.0330, 121.5654];
      const map = L.map(containerRef.current).setView(center, 11);

      // Fix marker icons
      delete L.Icon.Default.prototype._getIconUrl;
      L.Icon.Default.mergeOptions({
        iconRetinaUrl: '/leaflet/marker-icon-2x.png',
        iconUrl: '/leaflet/marker-icon.png',
        shadowUrl: '/leaflet/marker-shadow.png',
      });

      // Add OSM tile layer
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors',
        maxZoom: 19,
      }).addTo(map);

      mapRef.current = map;
      console.log('[Map] Initialized at', center);
    } catch (err) {
      setError(err.message);
      console.error('[Map] Init error:', err);
    }
  }, [loaded, city]);

  // Update markers when trades change
  useEffect(() => {
    if (!mapRef.current || !LRef.current || !trades || !trades.length) return;

    const L = LRef.current;
    const map = mapRef.current;

    // Remove existing circle markers
    const toRemove = [];
    map.eachLayer((layer) => {
      if (layer instanceof L.CircleMarker) {
        toRemove.push(layer);
      }
    });
    toRemove.forEach(l => map.removeLayer(l));

    const bounds = [];

    trades.forEach((trade) => {
      const lat = trade.lat || (cityCenters[city]?.[0] ?? 25.033) + (Math.random() - 0.5) * 0.05;
      const lng = trade.lon || (cityCenters[city]?.[1] ?? 121.565) + (Math.random() - 0.5) * 0.05;
      bounds.push([lat, lng]);

      const pricePerPing = trade.unit_price_tping || 0;
      let color;
      if (pricePerPing > 800000) color = '#dc2626';
      else if (pricePerPing > 600000) color = '#b91c1c';
      else if (pricePerPing > 400000) color = '#d97706';
      else if (pricePerPing > 250000) color = '#92400e';
      else color = '#637d56';

      const totalPriceWan = trade.total_price ? Math.round(trade.total_price / 10000).toLocaleString() : '-';
      const unitPriceWan = pricePerPing ? (pricePerPing / 10000).toFixed(1) : '-';
      const areaSqm = trade.building_area ? trade.building_area.toFixed(1) : '-';
      const areaPing = trade.building_area ? (trade.building_area / 3.3058).toFixed(1) : '-';
      const layoutStr = trade.rooms != null ? `${trade.rooms || '-'}房${trade.living_rooms || '-'}廳${trade.bathrooms || '-'}衛` : '-';

      const marker = L.circleMarker([lat, lng], {
        radius: 8,
        fillColor: color,
        color: '#fff',
        weight: 2,
        fillOpacity: 0.8,
      }).bindPopup(`
        <div style="min-width: 200px;">
          <p><strong>${trade.city}${trade.district}</strong></p>
          <p style="font-size:12px;color:#64748b">${trade.address}</p>
          <hr style="margin:4px 0;border:none;border-top:1px solid #eee">
          <p>總價: <strong style="color:#637d56">${totalPriceWan}萬</strong></p>
          <p>單價: <strong>${unitPriceWan}萬</strong> 元/坪</p>
          <p>面積: ${areaPing} 坪 (${areaSqm} ㎡)</p>
          <p>格局: ${layoutStr}</p>
          ${trade.building_type ? `<p>型態: ${trade.building_type}</p>` : ''}
          ${trade.trade_date ? `<p>交易日: ${trade.trade_date}</p>` : ''}
        </div>
      `);

      marker.addTo(map);
    });

    if (bounds.length > 0) {
      map.fitBounds(bounds, { padding: [50, 50] });
    }

    console.log(`[Map] ${trades.length} markers added`);
  }, [trades, city]);

  if (error) {
    return (
      <div style={{ width: '100%', height: '600px', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#f1f5f9', color: '#dc2626' }}>
        地圖載入失敗: {error}
      </div>
    );
  }

  if (!loaded) {
    return (
      <div style={{ width: '100%', height: '600px', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#f1f5f9', color: '#475569' }}>
        <IconMapPin className="w-5 h-5 inline-block" /> 地圖載入中...
      </div>
    );
  }

  return (
    <div ref={containerRef} style={{ width: '100%', height: '600px' }} />
  );
}
