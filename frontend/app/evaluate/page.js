'use client';
import { useState, useCallback, useEffect, useMemo } from 'react';
import dynamic from 'next/dynamic';
import { formatFloor } from '../../lib/floor';
const RadarChart = dynamic(() => import('../../components/RadarChart'), { ssr: false });
const ScoreRing = dynamic(() => import('../../components/ScoreRing'), { ssr: false });
import { API } from '@/lib/api';

/* ── SVG Icons ─────────────────────── */
function IconTransit({ className = "w-5 h-5" }) {
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="5" y="2" width="14" height="20" rx="2"/><line x1="9" y1="6" x2="9.01" y2="6"/><line x1="15" y1="6" x2="15.01" y2="6"/><line x1="9" y1="10" x2="9.01" y2="10"/><line x1="15" y1="10" x2="15.01" y2="10"/><path d="M9 14h6"/><path d="M9 18h6"/></svg>;
}
function IconEducation({ className = "w-5 h-5" }) {
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/></svg>;
}
function IconMedical({ className = "w-5 h-5" }) {
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 21C7 21 4 18 4 13V7l4-1 4-2 4 2 4 1v6c0 5-3 8-8 8z"/><line x1="12" y1="9" x2="12" y2="15"/><line x1="9" y1="12" x2="15" y2="12"/></svg>;
}
function IconShopping({ className = "w-5 h-5" }) {
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/><path d="M1 1h4l2.68 13.39a2 2 0 002 1.61h9.72a2 2 0 002-1.61L23 6H6"/></svg>;
}
function IconLeisure({ className = "w-5 h-5" }) {
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/></svg>;
}
function IconDining({ className = "w-5 h-5" }) {
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 8h1a4 4 0 010 8h-1"/><path d="M2 8h16v9a4 4 0 01-4 4H6a4 4 0 01-4-4V8z"/><line x1="6" y1="1" x2="6" y2="4"/><line x1="10" y1="1" x2="10" y2="4"/><line x1="14" y1="1" x2="14" y2="4"/></svg>;
}
function IconLocation({ className = "w-5 h-5" }) {
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/></svg>;
}
function IconClock({ className = "w-5 h-5" }) {
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12,6 12,12 16,14"/></svg>;
}
function IconHome({ className = "w-5 h-5" }) {
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/><polyline points="9,22 9,12 15,12 15,22"/></svg>;
}
function IconCar({ className = "w-5 h-5" }) {
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M5 17h14M5 17a2 2 0 01-2-2V9a2 2 0 012-2h1l2-3h8l2 3h1a2 2 0 012 2v6a2 2 0 01-2 2M5 17l-1 2h1m14-2l1 2h-1"/><circle cx="7.5" cy="17" r="1.5"/><circle cx="16.5" cy="17" r="1.5"/></svg>;
}
function IconBus({ className = "w-5 h-5" }) {
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="14" rx="2"/><line x1="3" y1="10" x2="21" y2="10"/><circle cx="7.5" cy="17" r="1.5"/><circle cx="16.5" cy="17" r="1.5"/></svg>;
}
function IconWalk({ className = "w-5 h-5" }) {
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M13 4a2 2 0 112 2 2 2 0 01-2-2z"/><path d="M15 6l-2 8"/><path d="M13 14l-2 6"/><path d="M8 14l2 6"/><path d="M10 14l-1-4"/><path d="M10 10a3 3 0 00-3-3 3 3 0 00-3 3l0 4"/></svg>;
}
function IconBike({ className = "w-5 h-5" }) {
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="5.5" cy="17.5" r="3.5"/><circle cx="18.5" cy="17.5" r="3.5"/><path d="M15 6a1 1 0 100-2 1 1 0 000 2z"/><path d="M12 17.5V14l-3-3 4-3 2 3h3"/></svg>;
}
function IconGPS({ className = "w-5 h-5" }) {
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="3,11 22,2 13,21 11,13"/></svg>;
}
function IconSearch({ className = "w-5 h-5" }) {
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>;
}
function IconTrendUp({ className = "w-5 h-5" }) {
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="23,6 13.5,15.5 8.5,10.5 1,18"/><polyline points="17,6 23,6 23,12"/></svg>;
}
function IconEmpty({ className = "w-5 h-5" }) {
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/><polyline points="9,22 9,12 15,12 15,22"/></svg>;
}
function IconChevronDown({ className = "w-4 h-4" }) {
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="6,9 12,15 18,9"/></svg>;
}

/* ── Dimensions Config ─────────────── */
const DIMENSIONS = [
  { key: 'transit',   label: '交通', icon: IconTransit, color: '#637d56' },
  { key: 'education', label: '教育', icon: IconEducation, color: '#475569' },
  { key: 'medical',   label: '醫療', icon: IconMedical, color: '#dc2626' },
  { key: 'shopping',  label: '購物', icon: IconShopping, color: '#d97706' },
  { key: 'leisure',   label: '休閒', icon: IconLeisure, color: '#556b48' },
  { key: 'dining',    label: '餐飲', icon: IconDining, color: '#92400e' },
];

