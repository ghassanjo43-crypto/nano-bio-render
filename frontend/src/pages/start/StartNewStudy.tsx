/**
 * Start New Study — the single entry point to all three pathways.
 *
 * The pathway a study begins on is recorded on the study itself, not merely
 * used for routing. That is what keeps a patient assessment, a research design
 * and a demonstration distinguishable wherever studies are later listed, and it
 * is what tells the sidebar which entry to keep active during the shared
 * `/workflow/*` steps.
 *
 * Every claim about availability on this screen is drawn from the module status
 * registry, so a card cannot promise something the platform does not do.
 */

import { useNavigate } from 'react-router-dom';
import { Alert, Badge, Button, Card } from '../../design-system/components';
import { Icon } from '../../shell/Icon';
import { STATUS_META, findNavItem } from '../../shell/navigation';
import { useWorkflow } from '../../workflow/WorkflowContext';
import './StartNewStudy.css';

interface PathwayCard {
  key: string;
  testId: string;
  icon: string;
  title: string;
  purpose: string;
  /** Short claims shown as chips. Each must be defensible. */
  facts: readonly string[];
  journey: readonly string[];
  primary: { label: string; to: string; testId: string };
  secondary: { label: string; to: string; testId: string };
  /** Nav key whose verified status governs what this card may claim. */
  statusKey: string;
  note?: string;
}

const PATHWAYS: readonly PathwayCard[] = [
  {
    key: 'patient_assessment',
    testId: 'pathway-patient',
    icon: 'document',
    title: 'Patient-Specific Assessment',
    purpose:
      'Upload a de-identified cancer medical report, extract and review its '
      + 'clinical information, and use confirmed findings to establish the '
      + 'research context.',
    facts: [
      'Recommended for patient-specific research',
      'De-identified reports only',
      'Research Use Only',
    ],
    journey: [
      'Upload report',
      'Extract clinical information',
      'Review source evidence',
      'Confirm or correct extracted fields',
      'Populate the disease and therapeutic context',
      'Continue to nanoparticle design',
      'Run available scientific engines',
      'Save results and generate a report',
    ],
    primary: { label: 'Upload Medical Report', to: '/report',
               testId: 'start-patient-upload' },
    // The drafts gate, where unsaved work genuinely lives. The Patient
    // Assessments list holds SAVED studies, which is a different thing, so
    // pointing "resume" at it would misdescribe what the button does.
    secondary: { label: 'Resume Saved Draft', to: '/start/session',
                 testId: 'resume-patient' },
    statusKey: 'patient-assessments',
    note:
      'Extraction is performed by a rule-based reader that has not been '
      + 'validated against annotated reports. Every field is shown with the '
      + 'excerpt that produced it and must be confirmed by you. Scanned '
      + 'documents cannot be read at all — no OCR engine is installed — and are '
      + 'reported as such so you can enter the details manually.',
  },
  {
    key: 'research_design',
    testId: 'pathway-research',
    icon: 'hexagon',
    title: 'Research & Nanoparticle Design',
    purpose:
      'Conduct disease-specific or formulation-focused research without using '
      + 'an individual patient report.',
    facts: [
      'No patient document involved',
      'Disease and formulation research',
      'Research Use Only',
    ],
    journey: [
      'Select research purpose',
      'Define disease or experimental context',
      'Select therapeutic payload where relevant',
      'Enter formulation and targeting parameters',
      'Review simulation inputs',
      'Run connected scientific engines',
      'Save, compare and report results',
    ],
    primary: { label: 'Start Research Study', to: '/start/research',
               testId: 'start-research' },
    secondary: { label: 'Resume Saved Draft', to: '/start/session',
                 testId: 'resume-research' },
    statusKey: 'research-designs',
  },
  {
    key: 'demo_scenario',
    testId: 'pathway-demo',
    icon: 'flask',
    title: 'Demo & Training Workspace',
    purpose:
      'Test and demonstrate the application using clearly labelled synthetic '
      + 'data.',
    facts: [
      'Synthetic demonstration data',
      'Never patient or clinical data',
      'Research Use Only',
    ],
    journey: [
      'Select a ready-made synthetic scenario',
      'Preview its inputs and limitations',
      'Load an isolated working copy',
      'Review populated workflow fields',
      'Deliberately run the connected engines',
      'View calculated results',
      'Save, compare or reset the demo run',
    ],
    primary: { label: 'Browse Demo Scenarios', to: '/demo',
               testId: 'start-demo' },
    // A demonstration run is saved server-side once it has been run, so this
    // opens the stored list rather than a draft.
    secondary: { label: 'Open Saved Demo Runs', to: '/studies',
                 testId: 'resume-demo' },
    statusKey: 'demo',
    note:
      'Scenarios prepopulate inputs only. Every score, profile and chart is '
      + 'calculated at run time by the genuine engines — no result is ever '
      + 'stored in a scenario.',
  },
];

