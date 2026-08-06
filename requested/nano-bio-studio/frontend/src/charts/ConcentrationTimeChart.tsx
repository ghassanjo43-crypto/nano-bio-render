/**
 * Concentration–time chart.
 *
 * Hard rule, inherited from `ScoreVisuals.tsx`: this component renders **only
 * the arrays handed to it from a real API response**. It contains no sample
 * series, no default geometry, no smoothing, no interpolation and no
 * extrapolation. Every plotted point corresponds to one point the engine
 * returned; the axis extents are read from the data rather than rounded to
 * pleasing numbers.
 *
 * If a caller has nothing to plot, it must not render this component — there is
 * no "empty chart" state, because an empty chart reads as a real result of
 * zero.
 *
 * Accessibility: the plot carries `role="img"` with a text description, and the
 * caller is expected to render the exact numeric values alongside it. The chart
 * is never the only way to read the numbers.
 */

import './ConcentrationTimeChart.css';

export interface SeriesSpec {
  key: string;
  label: string;
  /** Values, parallel to `time`. Must be the same length. */
  values: readonly number[];
}

export interface ConcentrationTimeChartProps {
  time: readonly number[];
  series: readonly SeriesSpec[];
  timeUnit: string;
  concentrationUnit: string;
  /** Optional markers for peak points, drawn from returned parameters only. */
  markers?: ReadonlyArray<{ key: string; label: string; t: number; value: number }>;
}

const W = 640;
const H = 300;
const PAD = { top: 16, right: 18, bottom: 44, left: 62 };

/** Axis ticks at the data's own extents — no rounding to "nice" numbers. */
function ticks(min: number, max: number, count: number): number[] {
  if (!(max > min)) return [min];
  const out: number[] = [];
  for (let i = 0; i <= count; i += 1) out.push(min + ((max - min) * i) / count);
  return out;
}

function format(value: number): string {
  if (value === 0) return '0';
  const abs = Math.abs(value);
  if (abs >= 1000 || abs < 0.001) return value.toExponential(2);
  if (abs >= 100) return value.toFixed(1);
  if (abs >= 1) return value.toFixed(2);
  return value.toFixed(3);
}

export function ConcentrationTimeChart({
  time, series, timeUnit, concentrationUnit, markers = [],
}: ConcentrationTimeChartProps) {
  // Defensive, not cosmetic: a caller must never reach here without data, and
  // rendering an axis with no curve would misrepresent an absent result.
  if (time.length === 0 || series.length === 0) return null;
  if (series.some((s) => s.values.length !== time.length)) return null;

  // Copy into dense arrays once, so every later read is a plain number. Every
  // element still corresponds one-to-one with a point the engine returned.
  const t: number[] = Array.from(time);
  const curves = series.map((s) => ({ ...s, points: Array.from(s.values) }));

  const tMin = t[0] as number;
  const tMax = t[t.length - 1] as number;
  const allValues = curves.flatMap((c) => c.points);
  const vMin = Math.min(0, ...allValues);
  const vMax = Math.max(...allValues);

  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;
  const tSpan = tMax - tMin || 1;
  const vSpan = vMax - vMin || 1;

  const x = (value: number) => PAD.left + ((value - tMin) / tSpan) * plotW;
  const y = (v: number) => PAD.top + plotH - ((v - vMin) / vSpan) * plotH;

  const path = (points: readonly number[]) =>
    points
      .map((v, i) =>
        `${i === 0 ? 'M' : 'L'} ${x(t[i] as number).toFixed(2)} ${y(v).toFixed(2)}`)
      .join(' ');

  const xTicks = ticks(tMin, tMax, 6);
  const yTicks = ticks(vMin, vMax, 4);

  const description = curves
    .map((c) => {
      const peak = Math.max(...c.points);
      const peakAt = t[c.points.indexOf(peak)] as number;
      return `${c.label} peaks at ${format(peak)} ${concentrationUnit} at `
        + `${format(peakAt)} ${timeUnit}`;
    })
    .join('; ');

  return (
    <figure className="ct-chart" data-testid="concentration-time-chart">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={
          `Concentration–time profile over ${format(tMin)} to ${format(tMax)} `
          + `${timeUnit}, calculated by the pharmacokinetic engine. ${description}. `
          + 'Exact values are listed in the accompanying tables.'
        }
      >
        {/* gridlines and value axis */}
        {yTicks.map((v) => (
          <g key={`y${v}`}>
            <line
              className="ct-chart__grid"
              x1={PAD.left} x2={W - PAD.right}
              y1={y(v)} y2={y(v)}
            />
            <text className="ct-chart__tick" x={PAD.left - 8} y={y(v)}
                  textAnchor="end" dominantBaseline="middle">
              {format(v)}
            </text>
          </g>
        ))}

        {/* time axis */}
        {xTicks.map((tick) => (
          <text key={`x${tick}`} className="ct-chart__tick" x={x(tick)}
                y={H - PAD.bottom + 18} textAnchor="middle">
            {format(tick)}
          </text>
        ))}

        <line className="ct-chart__axis" x1={PAD.left} x2={W - PAD.right}
              y1={y(vMin)} y2={y(vMin)} />
        <line className="ct-chart__axis" x1={PAD.left} x2={PAD.left}
              y1={PAD.top} y2={PAD.top + plotH} />

        {curves.map((c, i) => (
          <path
            key={c.key}
            className={`ct-chart__line ct-chart__line--${i % 2 === 0 ? 'a' : 'b'}`}
            d={path(c.points)}
            fill="none"
          />
        ))}

        {markers.map((m, i) => (
          <circle
            key={m.key}
            className={`ct-chart__marker ct-chart__marker--${i % 2 === 0 ? 'a' : 'b'}`}
            cx={x(m.t)} cy={y(m.value)} r={4}
          />
        ))}

        <text className="ct-chart__axislabel" x={PAD.left + plotW / 2}
              y={H - 6} textAnchor="middle">
          Time ({timeUnit})
        </text>
        <text className="ct-chart__axislabel" x={14}
              y={PAD.top + plotH / 2} textAnchor="middle"
              transform={`rotate(-90 14 ${PAD.top + plotH / 2})`}>
          Amount ({concentrationUnit})
        </text>
      </svg>

      <ul className="ct-chart__legend">
        {curves.map((c, i) => (
          <li key={c.key}>
            <span className={`ct-chart__swatch ct-chart__swatch--${i % 2 === 0 ? 'a' : 'b'}`}
                  aria-hidden="true" />
            {c.label}
          </li>
        ))}
        {markers.length > 0 && (
          <li>
            <span className="ct-chart__swatch ct-chart__swatch--marker" aria-hidden="true" />
            Peak, from the returned parameters
          </li>
        )}
      </ul>

      <figcaption className="ct-chart__caption">
        Plotted directly from the {t.length} calculated points returned by the
        engine. No smoothing, resampling or extrapolation is applied, and the
        axes span the data’s own range. Values are in {concentrationUnit}.
      </figcaption>
    </figure>
  );
}
