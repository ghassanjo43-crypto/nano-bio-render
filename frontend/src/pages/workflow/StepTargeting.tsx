/**
 * Targeting & Ligands — the targeting section of the design schema, on its own
 * route.
 *
 * Why it is a separate page
 * -------------------------
 * The nav registry listed Targeting & Ligands and Nanoparticle Design at the
 * same path, so on a pathway they were two consecutive steps with one URL and
 * "Continue" from the first landed on the first. Splitting the schema's
 * existing `targeting` section onto `/workflow/targeting` gives each step a
 * distinct stop.
 *
 * This adds no field and changes no calculation. The fields, their validation
 * and their defaults come from `pages/design/schema.ts`, exactly as they do on
 * `/workflow/design`, and the values live in the same session — editing a
 * ligand here is editing the same formulation, not a copy.
 *
 * Every field in this section is optional. Leaving the ligand empty selects
 * passive targeting, which the engine handles with a documented fixed baseline;
 * the page says so rather than implying targeting is required.
 */

import { useState } from 'react';
import { Card } from '../../design-system/components';
import { useWorkflow } from '../../workflow/WorkflowContext';
import PathwayNav, { PathwayProgress } from '../../workflow/PathwayNav';
import PathwayBanner from '../../workflow/PathwayBanner';
import { STEPS as FIELD_SECTIONS, fieldsForStep, validateAll } from '../design/schema';
import { FieldRenderer } from './Step2Design';
import './Step2Design.css';

const TARGETING = FIELD_SECTIONS.find((s) => s.id === 'targeting');

export default function StepTargeting() {
  const { session, setValue, setChips } = useWorkflow();
  const [errors, setErrors] = useState<Record<string, string>>({});

  const fields = fieldsForStep('targeting');

  /**
   * Validate only this section's fields before continuing.
   *
   * `validateAll` covers the whole form, and using it here would refuse to
   * advance because of a problem on a page the user is not looking at. The
   * design step keeps its own whole-form check for the run.
   */
  const validateSection = () => {
    const all = validateAll(session.values);
    const mine: Record<string, string> = {};
    for (const def of fields) {
      const name = def.name as string;
      if (all[name]) mine[name] = all[name]!;
    }
    setErrors(mine);
    return Object.keys(mine).length === 0;
  };

  return (
    <>
      <PathwayBanner />
      <PathwayProgress />

      <Card
        title="Targeting & Ligands"
        subtitle={TARGETING?.description
          ?? 'Active targeting strategy. Leave the ligand empty for passive targeting.'}
        accent
      >
        <p className="s2__desc">
          Every field here is optional. With no ligand recorded the study
          describes passive targeting, and the design engine applies its
          documented fixed baseline for the targeting component rather than
          inferring a value.
        </p>

        <div className="s2__fields">
          {fields.map((def) => (
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

        <PathwayNav onBeforeContinue={validateSection} />
      </Card>
    </>
  );
}
