/**
 * FindMap wrapper — 使用 Next.js dynamic import (ssr: false)
 * 解決 Leaflet 在 SSR 環境下無法存取的 window 物件問題。
 */
import dynamic from 'next/dynamic';

const FindMap = dynamic(() => import('./FindMapInner'), {
  ssr: false,
  loading: () => (
    <div className="w-full h-[600px] rounded-xl border border-stone-200 bg-stone-100 flex items-center justify-center">
      <div className="text-stone-400 text-sm">地圖載入中...</div>
    </div>
  ),
});

export default FindMap;
