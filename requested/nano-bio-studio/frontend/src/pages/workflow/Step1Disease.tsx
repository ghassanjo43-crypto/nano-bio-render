/**
 * Step 1 — Disease & Therapeutic Selection.
 *
 * Mirrors the legacy `pages/0_Disease_Selection.py`: choose an indication, then
 * a subtype, then a therapeutic drug valid for that subtype. Epidemiology and
 * unmet-need text come from the same source data; nothing is invented.
 */

import { useNavigate } from 'react-router-dom';
import { Alert, Card, EmptyState, SelectField } from '../../design-system/components';
import { Icon } from '../../shell/Icon';
import { DISEASES, drugsFor, findDisease, subtypesFor } from '../../workflow/diseaseData';
import { useWorkflow } from '../../workflow/WorkflowContext';
import { StepActions, StepBadge } from './WorkflowLayout';
import './Step1Disease.css';

export default function Step1Disease() {
  const navigate = useNavigate();
  const { session, setSelection, step1Complete, reachStep, saveDraft } = useWorkflow();
  const { disease, subtype, drug } = session.selection;

  const subtypes = subtypesFor(disease);
  const drugs = drugsFor(disease, subtype);
  const info = findDisease(disease);

  const handleContinue = () => {
    if (!step1Complete) return;
    reachStep(2);
    navigate('/workflow/design');
  };

  return (
    <>
      <Card
        title="Step 1 — Disease & Therapeutic Selection"
        subtitle="Choose the indication, disease subtype and therapeutic agent this formulation is intended to deliver."
        actions={<StepBadge complete={step1Complete} />}
        accent
      >
        <div className="s1__grid">
          <div className="s1__controls">
            <SelectField
              id="disease"
              label="Indication"
              required
              value={disease}
              onChange={(e) => setSelection({ disease: e.target.value })}
              options={[
                { value: '', label: 'Select a disease…' },
                ...DISEASES.map((d) => ({ value: d.name, label: d.name })),
              ]}
              help="Determines the biological context recorded with this design."
            />

            <SelectField
              id="subtype"
              label="Disease subtype"
              required
              value={subtype}
              disabled={!disease}
              onChange={(e) => setSelection({ subtype: e.target.value })}
              options={[
                { value: '', label: disease ? 'Select a subtype…' : 'Select a disease first' },
                ...subtypes.map((s) => ({ value: s.name, label: s.name })),
              ]}
              help={disease ? `${subtypes.length} subtypes available.` : undefined}
            />

            <SelectField
              id="drug"
              label="Therapeutic agent"
              required
              value={drug}
              disabled={!subtype}
              onChange={(e) => setSelection({ drug: e.target.value })}
              options={[
                { value: '', label: subtype ? 'Select a therapeutic…' : 'Select a subtype first' },
                ...drugs.map((d) => ({ value: d, label: d })),
              ]}
              help={subtype
                ? `${drugs.length} agents associated with this subtype.`
                : undefined}
            />
          </div>

          <aside className="s1__context">
            {info ? (
              <>
                <p className="eyebrow">Disease context</p>
                <h3 className="s1__context-title">{info.name}</h3>
                <dl className="s1__epi">
                  <div>
                    <dt>Annual incidence</dt>
                    <dd>{info.epidemiology.incidence ?? 'Not recorded'}</dd>
                  </div>
                  <div>
                    <dt>Annual mortality</dt>
                    <dd>{info.epidemiology.mortality ?? 'Not recorded'}</dd>
                  </div>
                  <div>
                    <dt>5-year survival</dt>
                    <dd>{info.epidemiology.fiveYearSurvival ?? 'Not recorded'}</dd>
                  </div>
                </dl>
                {info.unmetNeeds && (
                  <div className="s1__unmet">
                    <p className="eyebrow">Unmet clinical needs</p>
                    <p>{info.unmetNeeds}</p>
                  </div>
                )}
              </>
            ) : (
              <EmptyState
                icon={<Icon name="flask" size={20} />}
                title="No indication selected"
              >
                Disease statistics and unmet needs appear here once you choose an
                indication.
              </EmptyState>
            )}
          </aside>
        </div>

        {step1Complete && (
          <div className="s1__confirm">
            <Icon name="check" size={16} />
            <span>
              Selected <strong>{drug}</strong> for <strong>{subtype}</strong>
              {' '}({disease}).
            </span>
          </div>
        )}

        <StepActions
          onSaveDraft={saveDraft}
          onContinue={handleContinue}
          continueLabel="Continue to design parameters"
          continueDisabled={!step1Complete}
        />
      </Card>

      <Alert tone="info" title="How this selection is used" role="note">
        <p>
          The indication, subtype and therapeutic are recorded with this design
          session and appear in the review and results.
        </p>
        <p>
          <strong>They do not currently change the design impact score.</strong>{' '}
          That score is computed by the migrated formulation engine, which takes
          physicochemical parameters only. The disease-specific assessment
          engines — which are what consume this context — have not been migrated
          yet, so no disease-dependent result is produced or implied.
        </p>
      </Alert>
    </>
  );
}
