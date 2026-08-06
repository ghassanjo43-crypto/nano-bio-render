/**
 * Scientific data visualisations.
 *
 * Hard rule: these components render **only values passed in from a real API
 * response**. They contain no sample data, no default series and no placeholder
 * geometry. If a caller has nothing to show, it must not render a chart.
 *
 * Accessibility: every visual carries `role="img"` with a full text description,
 * and the numeric value is also rendered as visible text — the chart is never
 * the only way to read the number.
 */

import './ScoreVisuals.css';

export type ScoreTone = 'good' | 'moderate' | 'poor';

/* ------------------------------------------------------------------ gauge */

export interface GaugeProps {
  label: string;
  value: number;
  /** Inclusive display range, e.g. [0, 100] or [0, 10]. */
  min: number;
  max: number;
  /** Text such as "higher is better". Rendered visibly. */
  direction: string;
  tone: ScoreTone;
  decimals?: number;
}

/**
 * Radial gauge. The arc length encodes the value's position within [min, max];
 * the numeral is the authoritative reading.
 */
export function ScoreGauge({
  label, value, min, max, direction, tone, decimals = 2,
}: GaugeProps) {
  const span = max - min || 1;
  const frac = Math.min(1, Math.max(0, (value - min) / span));

  // 240° sweep starting at 150°, drawn as an SVG arc.
  const R = 46;
  const CX = 56;
  const CY = 56;
  const START = 150;
  const SWEEP = 240;

  const polar = (deg: number) => {
    const rad = (deg * Math.PI) / 180;
    return { x: CX + R * Math.cos(rad), y: CY + R * Math.sin(rad) };
  };
  const arc = (fromDeg: number, toDeg: number) => {
    const a = polar(fromDeg);
    const b = polar(toDeg);
    const large = Math.abs(toDeg - fromDeg) > 180 ? 1 : 0;
    return `M ${a.x.toFixed(2)} ${a.y.toFixed(2)} A ${R} ${R} 0 ${large} 1 ${b.x.toFixed(2)} ${b.y.toFixed(2)}`;
  };

  const trackPath = arc(START, START + SWEEP);
  const valuePath = arc(START, START + SWEEP * Math.max(frac, 0.001));

  return (
    <div className={`sv-gauge sv-gauge--${tone}`}>
      <div className="sv-gauge__chart">
        <svg
          viewBox="0 0 112 100"
          role="img"
          aria-label={`${label}: ${value.toFixed(decimals)} on a scale of ${min} to ${max}, ${direction}`}
        >
          <path d={trackPath} className="sv-gauge__track" fill="none" strokeLinecap="round" />
          <path d={valuePath} className="sv-gauge__value" fill="none" strokeLinecap="round" />
        </svg>
        <div className="sv-gauge__readout">
          <span className="sv-gauge__number">{value.toFixed(decimals)}</span>
          <span className="sv-gauge__range">of {max}</span>
        </div>
      </div>
      <p className="sv-gauge__label">{label}</p>
      <p className="sv-gauge__direction">{direction}</p>
    </div>
  );
}

/* ------------------------------------------------------------------- bars */

export interface BarDatum {
  key: string;
  label: string;
  value: number;
  min: number;
  max: number;
  tone: ScoreTone;
  /** Text shown to the right of the bar, e.g. "0–100 · higher is better". */
  scale: string;
}

/**
 * Horizontal comparison bars. Each row states its own scale because the
 * components are NOT on a common axis (Delivery 0–100, Toxicity 0–10, Cost
 * 0–100) — drawing them on one shared axis would misrepresent the data.
 */
export function ComponentBars({ data, caption }: { data: readonly BarDatum[]; caption: string }) {
  return (
    <div className="sv-bars" role="img" aria-label={
      `${caption}. ${data.map((d) => `${d.label} ${d.value.toFixed(2)} out of ${d.max}`).join('; ')}.`
    }>
      {data.map((d) => {
        const pct = Math.min(100, Math.max(0, ((d.value - d.min) / (d.max - d.min || 1)) * 100));
        return (
          <div className="sv-bar" key={d.key}>
            <div className="sv-bar__head">
              <span className="sv-bar__label">{d.label}</span>
              <span className="sv-bar__value">{d.value.toFixed(2)}</span>
            </div>
            <div className="sv-bar__track">
              <div
                className={`sv-bar__fill sv-bar__fill--${d.tone}`}
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="sv-bar__scale">{d.scale}</span>
          </div>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------------ radar */

export interface RadarAxis {
  key: string;
  label: string;
  /** Already normalised to 0–1 by the caller, which must document how. */
  normalised: number;
  /** Raw display value and its scale, for the text alternative. */
  display: string;
}

/**
 * Radar/triangle plot of normalised component scores.
 *
 * Normalisation is the caller's responsibility and is stated in the caption —
 * the three components have different native scales and directions, so the plot
 * shows "position within each component's own favourable range", not raw values.
 */
export function ComponentRadar({
  axes, caption,
}: { axes: readonly RadarAxis[]; caption: string }) {
  if (axes.length < 3) return null;

  const CX = 110;
  const CY = 104;
  const R = 74;
  const n = axes.length;

  const point = (i: number, r: number) => {
    const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
    return [CX + r * Math.cos(angle), CY + r * Math.sin(angle)] as const;
  };

  const rings = [0.25, 0.5, 0.75, 1];
  const polygon = (r: number) =>
    axes.map((_, i) => point(i, r).map((v) => v.toFixed(1)).join(',')).join(' ');

  const valuePoly = axes
    .map((a, i) => point(i, R * Math.max(0.04, Math.min(1, a.normalised)))
      .map((v) => v.toFixed(1)).join(','))
    .join(' ');

  return (
    <figure className="sv-radar">
      <svg
        viewBox="0 0 220 208"
        role="img"
        aria-label={`${caption} ${axes.map((a) => `${a.label}: ${a.display}`).join('; ')}.`}
      >
        {rings.map((r) => (
          <polygon key={r} points={polygon(R * r)} className="sv-radar__ring" />
        ))}
        {axes.map((_, i) => {
          const [x, y] = point(i, R);
          return <line key={i} x1={CX} y1={CY} x2={x} y2={y} className="sv-radar__spoke" />;
        })}
        <polygon points={valuePoly} className="sv-radar__area" />
        {axes.map((a, i) => {
          const [x, y] = point(i, R * Math.max(0.04, Math.min(1, a.normalised)));
          return <circle key={a.key} cx={x} cy={y} r={3.5} className="sv-radar__dot" />;
        })}
        {axes.map((a, i) => {
          const [x, y] = point(i, R + 22);
          return (
            <text
              key={a.key}
              x={x}
              y={y}
              className="sv-radar__label"
              textAnchor={x > CX + 5 ? 'start' : x < CX - 5 ? 'end' : 'middle'}
              dominantBaseline="middle"
            >
              {a.label}
            </text>
          );
        })}
      </svg>
      <figcaption className="sv-radar__caption">{caption}</figcaption>
    </figure>
  );
}
