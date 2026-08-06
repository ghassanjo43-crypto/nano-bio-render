/**
 * The workspace study lists.
 *
 * Each is a filtered view of the same stored records, rendered by the single
 * `StudyListPage` component. They exist as separate menu entries because users
 * think in pathways, not because there are separate stores or workflows.
 */

import StudyListPage from './StudyListPage';

export function MyStudiesPage() {
  return (
    <StudyListPage
      title="My Studies"
      subtitle={
        'Every study you have saved, across all three pathways, with the '
        + 'inputs and engine versions that produced each result.'
      }
      emptyTitle="No studies saved yet"
      emptyBody={
        'Nothing is listed here until you run and save a calculation. This page '
        + 'shows only genuine stored records — it is never populated with '
        + 'example activity.'
      }
      testId="studies"
    />
  );
}

export function PatientAssessmentsPage() {
  return (
    <StudyListPage
      pathway="patient_assessment"
      title="Patient Assessments"
      subtitle={
        'Studies begun from a de-identified medical report. The report itself '
        + 'is not shown here; only the study it established.'
      }
      emptyTitle="No patient assessments saved yet"
      emptyBody={
        'A study appears here once you upload a de-identified report, confirm '
        + 'the extracted fields and save a calculation. Only synthetic and '
        + 'de-identified documents may be uploaded.'
      }
      testId="patient-assessments"
      showPathwayColumn={false}
    />
  );
}

export function ResearchDesignsPage() {
  return (
    <StudyListPage
      pathway="research_design"
      title="Research Designs"
      subtitle={
        'Studies begun from a research question rather than an individual '
        + 'report.'
      }
      emptyTitle="No research designs saved yet"
      emptyBody={
        'Start a study from a research question, run the connected engines and '
        + 'save it, and it will be listed here.'
      }
      testId="research-designs"
      showPathwayColumn={false}
    />
  );
}

/**
 * Simulation History.
 *
 * Kept as its own entry because it answers a different question from My
 * Studies — "what has been run", chronologically, regardless of pathway — but
 * it is the same records and the same component.
 */
export default function HistoryPage() {
  return (
    <StudyListPage
      title="Simulation History"
      subtitle={
        'Runs stored on the server, most recent first, with the inputs and '
        + 'engine versions that produced them.'
      }
      emptyTitle="No runs stored yet"
      emptyBody={
        'Nothing is listed here until you run and save a calculation. This page '
        + 'shows only genuine stored records — it is never populated with '
        + 'example activity.'
      }
      testId="history"
    />
  );
}
