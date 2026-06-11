'use client';
/**
 * RadarChart — 雷達圖顯示多維度評分
 * Props: scores (object of {key: {score, label, color}}), size (px), centerScore (number)
 */
export default function RadarChart({ scores, size = 320, centerScore }) {
  const dims = Object.entries(scores || {});
  if (dims.length === 0) {
    return <div style={{ textAlign: 'center', padding: 40, color: '#9ca3af' }}>暫無評分資料</div>;
  }

  const n = dims.length;
  const center = size / 2;
  const radius = (size - 60) / 2;
  const levels = [0.2, 0.4, 0.6, 0.8, 1.0];

  function point(angle, r) {
    return [center + r * Math.cos(angle), center + r * Math.sin(angle)];
  }

  function polygonCoords(stepR) {
    return dims.map((_, i) => {
      const angle = (2 * Math.PI * i) / n - Math.PI / 2;
      const [x, y] = point(angle, stepR);
      return `${x},${y}`;
    }).join(' ');
  }

  // FIX: Use map index `i` instead of indexOf([key, val]) which always returns -1
  // because [key, val] creates a new array reference each iteration.
  const dataPoints = dims.map(([key, val], i) => {
    const angle = (2 * Math.PI * i) / n - Math.PI / 2;
    const r = (Math.min(Math.max(val.score || 0, 0), 100) / 100) * radius;
    const [x, y] = point(angle, r);
    return { x, y, label: val.label || key, score: val.score, color: val.color || '#6366f1' };
  });

  const dataPoly = dataPoints.map(p => `${p.x},${p.y}`).join(' ');

  const labelFontSize = size < 250 ? 10 : 12;

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ display: 'block', margin: '0 auto' }}>
      {/* Grid rings */}
      {levels.map((lvl, i) => (
        <polygon
          key={i}
          points={polygonCoords(lvl * radius)}
          fill="none"
          stroke="#e5e7eb"
          strokeWidth={1}
        />
      ))}
      {/* Axis lines */}
      {dataPoints.map((p, i) => (
        <line
          key={i}
          x1={center} y1={center}
          x2={p.x} y2={p.y}
          stroke="#d1d5db"
          strokeWidth={1}
        />
      ))}
      {/* Data polygon */}
      <polygon
        points={dataPoly}
        fill="rgba(99,102,241,0.15)"
        stroke="#6366f1"
        strokeWidth={2}
      />
      {/* Data points */}
      {dataPoints.map((p, i) => (
        <g key={i}>
          <circle cx={p.x} cy={p.y} r={4} fill={p.color} stroke="#fff" strokeWidth={2} />
          {/* Label */}
          {(() => {
            const angle = (2 * Math.PI * i) / n - Math.PI / 2;
            const lx = center + (radius + 20) * Math.cos(angle);
            const ly = center + (radius + 20) * Math.sin(angle);
            return (
              <text
                x={lx} y={ly}
                textAnchor="middle" dominantBaseline="middle"
                fontSize={labelFontSize} fill="#374151" fontWeight="500"
              >
                {p.label}
              </text>
            );
          })()}
          {/* Score */}
          <text
            x={p.x} y={p.y - 12}
            textAnchor="middle" dominantBaseline="middle"
            fontSize={labelFontSize - 1} fill={p.color} fontWeight="bold"
          >
            {Math.round(p.score)}
          </text>
        </g>
      ))}
      {/* Center overall score — ScoreRing (donut chart) */}
      {centerScore != null && (() => {
        const clamped = Math.max(0, Math.min(100, centerScore));
        const ringR = 24;
        const sw = 5;
        const circ = 2 * Math.PI * ringR;
        const progress = clamped / 100;
        const offset = circ * (1 - progress);
        let ringColor;
        if (clamped >= 80) ringColor = '#5a6b4e';
        else if (clamped >= 60) ringColor = '#5a6e82';
        else if (clamped >= 40) ringColor = '#b8943a';
        else ringColor = '#a85555';
        return (
          <g>
            {/* Background track */}
            <circle cx={center} cy={center} r={ringR} fill="#fff" stroke="#e5e7eb" strokeWidth={sw} />
            {/* Progress arc */}
            <circle
              cx={center} cy={center} r={ringR}
              fill="none" stroke={ringColor} strokeWidth={sw}
              strokeLinecap="round"
              strokeDasharray={circ}
              strokeDashoffset={offset}
              transform={`rotate(-90 ${center} ${center})`}
              style={{ transition: 'stroke-dashoffset 0.8s ease-out' }}
            />
            {/* Score number */}
            <text
              x={center} y={center - 3}
              textAnchor="middle" dominantBaseline="middle"
              fontSize="16" fontWeight="bold" fill="#1f2937"
            >
              {Math.round(clamped)}
            </text>
            <text
              x={center} y={center + 12}
              textAnchor="middle" dominantBaseline="middle"
              fontSize="9" fill="#6b7280"
            >
              綜合
            </text>
          </g>
        );
      })()}
    </svg>
  );
}
