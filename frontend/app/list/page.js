'use client';
import { useEffect, useState, Suspense, useMemo, useRef } from 'react';
import { useSearchParams } from 'next/navigation';
import { formatFloor } from '../../lib/floor';
import { TrainFront, GraduationCap, HeartPulse, ShoppingCart, Trees, UtensilsCrossed, Search, SlidersHorizontal, ArrowUp, ArrowDown, MapPin, Home } from 'lucide-react';

import { API } from '@/lib/api';

/* ─── SVG Icons ─────────────────────────────────────── */
function IconBuilding2({ className = "w-5 h-5" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 22v-10"/><path d="M16 22v-14"/><path d="M10 22v-4"/><path d="M4 22V10"/><path d="M9 6h8"/><path d="M12 6V2"/><path d="M8 12h2"/><path d="M14 12h2"/><path d="M8 16h2"/><path d="M14 16h2"/>
    </svg>
  );
}
function IconAlertTriangle({ className = "w-5 h-5" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
    </svg>
  );
}
function IconRefreshCw({ className = "w-5 h-5" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 21h5v-5"/>
    </svg>
  );
}
function IconMapPin({ className = "w-5 h-5" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>
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
      <path d="M21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
    </svg>
  );
}
function IconX({ className = "w-5 h-5" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
    </svg>
  );
}
function IconHomeEmpty({ className = "w-5 h-5" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>
    </svg>
  );
}

/* ─── Unified Dimension Config (matches backend DIMENSION_ORDER) ─── */
const DIMENSIONS = [
  { key: 'transit', label: '交通', icon: TrainFront, color: '#637d56' },
  { key: 'education', label: '教育', icon: GraduationCap, color: '#475569' },
  { key: 'medical', label: '醫療', icon: HeartPulse, color: '#dc2626' },
  { key: 'shopping', label: '購物', icon: ShoppingCart, color: '#d97706' },
  { key: 'leisure', label: '休閒', icon: Trees, color: '#556b48' },
  { key: 'dining', label: '餐飲', icon: UtensilsCrossed, color: '#92400e' },
];
const DIM_MAP = Object.fromEntries(DIMENSIONS.map(d => [d.key, d]));

/* ─── Helper Components ─── */

function PriceBadge({ price, unitPrice }) {
  return (
    <div className="flex flex-col">
      <span className="text-sm md:text-lg font-bold text-stone-900 tabular-nums leading-tight">{price}</span>
      {unitPrice && (
        <span className="text-xs md:text-sm font-medium text-emerald-600 tabular-nums">{unitPrice}</span>
      )}
    </div>
  );
}

