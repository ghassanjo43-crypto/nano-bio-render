/**
 * Nanoparticle Design — guided formulation workflow.
 *
 * Replaces the earlier single long form with a five-step workflow. The API call
 * and its numerical behaviour are unchanged: the same endpoint receives the same
 * field names, blank optional fields are still omitted so the scientific engine
 * applies its own documented defaults, and no result is ever fabricated.
 *
 * Inputs persist across step navigation; nothing is cleared until the user
 * explicitly resets.
 */

import { useCallback, useMemo, useState } from 'react';
import { scoreDesign } from '../../api/client';
import type { ScoreResult } from '../../api/types';
import {
  Alert, Badge, Button, Card, ChipGroup, EmptyState, InfoHint,
  SelectField, SkeletonBlock, TextField,
} from '../../design-system/components';
import { Icon } from '../../shell/Icon';
import { ResultPanel } from './ResultPanel';
import {
  FIELDS, INITIAL_CHIPS, INITIAL_VALUES, LIGAND_OPTIONS, STEPS,
  buildRequest, fieldsForStep, reviewRows, validateAll, validateStep,
  type ChipValues, type FieldDef, type FormValues, type StepId,
} from './schema';
import './DesignPage.css';

export default function DesignPage() {
  const [values, setValues] = useState<FormValues>(INITIAL_VALUES);
  const [chips, setChips] = useState<ChipValues>(INITIAL_CHIPS);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [stepIndex, setStepIndex] = useState(0);
  const [visited, setVisited] = useState<Set<StepId>>(new Set(['core']));
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ScoreResult | null>(null);

  const step = STEPS[stepIndex]!;
  const isReview = step.id === 'review';

  const setValue = useCallback((name: string, v: string) => {
    setValues((prev) => ({ ...prev, [name]: v }));
    setErrors((prev) => {
      if (!prev[name]) return prev;
      const next = { ...prev };
      delete next[name];
      return next;
    });
  }, []);

  const goTo = useCallback((index: number) => {
    const target = STEPS[index];
    if (!target) return;
    setStepIndex(index);
    setVisited((prev) => new Set(prev).add(target.id));
  }, []);

  const handleNext = () => {
    const stepErrors = validateStep(step.id, values);
    setErrors(stepErrors);
    if (Object.keys(stepErrors).length > 0) return;
    goTo(Math.min(stepIndex + 1, STEPS.length - 1));
  };

  const handleBack = () => goTo(Math.max(stepIndex - 1, 0));

  const handleCalculate = async () => {
    const allErrors = validateAll(values);
    setErrors(allErrors);
    if (Object.keys(allErrors).length > 0) {
      // Jump to the first step that has a problem.
      const firstBad = FIELDS.find((f) => allErrors[f.name as string]);
      if (firstBad) {
        const idx = STEPS.findIndex((s) => s.id === firstBad.step);
        if (idx >= 0) goTo(idx);
      }
      return;
    }
    setLoading(true);
    setResult(null);
    try {
      setResult(await scoreDesign(buildRequest(values, chips)));
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setValues(INITIAL_VALUES);
    setChips(INITIAL_CHIPS);
    setErrors({});
    setResult(null);
    goTo(0);
  };

  const rows = useMemo(() => reviewRows(values, chips), [values, chips]);
  const suppliedCount = rows.filter((r) => r.supplied).length;

  return (
    <div className="design">
      <Alert tone="warn" title="Computational research use only" role="note">
        Results are produced by rule-based models and are{' '}
        <strong>not experimentally validated</strong>, not clinically validated,
        and not a regulatory approval prediction, diagnosis, or treatment
        recommendation.
      </Alert>

      <div className="design__layout">
        {/* ------------------------------------------------ workflow */}
        <div className="design__workflow">
          <Card
            flush
            title="Formulation workflow"
            subtitle="Inputs are preserved as you move between steps."
            actions={
              <Button variant="ghost" size="sm" onClick={handleReset}
                      iconLeft={<Icon name="refresh" size={15} />}>
                Reset
              </Button>
            }
          >
            <ol className="design__steps" aria-label="Workflow steps">
              {STEPS.map((s, i) => {
                const state = i === stepIndex ? 'current'
                  : visited.has(s.id) ? 'done' : 'todo';
                return (
                  <li key={s.id}>
                    <button
                      type="button"
                      className={`design__step design__step--${state}`}
                      onClick={() => goTo(i)}
                      aria-current={i === stepIndex ? 'step' : undefined}
                    >
                      <span className="design__step-n" aria-hidden="true">
                        {state === 'done' && i !== stepIndex ? <Icon name="check" size={13} /> : i + 1}
                      </span>
                      <span className="design__step-label">
                        <span className="design__step-title">{s.title}</span>
                        <span className="design__step-short">{s.short}</span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ol>
          </Card>

          <Card
            title={step.title}
            subtitle={step.description}
            className="design__panel"
          >
            {isReview ? (
              <ReviewStep rows={rows} suppliedCount={suppliedCount} />
            ) : (
              <div className="design__fields">
                {fieldsForStep(step.id).map((def) => (
                  <FieldRenderer
                    key={def.name as string}
                    def={def}
                    values={values}
                    chips={chips}
                    error={errors[def.name as string]}
                    onValue={setValue}
                    onChips={(name, next) => setChips((p) => ({ ...p, [name]: next }))}
                  />
                ))}
              </div>
            )}

            <div className="design__nav">
              <Button
                variant="secondary"
                onClick={handleBack}
                disabled={stepIndex === 0}
                iconLeft={<Icon name="chevron-left" size={15} />}
              >
                Back
              </Button>

              {isReview ? (
                <Button
                  onClick={handleCalculate}
                  loading={loading}
                  size="lg"
                  iconRight={!loading ? <Icon name="arrow-right" size={16} /> : undefined}
                >
                  {loading ? 'Calculating…' : 'Calculate Score'}
                </Button>
              ) : (
                <Button onClick={handleNext} iconRight={<Icon name="chevron-right" size={15} />}>
                  Continue
                </Button>
              )}
            </div>
          </Card>
        </div>

        {/* -------------------------------------------------- results */}
        <div className="design__results">
          <Card
            title="Result"
            subtitle={
              result?.status === 'ok'
                ? 'Calculated by the canonical scientific engine.'
                : 'No values are shown until the engine returns a real result.'
            }
            accent={result?.status === 'ok'}
          >
            {loading && (
              <div data-testid="loading-state" className="design__loading">
                <SkeletonBlock lines={2} />
                <div className="design__loading-gauges">
                  {[0, 1, 2].map((i) => (
                    <div className="design__loading-gauge" key={i}>
                      <span className="ds-skeleton" style={{ width: 96, height: 96, borderRadius: '50%' }} />
                    </div>
                  ))}
                </div>
                <SkeletonBlock lines={3} />
                <p className="design__loading-note" role="status">
                  Calculating on the scientific engine…
                </p>
              </div>
            )}

            {!loading && result === null && (
              <EmptyState
                testId="empty-state"
                icon={<Icon name="hexagon" size={22} />}
                title="No result yet"
              >
                Complete the workflow and select <strong>Calculate Score</strong>.
                Nothing is displayed until the scientific engine returns a real
                result — no placeholder or example values are shown.
              </EmptyState>
            )}

            {!loading && result?.status === 'error' && (
              <div data-testid="error-state">
                <Alert tone="danger" title="Score unavailable">
                  <p>{result.error.message}</p>
                  {result.error.detail && (
                    <p className="design__err-detail mono">{result.error.detail}</p>
                  )}
                  <p className="design__err-code">
                    <Badge tone="danger">{result.error.error}</Badge>
                  </p>
                  <p>
                    No score is shown, because none was produced. A failed
                    calculation never falls back to a default value.
                  </p>
                </Alert>
                <div className="design__err-actions">
                  <Button variant="secondary" onClick={() => goTo(0)}
                          iconLeft={<Icon name="edit" size={15} />}>
                    Edit the design
                  </Button>
                  <Button onClick={handleCalculate} iconLeft={<Icon name="refresh" size={15} />}>
                    Try again
                  </Button>
                </div>
              </div>
            )}

            {!loading && result?.status === 'ok' && (
              <ResultPanel
                data={result.data}
                onEdit={() => goTo(0)}
                onRecalculate={handleCalculate}
              />
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- fields */

function FieldRenderer({
  def, values, chips, error, onValue, onChips,
}: {
  def: FieldDef;
  values: FormValues;
  chips: ChipValues;
  error?: string;
  onValue: (name: string, v: string) => void;
  onChips: (name: string, next: string[]) => void;
}) {
  const name = def.name as string;

  if (def.kind === 'chips') {
    return (
      <div className="design__field design__field--wide">
        <ChipGroup
          id={name}
          label={def.label}
          options={def.options}
          value={chips[name] ?? []}
          onChange={(next) => onChips(name, next)}
          hint={<InfoHint label={def.label}>{def.definition}</InfoHint>}
          help={
            (chips[name] ?? []).length === 0
              ? `Not selected — the engine will use its default: ${def.defaultNote}.`
              : undefined
          }
        />
      </div>
    );
  }

  if (def.kind === 'text' && name === 'ligand') {
    return (
      <div className="design__field">
        <SelectField
          id={name}
          label={def.label}
          value={values[name] ?? ''}
          onChange={(e) => onValue(name, e.target.value)}
          options={LIGAND_OPTIONS.map((o) => ({ value: o.value, label: o.label }))}
          error={error}
          hint={<InfoHint label={def.label}>{def.definition}</InfoHint>}
          help={
            !(values[name] ?? '').trim()
              ? 'Passive targeting. The engine applies a fixed 60/100 baseline for the targeting component.'
              : undefined
          }
        />
      </div>
    );
  }

  const range = def.kind === 'number'
    ? [def.min !== undefined ? `min ${def.min}` : null,
       def.max !== undefined ? `max ${def.max}` : null].filter(Boolean).join(' · ')
    : '';

  return (
    <div className="design__field">
      <TextField
        id={name}
        label={def.label}
        unit={def.unit}
        type="text"
        inputMode="decimal"
        required={def.required}
        value={values[name] ?? ''}
        onChange={(e) => onValue(name, e.target.value)}
        error={error}
        placeholder={def.required ? undefined : `default ${def.defaultNote ?? '—'}`}
        hint={<InfoHint label={def.label}>{def.definition}</InfoHint>}
        help={range || undefined}
      />
    </div>
  );
}

/* ---------------------------------------------------------------- review */

function ReviewStep({
  rows, suppliedCount,
}: { rows: ReturnType<typeof reviewRows>; suppliedCount: number }) {
  return (
    <div className="design__review" data-testid="review-step">
      <p className="design__review-lead">
        <strong>{suppliedCount}</strong> of {rows.length} parameters supplied.
        The remainder will use the scientific engine's own documented defaults —
        the interface does not invent values.
      </p>

      <div className="design__review-groups">
        {STEPS.filter((s) => s.id !== 'review').map((s) => {
          const group = rows.filter((r) => r.step === s.id);
          return (
            <div className="design__review-group" key={s.id}>
              <p className="eyebrow">{s.title}</p>
              <dl className="design__review-list">
                {group.map((r) => (
                  <div key={r.key} className={r.supplied ? 'is-set' : 'is-default'}>
                    <dt>
                      {r.label}
                      {r.unit && <span className="design__review-unit"> ({r.unit})</span>}
                    </dt>
                    <dd>
                      {r.value}
                      {!r.supplied && <span className="design__review-tag">default</span>}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>
          );
        })}
      </div>
    </div>
  );
}
