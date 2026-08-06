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
import LoginPage from './pages/LoginPage';
import ReportAssessment from './pages/report/ReportAssessment';
import ModulePlaceholder from './pages/ModulePlaceholder';
import NotFoundPage from './pages/NotFoundPage';
import UnauthorizedPage from './pages/UnauthorizedPage';
import ResultsStage from './pages/workflow/ResultsStage';
import SessionStartPage from './pages/workflow/SessionStartPage';
import Step1Disease from './pages/workflow/Step1Disease';
import Step2Design from './pages/workflow/Step2Design';
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
import { WorkflowProvider } from './workflow/WorkflowContext';

function placeholderFor(key: string) {
  return <ModulePlaceholder item={findNavItem(key)} />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route element={<ProtectedRoute />}>
        <Route
          element={
            <WorkflowProvider>
              <AppShell />
            </WorkflowProvider>
          }
        >
          {/* Landing: the pathway chooser, not a dashboard. */}
          <Route path="/" element={<Navigate to="/start" replace />} />

          {/* Start — the three pathways. `/start` asks how to begin;
              `/start/research` is the second level of the research pathway.
              The patient pathway continues at `/report`, and the demonstration
              pathway at `/demo`. All three converge on `/workflow`. */}
          <Route path="/start" element={<StartNewStudy />} />
          <Route path="/start/research" element={<ResearchPurpose />} />
          {/* The previous single-entry gate, still reachable for anyone who
              deep-linked it. It resumes an existing draft. */}
          <Route path="/start/session" element={<SessionStartPage />} />

          {/* The connected four-stage workflow, shared by all three pathways.
              There is ONE workflow; the pathway records how the study began. */}
          <Route path="/workflow" element={<WorkflowLayout />}>
            <Route index element={<Navigate to="/workflow/disease" replace />} />
            <Route path="disease" element={<Step1Disease />} />
            <Route path="design" element={<Step2Design />} />
            <Route path="review" element={<Step3Review />} />
            <Route path="results" element={<ResultsStage />} />
          </Route>

          {/* Platform status. `/dashboard` kept as a redirect so existing links
              and bookmarks do not break. */}
          <Route path="/home" element={<DashboardPage />} />
          <Route path="/dashboard" element={<Navigate to="/home" replace />} />

          {/* Demonstration scenarios: synthetic INPUTS only, run by the real
              engines. Loading one populates the ordinary workflow. */}
          <Route path="/demo" element={<DemoWorkspace />} />

          {/* Medical Report Assessment. Synthetic and de-identified documents
              only; extraction is honestly reported as unavailable. */}
          <Route path="/report" element={<ReportAssessment />} />

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
          <Route path="/compare" element={<ComparePage />} />
          <Route path="/projects" element={<ProjectsPage />} />
          {/* Reports are generated from a stored study, so the module entry
              point is the study list rather than a separate page. */}
          <Route path="/reports" element={<MyStudiesPage />} />

          {/* Nanoparticle 3D Builder. Reads the current design; writes only a
              confirmed preset. */}
          <Route path="/builder" element={<NanoparticleBuilder />} />

          {/* Evidence & Validation reads the verified module registry. */}
          <Route path="/evidence" element={<EvidencePage />} />

          {/* Modules whose genuine engines are not connected. These render an
              honest unavailable state and never a calculated-looking number. */}
          {/* Former placeholder path, kept so existing links resolve. */}
          <Route path="/visualisation"
                 element={<Navigate to="/builder" replace />} />
          <Route path="/protocol" element={placeholderFor('protocol')} />
          <Route path="/experimental-planning"
                 element={placeholderFor('experimental-planning')} />
          <Route path="/ai-co-designer" element={placeholderFor('ai-co-designer')} />
          <Route path="/ml-training" element={placeholderFor('ml-training')} />
          <Route path="/help" element={placeholderFor('help')} />
          <Route path="/settings" element={placeholderFor('settings')} />
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