function Tag({ children, color = 'stone' }) {
  const colors = {
    stone: 'bg-stone-100 text-stone-600 border-stone-200',
    emerald: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    amber: 'bg-amber-50 text-amber-700 border-amber-200',
    rose: 'bg-rose-50 text-rose-600 border-rose-200',
    slate: 'bg-stone-100 text-stone-500 border-stone-200',
    violet: 'bg-violet-50 text-violet-700 border-violet-200',
    indigo: 'bg-indigo-50 text-indigo-700 border-indigo-200',
    sky: 'bg-sky-50 text-sky-700 border-sky-200',
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 md:px-3 md:py-1 rounded-lg text-xs md:text-sm font-medium border ${colors[color] || colors.stone}`}>
      {children}
    </span>
  );
}

function FilterSection({ title, icon: IconComp, children, defaultOpen = true }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border border-stone-200 rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between p-4 bg-stone-50 hover:bg-stone-100 transition-colors"
      >
        <span className="font-semibold text-stone-700 text-sm md:text-base flex items-center gap-2">
          {IconComp && <IconComp className="w-4 h-4 text-emerald-600" />}
          {title}
        </span>
        <span className={`text-stone-400 transition-transform duration-200 ${open ? 'rotate-180' : ''}`}>
          ▾
        </span>
      </button>
      {open && (
        <div className="p-4 bg-white">
          {children}
        </div>
      )}
    </div>
  );
}

function AmenitiesPanel({ lat, lon, address, tradeId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [notFound, setNotFound] = useState(false); // API returned empty → no amenities nearby
  const [expandedCategory, setExpandedCategory] = useState(null);
  const [retryCount, setRetryCount] = useState(0);

  function doFetch() {
    if (!lat && !lon && !address) return;

    console.log('[Amenities] Fetching for tradeId:', tradeId, { lat, lon, address });

    let urlParts = ['/api/amenities'];
    // Prefer DB cache via trade_id — instant, no external API call
    if (tradeId) {
      urlParts.push(`trade_id=${tradeId}`);
    } else if (lat && lon) {
      urlParts.push(`lat=${lat}&lon=${lon}`);
    } else if (address) {
      urlParts.push(`address=${encodeURIComponent(address)}`);
    } else {
      return;
    }
    const url = urlParts.join('?');

    setLoading(true);
    setData(null);
    setError(null);
    setNotFound(false);

    const fetchPromise = fetch(url).then(async (res) => {
      console.log('[Amenities] Response status:', res.status);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      console.log('[Amenities] Got data:', Object.keys(json));
      return json;
    });

    const timeoutPromise = new Promise((_, reject) =>
      setTimeout(() => reject(new Error('超時')), 15000)
    );

    Promise.race([fetchPromise, timeoutPromise])
      .then((raw) => {
        // API may wrap in { amenities: {...} } or return flat categories
        const json = raw.amenities && typeof raw.amenities === 'object' ? raw.amenities : raw;
        console.log('[Amenities] Got data:', Object.keys(json));
        // Check if API returned valid data but zero categories
        const categories = Object.entries(json).filter(([_, cat]) => (cat.items || []).length > 0);
        if (categories.length === 0) {
          setNotFound(true); // No amenities found — this is a valid response
        } else {
          setData(json);
        }
      })
      .catch((e) => {
        console.error('[Amenities] Error:', e.message);
        setError(e.message || '查詢失敗');
      })
      .finally(() => {
        console.log('[Amenities] Done');
        setLoading(false);
      });
  }

  // Auto-fetch on mount
  useEffect(() => {
    doFetch();
  }, [lat, lon, address, tradeId]);

  function handleRetry() {
    setRetryCount(c => c + 1);
    doFetch();
  }

  // Don't show if no coordinates and no address
  if ((!lat || !lon) && !address) return null;

  // Build category summary — ordered by DIMENSIONS, only show those with data
  const categories = data ? DIMENSIONS
    .filter(dim => (data[dim.key]?.items || []).length > 0)
    .map(dim => [dim.key, { ...data[dim.key], name: dim.label, icon: <dim.icon size={14} strokeWidth={2} /> }])
    : [];
  const totalItems = categories.reduce((sum, [, cat]) => sum + cat.items.length, 0);

  return (
    <div className="mt-3 pt-3 border-t border-stone-100">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <span className={`text-xs md:text-sm font-semibold flex items-center gap-1 ${
          error ? 'text-red-500' : notFound ? 'text-stone-400' : 'text-emerald-700'
        }`}>
          <IconBuilding2 className="w-3 h-3 inline" /> 周邊生活機能
          {totalItems > 0 && (
            <span className="px-1.5 py-0.5 bg-emerald-200 text-emerald-800 text-[10px] md:text-xs rounded-full font-bold">
              {totalItems} 處
            </span>
          )}
        </span>
        {loading && (
          <div className="flex items-center gap-1">
            <div className="animate-spin h-3 w-3 border border-emerald-400 border-t-transparent rounded-full" />
            <span className="text-[10px] md:text-xs text-stone-400">查詢中</span>
          </div>
        )}
      </div>

      {/* State 1: Loading */}
      {loading && !data && !error && !notFound ? (
        <div className="flex items-center justify-center py-3">
          <div className="flex flex-col items-center gap-2">
            <div className="animate-spin h-5 w-5 border-2 border-emerald-300 border-t-transparent rounded-full" />
            <span className="text-[11px] md:text-sm text-stone-400">正在查詢周邊設施...</span>
          </div>
        </div>
      ) : false /* no short-circuit */}

      {/* State 2: Error — red box with retry button */}
      {error && !loading ? (
        <div className="rounded-lg bg-red-50 border border-red-200 p-3 text-center">
          <div className="flex items-center justify-center gap-1.5 mb-2">
            <IconAlertTriangle className="w-4 h-4" />
            <span className="text-xs md:text-sm font-medium text-red-600">載入失敗</span>
          </div>
          <p className="text-[10px] md:text-xs text-red-400 mb-2">{error}</p>
          <button
            onClick={handleRetry}
            className="inline-flex items-center gap-1 px-3 py-1.5 bg-red-500 hover:bg-red-600 text-white text-[10px] md:text-xs rounded-md transition-colors"
          >
            <IconRefreshCw className="w-4 h-4 inline" /> 重新載入
          </button>
        </div>
      ) : false /* no short-circuit */}

      {/* State 3: No amenities found — subtle gray, no action needed */}
      {notFound && !loading ? (
        <div className="rounded-lg bg-stone-50 border border-stone-100 p-3 text-center">
          <div className="flex items-center justify-center gap-1.5">
            <IconMapPin className="w-4 h-4" />
            <span className="text-[11px] md:text-sm text-stone-400">此位置周邊暫無生活機能資料</span>
          </div>
        </div>
      ) : false /* no short-circuit */}

      {/* State 4: Success — categories list */}
      {!loading && !error && !notFound && categories.length > 0 ? (
        /* Category summary row — always visible */
        <div className="space-y-1">
          {categories.map(([key, cat]) => {
            const items = cat.items || [];
            const isExpanded = expandedCategory === key;
            return (
              <div key={key}>
                {/* Clickable category pill */}
                <button
                  onClick={() => setExpandedCategory(isExpanded ? null : key)}
                  className={`w-full flex items-center justify-between px-3 py-1.5 md:px-4 md:py-2 rounded-lg transition-all text-xs md:text-sm ${
                    isExpanded
                      ? 'bg-emerald-100 text-emerald-800'
                      : 'bg-stone-50 hover:bg-emerald-50 text-stone-600'
                  }`}
                >
                  <span className="flex items-center gap-1.5">
                    {cat.icon}
                    <span className="font-medium">{cat.name}</span>
                    <span className={`text-[10px] md:text-xs px-1.5 py-0 rounded-full font-bold ${
                      isExpanded ? 'bg-emerald-200 text-emerald-900' : 'bg-stone-200 text-stone-500'
                    }`}>
                      {items.length}
                    </span>
                  </span>
                  <span className={`transition-transform duration-200 text-[10px] md:text-xs ${isExpanded ? 'rotate-180' : ''}`}>▾</span>
                </button>

                {/* Expanded item list */}
                {isExpanded && (
                  <div className="mt-1 ml-3 pl-3 border-l-2 border-emerald-200 space-y-0.5 animate-slide-down">
                    {items.map((item, i) => (
                      <div key={i} className="flex items-center justify-between text-[11px] md:text-sm py-0.5 md:py-1">
                        <span className="text-stone-600 truncate pr-2">{item.name}</span>
                        <span className="text-emerald-600 font-medium whitespace-nowrap tabular-nums">
                          {item.distance < 1000 ? `${item.distance}m` : `${(item.distance / 1000).toFixed(1)}km`}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

function TradeCard({ trade, index }) {
  const formatDate = (dateStr, season) => {
    if (dateStr) {
      const d = new Date(dateStr);
      // 過濾異常日期：超過 2028 年的視為錯誤（民國年誤存為西元年等）
      if (d.getFullYear() > 2028 || d.getFullYear() < 1950) {
        // fallthrough to season parsing below
      } else {
        return `${d.getFullYear()}/${String(d.getMonth() + 1).padStart(2, '0')}/${String(d.getDate()).padStart(2, '0')}`;
      }
    }
    // Fallback: parse season like "101S4" → ROC year 101, quarter 4 → ~西元 2012 Q4
    if (season) {
      const match = String(season).match(/^(\d{3})S(\d)$/);
      if (match) {
        const rocYear = parseInt(match[1], 10);
        const quarter = parseInt(match[2], 10);
        const westYear = rocYear + 1911;
        // 過濾異常 season（如 190S4 = 西元2101年，顯然錯誤）
        if (westYear > 2028 || westYear < 1950) return '—';
        const month = (quarter - 1) * 3 + 2; // Q1→2月, Q2→5月, Q3→8月, Q4→11月
        return `${westYear}/${String(month).padStart(2, '0')}/—`;
      }
    }
    return '—';
  };

  const formatPrice = (val) => {
    if (val == null) return '—';
    const num = Number(val);
    if (num >= 100000000) {
      // 破億 → 用「億」顯示，保留兩位小數
      const yi = (num / 100000000).toFixed(2);
      return `${parseFloat(yi)} 億`;
    }
    // 否則用「萬」顯示，整數
    const wan = Math.round(num / 10000);
    return `${wan.toLocaleString()} 萬`;
  };

  const formatUnitPrice = (val) => {
    if (val == null) return '—';
    // 手機版精簡顯示，去掉小數點後兩位
    const num = Number(val);
    if (typeof window !== 'undefined' && window.innerWidth < 768) {
      return `${num.toFixed(1)}萬/坪`;
    }
    return `${num.toFixed(2)} 萬/坪`;
  };

  const formatArea = (area) => {
    if (area == null) return '—';
    // 平方公尺轉坪 (1 坪 ≈ 3.3058 ㎡)
    const tping = Number(area) / 3.3058;
    return `${tping.toFixed(2)} 坪`;
  };

  // 判斷是否為純土地交易
  const isLandOnly = trade.is_land_only || (trade.building_type === '其他' && (!trade.building_area || trade.building_area === 0));
  // 土地交易用地積，建物用建築面積
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
    <div
      className="group relative bg-white rounded-xl border border-stone-200 p-3 md:p-5 hover:border-emerald-300 hover:shadow-lg hover:shadow-emerald-50 transition-all duration-300 animate-slide-up"
      style={{ animationDelay: `${index * 50}ms` }}
    >
      {/* Top row: Location + Date */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <Tag color="emerald">{trade.city}</Tag>
            <Tag color="stone">{trade.district}</Tag>
          </div>
          <h3 className="font-semibold text-stone-900 truncate group-hover:text-emerald-600 transition-colors text-sm md:text-base">
            <IconMapPin className="w-4 h-4 inline" /> {trade.address}
          </h3>
        </div>
        <div className="text-right flex-shrink-0 ml-4">
          <div className="text-xs md:text-sm text-stone-400">成交日期</div>
          <div className="text-sm md:text-base font-medium text-stone-700 tabular-nums">{formatDate(trade.trade_date, trade.season)}</div>
        </div>
      </div>

      {/* Middle row: Price + Key stats */}
      <div className="grid grid-cols-4 gap-2 mb-4 p-3 bg-stone-50 rounded-xl">
        <div>
          <div className="text-xs text-stone-400 mb-1">總價</div>
          <PriceBadge price={formatPrice(trade.total_price)} />
        </div>
        <div>
          <div className="text-xs text-stone-400 mb-1">{unitPriceLabel}</div>
          <div className="text-sm md:text-lg font-bold text-emerald-600 tabular-nums leading-tight">{formatUnitPrice(trade.unit_price_tping)}</div>
        </div>
        <div>
          <div className="text-xs text-stone-400 mb-1">{areaLabel}</div>
          <div className="text-sm md:text-lg font-bold text-stone-700 tabular-nums leading-tight">{formatArea(displayArea)}</div>
        </div>
        <div>
          <div className="text-xs text-stone-400 mb-1">屋齡</div>
          <div className="text-sm md:text-lg font-bold tabular-nums leading-tight">
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

      {/* Bottom row: Tags + Score */}
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

      {/* Lifestyle Score Badge */}
      {trade.score_overall != null && (
        <div className="mb-3 p-2.5 rounded-xl border" style={{
          borderColor: trade.score_overall >= 80 ? '#9ab57d' : trade.score_overall >= 60 ? '#94a3b8' : trade.score_overall >= 40 ? '#fcd34d' : '#fca5a5',
          backgroundColor: trade.score_overall >= 80 ? '#ecfdf5' : trade.score_overall >= 60 ? '#eff6ff' : trade.score_overall >= 40 ? '#fffbeb' : '#fef2f2'
        }}>
          <div className="flex items-center justify-between">
            <span className="text-xs text-stone-500 font-medium"><IconMapPin className="w-3 h-3 inline" /> 生活圈評分</span>
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

      {/* Amenities Panel */}
      <AmenitiesPanel tradeId={trade.id} lat={trade.lat} lon={trade.lon} address={trade.address} />
    </div>
  );
}

/* ─── Main Page ─── */

function TradeListInner() {
  const searchParams = useSearchParams();
  const [trades, setTrades] = useState([]);
  const [pagination, setPagination] = useState({ page: 1, page_size: 12, total: 0, total_pages: 0 });
  const [loading, setLoading] = useState(true);
  const [showFilters, setShowFilters] = useState(false);

  // Filters
  const [city, setCity] = useState(searchParams.get('city') || '');
  const [district, setDistrict] = useState(searchParams.get('district') || '');
  const [minPrice, setMinPrice] = useState('');
  const [maxPrice, setMaxPrice] = useState('');
  const [minUnitPrice, setMinUnitPrice] = useState('');
  const [maxUnitPrice, setMaxUnitPrice] = useState('');
  const [minArea, setMinArea] = useState('');
  const [maxArea, setMaxArea] = useState('');
  const [minAge, setMinAge] = useState('');
  const [maxAge, setMaxAge] = useState('');
  const [rooms, setRooms] = useState('');
  const [livingRooms, setLivingRooms] = useState('');
  const [bathrooms, setBathrooms] = useState('');
  const [buildingType, setBuildingType] = useState('');
  const [sortBy, setSortBy] = useState('trade_date');
  const [sortOrder, setSortOrder] = useState('desc');

  const CITIES = ['基隆市', '宜蘭縣', '臺北市', '新北市', '桃園市', '新竹市', '新竹縣', '苗栗縣', '臺中市', '彰化縣', '南投縣', '雲林縣', '嘉義縣', '嘉義市', '台南市', '高雄市', '屏東縣', '澎湖縣', '花蓮縣', '台東縣', '金門縣', '連江縣'];
  const BUILDING_TYPES = ['住宅大樓', '華廈', '公寓', '透天厝', '別墅'];

  const CITY_DISTRICTS = {
    '基隆市': ['七堵區', '暖暖區', '安樂區', '仁愛區', '中山區', '中正區'],
    '宜蘭縣': ['宜蘭市', '羅東鎮', '蘇澳鎮', '頭城鎮', '礁溪鄉', '壯圍鄉', '員山鄉', '冬山鄉', '五結鄉', '三星鄉', '大同鄉', '南澳鄉'],
    '臺北市': ['松山區', '信義區', '大安區', '中山區', '中正區', '大同區', '萬華區', '文山區', '南港區', '內湖區', '士林區', '北投區'],
    '新北市': ['板橋區', '新店區', '中和區', '新莊區', '永和區', '土城區', '三重區', '蘆洲區', '汐止區', '樹林區', '三峽區', '淡水區', '瑞芳區', '平溪區', '雙溪區', '貢寮區', '石碇區', '坪林區', '烏來區', '深坑區', '八里區', '五股區', '林口區', '泰山區'],
    '桃園市': ['桃園區', '中壢區', '平鎮區', '八德區', '楊梅區', '蘆竹區', '大溪區', '龜山區', '新屋區', '觀音區', '龍潭區'],
    '新竹市': ['東區', '西區', '北區'],
    '新竹縣': ['竹北市', '竹東鎮', '新豐鄉', '湖口鄉', '新埔鎮', '關西鎮', '芎林鄉', '橫山鄉', '寶山鄉', '北埔鄉', '峨眉鄉'],
    '苗栗縣': ['苗栗市', '竹南鎮', '頭份鎮', '通霄鎮', '苑裡鎮', '造橋鄉', '三灣鄉', '南庄鄉', '獅潭鄉', '後龍鎮', '大湖鄉', '公館鄉', '頭屋鄉', '銅鑼鄉', '三義鄉', '西湖鄉', '卓蘭鎮'],
    '臺中市': ['中西區', '南區', '東區', '北區', '西區', '太平區', '大里區', '霧峰區', '烏日區', '豐原區', '后里區', '石岡區', '東勢區', '和平區', '新社區', '潭子區', '大雅區', '神岡區', '沙鹿區', '龍井區', '梧棲區', '清水區', '大甲區', '外埔區', '大肚區'],
    '彰化縣': ['彰化市', '員林市', '和美鎮', '鹿港鎮', '線西鄉', '伸港鄉', '福興鄉', '秀水鄉', '花壇鄉', '芬園鄉', '大村鄉', '永靖鄉', '埔心鄉', '溪湖鎮', '北斗鎮', '田中鎮', '社頭鄉', '二林鎮', '埤頭鄉', '溪州鄉', '竹塘鄉', '二水鄉'],
    '南投縣': ['南投市', '草屯鎮', '埔里鎮', '國姓鄉', '水里鄉', '魚池鄉', '信義鄉', '集集鄉', '名間鄉', '鹿谷鄉'],
    '雲林縣': ['斗六市', '虎尾鎮', '斗南鎮', '西螺鎮', '北港鎮', '古坑鄉', '大埤鄉', '莿桐鄉', '溪州鄉', '崙背鄉', '二崙鄉', '褒忠鄉', '東勢鄉', '台西鄉', '四湖鄉', '元長鄉', '水林鄉', '口湖鄉', '麥寮鄉'],
    '嘉義縣': ['太保市', '朴子市', '布袋鎮', '大林鎮', '民雄鄉', '新港鄉', '六腳鄉', '東石鄉', '義竹鄉', '鹿草鄉', '水上鄉', '中埔鄉', '竹崎鄉', '梅山鄉', '番路鄉', '大埔鄉', '阿里山鄉'],
    '嘉義市': ['東區', '西區'],
    '台南市': ['中西區', '東區', '南區', '北區', '安平區', '安南區', '永康區', '歸仁區', '新化區', '左鎮區', '玉井區', '楠西區', '南化區', '仁德區', '關廟區', '龍崎區', '官田區', '麻豆區', '佳里區', '西港區', '七股區', '將軍區', '學甲區', '北門區', '新市區', '山上區', '下營區', '後壁區', '白河區', '東山區', '六甲區', '鹽水區', '善化區', '大內區', '安定區'],
    '高雄市': ['新興區', '前金區', '苓雅區', '鹽埕區', '鼓山區', '旗津區', '前鎮區', '三民區', '左營區', '楠梓區', '小港區', '鳳山區', '大寮區', '林園區', '鳥松區', '橋頭區', '仁武區', '大樹區', '大社區', '岡山區', '路竹區', '阿蓮區', '田寮區', '燕巢區', '彌陀區', '永安區', '茄萣區'],
    '屏東縣': ['屏東市', '潮州鎮', '東港鎮', '恆春鎮', '枋寮鄉', '長治鄉', '麟洛鄉', '九如鄉', '萬丹鄉', '內埔鄉', '竹田鄉', '新園鄉', '崁頂鄉', '琉球鄉', '佳冬鄉', '太麻里鄉', '車城鄉', '滿州鄉', '枋山鄉', '里港鄉', '高樹鄉', '鹽埔鄉', '泰武鄉', '萬巒鄉', '獅子鄉', '牡丹鄉', '三地門鄉', '霧台鄉', '瑪家鄉'],
    '澎湖縣': ['馬公市', '西嶼鄉', '望安鄉', '七美鄉', '白沙鄉', '湖西鄉'],
    '花蓮縣': ['花蓮市', '新城鄉', '秀林鄉', '吉安鄉', '壽豐鄉', '鳳林鎮', '光復鄉', '豐濱鄉', '瑞穗鄉', '玉里鎮', '富里鄉', '卓溪鄉'],
    '台東縣': ['台東市', '綠島鄉', '蘭嶼鄉', '延平鄉', '卑南鄉', '鹿野鄉', '關山鎮', '海端鄉', '池上鄉', '大武鄉', '成功鎮', '長濱鄉', '東河鄉', '金峰鄉', '太麻里鄉'],
    '金門縣': ['金城鎮', '金湖鎮', '金寧鄉', '金沙鎮', '烈嶼鄉', '烏坵鄉'],
    '連江縣': ['南竿鄉', '北竿鄉', '莒光鄉', '東引鄉'],
  };

  // 去重處理
  const getDistricts = (city) => {
    if (!city) return [];
    const districts = CITY_DISTRICTS[city] || [];
    return [...new Set(districts)];
  };

  const REGIONS = {
    '北部': ['基隆市', '宜蘭縣', '臺北市', '新北市', '桃園市', '新竹市', '新竹縣'],
    '中部': ['苗栗縣', '臺中市', '彰化縣', '南投縣', '雲林縣', '嘉義縣', '嘉義市'],
    '南部': ['澎湖縣', '台南市', '高雄市', '屏東縣'],
    '東部': ['花蓮縣', '台東縣', '金門縣', '連江縣'],
  };

  const [region, setRegion] = useState('');
  const filteredCities = useMemo(() => {
    if (!region) return CITIES;
    return REGIONS[region]?.filter(c => CITIES.includes(c)) || [];
  }, [region]);

  // 當區域改變時，清空縣市和行政區
  useEffect(() => {
    setCity('');
    setDistrict('');
  }, [region]);

  // 當縣市改變時，清空行政區
  useEffect(() => {
    setDistrict('');
  }, [city]);

  const activeFilterCount = [city, district, region, minPrice, maxPrice, minUnitPrice, maxUnitPrice, minArea, maxArea, minAge, maxAge, rooms, livingRooms, bathrooms, buildingType].filter(Boolean).length;

  const fetchTrades = (page = 1) => {
    setLoading(true);
    const params = new URLSearchParams();
    params.set('page', page);
    params.set('page_size', pagination.page_size);
    if (city) params.set('city', city);
    if (district) params.set('district', district);
    if (minPrice) params.set('min_price', minPrice);
    if (maxPrice) params.set('max_price', maxPrice);
    if (minUnitPrice) params.set('min_unit_price', minUnitPrice);
    if (maxUnitPrice) params.set('max_unit_price', maxUnitPrice);
    if (minArea) params.set('min_area', String(Number(minArea) * 3.3058)); // 坪轉㎡
    if (maxArea) params.set('max_area', String(Number(maxArea) * 3.3058)); // 坪轉㎡
    if (minAge) params.set('min_age', minAge);
    if (maxAge) params.set('max_age', maxAge);
    if (rooms) params.set('rooms', rooms);
    if (livingRooms) params.set('living_rooms', livingRooms);
    if (bathrooms) params.set('bathrooms', bathrooms);
    if (buildingType) params.set('building_type', buildingType);
    params.set('sort_by', sortBy);
    params.set('sort_order', sortOrder);

    fetch(`${API}/api/list/trades?${params.toString()}`)
      .then((res) => res.json())
      .then((data) => {
        const items = data.items || [];
        // Deduplicate by id to prevent SSR/CSR hydration duplicates
        const seenIds = new Set();
        const uniqueItems = items.filter(item => {
          if (seenIds.has(item.id)) return false;
          seenIds.add(item.id);
          return true;
        });
        setTrades(uniqueItems);
        setPagination({
          page: data.page,
          page_size: data.page_size,
          total: data.total,
          total_pages: data.total_pages,
        });
        setLoading(false);
      })
      .catch(() => setLoading(false));
  };

  useEffect(() => {
    fetchTrades(1);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Sync URL params to state and re-fetch after hydration (fixes SSR/CSR mismatch)
  useEffect(() => {
    const urlCity = searchParams.get('city');
    const urlDistrict = searchParams.get('district');
    let changed = false;
    if (urlCity && city !== urlCity) { setCity(urlCity); changed = true; }
    if (urlDistrict && district !== urlDistrict) { setDistrict(urlDistrict); changed = true; }
    if (changed) {
      // Small delay to ensure state updates are applied before fetching
      setTimeout(() => fetchTrades(1), 50);
    }
  }, [searchParams]);

  const handleSearch = () => {
    fetchTrades(1);
    setShowFilters(false);
  };

  const handleReset = () => {
    setRegion('');
    setCity('');
    setDistrict('');
    setMinPrice('');
    setMaxPrice('');
    setMinUnitPrice('');
    setMaxUnitPrice('');
    setMinArea('');
    setMaxArea('');
    setMinAge('');
    setMaxAge('');
    setRooms('');
    setLivingRooms('');
    setBathrooms('');
    setBuildingType('');
    setSortBy('trade_date');
    setSortOrder('desc');
    fetchTrades(1);
  };

  return (
    <div className="space-y-6 animate-fade-in">
      {/* ── Hero Header ── */}
      <div className="relative overflow-hidden rounded-2xl bg-emerald-700 p-8 text-white shadow-md border border-emerald-600">
        <div className="absolute inset-0 bg-[url('data:image/svg+xml,%3Csvg%20width%3D%2260%22%20height%3D%2260%22%20viewBox%3D%220%200%2060%2060%22%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%3E%3Cg%20fill%3D%22none%22%20fill-rule%3D%22evenodd%22%3E%3Cg%20fill%3D%22%23ffffff%22%20fill-opacity%3D%220.05%22%3E%3Cpath%20d%3D%22M36%2034v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6%2034v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6%204V0H4v4H0v2h4v4h2V6h4V4H6z%22%2F%3E%3C%2Fg%3E%3C%2Fg%3E%3C%2Fsvg%3E')] opacity-50" />
        <div className="relative z-10">
          <h1 className="text-2xl sm:text-3xl md:text-4xl font-bold mb-2">成交紀錄查詢</h1>
          <p className="text-white/80 text-sm md:text-lg">瀏覽所有實價成交資料，支援多種條件篩選與排序</p>
        </div>
      </div>

      {/* ── Toolbar ── */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Filter toggle button */}
        <button
          onClick={() => setShowFilters(!showFilters)}
          className={`relative flex items-center gap-2 px-4 md:px-5 py-2.5 rounded-xl font-medium text-sm transition-all duration-200 ${
            showFilters
              ? 'bg-emerald-600 text-white shadow-lg shadow-emerald-500/25'
              : 'bg-white text-stone-600 border border-stone-200 hover:border-emerald-300 hover:bg-emerald-50'
          }`}
        >
          <SlidersHorizontal className="w-4 h-4" />
          進階篩選
          {activeFilterCount > 0 && (
            <span className="absolute -top-2 -right-2 w-5 h-5 bg-red-500 text-white text-xs rounded-full flex items-center justify-center">
              {activeFilterCount}
            </span>
          )}
        </button>

        {/* Sort controls */}
        <div className="flex items-center gap-1 ml-auto bg-white border border-stone-200 rounded-xl p-1">
          <span className="text-xs text-stone-400 pl-1 pr-2">排序：</span>
          <select
            value={sortBy}
            onChange={(e) => { setSortBy(e.target.value); fetchTrades(1); }}
            className="px-2 py-1.5 border-none rounded-lg text-sm bg-transparent focus:ring-2 focus:ring-emerald-300 cursor-pointer"
          >
            <option value="trade_date">成交日期</option>
            <option value="total_price">總價</option>
            <option value="unit_price_tping">單價</option>
            <option value="building_area">面積</option>
          </select>
          <button
            onClick={() => { setSortOrder(sortOrder === 'desc' ? 'asc' : 'desc'); fetchTrades(1); }}
            className={`p-1.5 rounded-lg transition-colors ${sortOrder === 'desc' ? 'text-emerald-600 bg-emerald-50' : 'text-stone-400 hover:text-emerald-600'}`}
            title={sortOrder === 'desc' ? '由高到低' : '由低到高'}
          >
            {sortOrder === 'desc' ? <ArrowDown className="w-4 h-4" /> : <ArrowUp className="w-4 h-4" />}
          </button>
        </div>

        {/* Results count */}
        <div className="text-sm text-stone-500">
          共 <strong className="text-stone-900">{pagination.total.toLocaleString()}</strong> 筆
        </div>
      </div>

      {/* ── Expandable Filter Panel ── */}
      {showFilters && (
        <div className="rounded-xl border border-stone-200 bg-white shadow-sm p-6 space-y-4 animate-slide-down">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* Location */}
            <FilterSection title="地區篩選" icon={MapPin}>
              <div className="space-y-3">
                <div>
                  <label className="block text-xs md:text-sm font-medium text-stone-500 mb-1">區域</label>
                  <select
                    value={region}
                    onChange={(e) => setRegion(e.target.value)}
                    className="w-full px-3 py-2 border border-stone-200 rounded-lg text-sm md:text-base focus:ring-2 focus:ring-emerald-300 focus:border-transparent bg-white"
                  >
                    <option value="">全部區域</option>
                    {Object.keys(REGIONS).map((r) => <option key={r} value={r}>{r}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs md:text-sm font-medium text-stone-500 mb-1">縣市</label>
                  <select
                    value={city}
                    onChange={(e) => setCity(e.target.value)}
                    className="w-full px-3 py-2 border border-stone-200 rounded-lg text-sm md:text-base focus:ring-2 focus:ring-emerald-300 focus:border-transparent bg-white"
                  >
                    <option value="">全部</option>
                    {filteredCities.map((c) => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs md:text-sm font-medium text-stone-500 mb-1">行政區</label>
                  <select
                    value={district}
                    onChange={(e) => setDistrict(e.target.value)}
                    className="w-full px-3 py-2 border border-stone-200 rounded-lg text-sm md:text-base focus:ring-2 focus:ring-emerald-300 focus:border-transparent bg-white"
                  >
                    <option value="">全部</option>
                    {getDistricts(city).map((d) => <option key={d} value={d}>{d}</option>)}
                  </select>
                </div>
              </div>
            </FilterSection>

            {/* Price range */}
            <FilterSection title="價格範圍" icon={Search}>
              <div className="space-y-3">
                  <div>
                    <label className="block text-xs md:text-sm font-medium text-stone-500 mb-1">總價範圍 (萬元)</label>
                    <div className="flex gap-2">
                      <input type="number" value={minPrice} onChange={(e) => setMinPrice(e.target.value)} placeholder="最低" className="w-1/2 px-3 py-2 border border-stone-200 rounded-lg text-sm md:text-base focus:ring-2 focus:ring-emerald-300 focus:border-transparent" />
                      <input type="number" value={maxPrice} onChange={(e) => setMaxPrice(e.target.value)} placeholder="最高" className="w-1/2 px-3 py-2 border border-stone-200 rounded-lg text-sm md:text-base focus:ring-2 focus:ring-emerald-300 focus:border-transparent" />
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs md:text-sm font-medium text-stone-500 mb-1">單價範圍 (萬/坪)</label>
                    <div className="flex gap-2">
                      <input type="number" value={minUnitPrice} onChange={(e) => setMinUnitPrice(e.target.value)} placeholder="最低" className="w-1/2 px-3 py-2 border border-stone-200 rounded-lg text-sm md:text-base focus:ring-2 focus:ring-emerald-300 focus:border-transparent" />
                      <input type="number" value={maxUnitPrice} onChange={(e) => setMaxUnitPrice(e.target.value)} placeholder="最高" className="w-1/2 px-3 py-2 border border-stone-200 rounded-lg text-sm md:text-base focus:ring-2 focus:ring-emerald-300 focus:border-transparent" />
                    </div>
                  </div>
              </div>
            </FilterSection>

            {/* Area & Type */}
            <FilterSection title="房屋條件" icon={Home}>
              <div className="space-y-3">
                <div>
                  <label className="block text-xs md:text-sm font-medium text-stone-500 mb-1">面積範圍 (坪)</label>
                  <div className="flex gap-2">
                    <input type="number" value={minArea} onChange={(e) => setMinArea(e.target.value)} placeholder="最小" className="w-1/2 px-3 py-2 border border-stone-200 rounded-lg text-sm md:text-base focus:ring-2 focus:ring-emerald-300 focus:border-transparent" />
                    <input type="number" value={maxArea} onChange={(e) => setMaxArea(e.target.value)} placeholder="最大" className="w-1/2 px-3 py-2 border border-stone-200 rounded-lg text-sm md:text-base focus:ring-2 focus:ring-emerald-300 focus:border-transparent" />
                  </div>
                </div>
                <div>
                  <label className="block text-xs md:text-sm font-medium text-stone-500 mb-1">屋齡範圍 (年)</label>
                  <div className="flex gap-2">
                    <input type="number" value={minAge} onChange={(e) => setMinAge(e.target.value)} placeholder="最小" className="w-1/2 px-3 py-2 border border-stone-200 rounded-lg text-sm md:text-base focus:ring-2 focus:ring-emerald-300 focus:border-transparent" />
                    <input type="number" value={maxAge} onChange={(e) => setMaxAge(e.target.value)} placeholder="最大" className="w-1/2 px-3 py-2 border border-stone-200 rounded-lg text-sm md:text-base focus:ring-2 focus:ring-emerald-300 focus:border-transparent" />
                  </div>
                </div>
                <div>
                  <label className="block text-xs md:text-sm font-medium text-stone-500 mb-1">房屋類型</label>
                  <select
                    value={buildingType}
                    onChange={(e) => setBuildingType(e.target.value)}
                    className="w-full px-3 py-2 border border-stone-200 rounded-lg text-sm md:text-base focus:ring-2 focus:ring-emerald-300 focus:border-transparent bg-white"
                  >
                    <option value="">全部</option>
                    {BUILDING_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                  </select>
                </div>
                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <label className="block text-xs md:text-sm font-medium text-stone-500 mb-1">房間</label>
                    <input type="number" value={rooms} onChange={(e) => setRooms(e.target.value)} placeholder="—" className="w-full px-3 py-2 border border-stone-200 rounded-lg text-sm md:text-base focus:ring-2 focus:ring-emerald-300 focus:border-transparent" />
                  </div>
                  <div>
                    <label className="block text-xs md:text-sm font-medium text-stone-500 mb-1">廳數</label>
                    <input type="number" value={livingRooms} onChange={(e) => setLivingRooms(e.target.value)} placeholder="—" className="w-full px-3 py-2 border border-stone-200 rounded-lg text-sm md:text-base focus:ring-2 focus:ring-emerald-300 focus:border-transparent" />
                  </div>
                  <div>
                    <label className="block text-xs md:text-sm font-medium text-stone-500 mb-1">衛浴</label>
                    <input type="number" value={bathrooms} onChange={(e) => setBathrooms(e.target.value)} placeholder="—" className="w-full px-3 py-2 border border-stone-200 rounded-lg text-sm md:text-base focus:ring-2 focus:ring-emerald-300 focus:border-transparent" />
                  </div>
                </div>
              </div>
            </FilterSection>
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-2">
            <button onClick={handleSearch} className="bg-emerald-600 text-white rounded-lg px-5 py-2.5 font-semibold shadow-lg shadow-emerald-500/25 hover:bg-emerald-700 transition-all duration-200 px-8 py-2.5">
              搜尋
            </button>
            <button onClick={handleReset} className="bg-transparent text-stone-600 border border-stone-200 rounded-lg px-5 py-2.5 font-medium hover:text-stone-900 hover:border-emerald-300 hover:bg-emerald-50 transition-all duration-200 px-6 py-2.5">
              重設所有條件
            </button>
          </div>
        </div>
      )}

      {/* ── Active Filters Display ── */}
      {activeFilterCount > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm md:text-base text-stone-500">目前篩選：</span>
          {city && <Tag color="emerald">{city} <IconX className="w-3 h-3 inline" /></Tag>}
          {district && <Tag color="stone">{district} <IconX className="w-3 h-3 inline" /></Tag>}
          {buildingType && <Tag color="emerald">{buildingType} <IconX className="w-3 h-3 inline" /></Tag>}
          {(minPrice || maxPrice) && <Tag color="emerald">總價 {minPrice || '0'}-{maxPrice || '∞'} 萬 <IconX className="w-3 h-3 inline" /></Tag>}
          {(minUnitPrice || maxUnitPrice) && <Tag color="amber">單價 {minUnitPrice || '0'}-{maxUnitPrice || '∞'} 萬/坪 <IconX className="w-3 h-3 inline" /></Tag>}
          <button onClick={handleReset} className="text-xs md:text-sm text-red-500 hover:text-red-700 ml-2 underline">清除全部</button>
        </div>
      )}

      {/* ── Results Grid ── */}
      {loading ? (
        <div className="flex justify-center py-20">
          <div className="flex flex-col items-center gap-3">
            <div className="animate-spin h-10 w-10 border-4 border-emerald-400 border-t-transparent rounded-full" />
            <span className="text-sm md:text-base text-stone-400">載入成交紀錄...</span>
          </div>
        </div>
      ) : trades.length === 0 ? (
        <div className="text-center py-20">
          <IconHomeEmpty className="w-24 h-24 mx-auto text-stone-300" />
          <p className="text-xl text-stone-400 mb-2">沒有找到符合條件的成交紀錄</p>
          <p className="text-sm text-stone-300">嘗試調整篩選條件或清除所有篩選</p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 stagger-children">
            {trades.map((t, i) => (
              <TradeCard key={t.id} trade={t} index={i} />
            ))}
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-center gap-3 pt-4">
            <button
              onClick={() => fetchTrades(pagination.page - 1)}
              disabled={pagination.page <= 1}
              className="px-5 py-2.5 border border-stone-200 rounded-xl text-sm md:text-base font-medium text-stone-600 hover:bg-stone-50 hover:border-emerald-300 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
            >
              ← 上一頁
            </button>
            <div className="flex items-center gap-1">
              {Array.from({ length: Math.min(5, pagination.total_pages) }, (_, i) => {
                let pageNum;
                if (pagination.total_pages <= 5) {
                  pageNum = i + 1;
                } else if (pagination.page <= 3) {
                  pageNum = i + 1;
                } else if (pagination.page >= pagination.total_pages - 2) {
                  pageNum = pagination.total_pages - 4 + i;
                } else {
                  pageNum = pagination.page - 2 + i;
                }
                return (
                  <button
                    key={pageNum}
                    onClick={() => fetchTrades(pageNum)}
                    className={`w-10 h-10 rounded-xl text-sm md:text-base font-medium transition-all ${
                      pagination.page === pageNum
                        ? 'bg-emerald-600 text-white shadow-lg shadow-emerald-200'
                        : 'text-stone-600 hover:bg-stone-100'
                    }`}
                  >
                    {pageNum}
                  </button>
                );
              })}
            </div>
            <button
              onClick={() => fetchTrades(pagination.page + 1)}
              disabled={pagination.page >= pagination.total_pages}
              className="px-5 py-2.5 border border-stone-200 rounded-xl text-sm md:text-base font-medium text-stone-600 hover:bg-stone-50 hover:border-emerald-300 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
            >
              下一頁 →
            </button>
          </div>
        </>
      )}
    </div>
  );
}

export default function TradeListPage() {
  return (
    <Suspense fallback={
      <div className="flex justify-center py-20">
        <div className="animate-spin h-10 w-10 border-4 border-emerald-400 border-t-transparent rounded-full" />
      </div>
    }>
      <TradeListInner />
    </Suspense>
  );
}
