/**
 * Research purpose — the second level of the Research & Nanoparticle Design
 * pathway.
 *
 * Each purpose declares the status it genuinely has. A purpose is only offered
 * as operational when the engines it depends on are actually connected;
 * otherwise it states what is missing and, where useful, offers the nearest
 * thing that does work.
 *
 * Selecting a purpose records it on the study, so a later reader can tell what
 * the study set out to do — not merely what it computed.
 */

import { useNavigate } from 'react-router-dom';
import { Alert, Badge, Button, Card } from '../../design-system/components';
import { Icon } from '../../shell/Icon';
import { STATUS_META, type ModuleStatus } from '../../shell/navigation';
import { useWorkflow } from '../../workflow/WorkflowContext';
import './StartNewStudy.css';

interface Purpose {
  key: string;
  label: string;
  summary: string;
  status: ModuleStatus;
  /** Where selecting it goes. Only meaningful when it can be started. */
  to: string;
  /** What is missing, for anything not operational. */
  missing?: string;
}

/**
 * Statuses here are the honest consequence of what is connected:
 * `core.scoring.compute_impact` (design score) and `utils.pk_model` (PK) are
 * operational; the six assessment engines, the optimiser and the predictors are
 * not.
 */
export const RESEARCH_PURPOSES: readonly Purpose[] = [
  {
    key: 'disease_specific_design',
    label: 'Disease-Specific Nanoparticle Design',
    summary:
      'Design a formulation in the context of a chosen indication, subtype and '
      + 'therapeutic agent.',
    status: 'limited_prototype',
    to: '/workflow/disease',
    missing:
      'The therapeutic context is recorded for traceability but does not enter '
      + 'any calculation: the design score consumes physicochemical parameters '
      + 'only. Disease-specific assessment needs the assessment engines, which '
      + 'have profiles for two indications and are not connected.',
  },
  {
    key: 'therapeutic_delivery',
    label: 'Therapeutic Delivery Optimization',
    summary:
      'Explore how formulation parameters change the calculated delivery, '
      + 'toxicity and cost components.',
    status: 'operational',
    to: '/workflow/disease',
  },
  {
    key: 'existing_formulation',
    label: 'Existing Formulation Optimization',
    summary:
      'Start from a formulation you already have and vary it against the '
      + 'connected engines.',
    status: 'operational',
    to: '/workflow/disease',
  },
  {
    key: 'targeting_ligand',
    label: 'Targeting-Ligand Assessment',
    summary:
      'Assess a targeting ligand, its density and its receptor-binding '
      + 'affinity.',
    status: 'limited_prototype',
    to: '/workflow/disease',
    missing:
      'Ligand inputs feed the targeting component of the design score, but no '
      + 'dedicated ligand-assessment engine exists. With no ligand the scorer '
      + 'applies a fixed passive-targeting baseline of 60/100, an uncalibrated '
      + 'constant whose derivation is an open scientific question.',
  },
  {
    key: 'biodistribution_pk',
    label: 'Biodistribution and PK Simulation',
    summary:
      'Run the migrated two-compartment pharmacokinetic model over a dose and '
      + 'four rate constants.',
    status: 'operational',
    to: '/workflow/disease',
    missing:
      'Biodistribution beyond the two modelled compartments is not simulated, '
      + 'and the model produces no clearance because it carries no volume term.',
  },
  {
    key: 'compare_designs',
    label: 'Compare Nanoparticle Designs',
    summary:
      'Align two or more completed studies field by field on their genuinely '
      + 'calculated values.',
    status: 'operational',
    to: '/compare',
  },
  {
    key: 'experimental_planning',
    label: 'Experimental Planning',
    summary:
      'Plan wet-lab experiments against a design, with success criteria linked '
      + 'to calculated predictions.',
    status: 'not_operational',
    to: '/experimental-planning',
    missing:
      'No experimental-planning engine exists. The legacy protocol generator '
      + 'is deterministic text and is not migrated; it also needs formulation '
      + 'fields this workflow does not collect.',
  },
  {
    key: 'reproduce_published',
    label: 'Reproduce a Published Formulation',
    summary:
      'Enter a formulation from the literature and compute its scores under '
      + 'this platform.',
    status: 'limited_prototype',
    to: '/workflow/disease',
    missing:
      'You can enter and score a published formulation, but the platform holds '
      + 'no literature corpus to compare against and cannot verify that your '
      + 'entry matches the source.',
  },
  {
    key: 'general_exploration',
    label: 'General Research Exploration',
    summary:
      'An open-ended study with no particular purpose declared in advance.',
    status: 'operational',
    to: '/workflow/disease',
  },
];

export default function ResearchPurpose() {
  const navigate = useNavigate();
  const { startStudy } = useWorkflow();

  function choose(purpose: Purpose) {
    if (purpose.status === 'not_operational') return;
    startStudy('research_design', purpose.key);
    navigate(purpose.to);
  }

  return (
    <>
      <Card
        title="What is the purpose of this study?"
        subtitle="Recorded on the study, so a later reader can tell what it set out to do."
        accent
        actions={
          <Button variant="ghost" onClick={() => navigate('/start')}
                  iconLeft={<Icon name="chevron-left" size={15} />}>
            Back to pathways
          </Button>
        }
      >
        <p className="sns__lead">
          Each purpose shows the status it genuinely has. Where a purpose depends
          on something not yet connected, it says so and what is missing — the
          study can still proceed, but only the connected engines will run.
        </p>

        <ul className="sns__purposes" data-testid="research-purposes">
          {RESEARCH_PURPOSES.map((purpose) => {
            const meta = STATUS_META[purpose.status];
            const blocked = purpose.status === 'not_operational';
            return (
              <li key={purpose.key} data-testid={`purpose-${purpose.key}`}
                  className={blocked ? 'is-blocked' : undefined}>
                <div className="sns__purposehead">
                  <span className="sns__purposetitle">{purpose.label}</span>
                  <Badge tone={meta.tone} dot>{meta.label}</Badge>
                </div>
                <p className="sns__purposebody">{purpose.summary}</p>
                {purpose.missing && (
                  <p className="sns__purposemissing">
                    <strong>Limitation:</strong> {purpose.missing}
                  </p>
                )}
                <Button
                  variant={blocked ? 'ghost' : 'secondary'}
                  disabled={blocked}
                  onClick={() => choose(purpose)}
                  data-testid={`choose-${purpose.key}`}
                  iconRight={blocked ? undefined
                                     : <Icon name="arrow-right" size={15} />}
                >
                  {blocked ? 'Not available' : 'Select this purpose'}
                </Button>
              </li>
            );
          })}
        </ul>
      </Card>

      <Alert tone="info" title="Availability is stated, not implied" role="note">
        A purpose marked <strong>Limited prototype</strong> will run, but only
        the connected engines contribute. A purpose marked{' '}
        <strong>Not yet operational</strong> cannot be selected, because nothing
        genuine sits behind it and offering it would imply otherwise.
      </Alert>
    </>
  );
}
