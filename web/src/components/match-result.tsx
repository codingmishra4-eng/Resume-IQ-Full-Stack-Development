import type { MatchResult } from "@/lib/features";
import { Badge } from "./ui";
export function MatchView({ result }: { result: MatchResult }) {
  return (
    <div className="feature-result">
      <h3>{result.match_score.toFixed(1)}% estimated alignment</h3>
      <div
        className="match-meter"
        role="meter"
        aria-label="Estimated skill alignment"
        aria-valuenow={result.match_score}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <span style={{ width: `${result.match_score}%` }} />
      </div>
      <p>{result.explanation}</p>
      {(
        [
          ["Matching skills", result.matching],
          ["Related skills (partial credit)", result.partial],
          ["Missing skills", result.missing],
          ["Matching keywords", result.keyword_matching],
          ["Job keywords", result.jd_extra_keywords],
        ] as const
      ).map(([label, items]) => (
        <div key={label}>
          <h4>{label}</h4>
          <div className="chips">
            {items.length ? (
              items.map((item) => <Badge key={item}>{item}</Badge>)
            ) : (
              <span className="muted">None detected</span>
            )}
          </div>
        </div>
      ))}
      {result.notes.map((note, index) => (
        <p key={index}>{note}</p>
      ))}
      {result.missing.length > 0 && (
        <p>
          Prioritize genuine skill gaps. Add a skill to your resume only when
          you can support it with actual experience.
        </p>
      )}
    </div>
  );
}