/* ── Shared Input Styles ───────────── */
const inputCls = 'w-full bg-white border border-[#e8e4df] rounded-md px-4 py-2.5 text-[#2a2a2a] placeholder-[#ccc] focus:outline-none focus:ring-1 focus:ring-[#5a6b4e] focus:border-[#5a6b4e] transition-all text-sm';

/* ── Format Helpers ────────────────── */
function scoreColor(baseColor, s) {
  // baseColor: hex string like '#637d56' (dimension identity color)
  // s: score 0-100; returns lighter/darker variant preserving hue
  if (s == null || !baseColor) return baseColor || '#94a3b8';
  
  const hex = baseColor.replace('#', '');
  const r = parseInt(hex.substring(0, 2), 16);
  const g = parseInt(hex.substring(2, 4), 16);
  const b = parseInt(hex.substring(4, 6), 16);
  
  const t = Math.max(0, Math.min(100, s)) / 100;
  // Mix with gray: low score = muted/dark, high score = vibrant original
  const mixGray = 0.35 + 0.65 * t;
  const grayBase = 180;
  const nr = Math.round(r * mixGray + grayBase * (1 - mixGray));
  const ng = Math.round(g * mixGray + grayBase * (1 - mixGray));
  const nb = Math.round(b * mixGray + grayBase * (1 - mixGray));
  
  return `rgb(${nr}, ${ng}, ${nb})`;
}

/* ── Section Header (Dashboard 區塊標題) ── */
function SectionHeader({ icon: Icon, title, subtitle }) {
  return (
    <div className="flex items-start gap-3 mb-4">
      <div className="p-2 rounded-sm bg-[#f0eeeb] mt-0.5">
        <Icon className="w-5 h-5 text-[#5a6b4e]" />
      </div>
      <div>
        <h3 className="text-base font-semibold text-[#2a2a2a]">{title}</h3>
        {subtitle && <p className="text-xs text-[#777] mt-0.5">{subtitle}</p>}
      </div>
    </div>
  );
}

/* ── Error Box with actionable suggestions ── */
function ErrorBox({ message, context }) {
  // Provide specific suggestions based on error content
  let suggestion = null;
  const msg = (message || '').toLowerCase();
  
  if (msg.includes('geocode') || msg.includes('地址') || msg.includes('找不到')) {
    suggestion = '請確認地址格式完整（例：台北市大安區信義路四段123號），或嘗試輸入經緯度。';
  } else if (msg.includes('network') || msg.includes('fetch') || msg.includes('連接')) {
    suggestion = '請檢查網路連線，或稍後再試。若問題持續，可能是伺服器維護中。';
  } else if (msg.includes('rate') || msg.includes('限流') || msg.includes('too many')) {
    suggestion = '請求太頻繁，請等待幾秒鐘後再試。';
  } else if (msg.includes('commute') || msg.includes('通勤') || msg.includes('路線')) {
    suggestion = '請確認目的地名稱是否正確，或嘗試其他寫法（如「台北101」改為「信義區」）。';
  } else if (msg.includes('radius') || msg.includes('半徑')) {
    suggestion = '請調整搜尋半徑範圍後再試。';
  } else {
    suggestion = '請重新操作一次，若問題持續請聯繫管理員。';
  }

  return (
    <div className="bg-[#fef2f2] border border-[#fecaca] rounded-md p-4">
      <div className="flex items-start gap-2">
        <svg className="w-5 h-5 text-[#dc2626] flex-shrink-0 mt-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
        <div className="flex-1">
          <p className="text-sm text-[#991b1b] font-medium">{message}</p>
          <p className="text-xs text-[#dc2626] mt-1">{suggestion}</p>
        </div>
      </div>
    </div>
  );
}

/* ════════════════════════════════════════
   Main Page
   ═════════════════════════════════════ */
