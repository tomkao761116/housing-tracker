'use client';

import './globals.css';
import { useState, useEffect } from 'react';
import Link from 'next/link';

/* ─── SVG Icons (Lucide-style, stroke-width 1.5 for subtlety) ─── */
function IconLayoutDashboard({ className = "w-5 h-5" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="9" rx="1" />
      <rect x="14" y="3" width="7" height="5" rx="1" />
      <rect x="14" y="12" width="7" height="9" rx="1" />
      <rect x="3" y="16" width="7" height="5" rx="1" />
    </svg>
  );
}
function IconTrophy({ className = "w-5 h-5" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6" /><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18" />
      <path d="M4 22h16" /><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20 7 22" />
      <path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20 17 22" />
      <path d="M18 2H6v7a6 6 0 0 0 12 0V2Z" />
    </svg>
  );
}
function IconList({ className = "w-5 h-5" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <line x1="8" y1="6" x2="21" y2="6" /><line x1="8" y1="12" x2="21" y2="12" /><line x1="8" y1="18" x2="21" y2="18" />
      <line x1="3" y1="6" x2="3.01" y2="6" /><line x1="3" y1="12" x2="3.01" y2="12" /><line x1="3" y1="18" x2="3.01" y2="18" />
    </svg>
  );
}
function IconSearch({ className = "w-5 h-5" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );
}
function IconHome({ className = "w-5 h-5" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8" /><path d="M3 10a2 2 0 0 1 .709-1.528l7-5.999a2 2 0 0 1 2.582 0l7 5.999A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
    </svg>
  );
}
function IconBarChart3({ className = "w-5 h-5" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <line x1="12" y1="20" x2="12" y2="10" /><line x1="18" y1="20" x2="18" y2="4" /><line x1="6" y1="20" x2="6" y2="16" />
    </svg>
  );
}
function IconMapPin({ className = "w-5 h-5" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" /><circle cx="12" cy="10" r="3" />
    </svg>
  );
}
function IconBuilding({ className = "w-5 h-5" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect width="16" height="20" x="4" y="2" rx="2" ry="2" />
      <path d="M9 22v-4h6v4" /><path d="M8 6h.01" /><path d="M16 6h.01" /><path d="M12 6h.01" />
      <path d="M12 10h.01" /><path d="M12 14h.01" /><path d="M16 10h.01" /><path d="M16 14h.01" /><path d="M8 10h.01" /><path d="M8 14h.01" />
    </svg>
  );
}
function IconHouse({ className = "w-5 h-5" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8" /><path d="M3 10a2 2 0 0 1 .709-1.528l7-5.999a2 2 0 0 1 2.582 0l7 5.999A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
    </svg>
  );
}
function IconCompass({ className = "w-5 h-5" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" /><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76" />
    </svg>
  );
}
function IconMessageCircle({ className = "w-5 h-5" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z" />
    </svg>
  );
}

const navLinks = [
  { href: '/', label: '首頁', icon: IconHouse },
  { href: '/find', label: '找房', icon: IconCompass },
  { href: '/evaluate', label: '地點評估', icon: IconMapPin },
];

/* ─── Hamburger Button (SVG) ─── */
function HamburgerButton({ onClick }) {
  return (
    <button
      onClick={onClick}
      className="md:hidden flex flex-col justify-center items-center gap-1.5 w-10 h-10 rounded border border-[#e0ddd8] bg-white/50 hover:bg-stone-50 transition-colors"
      aria-label="選單"
    >
      <span className="block w-5 h-px bg-slate-700" />
      <span className="block w-5 h-px bg-slate-700" />
      <span className="block w-5 h-px bg-slate-700" />
    </button>
  );
}

/* ─── Active Nav Link Detector (SPA-aware) ─── */
function useActivePath() {
  const [active, setActive] = useState('');
  useEffect(() => {
    setActive(window.location.pathname);
    document.title = '房屋實價追蹤系統';
    const observer = new MutationObserver(() => {
      setActive(window.location.pathname);
    });
    observer.observe(document.body, { childList: true, subtree: true });
    const handlePop = () => setActive(window.location.pathname);
    window.addEventListener('popstate', handlePop);
    return () => {
      observer.disconnect();
      window.removeEventListener('popstate', handlePop);
    };
  }, []);
  return active;
}

