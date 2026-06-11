'use client';

import './globals.css';
import { useState, useEffect } from 'react';
import Link from 'next/link';

/* ─── SVG Icons (Lucide-style) ─── */
function IconLayoutDashboard({ className = "w-5 h-5" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="9" rx="1" />
      <rect x="14" y="3" width="7" height="5" rx="1" />
      <rect x="14" y="12" width="7" height="9" rx="1" />
      <rect x="3" y="16" width="7" height="5" rx="1" />
    </svg>
  );
}
function IconTrophy({ className = "w-5 h-5" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6" /><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18" />
      <path d="M4 22h16" /><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20 7 22" />
      <path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20 17 22" />
      <path d="M18 2H6v7a6 6 0 0 0 12 0V2Z" />
    </svg>
  );
}
function IconList({ className = "w-5 h-5" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="8" y1="6" x2="21" y2="6" /><line x1="8" y1="12" x2="21" y2="12" /><line x1="8" y1="18" x2="21" y2="18" />
      <line x1="3" y1="6" x2="3.01" y2="6" /><line x1="3" y1="12" x2="3.01" y2="12" /><line x1="3" y1="18" x2="3.01" y2="18" />
    </svg>
  );
}
function IconSearch({ className = "w-5 h-5" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );
}
function IconHome({ className = "w-5 h-5" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8" /><path d="M3 10a2 2 0 0 1 .709-1.528l7-5.999a2 2 0 0 1 2.582 0l7 5.999A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
    </svg>
  );
}
function IconBarChart3({ className = "w-5 h-5" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="12" y1="20" x2="12" y2="10" /><line x1="18" y1="20" x2="18" y2="4" /><line x1="6" y1="20" x2="6" y2="16" />
    </svg>
  );
}
function IconMapPin({ className = "w-5 h-5" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" /><circle cx="12" cy="10" r="3" />
    </svg>
  );
}
function IconBuilding({ className = "w-5 h-5" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect width="16" height="20" x="4" y="2" rx="2" ry="2" />
      <path d="M9 22v-4h6v4" /><path d="M8 6h.01" /><path d="M16 6h.01" /><path d="M12 6h.01" />
      <path d="M12 10h.01" /><path d="M12 14h.01" /><path d="M16 10h.01" /><path d="M16 14h.01" /><path d="M8 10h.01" /><path d="M8 14h.01" />
    </svg>
  );
}
function IconHouse({ className = "w-5 h-5" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8" /><path d="M3 10a2 2 0 0 1 .709-1.528l7-5.999a2 2 0 0 1 2.582 0l7 5.999A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
    </svg>
  );
}
function IconCompass({ className = "w-5 h-5" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" /><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76" />
    </svg>
  );
}
function IconMessageCircle({ className = "w-5 h-5" }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
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
          <span className="text-lg font-bold text-slate-800">選單</span>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded text-zinc-500 hover:text-slate-800 hover:bg-stone-50 transition-colors"
            aria-label="關閉選單"
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
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
                    ? 'bg-stone-100 text-slate-800 font-semibold'
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

/* ─── Park Background SVG Component (S-curve diagonal path) ─── */
function ParkBackground() {
  return (
    <div className="fixed inset-0 pointer-events-none z-0 opacity-[0.12]" aria-hidden="true">
      <svg width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" style={{position:'absolute'}}>
        <defs>
          <pattern id="parkPattern" x="0" y="0" width="800" height="1000" patternUnits="userSpaceOnUse">
            {/* Main S-curve path: top-right to bottom-left */}
            <path d="M750 0 Q700 80 650 120 Q580 170 600 240 Q620 310 550 360 Q470 420 500 500 Q530 580 450 640 Q370 700 400 780 Q430 860 350 920 Q280 970 250 1000"
                  stroke="#6b7c5e" fill="none" strokeWidth="2.5" strokeLinecap="round" />
            {/* Branch paths */}
            <path d="M600 240 Q560 260 500 250 Q460 245 440 270"
                  stroke="#6b7c5e" fill="none" strokeWidth="1.5" strokeLinecap="round" />
            <path d="M500 500 Q540 520 600 510 Q640 505 660 530"
                  stroke="#6b7c5e" fill="none" strokeWidth="1.5" strokeLinecap="round" />
            <path d="M400 780 Q360 800 300 790 Q260 785 240 810"
                  stroke="#6b7c5e" fill="none" strokeWidth="1.5" strokeLinecap="round" />
            {/* Trees along path */}
            <g stroke="#6b7c5e" fill="none" strokeLinecap="round">
              <line x1="500" y1="100" x2="500" y2="160" strokeWidth="2"/>
              <circle cx="500" cy="75" r="35" strokeWidth="1.5"/>
              <path d="M475 55 Q485 40 495 55 Q505 35 515 55 Q525 40 530 60" strokeWidth="1"/>
            </g>
            <g stroke="#6b7c5e" fill="none" strokeLinecap="round">
              <line x1="350" y1="300" x2="350" y2="360" strokeWidth="2"/>
              <circle cx="350" cy="275" r="30" strokeWidth="1.5"/>
            </g>
            <g stroke="#6b7c5e" fill="none" strokeLinecap="round">
              <line x1="600" y1="450" x2="600" y2="510" strokeWidth="2"/>
              <circle cx="600" cy="425" r="32" strokeWidth="1.5"/>
            </g>
            <g stroke="#6b7c5e" fill="none" strokeLinecap="round">
              <line x1="280" y1="600" x2="280" y2="660" strokeWidth="2"/>
              <circle cx="280" cy="575" r="28" strokeWidth="1.5"/>
            </g>
            <g stroke="#6b7c5e" fill="none" strokeLinecap="round">
              <line x1="480" y1="750" x2="480" y2="810" strokeWidth="2"/>
              <circle cx="480" cy="725" r="30" strokeWidth="1.5"/>
            </g>
            <g stroke="#6b7c5e" fill="none" strokeLinecap="round">
              <line x1="180" y1="880" x2="180" y2="940" strokeWidth="2"/>
              <circle cx="180" cy="855" r="26" strokeWidth="1.5"/>
            </g>
            {/* Small bushes */}
            <g stroke="#6b7c5e" fill="none" strokeLinecap="round">
              <line x1="420" y1="200" x2="420" y2="225" strokeWidth="1.5"/>
              <circle cx="420" cy="190" r="15" strokeWidth="1"/>
            </g>
            <g stroke="#6b7c5e" fill="none" strokeLinecap="round">
              <line x1="540" y1="400" x2="540" y2="425" strokeWidth="1.5"/>
              <circle cx="540" cy="388" r="14" strokeWidth="1"/>
            </g>
            <g stroke="#6b7c5e" fill="none" strokeLinecap="round">
              <line x1="320" y1="550" x2="320" y2="575" strokeWidth="1.5"/>
              <circle cx="320" cy="538" r="14" strokeWidth="1"/>
            </g>
            {/* Flowers */}
            <g stroke="#6b7c5e" fill="none" strokeWidth="1">
              <circle cx="460" cy="180" r="4"/><circle cx="468" cy="176" r="3"/><circle cx="456" cy="182" r="3"/>
              <line x1="462" y1="182" x2="462" y2="195"/>
            </g>
            <g stroke="#6b7c5e" fill="none" strokeWidth="1">
              <circle cx="380" cy="480" r="4"/><circle cx="388" cy="476" r="3"/><circle cx="376" cy="482" r="3"/>
              <line x1="382" y1="482" x2="382" y2="495"/>
            </g>
            <g stroke="#6b7c5e" fill="none" strokeWidth="1">
              <circle cx="240" cy="720" r="4"/><circle cx="248" cy="716" r="3"/><circle cx="236" cy="722" r="3"/>
              <line x1="242" y1="722" x2="242" y2="735"/>
            </g>
            {/* Benches */}
            <g stroke="#6b7c5e" fill="none" strokeWidth="1.2">
              <rect x="300" y="250" width="28" height="2.5" rx="1"/>
              <rect x="302" y="252.5" width="24" height="2.5" rx="1"/>
              <line x1="304" y1="255" x2="304" y2="266"/>
              <line x1="322" y1="255" x2="322" y2="266"/>
            </g>
            <g stroke="#6b7c5e" fill="none" strokeWidth="1.2">
              <rect x="450" y="650" width="28" height="2.5" rx="1"/>
              <rect x="452" y="652.5" width="24" height="2.5" rx="1"/>
              <line x1="454" y1="655" x2="454" y2="666"/>
              <line x1="472" y1="655" x2="472" y2="666"/>
            </g>
            {/* Lamp posts */}
            <g stroke="#6b7c5e" fill="none" strokeWidth="1.2">
              <line x1="550" y1="150" x2="550" y2="200"/>
              <circle cx="550" cy="146" r="5"/>
              <line x1="542" y1="150" x2="558" y2="150"/>
            </g>
            <g stroke="#6b7c5e" fill="none" strokeWidth="1.2">
              <line x1="380" y1="550" x2="380" y2="600"/>
              <circle cx="380" cy="546" r="5"/>
            </g>
            {/* Stone steps on path */}
            <ellipse cx="680" cy="60" rx="7" ry="2.5" stroke="#6b7c5e" fill="none" strokeWidth="1"/>
            <ellipse cx="620" cy="150" rx="6" ry="2.5" stroke="#6b7c5e" fill="none" strokeWidth="1"/>
            <ellipse cx="570" cy="280" rx="7" ry="2.5" stroke="#6b7c5e" fill="none" strokeWidth="1"/>
            <ellipse cx="520" cy="420" rx="6" ry="2.5" stroke="#6b7c5e" fill="none" strokeWidth="1"/>
            <ellipse cx="470" cy="560" rx="7" ry="2.5" stroke="#6b7c5e" fill="none" strokeWidth="1"/>
            <ellipse cx="420" cy="700" rx="6" ry="2.5" stroke="#6b7c5e" fill="none" strokeWidth="1"/>
            <ellipse cx="370" cy="840" rx="7" ry="2.5" stroke="#6b7c5e" fill="none" strokeWidth="1"/>
            <ellipse cx="310" cy="950" rx="6" ry="2.5" stroke="#6b7c5e" fill="none" strokeWidth="1"/>
            {/* Grass tufts */}
            <g stroke="#6b7c5e" fill="none" strokeWidth="1">
              <path d="M100 300 Q102 290 105 300"/><path d="M105 302 Q107 292 110 302"/>
            </g>
            <g stroke="#6b7c5e" fill="none" strokeWidth="1">
              <path d="M700 500 Q702 490 705 500"/><path d="M705 502 Q707 492 710 502"/>
            </g>
            <g stroke="#6b7c5e" fill="none" strokeWidth="1">
              <path d="M100 700 Q102 690 105 700"/><path d="M105 702 Q107 692 110 702"/>
            </g>
            {/* Birds */}
            <g stroke="#6b7c5e" fill="none" strokeWidth="1">
              <path d="M650 40 Q654 34 658 40 Q662 34 666 40"/>
              <path d="M680 55 Q683 50 686 55 Q689 50 692 55"/>
            </g>
            {/* Clouds */}
            <g stroke="#6b7c5e" fill="none" strokeWidth="0.8">
              <path d="M600 20 Q604 12 612 16 Q620 8 628 16 Q636 12 640 20 Q644 26 636 28 L604 28 Q596 26 600 20Z"/>
            </g>
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#parkPattern)" />
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
        {/* Park line art background */}
        <ParkBackground />

        {/* ── Navigation Bar (Style 1: Minimal) ── */}
        <nav className="bg-white/90 backdrop-blur-xl border-b border-[#e8e4df] sticky top-0 z-50">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex items-center justify-between h-16">
              {/* Brand */}
              <Link
                href="/"
                className="flex items-center gap-2.5 group"
              >
                <div className="w-8 h-8 rounded-sm bg-[#2a2a2a] flex items-center justify-center group-hover:bg-[#5a6b4e] transition-colors">
                  <IconHouse className="w-5 h-5 text-white" />
                </div>
                <span className="text-base sm:text-lg font-medium text-[#1a1a1a] truncate max-w-[120px] sm:max-w-none">
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
                      className={`relative flex items-center gap-1.5 px-3 py-2 rounded-sm text-sm font-medium transition-all duration-150 ${
                        isActive
                          ? 'bg-stone-100 text-[#1a1a1a]'
                          : 'text-zinc-600 hover:text-[#1a1a1a] hover:bg-stone-50/50'
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
                <span className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1 text-xs font-medium text-zinc-500">
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
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 animate-fade-in">
          {children}
        </main>
      </body>
    </html>
  );
}