export default function StartNewStudy() {
  const navigate = useNavigate();
  const { startStudy, hasResumableSession, session } = useWorkflow();

  function begin(card: PathwayCard) {
    // The research pathway picks its purpose on the next screen, so the study
    // is only stamped once that choice is made. The other two are unambiguous.
    if (card.key !== 'research_design') {
      startStudy(card.key as 'patient_assessment' | 'demo_scenario');
    }
    navigate(card.primary.to);
  }

  return (
    <>
      <Card
        title="How would you like to begin?"
        subtitle="Every pathway creates the same study record, with its origin recorded."
        accent
      >
        <p className="sns__lead">
          A study can start from a de-identified medical report, from a research
          question, or from a synthetic demonstration scenario. Whichever you
          choose, the study is saved in the same structure and stays
          distinguishable by its origin in Projects, History, Compare Results and
          Reports.
        </p>

        {hasResumableSession && (
          <Alert tone="info" title="You have work in progress" role="note">
            <p>
              Starting a new study leaves your current session untouched — you
              can return to it from <strong>My Studies</strong>.
              {session.selection.disease && (
                <> The session in progress is <strong>
                  {session.selection.disease}</strong>.</>
              )}
            </p>
          </Alert>
        )}

        <div className="sns__grid" data-testid="pathway-cards">
          {PATHWAYS.map((card) => {
            const item = findNavItem(card.statusKey);
            const meta = STATUS_META[item.status];
            return (
              <article className="sns__card" key={card.key}
                       data-testid={card.testId}>
                <header className="sns__head">
                  <span className="sns__icon" aria-hidden="true">
                    <Icon name={card.icon as never} size={22} />
                  </span>
                  <Badge tone={meta.tone} dot>{meta.label}</Badge>
                </header>

                <h3 className="sns__title">{card.title}</h3>
                <p className="sns__purpose">{card.purpose}</p>

                <ul className="sns__facts">
                  {card.facts.map((fact) => (
                    <li key={fact}>
                      <Icon name="check" size={13} />
                      {fact}
                    </li>
                  ))}
                </ul>

                <details className="sns__journey">
                  <summary>What this pathway involves</summary>
                  <ol>
                    {card.journey.map((step) => <li key={step}>{step}</li>)}
                  </ol>
                </details>

                {card.note && <p className="sns__note">{card.note}</p>}

                <div className="sns__actions">
                  <Button fullWidth onClick={() => begin(card)}
                          data-testid={card.primary.testId}
                          iconRight={<Icon name="arrow-right" size={15} />}>
                    {card.primary.label}
                  </Button>
                  <Button fullWidth variant="secondary"
                          onClick={() => navigate(card.secondary.to)}
                          data-testid={card.secondary.testId}
                          iconLeft={<Icon name="clock" size={15} />}>
                    {card.secondary.label}
                  </Button>
                </div>
              </article>
            );
          })}
        </div>
      </Card>

      <Alert tone="warn" title="Research use only" role="note">
        Every value this platform produces is a computational research-planning
        result. It is not experimentally validated, not clinically validated, not
        a regulatory approval prediction, not a diagnosis, and not a dosing or
        treatment recommendation.
      </Alert>
    </>
  );
}