/* ─── Mobile Slide-out Menu ─── */
function MobileMenu({ open, onClose, activePath }) {
  return (
    <>
      <div
        className={`mobile-menu-overlay ${open ? 'open' : ''}`}
        onClick={onClose}
        aria-hidden={!open}
      />
      <div className={`mobile-menu-panel ${open ? 'open' : ''}`}>
        <div className="flex items-center justify-between mb-8">
          <span className="text-lg font-medium text-slate-800">選單</span>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded text-zinc-500 hover:text-slate-800 hover:bg-stone-50 transition-colors"
            aria-label="關閉選單"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
        <nav className="flex flex-col gap-1">
          {navLinks.map((link) => {
            const isActive =
              link.href === '/'
                ? activePath === '/'
                : activePath.startsWith(link.href);
            const IconComp = link.icon;
            return (
              <Link
                key={link.href}
                href={link.href}
                onClick={onClose}
                className={`flex items-center gap-3 px-4 py-3 rounded transition-colors ${
                  isActive
                    ? 'bg-[#f0eeeb] text-slate-800'
                    : 'text-zinc-600 hover:text-slate-800 hover:bg-stone-50'
                }`}
              >
                <IconComp className="w-5 h-5" />
                <span>{link.label}</span>
              </Link>
            );
          })}
        </nav>
        <div className="mt-auto pt-6 border-t border-[#e0ddd8]">
          <p className="text-xs text-zinc-400">資料來源：內政部地政司</p>
        </div>
      </div>
    </>
  );
}

/* ─── Mountain Silhouette SVG (top-right corner, ink wash style) ─── */
function MountainSilhouette() {
  return (
    <div className="fixed top-0 right-0 pointer-events-none z-0" aria-hidden="true">
      <svg width="100vw" height="100vh" viewBox="0 0 1200 800" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMin slice" style={{position:'absolute', top: 0, right: 0}}>
        {/* Sun circle — warm accent */}
        <circle cx="960" cy="120" r="50" fill="#d48a5a" opacity="0.2"/>
        {/* Far mountains - lightest */}
        <path d="M1200 0 L1200 300 Q1100 270 1000 240 Q900 210 800 255 Q700 300 600 270 Q500 240 400 285 Q300 330 200 300 Q100 270 0 315 L0 0 Z"
              fill="#6b7c5e" opacity="0.25"/>
        {/* Mid mountains */}
        <path d="M1200 0 L1200 420 Q1080 360 960 390 Q840 420 720 360 Q600 300 480 375 Q360 450 240 390 Q120 330 0 405 L0 0 Z"
              fill="#6b7c5e" opacity="0.18"/>
        {/* Near mountains - darkest */}
        <path d="M1200 0 L1200 520 Q1060 450 920 495 Q780 540 640 465 Q500 390 360 480 Q220 570 0 495 L0 0 Z"
              fill="#6b7c5e" opacity="0.12"/>
        {/* Mist layers between mountains */}
        <path d="M1200 225 Q1000 210 800 232 Q600 255 400 225 Q200 195 0 232 L0 240 Q200 203 400 233 Q600 263 800 240 Q1000 217 1200 232 Z"
              fill="#6b7c5e" opacity="0.08"/>
        <path d="M1200 345 Q1000 330 800 352 Q600 375 400 345 Q200 315 0 352 L0 360 Q200 323 400 353 Q600 383 800 360 Q1000 337 1200 352 Z"
              fill="#6b7c5e" opacity="0.06"/>
      </svg>
    </div>
  );
}

export default function RootLayout({ children }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const activePath = useActivePath();

  return (
    <html lang="zh-TW">
      <body className="min-h-screen bg-[#faf9f7] text-[#2a2a2a] antialiased relative">
        {/* Mountain silhouette background */}
        <MountainSilhouette />

        {/* ── Navigation Bar (Japanese Minimalist) ── */}
        <nav className="bg-white border-b border-[#e8e4df] sticky top-0 z-50">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex items-center justify-between h-14">
              {/* Brand */}
              <Link
                href="/"
                className="flex items-center gap-2 group"
              >
                <IconHouse className="w-5 h-5 text-[#2a2a2a] group-hover:text-[#6b7c5e] transition-colors" />
                <span className="text-sm font-normal text-[#2a2a2a] tracking-wide">
                  房屋實價追蹤
                </span>
              </Link>

              {/* Desktop Links */}
              <div className="hidden md:flex items-center gap-1">
                {navLinks.map((link) => {
                  const isActive =
                    link.href === '/'
                      ? activePath === '/'
                      : activePath.startsWith(link.href);
                  const IconComp = link.icon;
                  return (
                    <Link
                      key={link.href}
                      href={link.href}
                      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-normal transition-all duration-150 ${
                        isActive
                          ? 'bg-[#f0eeeb] text-[#2a2a2a]'
                          : 'text-zinc-500 hover:text-[#2a2a2a] hover:bg-stone-50/50'
                      }`}
                    >
                      <IconComp className="w-4 h-4" />
                      <span>{link.label}</span>
                    </Link>
                  );
                })}
              </div>

              {/* Right side */}
              <div className="flex items-center gap-3">
                <span className="hidden sm:inline text-xs text-zinc-400">
                  內政部地政司
                </span>
                <HamburgerButton onClick={() => setMenuOpen(true)} />
              </div>
            </div>
          </div>
        </nav>

        {/* ── Mobile Menu ── */}
        <MobileMenu open={menuOpen} onClose={() => setMenuOpen(false)} activePath={activePath} />

        {/* ── Main Content ── */}
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 animate-fade-in">
          {children}
        </main>
      </body>
    </html>
  );
}
