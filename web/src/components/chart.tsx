import type { Analysis } from "@/lib/api";
import { date } from "@/lib/format";
export function ScoreChart({ analyses }: { analyses: Analysis[] }) {
  const values = analyses
    .filter(
      (item): item is Analysis & { ats_score: number } =>
        item.ats_score !== null,
    )
    .slice(0, 8)
    .reverse();
  const points = values.map((item, index) => ({
    x: values.length === 1 ? 290 : 45 + (index * 505) / (values.length - 1),
    y: 174 - item.ats_score * 1.4,
    ...item,
  }));
  const line = points.map((point) => `${point.x},${point.y}`).join(" ");
  return (
    <figure className="chart">
      <svg
        role="img"
        aria-label="Saved estimated ATS scores, from 0 to 100"
        viewBox="0 0 590 215"
      >
        <title>Saved estimated ATS scores</title>
        <defs>
          <linearGradient id="score-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#c5f597" stopOpacity=".22" />
            <stop offset="100%" stopColor="#c5f597" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[0, 25, 50, 75, 100].map((value) => (
          <g key={value}>
            <line
              x1="40"
              x2="560"
              y1={174 - value * 1.4}
              y2={174 - value * 1.4}
              stroke="#ffffff0c"
              strokeDasharray="4 5"
            />
            <text x="10" y={178 - value * 1.4} fill="#979ba9" fontSize="10">
              {value}
            </text>
          </g>
        ))}
        {points.length > 1 && (
          <>
            <polygon
              points={`45,174 ${line} 550,174`}
              fill="url(#score-fill)"
            />
            <polyline
              points={line}
              fill="none"
              stroke="#c5f597"
              strokeWidth="2.5"
              strokeLinejoin="round"
            />
          </>
        )}
        {points.map((point) => (
          <g key={point.id}>
            <circle
              cx={point.x}
              cy={point.y}
              r="5"
              fill="#c5f597"
              stroke="#14171c"
              strokeWidth="3"
            />
            <text
              x={point.x}
              y="201"
              textAnchor="middle"
              fill="#979ba9"
              fontSize="10"
            >
              {date(point.created_at, { year: undefined })}
            </text>
            <title>
              {date(point.created_at)}: {point.ats_score.toFixed(1)}
            </title>
          </g>
        ))}
      </svg>
      <figcaption>
        Historical heuristic estimates, not certified ATS scores.
      </figcaption>
      <table className="sr-only">
        <caption>Saved analysis scores</caption>
        <thead>
          <tr>
            <th>Date</th>
            <th>Estimated score</th>
          </tr>
        </thead>
        <tbody>
          {values.map((item) => (
            <tr key={item.id}>
              <td>{date(item.created_at)}</td>
              <td>{item.ats_score}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}
