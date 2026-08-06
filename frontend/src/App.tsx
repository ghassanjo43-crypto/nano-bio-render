/**
 * Application routing.
 *
 * After login the user lands on the **pathway chooser** (`/start`), not a
 * dashboard: the platform's primary activity is the scientific workflow, and
 * the first question is which of the three pathways the study begins from.
 *
 * There is exactly ONE scientific workflow (`/workflow/*`), shared by all three
 * pathways and mirroring the legacy Streamlit sequence (disease → design
 * parameters → run → results). The pathway records how a study began; it does
 * not fork the science. Nothing in this file changes any calculation.
 *
 * Route policy:
 *  - `/login` is public; authenticated users are redirected to `/start`.
 *  - Everything else sits behind `ProtectedRoute`, which waits for the initial
 *    session check so a refresh does not bounce an authenticated user out.
 *  - `/admin` additionally requires the admin role via `RoleRoute`.
 *  - Workflow steps are gated by `WorkflowLayout`, which redirects back to the
 *    first incomplete step if a later one is deep-linked.
 */

import { Navigate, Route, Routes } from 'react-router-dom';
import { ProtectedRoute, RoleRoute } from './auth/guards';
import DashboardPage from './pages/DashboardPage';
import DemoWorkspace from './pages/demo/DemoWorkspace';
import EvidencePage from './pages/EvidencePage';
// The builder itself is a normal chunk; the heavy three.js scene inside it is
// what is lazily loaded (see NanoparticleBuilder).
import NanoparticleBuilder from './pages/builder/NanoparticleBuilder';
import ScientificReadinessPage from './pages/readiness/ScientificReadinessPage';
import ValidationRegistryPage from './pages/validation/ValidationRegistryPage';
import NewExperimentPage from './pages/validation/NewExperimentPage';
import ExperimentDetailPage from './pages/validation/ExperimentDetailPage';
import CandidateVersionsRoute from './pages/candidates/CandidateVersionsRoute';
import NotificationCenter from './pages/notifications/NotificationCenter';
import LoginPage from './pages/LoginPage';
import ReportAssessment from './pages/report/ReportAssessment';
import ModulePlaceholder from './pages/ModulePlaceholder';
import NotFoundPage from './pages/NotFoundPage';
import UnauthorizedPage from './pages/UnauthorizedPage';
import ResultsStage from './pages/workflow/ResultsStage';
import SessionStartPage from './pages/workflow/SessionStartPage';
import Step1Disease from './pages/workflow/Step1Disease';
import Step2Design from './pages/workflow/Step2Design';
import StepTargeting from './pages/workflow/StepTargeting';
import Step3Review from './pages/workflow/Step3Review';
import WorkflowLayout from './pages/workflow/WorkflowLayout';
import StartNewStudy from './pages/start/StartNewStudy';
import ResearchPurpose from './pages/start/ResearchPurpose';
import ComparePage from './pages/workspace/ComparePage';
import HistoryPage, {
  MyStudiesPage, PatientAssessmentsPage, ResearchDesignsPage,
} from './pages/workspace/StudyLists';
import ProjectsPage from './pages/workspace/ProjectsPage';
import RunDetailPage from './pages/workspace/RunDetailPage';
import AppShell from './shell/AppShell';
import { findNavItem } from './shell/navigation';
import { OrganizationProvider } from './organizations/OrganizationContext';
import OrganizationAdminPage from './pages/organization/OrganizationAdminPage';
import StudyTeamPage from './pages/organization/StudyTeamPage';
import AcceptInvitationPage from './pages/organization/AcceptInvitationPage';
import SetPasswordPage from './pages/account/SetPasswordPage';
import ForgotPasswordPage from './pages/account/ForgotPasswordPage';
import AccountSecurityPage from './pages/account/AccountSecurityPage';
import { WorkflowProvider } from './workflow/WorkflowContext';
import PathwayFrame from './workflow/PathwayFrame';

