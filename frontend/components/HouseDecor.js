'use client';

/* ─── House Divider Component (Style 1: Japanese Minimalist) ─── */
export function HouseDivider({ className = '' }) {
  return (
    <div className={`flex items-center gap-3 my-8 ${className}`}>
      <div className="flex-1 h-px bg-[#e0ddd8]" />
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#6b7c5e" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" opacity="0.35">
        <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
      </svg>
      <div className="flex-1 h-px bg-[#e0ddd8]" />
    </div>
  );
}

/* ─── Button (Style 1: Outline / Minimal) ─── */
export function HouseButton({ children, className = '', as: AsComponent = 'button', ...props }) {
  const baseClasses =
    'inline-flex items-center justify-center gap-2 px-7 py-2.5 text-sm font-medium transition-all duration-200 border rounded-sm hover:shadow-sm active:translate-y-px';

  if (AsComponent) {
    return (
      <AsComponent className={`${baseClasses} ${className}`} {...props}>
        {children}
      </AsComponent>
    );
  }

  return (
    <button className={`${baseClasses} ${className}`} {...props}>
      {children}
    </button>
  );
}