export default function EvaluatePage() {
  // Input state
  const [address, setAddress] = useState('');
  const [lat, setLat] = useState('');
  const [lon, setLon] = useState('');
  const [radius, setRadius] = useState(1000);
  // Resolved coordinates (from address geocoding or direct input)
  const [resolvedLat, setResolvedLat] = useState('');
  const [resolvedLon, setResolvedLon] = useState('');

  // Scorecard state
  const [scoreResult, setScoreResult] = useState(null);
  const [scoreLoading, setScoreLoading] = useState(false);
  const [scoreError, setScoreError] = useState(null);

  // POI state
  const [poiResult, setPoiResult] = useState(null);
  const [poiExpanded, setPoiExpanded] = useState({}); // { transit: true, ... }

  // Commute state
  const [commuteDest, setCommuteDest] = useState('');
  const [commuteResult, setCommuteResult] = useState(null);
  const [commuteLoading, setCommuteLoading] = useState(false);
  const [commuteError, setCommuteError] = useState(null);
  const [showDestSuggestions, setShowDestSuggestions] = useState(false);

  /* ── Popular commute destinations (autocomplete) ── */
  const POPULAR_DESTINATIONS = [
    '台北101', '信義區', '南港軟體園區', '內湖科技園區',
    '松山機場', '桃園機場', '台北車站', '板橋車站',
    '新北市政府', '台中市政府', '高雄市政府', '台南市政府',
    '新竹科學園區', '台中國際機場', '高鐵台北站', '高鐵台中站',
    '高鐵左營站', '遠東百貨', '微風南山', 'ATT 4 FUN',
  ];

  const filteredDestinations = useMemo(() => {
    if (!commuteDest || commuteDest.length < 1) return POPULAR_DESTINATIONS.slice(0, 8);
    return POPULAR_DESTINATIONS.filter(d => d.includes(commuteDest)).slice(0, 6);
  }, [commuteDest]);

  // Trades state
  const [tradesResult, setTradesResult] = useState(null);
  const [tradesLoading, setTradesLoading] = useState(false);
  const [tradesError, setTradesError] = useState(null);
  const [tradesSort, setTradesSort] = useState('distance'); // distance | date | price | unitPrice

  /* ── GPS Location ── */
  const handleGetLocation = useCallback(() => {
    if (!navigator.geolocation) {
      alert('您的瀏覽器不支援定位功能');
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setAddress(''); // Clear address when using GPS
        setLat(pos.coords.latitude.toFixed(5));
        setLon(pos.coords.longitude.toFixed(5));
      },
      () => alert('無法取得位置資訊，請手動輸入座標')
    );
  }, []);

  /* ── Handle address input (mutually exclusive with coords) ── */
  const handleAddressChange = (e) => {
    const val = e.target.value;
    setAddress(val);
    if (val) {
      setLat('');
      setLon('');
    }
  };

  /* ── Handle coord input (mutually exclusive with address) ── */
  const handleLatChange = (e) => {
    const val = e.target.value;
    setLat(val);
    if (val) {
      setAddress('');
    }
  };
  const handleLonChange = (e) => {
    const val = e.target.value;
    setLon(val);
    if (val) {
      setAddress('');
    }
  };

  /* ── Fetch Scorecard + POIs + Trades ── */
  const fetchAll = useCallback(async () => {
    // Validate: need either address OR both lat and lon
    if (address) {
      // Will be geocoded by backend
    } else if (!lat || !lon) {
      setScoreError('請輸入地址或經緯度座標');
      return;
    }
    setScoreLoading(true);
    setScoreError(null);
    try {
      let url = `${API}/api/scorecard?radius=${radius}`;
      if (address) {
        url += `&address=${encodeURIComponent(address)}`;
      } else {
        url += `&lat=${lat}&lon=${lon}`;
      }
      // Fetch scorecard
      const scoreRes = await fetch(url);
      if (!scoreRes.ok) throw new Error('API 請求失敗');
      const scoreData = await scoreRes.json();
      if (scoreData.error) {
        setScoreError(scoreData.error);
        return;
      }
      setScoreResult(scoreData);
      // Save resolved coordinates for other tabs
      const finalLat = scoreData.location ? String(scoreData.location.lat) : lat;
      const finalLon = scoreData.location ? String(scoreData.location.lon) : lon;
      setResolvedLat(finalLat);
      setResolvedLon(finalLon);
      // Also fetch nearby trades in parallel
      setTradesLoading(true);
      setTradesError(null);
      try {
        const tradesRes = await fetch(`${API}/api/trades/nearby?lat=${finalLat}&lon=${finalLon}&radius=${radius}`);
        if (!tradesRes.ok) throw new Error('API 請求失敗');
        const tradesData = await tradesRes.json();
        setTradesResult(tradesData);
      } catch (err) {
        setTradesError(err.message);
      } finally {
        setTradesLoading(false);
      }
      // POI data is now included in scorecard response (dimensions[].pois)
      // No need for separate /api/location-pois call
    } catch (err) {
      setScoreError(err.message);
    } finally {
      setScoreLoading(false);
    }
  }, [lat, lon, radius, address]);

  /* ── Toggle POI dimension expand ── */
  const togglePoi = (key) => {
    setPoiExpanded(prev => ({ ...prev, [key]: !prev[key] }));
  };

  /* ── Fetch Commute ── */
  const effectiveLat = lat || resolvedLat;
  const effectiveLon = lon || resolvedLon;

  const fetchCommute = useCallback(async () => {
    if (!effectiveLat || !effectiveLon || !commuteDest) {
      setCommuteError('請輸入目的地並確認位置');
      return;
    }
    setCommuteLoading(true);
    setCommuteError(null);
    try {
      const res = await fetch(`${API}/api/time?lat=${effectiveLat}&lon=${effectiveLon}&destination=${encodeURIComponent(commuteDest)}`);
      if (!res.ok) throw new Error('API 請求失敗');
      const data = await res.json();
      setCommuteResult(data);
    } catch (err) {
      setCommuteError(err.message);
    } finally {
      setCommuteLoading(false);
    }
  }, [effectiveLat, effectiveLon, commuteDest]);

  /* ── Fetch Nearby Trades ── */
  const fetchTrades = useCallback(async () => {
    if (!effectiveLat || !effectiveLon) {
      setTradesError('請輸入位置或先查詢生活圈評分');
      return;
    }
    setTradesLoading(true);
    setTradesError(null);
    try {
      const res = await fetch(`${API}/api/trades/nearby?lat=${effectiveLat}&lon=${effectiveLon}&radius=${radius}`);
      if (!res.ok) throw new Error('API 請求失敗');
      const data = await res.json();
      setTradesResult(data);
    } catch (err) {
      setTradesError(err.message);
    } finally {
      setTradesLoading(false);
    }
  }, [effectiveLat, effectiveLon, radius]);

  /* ── Geocoding preview (即時地址確認) ── */
  const [geoPreview, setGeoPreview] = useState(null);
  const [geoLoading, setGeoLoading] = useState(false);
  let geoDebounceRef = null;

  /* ── Toggle advanced coord input ── */
  const [showCoords, setShowCoords] = useState(false);

  /* ── Auto-fetch trades when scorecard resolves ── */
  useEffect(() => {
    // 生活圈評分完成後，自動載入周邊成交
    if (resolvedLat && resolvedLon && !tradesResult && !tradesLoading) {
      fetchTrades();
    }
  }, [resolvedLat, resolvedLon, tradesResult, tradesLoading, fetchTrades]);

  /* ── Close autocomplete on outside click ── */
  useEffect(() => {
    const handler = () => setShowDestSuggestions(false);
    document.addEventListener('click', handler);
    return () => document.removeEventListener('click', handler);
  }, []);

  /* ── Debounced geocoding preview ── */
  const handleAddressInput = (e) => {
    const val = e.target.value;
    setAddress(val);
    if (val) { setLat(''); setLon(''); }
    setGeoPreview(null);
    if (geoDebounceRef) clearTimeout(geoDebounceRef);
    if (val.length >= 5) {
      setGeoLoading(true);
      geoDebounceRef = setTimeout(async () => {
        try {
          const res = await fetch(`${API}/api/scorecard?radius=1000&address=${encodeURIComponent(val)}`);
          const data = await res.json();
          if (data.location) {
            setGeoPreview({ lat: data.location.lat, lon: data.location.lon, display: data.address || val });
          }
        } catch {}
        setGeoLoading(false);
      }, 600);
    } else {
      setGeoLoading(false);
    }
  };

  const useGeoPreview = () => {
    if (geoPreview) {
      setAddress(geoPreview.display);
      setLat(String(geoPreview.lat));
      setLon(String(geoPreview.lon));
      setGeoPreview(null);
    }
  };

  /* ── Extract scores for display ── */
  const overallScore = scoreResult?.overall_score ?? scoreResult?.scores?.overall;
  const dimScores = scoreResult?.dimensions || {};


  return (
    <div className="min-h-screen bg-[#faf9f7]">
      {/* ════════════════════════════════════════
          HEADER (仿照找房頁)
          ═════════════════════════════════════════ */}
      <div className="border-b border-[#e8e4df] bg-white/80 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
          <h1 className="text-xl font-medium text-[#2a2a2a] tracking-tight">地點評估</h1>
          <p className="text-sm text-[#999] mt-1">輸入地址，一次獲得生活圈評分、通勤時間與周邊成交比較。</p>
        </div>
      </div>

      {/* ════════════════════════════════════════
          CONTENT
          ═════════════════════════════════════════ */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 pt-6 pb-8 space-y-6">

      {/* ════════════════════════════════════════
          INPUT SECTION (精簡版)
          ═════════════════════════════════════════ */}
      <div className="bg-white/80 backdrop-blur-sm rounded-sm border border-[#e8e4df] p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-[#2a2a2a]">位置設定</h2>
          <button
            onClick={() => setShowCoords(!showCoords)}
            className="text-xs text-[#999] hover:text-[#777] transition-colors"
          >
            {showCoords ? '收起經緯度' : '手動輸入經緯度'}
          </button>
        </div>

        {/* Address input with geocoding preview */}
        <div>
          <input
            type="text"
            value={address}
            onChange={handleAddressInput}
            placeholder="例：台北市大安區信義路四段 100 號"
            className={inputCls}
          />
          {/* Geocoding preview */}
          {geoLoading && (
            <div className="flex items-center gap-2 mt-2 text-xs text-[#999]">
              <svg className="animate-spin w-3 h-3" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
              </svg>
              確認位置中...
            </div>
          )}
          {geoPreview && !geoLoading && (
            <div className="flex items-center gap-2 mt-2 px-3 py-2 rounded-sm bg-[#f0f7ed] border border-[#cddcb8] text-xs">
              <IconLocation className="w-3.5 h-3.5 text-[#5a6b4e] flex-shrink-0" />
              <span className="text-[#777] flex-1 truncate">{geoPreview.display}</span>
              <button
                onClick={useGeoPreview}
                className="px-2 py-0.5 rounded bg-[#5a6b4e] text-white hover:bg-[#4a5d3e] transition-colors flex-shrink-0"
              >
                使用此位置
              </button>
            </div>
          )}
        </div>

        {/* Lat/Lon inputs (collapsible) */}
        {showCoords && (
          <div className="pt-2 border-t border-[#e8e4df] space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-[#999] uppercase tracking-wider">經緯度座標</span>
              <button
                onClick={handleGetLocation}
                className="flex items-center gap-1 px-3 py-1.5 rounded-sm bg-[#f0eeeb] text-[#5a6b4e] hover:bg-[#e8e4df] transition-colors text-xs font-medium"
              >
                <IconGPS className="w-3.5 h-3.5" />
                GPS 定位
              </button>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-medium text-[#999] uppercase tracking-wider mb-2 block">緯度</label>
                <input
                  type="number"
                  step="0.000001"
                  value={lat}
                  onChange={handleLatChange}
                  placeholder="25.0330"
                  className={inputCls}
                />
              </div>
              <div>
                <label className="text-xs font-medium text-[#999] uppercase tracking-wider mb-2 block">經度</label>
                <input
                  type="number"
                  step="0.000001"
                  value={lon}
                  onChange={handleLonChange}
                  placeholder="121.5654"
                  className={inputCls}
                />
              </div>
            </div>
          </div>
        )}

        {/* Radius slider with context labels */}
        <div>
          <label className="text-xs font-medium text-[#999] uppercase tracking-wider mb-2 block">
            搜尋半徑：{radius} 公尺
            {radius <= 800 && '（步行圈）'}
            {radius > 800 && radius <= 1500 && '（生活圈）'}
            {radius > 1500 && radius <= 2200 && '（自行車圈）'}
            {radius > 2200 && '（車程圈）'}
          </label>
          <input
            type="range"
            min="500"
            max="3000"
            step="100"
            value={radius}
            onChange={e => setRadius(parseInt(e.target.value))}
            className="w-full h-2 rounded-full appearance-none cursor-pointer accent-emerald-500"
            style={{
              background: `linear-gradient(to right, #637d56 ${((radius - 500) / 2500) * 100}%, #e2e8f0 ${((radius - 500) / 2500) * 100}%)`,
            }}
          />
          <div className="flex justify-between text-xs text-[#999] mt-1">
            <span>500m · 步行</span>
            <span>1500m · 自轉</span>
            <span>3000m · 車程</span>
          </div>
        </div>

        {/* Search button */}
        <button
          onClick={fetchAll}
          disabled={scoreLoading}
          type="button"
          className="w-full flex items-center justify-center gap-2 px-6 py-3 rounded-sm bg-[#5a6b4e] text-white font-medium hover:bg-[#4a5d3e] disabled:opacity-50 disabled:cursor-not-allowed transition-all"
        >
          {scoreLoading ? (
            <>
              <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
              </svg>
              查詢中...
            </>
          ) : (
            <>
              <IconSearch className="w-4 h-4" />
              搜尋生活圈評分
            </>
          )}
        </button>
      </div>

      {/* ════════════════════════════════════════
          DASHBOARD: SCORECARD (生活圈評分)
          ═════════════════════════════════════════ */}
      <div className="space-y-4">
        <SectionHeader
          icon={IconLocation}
          title="生活圈評分"
          subtitle="六大維度綜合評估居住環境品質"
        />

        {/* Error */}
        {scoreError && <ErrorBox message={scoreError} />}

        {/* Scorecard Results */}
        {scoreResult && (
          <div className="space-y-4">
            {/* Overall score + Radar */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* Score Ring */}
              <div className="bg-white/80 backdrop-blur-sm rounded-sm border border-[#e8e4df] p-6 flex flex-col items-center justify-center">
                <h3 className="text-base font-semibold text-[#2a2a2a] mb-4">綜合評分</h3>
                <ScoreRing score={overallScore ?? 0} size={160} />
                <div className="mt-4 text-center">
                  <p className="text-sm text-[#777] flex items-center justify-center gap-1 flex-wrap">
                    {scoreResult.suggestion ? (
                      <>
                        {(() => {
                          const emojiMap = {
                            '🚇': { label: '交通', icon: IconTransit },
                            '🏫': { label: '教育', icon: IconEducation },
                            '🏥': { label: '醫療', icon: IconMedical },
                            '🛒': { label: '購物', icon: IconShopping },
                            '🌳': { label: '休閒', icon: IconLeisure },
                            '🍽️': { label: '餐飲', icon: IconDining },
                          };
                          let text = scoreResult.suggestion;
                          const parts = [];
                          let lastIndex = 0;
                          const regex = /[\u{1F300}-\u{1F9FF}]/gu;
                          let match;
                          let idx = 0;
                          while ((match = regex.exec(text)) !== null) {
                            const emoji = match[0];
                            const start = match.index;
                            if (start > lastIndex) {
                              parts.push(<span key={`t-${idx++}`}>{text.slice(lastIndex, start)}</span>);
                            }
                            const info = emojiMap[emoji];
                            const IconComp = info?.icon || IconLocation;
                            parts.push(<IconComp key={`i-${idx++}`} className="w-4 h-4 text-[#5a6b4e]" />);
                            lastIndex = regex.lastIndex;
                          }
                          if (lastIndex < text.length) {
                            parts.push(<span key={`t-${idx++}`}>{text.slice(lastIndex)}</span>);
                          }
                          return parts.length > 0 ? parts : text;
                        })()}
                      </>
                    ) : (
                      '此區域生活機能均衡，適合居住。'
                    )}
                  </p>
                </div>
              </div>

              {/* Radar Chart */}
              <div className="bg-white/80 backdrop-blur-sm rounded-sm border border-[#e8e4df] p-6">
                <h3 className="text-base font-semibold text-[#2a2a2a] mb-4 text-center">六維度雷達圖</h3>
                <RadarChart
                  scores={DIMENSIONS.reduce((acc, dim) => {
                    const dimData = dimScores[dim.key] || {};
                    if (dimData.score != null) {
                      acc[dim.key] = { score: dimData.score, label: dim.label, color: dim.color };
                    }
                    return acc;
                  }, {})}
                  size={320}
                />
              </div>
            </div>

            {/* Dimension Scores — Clickable Accordions */}
            <div className="bg-white/80 backdrop-blur-sm rounded-sm border border-[#e8e4df] overflow-hidden">
              <div className="divide-y divide-stone-100">
                {DIMENSIONS.map(dim => {
                  const dimData = dimScores[dim.key] || {};
                  const val = dimData.score != null ? dimData.score : dimScores[dim.key];
                  const count = dimData.count || 0;
                  const items = (dimData.pois || []).map(p => {
                    let name = p.name;
                    if (dim.key === 'transit' && p.type) {
                      const typeLabel = {
                        bus_stop: '公車站',
                        railway_station: '火車站',
                        station: '捷運站',
                        platform: '月台',
                      }[p.type] || p.type;
                      name = `${typeLabel} ${name}`;
                    }
                    return { name, distance: p.distance };
                  });
                  const isExpanded = poiExpanded[dim.key];

                  return (
                    <div key={dim.key}>
                      {/* Accordion Header */}
                      <button
                        onClick={() => togglePoi(dim.key)}
                        className="w-full flex items-center justify-between px-6 py-4 hover:bg-[#f5f4f0]/50 transition-colors"
                      >
                        <div className="flex items-center gap-3">
                          <div className="p-2 rounded-sm" style={{ backgroundColor: dim.color + '15' }}>
                            <dim.icon className="w-5 h-5" style={{ color: dim.color }} />
                          </div>
                          <div className="text-left">
                            <span className="text-sm font-medium text-stone-800">{dim.label}</span>
                          </div>
                        </div>
                        <div className="flex items-center gap-3">
                          <div className="text-right">
                            <div className="text-xl font-bold leading-none" style={{ color: scoreColor(dim.color, val) }}>
                              {val != null ? val : '-'}
                            </div>
                          </div>
                          <IconChevronDown
                            className={`w-4 h-4 text-[#999] transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}
                          />
                        </div>
                      </button>

                      {/* Expanded Content */}
                      {isExpanded && (
                        <div className="px-6 pb-4">
                          <p className="text-xs text-[#999] mb-2">{count} 個 POI 在此範圍內</p>
                          {count === 0 ? (
                            <p className="text-sm text-[#999] py-2">此範圍內無 {dim.label} 相關 POI</p>
                          ) : (
                            <div className="space-y-1 max-h-80 overflow-y-auto">
                              {items.slice(0, 50).map((item, i) => (
                                <div
                                  key={i}
                                  className="flex items-center justify-between px-3 py-2 rounded-sm bg-stone-50/50 text-sm"
                                >
                                  <span className="text-stone-700 truncate mr-4">{item.name}</span>
                                  <span className="text-[#999] whitespace-nowrap font-mono text-xs">
                                    {item.distance}m
                                  </span>
                                </div>
                              ))}
                              {items.length > 50 && (
                                <p className="text-xs text-[#999] text-center py-2">僅顯示前 50 筆，共 {items.length} 個</p>
                              )}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* Empty state */}
        {!scoreResult && !scoreLoading && !scoreError && (
          <div className="bg-white/80 backdrop-blur-sm rounded-sm border border-[#e8e4df] p-12 text-center">
            <IconLocation className="w-12 h-12 text-stone-300 mx-auto mb-4" />
            <p className="text-[#999]">輸入位置後點擊「查詢生活圈評分」開始評估</p>
          </div>
        )}
      </div>

      {/* ════════════════════════════════════════
          DASHBOARD: COMMUTE (通勤分析)
          ═════════════════════════════════════════ */}
      <div className="space-y-4">
        <SectionHeader
          icon={IconClock}
          title="通勤分析"
          subtitle="查詢各交通方式到達目的地的時間"
        />

        {/* Commute settings */}
        <div className="bg-white/80 backdrop-blur-sm rounded-sm border border-[#e8e4df] p-6 space-y-4">
          {/* Destination with autocomplete */}
          <div className="relative" onClick={e => e.stopPropagation()}>
            <label className="text-xs font-medium text-[#999] uppercase tracking-wider mb-2 block">目的地</label>
            <input
              type="text"
              value={commuteDest}
              onChange={e => setCommuteDest(e.target.value)}
              onFocus={() => setShowDestSuggestions(true)}
              placeholder="例：台北101、松山機場、南港軟體園區"
              className={inputCls}
              onKeyDown={e => e.key === 'Enter' && fetchCommute()}
            />
            {showDestSuggestions && filteredDestinations.length > 0 && (
              <div className="absolute z-10 w-full mt-1 bg-white border border-[#d0cdc8] rounded-sm shadow-lg max-h-48 overflow-y-auto">
                {filteredDestinations.map((dest, i) => (
                  <button
                    key={i}
                    type="button"
                    className="w-full text-left px-4 py-2.5 text-sm text-stone-700 hover:bg-[#f0f7ed] transition-colors first:rounded-t-xl last:rounded-b-xl"
                    onMouseDown={() => {
                      setCommuteDest(dest);
                      setShowDestSuggestions(false);
                      fetchCommute();
                    }}
                  >
                    {dest}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Submit */}
          <div className="flex justify-end">
            <button
              onClick={fetchCommute}
              disabled={commuteLoading}
              className="flex items-center gap-2 px-6 py-3 rounded-sm bg-[#5a6b4e] text-white font-medium hover:bg-[#4a5d3e] disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
              {commuteLoading ? (
                <>
                  <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                  </svg>
                  計算中...
                </>
              ) : (
                <>
                  <IconCar className="w-4 h-4" />
                  查詢通勤時間
                </>
              )}
            </button>
          </div>
        </div>

        {/* Error */}
        {commuteError && <ErrorBox message={commuteError} />}

        {/* Results — Bar chart visualization */}
        {commuteResult && (
          <div className="bg-white/80 backdrop-blur-sm rounded-sm border border-[#e8e4df] p-6">
            <h3 className="text-base font-semibold text-[#2a2a2a] mb-4 flex items-center gap-2">
              <IconTrendUp className="w-5 h-5 text-[#5a6b4e]" />
              通勤時間（{commuteResult.data?.[0]?.destination || ''}）
            </h3>
            {commuteResult.data && commuteResult.data.length > 0 ? (() => {
              const maxDuration = Math.max(...commuteResult.data.map(d => d.duration || 0), 1);
              return (
                <div className="space-y-4">
                  {commuteResult.data.map((item, i) => {
                    const pct = ((item.duration || 0) / maxDuration) * 100;
                    let barColor;
                    if (item.mode === 'car') barColor = '#637d56';
                    else if (item.mode === 'public') barColor = '#3b82f6';
                    else if (item.mode === 'walk') barColor = '#d97706';
                    else barColor = '#14b8a6';
                    return (
                      <div key={i}>
                        <div className="flex items-center justify-between mb-1.5">
                          <div className="flex items-center gap-2">
                            <div className="p-1.5 rounded-md" style={{ backgroundColor: barColor + '15' }}>
                              {item.mode === 'car' ? <IconCar className="w-4 h-4" style={{ color: barColor }} /> :
                               item.mode === 'public' ? <IconBus className="w-4 h-4" style={{ color: barColor }} /> :
                               item.mode === 'walk' ? <IconWalk className="w-4 h-4" style={{ color: barColor }} /> :
                               <IconBike className="w-4 h-4" style={{ color: barColor }} />}
                            </div>
                            <span className="text-sm font-medium text-stone-700">{item.label || item.mode}</span>
                            {item.distance != null && (
                              <span className="text-xs text-[#999]">{item.distance} km</span>
                            )}
                          </div>
                          <div className="text-right">
                            <span className="text-sm font-bold text-stone-800">{item.duration || '-'} 分</span>
                            {item.source === 'estimate' && (
                              <span className="ml-1.5 text-xs text-[#999]">預估</span>
                            )}
                          </div>
                        </div>
                        <div className="h-3 bg-[#f5f4f0] rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full transition-all duration-700 ease-out"
                            style={{ width: `${pct}%`, backgroundColor: barColor }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              );
            })() : (
              <div className="text-center py-8 text-[#999]">
                未找到符合條件的通勤路線
              </div>
            )}
          </div>
        )}

        {/* Empty state */}
        {!commuteResult && !commuteLoading && !commuteError && (
          <div className="bg-white/80 backdrop-blur-sm rounded-sm border border-[#e8e4df] p-12 text-center">
            <IconClock className="w-12 h-12 text-stone-300 mx-auto mb-4" />
            <p className="text-[#777] mb-4">輸入目的地後即可查詢各交通方式的通勤時間</p>
            {filteredDestinations.length > 0 && (
              <div className="flex flex-wrap justify-center gap-2">
                {filteredDestinations.slice(0, 6).map((dest, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => { setCommuteDest(dest); fetchCommute(); }}
                    className="px-3 py-1.5 text-xs bg-[#f0f7ed] text-[#4a5d3e] rounded-full hover:bg-emerald-100 transition-colors"
                  >
                    {dest}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* ════════════════════════════════════════
          DASHBOARD: TRADES (周邊成交)
          ═════════════════════════════════════════ */}
      <div className="space-y-4">
        <SectionHeader
          icon={IconHome}
          title="周邊成交紀錄"
          subtitle={tradesResult ? `共 ${tradesResult.data.length} 筆 · 半徑 ${radius}m` : '查詢生活圈評分後自動載入'}
        />

        {/* Error */}
        {tradesError && <ErrorBox message={tradesError} />}

        {/* Loading */}
        {tradesLoading && (
          <div className="bg-white/80 backdrop-blur-sm rounded-sm border border-[#e8e4df] p-12 text-center">
            <svg className="animate-spin w-8 h-8 text-emerald-500 mx-auto mb-3" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
            </svg>
            <p className="text-[#999]">載入中...</p>
          </div>
        )}

        {/* Results as cards */}
        {!tradesLoading && tradesResult && tradesResult.data && tradesResult.data.length > 0 && (
          <div>
            {/* Sort controls */}
            <div className="flex items-center gap-2 mb-3">
              <span className="text-xs text-[#999]">排序：</span>
              {[
                { key: 'distance', label: '距離' },
                { key: 'date', label: '日期' },
                { key: 'price', label: '總價' },
                { key: 'unitPrice', label: '單價' },
              ].map(opt => (
                <button
                  key={opt.key}
                  onClick={() => setTradesSort(opt.key)}
                  className={`px-3 py-1 rounded-sm text-xs font-medium transition-all ${
                    tradesSort === opt.key
                      ? 'bg-[#5a6b4e] text-white'
                      : 'bg-[#f5f4f0] text-[#777] hover:bg-stone-200'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>

            {(() => {
              const sorted = [...tradesResult.data].sort((a, b) => {
                switch (tradesSort) {
                  case 'distance':
                    return (a.distance || 0) - (b.distance || 0);
                  case 'date':
                    return new Date(b.trade_date || 0) - new Date(a.trade_date || 0);
                  case 'price':
                    return (b.total_price || 0) - (a.total_price || 0);
                  case 'unitPrice':
                    return (b.unit_price || 0) - (a.unit_price || 0);
                  default:
                    return 0;
                }
              });

              return sorted.map((trade, i) => {
                const totalPriceWan = trade.total_price ? Math.round(trade.total_price / 10000).toLocaleString() : '—';
                const unitPriceStr = trade.unit_price != null ? `${Number(trade.unit_price).toFixed(1)}萬` : '—';
                const areaPing = trade.area_sqm ? (Number(trade.area_sqm) * 0.3025).toFixed(1) : '—';
                const floorStr = trade.floor ? formatFloor(trade.floor, trade.total_floors) : '—';
                const ageStr = trade.building_age != null ? (trade.building_age === 0 ? '新成屋' : `${trade.building_age}年`) : '—';
                const dateStr = trade.trade_date ? new Date(trade.trade_date).toLocaleDateString('zh-TW') : '—';
                const distStr = trade.distance ? `${Math.round(trade.distance)}m` : '';

                return (
                  <div key={i} className="bg-white rounded-sm border border-[#d0cdc8] hover:border-stone-300 hover:shadow-sm transition-all mb-2 cursor-pointer px-4 py-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5 mb-1 flex-wrap">
                          <h3 className="font-semibold text-stone-800 truncate">{trade.address || trade.building_name || '-'}</h3>
                          {distStr && <span className="text-xs bg-[#f0f7ed] text-[#5a6b4e] px-1.5 py-0.5 rounded whitespace-nowrap">{distStr}</span>}
                        </div>
                        <p className="text-xs text-[#777] truncate">{trade.city}{trade.district}</p>
                      </div>
                      <div className="text-right flex-shrink-0">
                        <div className="text-lg font-bold text-[#4a5d3e]">{totalPriceWan}<span className="text-xs font-normal text-[#777] ml-0.5">萬</span></div>
                        <div className="text-xs text-[#777]">{unitPriceStr}/坪</div>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-xs text-[#777]">
                      <span>{areaPing} 坪</span>
                      <span>屋齡{ageStr}</span>
                      <span>{floorStr}</span>
                      <span>{dateStr}</span>
                    </div>
                  </div>
                );
              });
            })()}
          </div>
        )}

        {/* No results */}
        {!tradesLoading && tradesResult && tradesResult.data && tradesResult.data.length === 0 && (
          <div className="bg-white/80 backdrop-blur-sm rounded-sm border border-[#e8e4df] p-12 text-center">
            <IconEmpty className="w-12 h-12 text-stone-300 mx-auto mb-4" />
            <p className="text-[#999]">該區域附近暫無成交紀錄</p>
          </div>
        )}

        {/* Empty state - no data yet and not loading */}
        {!tradesLoading && !tradesResult && !tradesError && (
          <div className="bg-white/80 backdrop-blur-sm rounded-sm border border-[#e8e4df] p-12 text-center">
            <IconHome className="w-12 h-12 text-stone-300 mx-auto mb-4" />
            <p className="text-[#999]">先搜尋生活圈評分後，下方即可看到周邊成交</p>
          </div>
        )}
      </div>
    </div>
  </div>
  );
}