function placeholderFor(key: string) {
  return <ModulePlaceholder item={findNavItem(key)} />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      {/* Account recovery, outside ProtectedRoute deliberately.
          Somebody activating an account has no session yet, and somebody
          resetting a password usually cannot sign in — which is why they are
          here. Putting these behind the guard would redirect them to the login
          screen they are trying to get past, and the redirect would carry the
          token in the `from` location. Each page takes a token from the query
          string and nothing else. */}
      <Route path="/account/activate"
             element={<SetPasswordPage mode="activate" />} />
      <Route path="/account/reset"
             element={<SetPasswordPage mode="reset" />} />
      <Route path="/account/forgot" element={<ForgotPasswordPage />} />

      <Route element={<ProtectedRoute />}>
        <Route
          element={
            <OrganizationProvider>
              <WorkflowProvider>
                <AppShell />
              </WorkflowProvider>
            </OrganizationProvider>
          }
        >
          {/* Landing: the pathway chooser, not a dashboard. */}
          <Route path="/" element={<Navigate to="/start" replace />} />

          {/* Start — the three pathways. `/start` asks how to begin;
              `/start/research` is the second level of the research pathway.
              The patient pathway continues at `/report`, and the demonstration
              pathway at `/demo`. All three converge on `/workflow`. */}
          <Route path="/start" element={<StartNewStudy />} />
          <Route path="/start/research"
                 element={<PathwayFrame><ResearchPurpose /></PathwayFrame>} />
          {/* The previous single-entry gate, still reachable for anyone who
              deep-linked it. It resumes an existing draft. */}
          <Route path="/start/session" element={<SessionStartPage />} />

          {/* The connected four-stage workflow, shared by all three pathways.
              There is ONE workflow; the pathway records how the study began. */}
          <Route path="/workflow" element={<WorkflowLayout />}>
            <Route index element={<Navigate to="/workflow/disease" replace />} />
            <Route path="disease" element={<Step1Disease />} />
            <Route path="design" element={<Step2Design />} />
            {/* Targeting & Ligands renders the schema's `targeting` section.
                It is a separate route so that step and Nanoparticle Design are
                distinct stops on a pathway rather than one URL twice. */}
            <Route path="targeting" element={<StepTargeting />} />
            <Route path="review" element={<Step3Review />} />
            <Route path="results" element={<ResultsStage />} />
          </Route>

          {/* Platform status. `/dashboard` kept as a redirect so existing links
              and bookmarks do not break. */}
          <Route path="/home" element={<DashboardPage />} />
          <Route path="/dashboard" element={<Navigate to="/home" replace />} />

          {/* Demonstration scenarios: synthetic INPUTS only, run by the real
              engines. Loading one populates the ordinary workflow. */}
          <Route path="/demo"
                 element={<PathwayFrame><DemoWorkspace /></PathwayFrame>} />

          {/* Medical Report Assessment. Synthetic and de-identified documents
              only; extraction is honestly reported as unavailable. */}
          <Route path="/report"
                 element={<PathwayFrame><ReportAssessment /></PathwayFrame>} />

          {/* Workspace — four filtered views of the same stored records, all
              rendered by one component. Not four separate workflows. */}
          <Route path="/studies" element={<MyStudiesPage />} />
          <Route path="/studies/:runId" element={<RunDetailPage />} />
          <Route path="/patient-assessments" element={<PatientAssessmentsPage />} />
          <Route path="/research-designs" element={<ResearchDesignsPage />} />
          <Route path="/history" element={<HistoryPage />} />
          {/* Stored studies were addressed under /history before the workspace
              was reorganised. Redirect rather than break saved links. */}
          <Route path="/history/:runId" element={<RunDetailPage />} />
          <Route path="/compare"
                 element={<PathwayFrame><ComparePage /></PathwayFrame>} />
          <Route path="/projects" element={<ProjectsPage />} />
          {/* Reports are generated from a stored study, so the module entry
              point is the study list rather than a separate page. */}
          <Route path="/reports"
                 element={<PathwayFrame><MyStudiesPage /></PathwayFrame>} />

          {/* Nanoparticle 3D Builder. Reads the current design; writes only a
              confirmed preset. */}
          <Route path="/builder" element={<NanoparticleBuilder />} />

          {/* Scientific Readiness assesses THIS STUDY's data, per area.
              Distinct from /evidence, which reports module build status. */}
          <Route path="/scientific-readiness"
                 element={<PathwayFrame><ScientificReadinessPage /></PathwayFrame>} />

          {/* Experimental Validation Registry (Phase 2, Milestone 1).
              Records in-vitro experiments against an exact candidate version
              and is the ONLY path by which E3 is granted. */}
          <Route path="/validation"
                 element={<PathwayFrame><ValidationRegistryPage /></PathwayFrame>} />
          <Route path="/validation/new" element={<NewExperimentPage />} />
          <Route path="/validation/experiments/:experimentId"
                 element={<ExperimentDetailPage />} />

          {/* Candidate revision and supersession.
              Addressed by candidate; every action inside it is addressed to an
              exact version. The screen never says "latest version" — it names
              the latest draft, the latest approved and the current effective
              version separately, because those are three different claims. */}
          <Route path="/validation/candidates/:candidateId/versions"
                 element={<CandidateVersionsRoute />} />
          <Route path="/notifications" element={<NotificationCenter />} />

          {/* Evidence & Validation reads the verified module registry. */}
          <Route path="/evidence"
                 element={<PathwayFrame><EvidencePage /></PathwayFrame>} />

          {/* Modules whose genuine engines are not connected. These render an
              honest unavailable state and never a calculated-looking number. */}
          {/* Former placeholder path, kept so existing links resolve. */}
          <Route path="/visualisation"
                 element={<Navigate to="/builder" replace />} />
          <Route path="/protocol"
                 element={<PathwayFrame>{placeholderFor('protocol')}</PathwayFrame>} />
          <Route path="/experimental-planning"
                 element={<PathwayFrame>
                   {placeholderFor('experimental-planning')}
                 </PathwayFrame>} />
          <Route path="/ai-co-designer" element={placeholderFor('ai-co-designer')} />
          <Route path="/ml-training" element={placeholderFor('ml-training')} />
          <Route path="/help" element={placeholderFor('help')} />
          <Route path="/settings" element={placeholderFor('settings')} />
          {/* Organization administration. Reachable by every member: the
              screens show what the caller may see, and every control they
              cannot use is both hidden AND refused by the backend. A route
              guarded only in the client would be a guard on the menu, not on
              the data. */}
          <Route path="/organization" element={<OrganizationAdminPage />} />
          <Route path="/organization/studies/:studyId/team"
                 element={<StudyTeamPage />} />
          {/* Redeeming an invitation. Takes only a token from the query
              string — never a redirect target. */}
          <Route path="/invitations/accept" element={<AcceptInvitationPage />} />

          {/* The signed-in user's own security screen: password, sessions,
              recent activity. Available to every account — there is no role
              that should be unable to see where its own account is signed
              in. */}
          <Route path="/account/security" element={<AccountSecurityPage />} />

          <Route path="/unauthorized" element={<UnauthorizedPage />} />

          <Route element={<RoleRoute roles={['admin']} />}>
            <Route path="/admin" element={placeholderFor('admin')} />
          </Route>

          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Route>
    </Routes>
  );
}
