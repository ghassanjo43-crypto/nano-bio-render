/**
 * Step 2 — Nanoparticle Design Parameters.
 *
 * Mirrors the legacy `pages/1_Design_Parameters.py`. Fields are grouped into
 * four sections (core, surface, targeting, stability) driven by the same
 * declarative schema that builds the API payload, so rendering, validation and
 * the request can never diverge.
 *
 * Values live in the workflow session, so they survive navigation in both
 * directions and across a draft save/resume.
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Card, ChipGroup, InfoHint, SelectField, TextField, Tabs }
  from '../../design-system/components';
import { Icon } from '../../shell/Icon';
import { useWorkflow } from '../../workflow/WorkflowContext';
import {
  LIGAND_OPTIONS, STEPS as FIELD_SECTIONS, fieldsForStep, validateAll,
  type FieldDef, type StepId,
} from '../design/schema';
import { StepActions, StepBadge } from './WorkflowLayout';
import PathwayNav, { PathwayProgress } from '../../workflow/PathwayNav';
import PathwayBanner from '../../workflow/PathwayBanner';
import './Step2Design.css';

const SECTIONS = FIELD_SECTIONS.filter((s) => s.id !== 'review');

export default function Step2Design() {
  const navigate = useNavigate();
  const { session, setValue, setChips, step2Complete, reachStep, saveDraft } = useWorkflow();
  const [section, setSection] = useState<StepId>('core');
  const [errors, setErrors] = useState<Record<string, string>>({});

  /**
   * Validate the whole form before the pathway advances.
   *
   * Returning false keeps the user here and opens the first section that has a
   * problem, so Continue cannot carry an invalid formulation forward.
   */
  const handleBeforeContinue = () => {
    const found = validateAll(session.values);
    setErrors(found);
    if (Object.keys(found).length > 0) {
      const firstBad = SECTIONS.find((s) =>
        fieldsForStep(s.id).some((f) => found[f.name as string]));
      if (firstBad) setSection(firstBad.id);
      return false;
    }
    reachStep(3);
    return true;
  };

  const active = SECTIONS.find((s) => s.id === section) ?? SECTIONS[0]!;
  const errorCountFor = (id: StepId) =>
    fieldsForStep(id).filter((f) => errors[f.name as string]).length;

  return (
    <>
    <PathwayBanner />
    <PathwayProgress />
    <Card
      title="Step 2 — Nanoparticle Design Parameters"
      subtitle="Define the formulation. Only size, charge and encapsulation are required; every other field falls back to the scientific engine's documented default."
      actions={
        <div className="s2__headactions">
          {/* The builder visualises the formulation being edited here, so it
              is reachable from the design step as well as from review. */}
          <Button variant="secondary" size="sm"
                  onClick={() => navigate('/builder')}
                  iconLeft={<Icon name="atom" size={15} />}
                  data-testid="view-in-3d-step2">
            View in 3D
          </Button>
          <StepBadge complete={step2Complete} />
        </div>
      }
      accent
    >
      <Tabs
        ariaLabel="Design parameter sections"
        active={section}
        onChange={(id) => setSection(id as StepId)}
        tabs={SECTIONS.map((s) => {
          const n = errorCountFor(s.id);
          return {
            id: s.id,
            label: s.title,
            badge: n > 0
              ? <span className="s2__tab-err" aria-label={`${n} problems`}>{n}</span>
              : undefined,
          };
        })}
      />

      <div
        role="tabpanel"
        id={`panel-${active.id}`}
        aria-labelledby={`tab-${active.id}`}
        className="s2__panel"
      >
        <p className="s2__desc">{active.description}</p>
        <div className="s2__fields">
          {fieldsForStep(active.id).map((def) => (
            <FieldRenderer
              key={def.name as string}
              def={def}
              value={session.values[def.name as string] ?? ''}
              chips={session.chips[def.name as string] ?? []}
              error={errors[def.name as string]}
              onValue={(v) => {
                setValue(def.name as string, v);
                if (errors[def.name as string]) {
                  setErrors((prev) => {
                    const next = { ...prev };
                    delete next[def.name as string];
                    return next;
                  });
                }
              }}
              onChips={(next) => setChips(def.name as string, next)}
            />
          ))}
        </div>
      </div>

      <StepActions onSaveDraft={saveDraft} />

      <PathwayNav onBeforeContinue={handleBeforeContinue} />
    </Card>
    </>
  );
}

/**
 * One schema field, rendered by its declared kind.
 *
 * Exported so the Targeting & Ligands step renders the same controls from the
 * same schema. A second copy would let the two pages drift into disagreeing
 * about a field's help text, its default note, or whether it is required.
 */
export function FieldRenderer({
  def, value, chips, error, onValue, onChips,
}: {
  def: FieldDef;
  value: string;
  chips: string[];
  error?: string;
  onValue: (v: string) => void;
  onChips: (next: string[]) => void;
}) {
  const name = def.name as string;

  if (def.kind === 'chips') {
    return (
      <div className="s2__field s2__field--wide">
        <ChipGroup
          id={name}
          label={def.label}
          options={def.options}
          value={chips}
          onChange={onChips}
          hint={<InfoHint label={def.label}>{def.definition}</InfoHint>}
          help={chips.length === 0
            ? `Not selected — the engine will use its default: ${def.defaultNote}.`
            : undefined}
        />
      </div>
    );
  }

  if (def.kind === 'text' && name === 'ligand') {
    return (
      <div className="s2__field">
        <SelectField
          id={name}
          label={def.label}
          value={value}
          onChange={(e) => onValue(e.target.value)}
          options={LIGAND_OPTIONS.map((o) => ({ value: o.value, label: o.label }))}
          error={error}
          hint={<InfoHint label={def.label}>{def.definition}</InfoHint>}
          help={!value.trim()
            ? 'Passive targeting. The engine applies a fixed 60/100 baseline for the targeting component.'
            : undefined}
        />
      </div>
    );
  }

  const range = def.kind === 'number'
    ? [def.min !== undefined ? `min ${def.min}` : null,
       def.max !== undefined ? `max ${def.max}` : null].filter(Boolean).join(' · ')
    : '';

  return (
    <div className="s2__field">
      <TextField
        id={name}
        label={def.label}
        unit={def.unit}
        type="text"
        inputMode="decimal"
        required={def.required}
        value={value}
        onChange={(e) => onValue(e.target.value)}
        error={error}
        placeholder={def.required ? undefined : `default ${def.defaultNote ?? '—'}`}
        hint={<InfoHint label={def.label}>{def.definition}</InfoHint>}
        help={range || undefined}
      />
    </div>
  );
}

export { Icon };
