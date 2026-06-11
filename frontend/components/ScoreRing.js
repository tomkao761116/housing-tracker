'use client';
/**
 * ScoreRing — 環形進度指示器（SVG donut chart）
 * Props: score (0-100), size (px), strokeWidth (px)
 * Uses gradient from gray (low) to vibrant green (high)
 */
export default function ScoreRing({ score, size = 90, strokeWidth = 7 }) {
  if (score == null) return null;

  const clamped = Math.max(0, Math.min(100, score));
  const center = size / 2;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const progress = clamped / 100;
  const offset = circumference * (1 - progress);

  // Dynamic color based on score
  let ringColor;
  if (clamped >= 80) ringColor = '#637d56';
  else if (clamped >= 60) ringColor = '#475569';
  else if (clamped >= 40) ringColor = '#d97706';
  else ringColor = '#dc2626';

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      {/* Background track */}
      <circle
        cx={center} cy={center} r={radius}
        fill="none" stroke="#e5e7eb" strokeWidth={strokeWidth}
      />
      {/* Progress arc */}
      <circle
        cx={center} cy={center} r={radius}
        fill="none" stroke={ringColor} strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        transform={`rotate(-90 ${center} ${center})`}
        style={{ transition: 'stroke-dashoffset 0.8s ease-out' }}
      />
      {/* Center text */}
      <text
        x={center} y={center - 4}
        textAnchor="middle" dominantBaseline="middle"
        fontSize={size * 0.22} fontWeight="bold" fill="#1f2937"
      >
        {Math.round(clamped)}
      </text>
      <text
        x={center} y={center + size * 0.15}
        textAnchor="middle" dominantBaseline="middle"
        fontSize={size * 0.11} fill="#6b7280"
      >
        綜合
      </text>
    </svg>
  );
}
