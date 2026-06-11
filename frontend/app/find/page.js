'use client';
import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import dynamic from 'next/dynamic';
import { formatFloor } from '../../lib/floor';
import { API } from '@/lib/api';

// Dynamic import for map - avoids SSR issues with Leaflet
const FindMap = dynamic(() => import('../components/FindMap'), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center h-[600px] bg-[#f5f4f0] rounded-sm border border-[#e8e4df]">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#5a6b4e]" />
      <span className="ml-3 text-[#999]">地圖載入中...</span>
    </div>
  ),
});

/* ═══════════════════ SVG Icons ═══════════════════ */
const Icon = ({ d, size = 16, className = '' }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d={d} />
  </svg>
);

const Icons = {
  money: () => <Icon d="M12 1v22M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" size={15} className="text-[#999]" />,
  ruler: () => <Icon d="M21.3 15.3a2.4 2.4 0 0 1 0 3.4l-2.6 2.6a2.4 2.4 0 0 1-3.4 0L2.7 8.7a2.41 2.41 0 0 1 0-3.4l2.6-2.6a2.41 2.41 0 0 1 3.4 0Z" size={15} className="text-[#999]" />,
  tag: () => <Icon d="M12.586 2.586A2 2 0 0 0 11.172 2H4a2 2 0 0 0-2 2v7.172a2 2 0 0 0 .586 1.414l5 5a2 2 0 0 0 2.828 0l7.172-7.172a2 2 0 0 0 0-2.828l-5-5z M8 14s-1.5-1-1.5-2.5a1.5 1.5 0 1 1 3 0c0 1.5-1.5 2.5-1.5 2.5" size={15} className="text-[#999]" />,
  building: () => <Icon d="M3 21h18M5 21V7l8-4v18M19 21V11l-6-4M9 9h1M9 13h1M9 17h1" size={15} className="text-[#999]" />,
  bed: () => <Icon d="M2 4v16M2 8h18a2 2 0 0 1 2 2v10M2 17h20M6 8v9" size={15} className="text-[#999]" />,
  sofa: () => <Icon d="M20 9V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v3M2 11v5a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-5a2 2 0 0 0-4 0v2H6v-2a2 2 0 0 0-4 0zM4 18v2M20 18v2" size={15} className="text-[#999]" />,
  bath: () => <Icon d="M4 12h16a1 1 0 0 1 1 1v3a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4v-3a1 1 0 0 1 1-1zM6 12V5a2 2 0 0 1 2-2h3v2.5" size={15} className="text-[#999]" />,
  construction: () => <Icon d="M2 20h20M4 20V8l8-6 8 6v12M9 20v-6h6v6M9 12h.01M15 12h.01" size={15} className="text-[#999]" />,
  search: () => <Icon d="M21 21l-6-6M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16z" size={16} />,
  list: () => <Icon d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01" size={16} />,
  empty: () => <Icon d="M3 21h18M5 21V7l7-4 7 4v14M9 21v-6h6v6" size={48} className="text-[#d0cdc8]" />,
  chart: () => <Icon d="M18 20V10M12 20V4M6 20v-6" size={16} className="text-[#999]" />,
  location: () => <Icon d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z M12 9a2 2 0 1 0 0-4 2 2 0 0 0 0 4z" size={14} className="text-[#999]" />,
  transit: () => <Icon d="M3 7h2l2-3h6l2 3h2a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2zM9 18a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM15 18a2 2 0 1 0 0-4 2 2 0 0 0 0 4z" size={14} className="text-[#999]" />,
  education: () => <Icon d="M22 10v6M2 10l10-5 10 5-10 5z M6 12v5c3 3 9 3 12 0v-5" size={14} className="text-[#999]" />,
  medical: () => <Icon d="M12 2v20M2 12h20" size={14} className="text-[#999]" />,
  shopping: () => <Icon d="M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4zM3 6h18M16 10a4 4 0 0 1-8 0" size={14} className="text-[#999]" />,
  leisure: () => <Icon d="M12 22V8M5 12l7-3 7 3M7 16l5-2 5 2" size={14} className="text-[#999]" />,
  dining: () => <Icon d="M18 8h1a4 4 0 0 1 0 8h-1M2 8h16v9a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4V8zM6 1v3M10 1v3M14 1v3" size={14} className="text-[#999]" />,
};

const AMENITY_ICONS = {
  transit: Icons.transit,
  education: Icons.education,
  medical: Icons.medical,
  shopping: Icons.shopping,
  leisure: Icons.leisure,
  dining: Icons.dining,
};

const SORT_OPTIONS = [
  { value: 'trade_date', label: '交易日期' },
  { value: 'total_price', label: '總價' },
  { value: 'unit_price', label: '單價' },
  { value: 'building_area', label: '面積' },
  { value: 'building_age', label: '屋齡' },
  { value: 'score_overall', label: '綜合評分' },
];

const SCORE_DIMENSIONS = [
  { key: 'transit', label: '交通', icon: Icons.transit },
  { key: 'education', label: '教育', icon: Icons.education },
  { key: 'medical', label: '醫療', icon: Icons.medical },
  { key: 'shopping', label: '購物', icon: Icons.shopping },
  { key: 'leisure', label: '休閒', icon: Icons.leisure },
  { key: 'dining', label: '餐飲', icon: Icons.dining },
];

export default function FindPage() {
  // ── Filters ──
  const [city, setCity] = useState('');
  const [district, setDistrict] = useState('');
  const [keyword, setKeyword] = useState('');
  const [priceFilter, setPriceFilter] = useState('');
  const [areaFilter, setAreaFilter] = useState('');
  const [unitPriceFilter, setUnitPriceFilter] = useState('');
  const [rooms, setRooms] = useState(0);
  const [livingRooms, setLivingRooms] = useState(0);
  const [bathrooms, setBathrooms] = useState(0);
  const [floorFilter, setFloorFilter] = useState('');
  const [buildingType, setBuildingType] = useState('');
  const [hasElevator, setHasElevator] = useState(false);
  const [season, setSeason] = useState('');

  // ── Score filters ──
  const [minScoreOverall, setMinScoreOverall] = useState('');
  const [scoreFiltersExpanded, setScoreFiltersExpanded] = useState(false);

  // ── Sort ──
  const [sortBy, setSortBy] = useState('trade_date');
  const [sortOrder, setSortOrder] = useState('desc');

  // ── Data ──
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);
  const [initialLoad, setInitialLoad] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [selectedId, setSelectedId] = useState(null);
  const [expandedId, setExpandedId] = useState(null);
  const [mapColorMode, setMapColorMode] = useState('score'); // 'score' | 'price'
  const [hoveredId, setHoveredId] = useState(null);
  const [boxActive, setBoxActive] = useState(false);
  const listRef = useRef(null);

  // ── Dropdown options ──
  const [cities, setCities] = useState([]);
  const [allDistricts, setAllDistricts] = useState({});
  const [yearRange, setYearRange] = useState({ min_gregorian: null, max_gregorian: null });

  const PAGE_SIZE = 20;

  // ── Load options ──
  useEffect(() => {
    fetch(`${API}/api/find/options`)
      .then(r => r.json())
      .then(data => {
        setCities(data.cities || []);
        setAllDistricts(data.city_districts || {});
        if (data.year_range) setYearRange(data.year_range);
      })
      .catch(() => {});
  }, []);

  const districts = useMemo(() => {
    return city && allDistricts[city] ? allDistricts[city] : [];
  }, [city, allDistricts]);

  useEffect(() => { setDistrict(''); }, [city]);

  // ── Fetch trades ──
  const fetchTrades = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set('page', page.toString());
      params.set('page_size', PAGE_SIZE.toString());
      params.set('sort_by', sortBy);
      params.set('sort_order', sortOrder);
      if (city) params.set('city', city);
      if (district) params.set('district', district);
      if (keyword) params.set('keyword', keyword);
      if (priceFilter) {
        const parts = priceFilter.split('-');
        if (parts.length === 2) {
          if (parts[0]) params.set('min_total_price', parts[0]);
          if (parts[1]) params.set('max_total_price', parts[1]);
        }
      }
      if (areaFilter) {
        // Handle formats: "10-15", "60-", "-10"
        const parts = areaFilter.split('-');
        if (parts.length === 2) {
          const min = parts[0] || '';
          const max = parts[1] || '';
          if (min) params.set('min_area_tping', min);
          if (max) params.set('max_area_tping', max);
        } else if (parts.length === 1 && parts[0].startsWith('-')) {
          // e.g. "-10" means under 10
          params.set('max_area_tping', parts[0].slice(1));
        } else {
          params.set('min_area_tping', parts[0] || '');
        }
      }
      if (unitPriceFilter) {
        const parts = unitPriceFilter.split('-');
        if (parts.length === 2) {
          if (parts[0]) params.set('min_unit_price', parts[0]);
          if (parts[1]) params.set('max_unit_price', parts[1]);
        }
      }
      if (floorFilter) {
        const parts = floorFilter.split('-');
        if (parts.length === 2) {
          if (parts[0]) params.set('min_floor', parts[0]);
          if (parts[1]) params.set('max_floor', parts[1]);
        }
      }
      if (rooms > 0) params.set('min_rooms', rooms.toString());
      if (livingRooms > 0) params.set('min_living_rooms', livingRooms.toString());
      if (bathrooms > 0) params.set('min_bathrooms', bathrooms.toString());
      if (buildingType) params.set('building_type', buildingType);
      if (hasElevator) params.set('has_elevator', 'true');
      if (season) params.set('season', season);
      if (minScoreOverall) params.set('min_score_overall', minScoreOverall);

      const res = await fetch(`${API}/api/find?${params}`);
      const data = await res.json();
      setTrades(data.items || []);
      setTotal(data.total || 0);
      setInitialLoad(false);
    } catch (err) {
      console.error(err);
      setInitialLoad(false);
    } finally {
      setLoading(false);
    }
  }, [page, sortBy, sortOrder, city, district, keyword, priceFilter, areaFilter, unitPriceFilter, floorFilter, rooms, livingRooms, bathrooms, buildingType, hasElevator, season, minScoreOverall]);

  useEffect(() => { fetchTrades(); }, [fetchTrades]);

  useEffect(() => { setPage(1); }, [city, district, keyword, priceFilter, areaFilter, unitPriceFilter, floorFilter, rooms, livingRooms, bathrooms, buildingType, hasElevator, season, sortBy, sortOrder, minScoreOverall]);

  // ── Scroll to selected card when selectedId changes ──
  useEffect(() => {
    if (selectedId && listRef.current) {
      const el = listRef.current.querySelector(`[data-trade-id="${selectedId}"]`);
      el?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [selectedId]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  const resetFilters = () => {
    setCity(''); setDistrict(''); setKeyword(''); 
    setPriceFilter(''); setAreaFilter(''); setUnitPriceFilter(''); setFloorFilter('');
    setRooms(0); setLivingRooms(0); setBathrooms(0);
    setBuildingType(''); setHasElevator(false); setSeason('');
    setMinScoreOverall('');
  };

  const yearStr = yearRange.min_gregorian && yearRange.max_gregorian
    ? `${yearRange.min_gregorian}–${yearRange.max_gregorian}`
    : '—';

  const inputClass = 'border border-[#e8e4df] rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[#5a6b4e] focus:border-[#5a6b4e]';
  const smallInputClass = 'px-2 py-1.5 border border-[#e8e4df] rounded-md text-xs outline-none focus:ring-1 focus:ring-[#5a6b4e] focus:border-[#5a6b4e] min-w-[130px]';
  const tinySelectClass = 'px-2 py-1.5 border border-[#e8e4df] rounded-md text-xs outline-none focus:ring-1 focus:ring-[#5a6b4e] focus:border-[#5a6b4e]';

  return (
    <div className="min-h-screen bg-[#faf9f7]">
      {/* ═══════════════════ HEADER ═══════════════════ */}
      <div className="border-b border-[#e8e4df] bg-white/80 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
          <h1 className="text-xl font-medium text-[#2a2a2a] tracking-tight">全台房屋成交紀錄查詢</h1>
          <p className="text-sm text-[#999] mt-1">即時掌握各區域房價趨勢，找到最適合你的理想居所</p>
        </div>
      </div>

      {/* ═══════════════════ SEARCH CARD ═══════════════════ */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 pt-6 pb-2">
        <div className="bg-white/80 backdrop-blur-sm rounded-sm shadow-sm border border-[#e8e4df] p-6">
          {/* Primary row: City + District + Keyword + Search + Reset */}
          <div className="flex flex-wrap gap-3 items-end mb-4">
            <div className="flex-1 min-w-[150px]">
              <label className="block text-xs font-medium text-[#777] mb-1">城市</label>
              <select
                value={city}
                onChange={(e) => setCity(e.target.value)}
                className={`w-full ${inputClass}`}
              >
                <option value="">全部城市</option>
                {cities.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div className="flex-1 min-w-[150px]">
              <label className="block text-xs font-medium text-[#777] mb-1">行政區</label>
              <select
                value={district}
                onChange={(e) => setDistrict(e.target.value)}
                className={`w-full ${inputClass} disabled:opacity-50`}
                disabled={!city}
              >
                <option value="">全部行政區</option>
                {districts.map(d => <option key={d} value={d}>{d}</option>)}
              </select>
            </div>
            <div className="flex-[2] min-w-[200px]">
              <label className="block text-xs font-medium text-[#777] mb-1">關鍵字搜尋（地址、建案名稱）</label>
              <input
                type="text"
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                placeholder="例：中山路、信義計畫區..."
                className={`w-full ${inputClass}`}
              />
            </div>
            <div className="flex items-end gap-2">
              <button
                onClick={() => fetchTrades()}
                className="px-5 py-2 bg-[#5a6b4e] text-white hover:bg-[#4a5d3e] rounded-md text-sm whitespace-nowrap flex items-center gap-1.5 transition-colors"
              >
                <Icons.search /> 搜尋
              </button>
              <button
                onClick={resetFilters}
                className="px-4 py-2 border border-[#d0cdc8] text-[#777] hover:border-[#5a6b4e] hover:text-[#5a6b4e] rounded-md text-sm transition-colors whitespace-nowrap"
              >
                重置
              </button>
            </div>
          </div>

          {/* Advanced filters - compact inline layout */}
          <div className="border-t border-[#e8e4df] pt-3">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              
              {/* Price range */}
              <span className="text-[#777] whitespace-nowrap flex items-center gap-1"><Icons.money /> 總價</span>
              <select value={priceFilter} onChange={e => setPriceFilter(e.target.value)} className={smallInputClass}>
                <option value="">不限</option>
                <option value="0-500">500 萬以下</option>
                <option value="500-1000">500–1000 萬</option>
                <option value="1000-1500">1000–1500 萬</option>
                <option value="1500-2000">1500–2000 萬</option>
                <option value="2000-3000">2000–3000 萬</option>
                <option value="3000-5000">3000–5000 萬</option>
                <option value="5000-">5000 萬以上</option>
              </select>

              <span className="w-px h-5 bg-[#e8e4df] mx-1 hidden sm:block" />

              {/* Area */}
              <span className="text-[#777] whitespace-nowrap flex items-center gap-1"><Icons.ruler /> 面積</span>
              <select value={areaFilter} onChange={e => setAreaFilter(e.target.value)} className={smallInputClass}>
                <option value="">不限</option>
                <option value="-10">10 坪以下</option>
                <option value="10-15">10–15 坪</option>
                <option value="15-20">15–20 坪</option>
                <option value="20-30">20–30 坪</option>
                <option value="30-40">30–40 坪</option>
                <option value="40-50">40–50 坪</option>
                <option value="50-60">50–60 坪</option>
                <option value="60-">60 坪以上</option>
              </select>

              <span className="w-px h-5 bg-[#e8e4df] mx-1 hidden sm:block" />

              {/* Unit price */}
              <span className="text-[#777] whitespace-nowrap flex items-center gap-1"><Icons.tag /> 單價</span>
              <select value={unitPriceFilter} onChange={e => setUnitPriceFilter(e.target.value)} className={smallInputClass}>
                <option value="">不限</option>
                <option value="0-10">10 萬/坪以下</option>
                <option value="10-20">10–20 萬/坪</option>
                <option value="20-30">20–30 萬/坪</option>
                <option value="30-40">30–40 萬/坪</option>
                <option value="40-50">40–50 萬/坪</option>
                <option value="50-60">50–60 萬/坪</option>
                <option value="60-70">60–70 萬/坪</option>
                <option value="70-80">70–80 萬/坪</option>
                <option value="80-">80 萬/坪以上</option>
              </select>

              <span className="w-px h-5 bg-[#e8e4df] mx-1 hidden sm:block" />

              {/* Floor */}
              <span className="text-[#777] whitespace-nowrap flex items-center gap-1"><Icons.building /> 樓層</span>
              <select value={floorFilter} onChange={e => setFloorFilter(e.target.value)} className={smallInputClass}>
                <option value="">不限</option>
                <option value="1-1">1F (一樓)</option>
                <option value="2-2">2F (二樓)</option>
                <option value="3-3">3F (三樓)</option>
                <option value="4-4">4F (四樓)</option>
                <option value="5-5">5F (五樓)</option>
                <option value="6-6">6F (六樓)</option>
                <option value="7-7">7F (七樓)</option>
                <option value="8-8">8F (八樓)</option>
                <option value="9-9">9F (九樓)</option>
                <option value="10-10">10F (十樓)</option>
                <option value="11-15">11–15F</option>
                <option value="16-20">16–20F</option>
                <option value="21-">21F 以上</option>
              </select>

              <span className="w-px h-5 bg-[#e8e4df] mx-1 hidden sm:block" />

              {/* Rooms */}
              <span className="text-[#777] whitespace-nowrap"><Icons.bed /></span>
              <select value={rooms} onChange={e => setRooms(Number(e.target.value))} className={tinySelectClass}>
                <option value={0}>全部</option>
                <option value={1}>1 房</option>
                <option value={2}>2 房</option>
                <option value={3}>3 房</option>
                <option value={4}>4 房</option>
                <option value={5}>5 房+</option>
              </select>

              {/* Living rooms */}
              <span className="text-[#777] whitespace-nowrap"><Icons.sofa /></span>
              <select value={livingRooms} onChange={e => setLivingRooms(Number(e.target.value))} className={tinySelectClass}>
                <option value={0}>全部</option>
                <option value={1}>1 廳</option>
                <option value={2}>2 廳</option>
                <option value={3}>3 廳+</option>
              </select>

              {/* Bathrooms */}
              <span className="text-[#777] whitespace-nowrap"><Icons.bath /></span>
              <select value={bathrooms} onChange={e => setBathrooms(Number(e.target.value))} className={tinySelectClass}>
                <option value={0}>全部</option>
                <option value={1}>1 衛</option>
                <option value={2}>2 衛</option>
                <option value={3}>3 衛+</option>
              </select>

              <span className="w-px h-5 bg-[#e8e4df] mx-1 hidden sm:block" />

              {/* Building type */}
              <span className="text-[#777] whitespace-nowrap"><Icons.construction /></span>
              <select value={buildingType} onChange={e => setBuildingType(e.target.value)} className={tinySelectClass}>
                <option value="">全部</option>
                <option value="住宅大樓">住宅大樓</option>
                <option value="華廈大樓">華廈大樓</option>
                <option value="公寓">公寓</option>
                <option value="別墅">別墅</option>
                <option value="集合住宅">集合住宅</option>
              </select>

              {/* Elevator */}
              <label className="flex items-center gap-1.5 cursor-pointer ml-1">
                <input type="checkbox" checked={hasElevator} onChange={e => setHasElevator(e.target.checked)} className="w-3.5 h-3.5 text-[#5a6b4e] rounded focus:ring-[#5a6b4e]" />
                <span className="text-[#777] text-xs whitespace-nowrap">有電梯</span>
              </label>

              {/* Score filter toggle — subtle link style */}
              <button
                onClick={() => setScoreFiltersExpanded(!scoreFiltersExpanded)}
                className={`ml-1 px-2 py-1 text-xs underline decoration-dashed underline-offset-2 transition-colors flex items-center gap-1 ${
                  minScoreOverall ? 'text-[#5a6b4e]' : 'text-[#999] hover:text-[#5a6b4e]'
                }`}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
                生活圈評分 {minScoreOverall ? `≥ ${minScoreOverall}` : ''}
              </button>
            </div>

            {/* Score filter expanded panel */}
            {scoreFiltersExpanded && (
              <div className="border-t border-[#e8e4df] pt-3 mt-1">
                <div className="flex flex-wrap items-center gap-3 text-sm">
                  {/* Overall score slider */}
                  <div className="flex items-center gap-2">
                    <span className="text-[#777] text-xs whitespace-nowrap">綜合評分 ≥</span>
                    <input
                      type="range"
                      min="0"
                      max="100"
                      step="5"
                      value={minScoreOverall || 0}
                      onChange={e => setMinScoreOverall(e.target.value === '0' ? '' : e.target.value)}
                      className="w-32 accent-[#5a6b4e]"
                    />
                    <span className="text-sm font-semibold text-[#5a6b4e] w-8">{minScoreOverall || '0'}</span>
                  </div>

                  {/* Quick preset pill buttons */}
                  <div className="flex items-center gap-1.5 ml-2">
                    <span className="text-[#999] text-xs">快速設定：</span>
                    {[60, 70, 80].map(v => (
                      <button
                        key={v}
                        onClick={() => setMinScoreOverall(minScoreOverall === String(v) ? '' : String(v))}
                        className={`px-3 py-1 text-xs rounded-full border transition-colors ${
                          minScoreOverall === String(v)
                            ? 'bg-[#5a6b4e] text-white border-[#5a6b4e]'
                            : 'border-[#d0cdc8] text-[#777] hover:border-[#5a6b4e] hover:text-[#5a6b4e]'
                        }`}
                      >
                        ≥ {v}
                      </button>
                    ))}
                    {minScoreOverall && (
                      <button
                        onClick={() => setMinScoreOverall('')}
                        className="px-3 py-1 text-xs rounded-full border border-[#d0cdc8] text-[#999] hover:border-[#5a6b4e] hover:text-[#5a6b4e] transition-colors"
                      >
                        清除
                      </button>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ═══════════════════ RESULTS ═══════════════════ */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4">
        {/* Toolbar */}
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <div className="flex items-center gap-3">
            <span className="text-sm text-[#777]">共 <strong className="text-[#2a2a2a]">{total.toLocaleString()}</strong> 筆成交紀錄</span>
          </div>
          <div className="flex items-center gap-2">
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className={`${inputClass} text-xs py-1.5`}
            >
              {SORT_OPTIONS.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
            </select>
            <button
              onClick={() => setSortOrder(sortOrder === 'desc' ? 'asc' : 'desc')}
              className={`rounded-full px-3 py-1.5 text-xs border transition-colors ${
                sortOrder === 'desc'
                  ? 'bg-[#5a6b4e] text-white border-[#5a6b4e]'
                  : 'border-[#e8e4df] text-[#777] hover:border-[#5a6b4e] hover:text-[#5a6b4e]'
              }`}
              title={sortOrder === 'desc' ? '降冪' : '升冪'}
            >
              {sortOrder === 'desc' ? '↓ 降冪' : '↑ 升冪'}
            </button>
          </div>
        </div>

        {/* Content - Split view: List + Map side by side */}
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#5a6b4e]" />
            <span className="ml-3 text-[#999]">載入中...</span>
          </div>
        ) : trades.length === 0 ? (
          <div className="text-center py-20">
            <div className="flex justify-center mb-3"><Icons.empty /></div>
            <p className="text-[#999]">找不到符合條件的成交紀錄</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* List Panel */}
            <div ref={listRef}>
              {boxActive && (
                <button
                  onClick={() => { setBoxActive(false); fetchTrades(); }}
                  className="mb-3 px-3 py-2 bg-[#5a6b4e] text-white rounded-md text-xs flex items-center gap-1.5 w-fit hover:bg-[#4a5d3e] transition-colors"
                >
                  ↩ 復原篩選結果
                </button>
              )}
              {trades.map((trade) => (
                <TradeCard
                  key={trade.id}
                  trade={trade}
                  isSelected={selectedId === trade.id}
                  isExpanded={expandedId === trade.id}
                  isHovered={hoveredId === trade.id}
                  onSelect={() => setSelectedId(trade.id)}
                  onToggleExpand={() => setExpandedId(expandedId === trade.id ? null : trade.id)}
                  onHover={(id) => setHoveredId(id)}
                />
              ))}
            </div>

            {/* Map Panel */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm text-[#777] flex items-center gap-1.5"><Icons.location /> 成交地點分布</span>
                <div className="flex items-center gap-2">
                  {selectedId && (
                    <button
                      onClick={() => setSelectedId(null)}
                      className="rounded-full px-3 py-1.5 text-xs border border-[#e8e4df] text-[#777] hover:border-[#5a6b4e] hover:text-[#5a6b4e] transition-colors"
                    >
                      ✕ 清除選取
                    </button>
                  )}
                  <button
                    onClick={() => setMapColorMode(mapColorMode === 'score' ? 'price' : 'score')}
                    className="rounded-full px-3 py-1.5 text-xs border border-[#e8e4df] text-[#777] hover:border-[#5a6b4e] hover:text-[#5a6b4e] transition-colors"
                  >
                    {mapColorMode === 'score' ? '依評分著色' : '依總價著色'}
                  </button>
                </div>
              </div>
              <div className="sticky top-4">
                <FindMap
                  trades={trades}
                  selectedId={selectedId}
                  onSelect={setSelectedId}
                  hoveredId={hoveredId}
                  onMarkerHover={setHoveredId}
                  colorMode={mapColorMode}
                  filters={{
                    city,
                    district,
                    ...(() => {
                      if (!priceFilter) return {};
                      const [min, max] = priceFilter.split('-');
                      return {
                        minTotalPrice: min ? Number(min) : null,
                        maxTotalPrice: max ? Number(max) : null,
                      };
                    })(),
                    ...(() => {
                      if (!unitPriceFilter) return {};
                      const [min, max] = unitPriceFilter.split('-');
                      return {
                        minUnitPrice: min ? Number(min) : null,
                        maxUnitPrice: max ? Number(max) : null,
                      };
                    })(),
                    buildingType,
                    hasElevator,
                    // 面積需要從 areaFilter 解析
                    ...(() => {
                      if (!areaFilter) return {};
                      if (areaFilter.startsWith('-')) {
                        return { maxAreaTping: Number(areaFilter.slice(1)) };
                      } else if (areaFilter.endsWith('-')) {
                        return { minAreaTping: Number(areaFilter.slice(0, -1)) };
                      } else {
                        const [min, max] = areaFilter.split('-').map(Number);
                        return { minAreaTping: min, maxAreaTping: max };
                      }
                    })(),
                  }}
                  onBoxSelect={(boxedTrades) => {
                    setBoxActive(true);
                    setTrades(boxedTrades);
                    setTotal(boxedTrades.length);
                  }}
                />
              </div>
            </div>
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (() => {
          const pages = [];
          const start = Math.max(1, page - 2);
          const end = Math.min(totalPages, page + 2);
          for (let i = start; i <= end; i++) pages.push(i);
          return (
            <div className="flex items-center justify-center gap-1.5 mt-6">
              <button
                onClick={() => setPage(Math.max(1, page - 1))}
                disabled={page === 1}
                className="px-3 py-1.5 text-sm text-[#777] hover:bg-[#f5f4f0] rounded-md disabled:opacity-30 transition-colors"
              >
                ←
              </button>
              {start > 1 && (
                <>
                  <button onClick={() => setPage(1)} className="w-8 h-8 rounded-full text-sm text-[#777] hover:bg-[#f5f4f0] transition-colors">1</button>
                  {start > 2 && <span className="text-[#999] px-1">…</span>}
                </>
              )}
              {pages.map(p => (
                <button
                  key={p}
                  onClick={() => setPage(p)}
                  className={`w-8 h-8 rounded-full text-sm transition-colors ${
                    p === page ? 'bg-[#5a6b4e] text-white' : 'text-[#777] hover:bg-[#f5f4f0]'
                  }`}
                >
                  {p}
                </button>
              ))}
              {end < totalPages && (
                <>
                  {end < totalPages - 1 && <span className="text-[#999] px-1">…</span>}
                  <button onClick={() => setPage(totalPages)} className="w-8 h-8 rounded-full text-sm text-[#777] hover:bg-[#f5f4f0] transition-colors">{totalPages}</button>
                </>
              )}
              <button
                onClick={() => setPage(Math.min(totalPages, page + 1))}
                disabled={page === totalPages}
                className="px-3 py-1.5 text-sm text-[#777] hover:bg-[#f5f4f0] rounded-md disabled:opacity-30 transition-colors"
              >
                →
              </button>
            </div>
          );
        })()}
      </div>
    </div>
  );
}

/* ═══════════════════ Trade Card ═══════════════════ */
function TradeCard({ trade, isSelected, isExpanded, isHovered, onSelect, onToggleExpand, onHover }) {
  const totalPriceWan = trade.total_price ? Math.round(trade.total_price / 10000).toLocaleString() : '—';
  const unitPriceStr = trade.unit_price_tping != null ? `${Number(trade.unit_price_tping).toFixed(1)}萬` : '—';
  const buildingAreaPing = trade.building_area ? (trade.building_area * 0.3025).toFixed(1) : '—';
  const landAreaPing = trade.land_area ? (trade.land_area * 0.3025).toFixed(1) : null;
  const layoutStr = trade.rooms != null ? `${trade.rooms || '?'}房${trade.living_rooms || '?'}廳${trade.bathrooms || '?'}衛` : '—';
  const ageStr = trade.building_age != null ? (trade.building_age === 0 ? '新成屋' : `${trade.building_age}年`) : '—';
  const floorStr = trade.floor ? formatFloor(trade.floor, trade.total_floors) : '—';
  const dateStr = trade.trade_date ? new Date(trade.trade_date).toLocaleDateString('zh-TW') : '—';

  return (
    <div
      data-trade-id={trade.id}
      className={`bg-white/80 backdrop-blur-sm rounded-sm shadow-sm border border-[#e8e4df] p-5 mb-3 transition-all cursor-pointer hover:border-[#d0cdc8] ${
        isSelected ? 'border-[#5a6b4e] ring-1 ring-[#5a6b4e]/20' : ''
      }`}
      onClick={onSelect}
      onMouseEnter={() => onHover?.(trade.id)}
      onMouseLeave={() => onHover?.(null)}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 mb-1 flex-wrap">
            <h3 className="text-[#2a2a2a] font-medium truncate">{trade.address}</h3>
            {trade.has_elevator && <span className="inline-block px-2 py-0.5 text-xs rounded bg-[#f5f4f0] text-[#777] whitespace-nowrap">電梯</span>}
            {trade.building_type && trade.building_type !== '其他' && <span className="inline-block px-2 py-0.5 text-xs rounded bg-[#f5f4f0] text-[#777] whitespace-nowrap">{trade.building_type}</span>}
          </div>
          <div className="flex items-center gap-2 text-sm text-[#999]">
            <span>{trade.city}{trade.district}</span>
            <span>·</span>
            <span>{dateStr}</span>
          </div>
        </div>
        <div className="text-right flex-shrink-0">
          <div className="text-[#5a6b4e] font-medium">{totalPriceWan}<span className="text-xs font-normal text-[#999] ml-0.5">萬</span></div>
          <div className="text-xs text-[#999]">{unitPriceStr}/坪</div>
        </div>
      </div>

      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-xs text-[#999]">
        <span>{buildingAreaPing} 坪{landAreaPing ? ` (土地${landAreaPing}坪)` : ''}</span>
        <span>{layoutStr}</span>
        <span>屋齡{ageStr}</span>
        <span>{floorStr}</span>
      </div>

      {/* ── 生活機能評分 + POI toggle（常駐顯示） ── */}
      {(trade.score_transit != null || trade.score_education != null || trade.score_medical != null || trade.score_shopping != null || trade.score_leisure != null || trade.score_dining != null) && (
        <div className="mt-3 pt-3 border-t border-[#e8e4df]">
          <div className="flex items-start gap-3">
            {/* Overall score circle */}
            {trade.score_overall != null && (
              <div className="flex-shrink-0 flex flex-col items-center">
                <div className="w-10 h-10 rounded-full border-2 flex items-center justify-center"
                     style={{ borderColor: getScoreRingColor(trade.score_overall) }}>
                  <span className="text-sm font-bold" style={{ color: getScoreRingColor(trade.score_overall) }}>
                    {trade.score_overall}
                  </span>
                </div>
                <span className="text-[10px] text-[#999] mt-0.5">綜合</span>
              </div>
            )}
            {/* Category score pills + POI toggle */}
            <div className="flex flex-wrap items-center gap-1.5 flex-1">
              {trade.score_transit != null && <ScorePill icon={<Icons.transit />} label="交通" score={trade.score_transit} />}
              {trade.score_education != null && <ScorePill icon={<Icons.education />} label="教育" score={trade.score_education} />}
              {trade.score_medical != null && <ScorePill icon={<Icons.medical />} label="醫療" score={trade.score_medical} />}
              {trade.score_shopping != null && <ScorePill icon={<Icons.shopping />} label="購物" score={trade.score_shopping} />}
              {trade.score_leisure != null && <ScorePill icon={<Icons.leisure />} label="休閒" score={trade.score_leisure} />}
              {trade.score_dining != null && <ScorePill icon={<Icons.dining />} label="餐飲" score={trade.score_dining} />}
              {/* POI 展開/收合按鈕 — 固定在評分列右側 */}
              <button
                onClick={(e) => { e.stopPropagation(); onToggleExpand(); }}
                className={`ml-auto text-xs flex items-center gap-0.5 transition-colors ${isExpanded ? 'text-[#5a6b4e]' : 'text-[#999] hover:text-[#5a6b4e]'}`}
              >
                {isExpanded ? '▲ 收起' : '▼ 查看'} POI
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── POI 清單展開區（可捲動） ── */}
      {isExpanded && (
        <div className="px-0 pb-3 border-t border-[#e8e4df] pt-3 overflow-hidden transition-all">
          <h4 className="text-xs font-medium text-[#777] mb-2 flex items-center gap-1.5"><Icons.shopping /> 周邊生活機能</h4>
          {trade.amenities && trade.amenities.length > 0 ? (() => {
            const CATEGORY_LABELS = { transit: '交通', education: '教育', medical: '醫療', shopping: '購物', leisure: '休閒', dining: '餐飲' };
            const groups = {};
            trade.amenities.forEach(am => {
              if (!groups[am.category]) groups[am.category] = [];
              groups[am.category].push(am);
            });
            return (
              <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
                {Object.entries(groups).map(([cat, items]) => (
                  <div key={cat}>
                    <div className="flex items-center gap-1.5 text-xs font-medium text-[#777] mb-1">
                      {(() => { const IconComp = AMENITY_ICONS[cat]; return IconComp ? <IconComp /> : <Icons.location />; })()}
                      <span>{CATEGORY_LABELS[cat] || cat}</span>
                    </div>
                    <div className="flex flex-wrap gap-1.5 ml-5">
                      {items.map((item, idx) => (
                        <span key={idx} className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded bg-[#f5f4f0] text-[#777]">
                          {item.name}
                          <span className="text-[#999]">{item.distance}m</span>
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            );
          })() : (
            <p className="text-xs text-[#999]">此筆成交紀錄暫無周邊 POI 明細</p>
          )}
        </div>
      )}
    </div>
  );
}

function ScoreBar({ label, score }) {
  const pct = Math.min(100, (score || 0));
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-[#999] w-8">{label}</span>
      <div className="flex-1 bg-[#f5f4f0] rounded-full h-2">
        <div
          className={`h-2 rounded-full transition-all ${getScoreBarColor(score)}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs font-medium text-[#777] w-8 text-right">{score}</span>
    </div>
  );
}

function getScoreColorInline(score) {
  if (score >= 80) return 'text-green-600';
  if (score >= 60) return 'text-blue-600';
  if (score >= 40) return 'text-amber-600';
  return 'text-red-600';
}

function getScoreBarColor(score) {
  if (score >= 80) return 'bg-green-500';
  if (score >= 60) return 'bg-blue-500';
  if (score >= 40) return 'bg-amber-500';
  return 'bg-red-500';
}

function getScoreRingColor(score) {
  if (score >= 80) return '#5a6b4e';
  if (score >= 60) return '#5a6e82';
  if (score >= 40) return '#b8943a';
  return '#a85555';
}

function ScorePill({ icon, label, score, color }) {
  const bg = color ? (score >= 80 ? 'bg-[#f4f6f2] border-[#dce0d8]' : score >= 60 ? 'bg-[#edf1f5] border-[#d5dde5]' : score >= 40 ? 'bg-[#faf5eb] border-[#ece4d0]' : 'bg-[#f9efef] border-[#e5d5d5]') : 'bg-[#f5f4f0] border-[#e8e4df]';
  const textCol = color ? (score >= 80 ? 'text-[#5a6b4e]' : score >= 60 ? 'text-[#5a6e82]' : score >= 40 ? 'text-[#b8943a]' : 'text-[#a85555]') : 'text-[#777]';
  return (
    <div className={`inline-flex items-center gap-1 px-2 py-1 rounded-full border text-xs ${bg}`}>
      <span>{icon}</span>
      <span className="text-[#999]">{label}</span>
      <span className={`font-semibold ${textCol}`}>{score}</span>
    </div>
  );
}
