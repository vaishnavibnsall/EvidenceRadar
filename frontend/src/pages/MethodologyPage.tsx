import { useMemo } from "react";
import { Database, ExternalLink, TriangleAlert } from "lucide-react";
import { api } from "../api/client";
import { useAsync } from "../hooks/useAsync";
import { PageHeader } from "../components/PageHeader";
import { ErrorState, Loader } from "../components/States";
import { pct } from "../utils/format";
import "./MethodologyPage.css";

const WEIGHT_LABELS: Record<string, string> = {
  base: "Base disproportionality (PRR / ROR)",
  bayes: "Bayesian strength (EBGM / EB05)",
  volume: "Case volume",
  trend: "Temporal trend",
  support: "Cross-source support (trials & reviews)",
};

const WEIGHT_COLORS = ["#22d3ee", "#2dd4bf", "#38bdf8", "#818cf8", "#a78bfa", "#f59e0b"];

function weightLabel(key: string): string {
  return WEIGHT_LABELS[key] ?? key.charAt(0).toUpperCase() + key.slice(1);
}

export function MethodologyPage() {
  const { data, loading, error, reload } = useAsync(() => api.methodology(), []);

  const weights = useMemo(() => {
    const entries = Object.entries(data?.scoring.weights ?? {});
    const total = entries.reduce((sum, [, value]) => sum + value, 0);
    return entries.map(([key, value], index) => ({
      key,
      label: weightLabel(key),
      value,
      share: total > 0 ? value / total : 0,
      color: WEIGHT_COLORS[index % WEIGHT_COLORS.length],
    }));
  }, [data]);

  return (
    <div className="page">
      <PageHeader
        title="Methodology"
        subtitle="How EvidenceRadar turns raw pharmacovigilance data into ranked, explainable signals."
      />

      <section className="panel">
        <div className="panel__body">
          <p className="methodology__intro">
            EvidenceRadar fuses three real-world evidence sources — FAERS adverse-event reports,
            ClinicalTrials.gov studies and aggregated patient reviews — to surface drug–reaction
            combinations that deserve attention. For every pair we compute classical
            disproportionality measures (PRR, ROR, chi²) alongside Bayesian shrinkage metrics
            (IC, EBGM, EB05), then fold them into a single 0–100 evidence score together with case
            volume, temporal trend and cross-source support. Known, label-listed reactions are
            penalised so that genuinely novel safety signals rise to the top of the radar.
          </p>
        </div>
      </section>

      {loading ? <Loader label="Loading methodology…" /> : null}

      {error ? (
        <section className="panel">
          <ErrorState title="Could not load methodology" message={error.message} onRetry={reload} />
        </section>
      ) : null}

      {data ? (
        <>
          <section>
            <div className="section-head">
              <div className="section-head__title">Disproportionality measures</div>
              <div className="section-head__subtitle">
                Statistical metrics computed for every drug–reaction pair
              </div>
            </div>
            <div className="measure-grid">
              {data.disproportionality.map((measure) => (
                <article key={measure.title} className="measure-card">
                  <div className="measure-card__title">{measure.title}</div>
                  <pre className="code-block">
                    <code>{measure.formula}</code>
                  </pre>
                  <p className="measure-card__desc">{measure.description}</p>
                </article>
              ))}
            </div>
          </section>

          <section className="panel">
            <div className="panel__head">
              <div>
                <div className="panel__title">Evidence score composition</div>
                <div className="panel__subtitle">
                  Weighted blend of five components, normalised to 100%
                </div>
              </div>
            </div>
            <div className="panel__body">
              <div className="weights">
                <div className="weights__bar" role="img" aria-label="Scoring weights breakdown">
                  {weights.map((weight) => (
                    <div
                      key={weight.key}
                      className="weights__segment"
                      style={{ width: `${weight.share * 100}%`, background: weight.color }}
                      title={`${weight.label}: ${pct(weight.share, 1)}`}
                    >
                      {weight.share >= 0.12 ? pct(weight.share, 0) : ""}
                    </div>
                  ))}
                </div>

                <div className="weights__legend">
                  {weights.map((weight) => (
                    <div key={weight.key} className="weights__legend-item">
                      <span className="weights__swatch" style={{ background: weight.color }} />
                      <span>
                        {weight.label} — <strong>{pct(weight.share, 1)}</strong>
                      </span>
                    </div>
                  ))}
                </div>

                <div className="weights__penalty">
                  <TriangleAlert size={16} aria-hidden />
                  Label penalty: reactions already listed in the FDA label are multiplied by{" "}
                  <strong>{data.scoring.label_penalty}</strong> to deprioritise on-label effects.
                </div>

                {data.scoring.formula ? (
                  <pre className="code-block">
                    <code>{data.scoring.formula}</code>
                  </pre>
                ) : null}
              </div>
            </div>
          </section>

          <section>
            <div className="section-head">
              <div className="section-head__title">Data sources</div>
              <div className="section-head__subtitle">
                Everything on the dashboard traces back to these
              </div>
            </div>
            <div className="source-grid">
              {data.sources.map((source) => (
                <article key={source.name} className="source-card">
                  <div className="source-card__name">
                    <Database size={15} aria-hidden /> {source.name}
                  </div>
                  {source.records ? (
                    <div className="source-card__records">{source.records}</div>
                  ) : null}
                  <p className="source-card__desc">{source.description}</p>
                  {source.url ? (
                    <a
                      className="source-card__link"
                      href={source.url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Visit source <ExternalLink size={12} aria-hidden />
                    </a>
                  ) : null}
                </article>
              ))}
            </div>
          </section>

          <section className="panel">
            <div className="panel__head">
              <div>
                <div className="panel__title">Limitations &amp; caveats</div>
                <div className="panel__subtitle">
                  Signals are hypothesis-generating, not causal conclusions
                </div>
              </div>
            </div>
            <div className="panel__body">
              <ul className="limitations">
                {data.limitations.map((limitation, index) => (
                  <li key={index} className="limitations__item">
                    <TriangleAlert size={16} aria-hidden />
                    <span>{limitation}</span>
                  </li>
                ))}
              </ul>
              <p className="methodology__note">
                Disproportionality in spontaneous reporting databases is susceptible to masking,
                duplication, notoriety bias and reporting artefacts. Always confirm a signal against
                the primary label, literature and clinical context before drawing conclusions.
              </p>
            </div>
          </section>
        </>
      ) : null}
    </div>
  );
}
