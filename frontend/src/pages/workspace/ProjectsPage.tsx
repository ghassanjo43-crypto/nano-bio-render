/**
 * Projects — genuine server-stored groupings of runs.
 *
 * Nothing here is seeded or sampled. An account with no projects sees an empty
 * state, never invented activity.
 *
 * Deleting a project never destroys calculated records: the backend nulls the
 * runs' `project_id` instead of cascading, so a grouping mistake cannot cost a
 * user their results.
 */

import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createProject, deleteProject, listProjects, listRuns } from '../../api/client';
import type {
  ProjectSummary, RunSummary, WorkspaceErrorResponse,
} from '../../api/types';
import {
  Alert, Badge, Button, Card, DataTable, Dialog, EmptyState, SkeletonBlock,
  TextField,
} from '../../design-system/components';
import { Icon } from '../../shell/Icon';
import './WorkspacePages.css';

export default function ProjectsPage() {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<ProjectSummary[] | null>(null);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [error, setError] = useState<WorkspaceErrorResponse | null>(null);

  const [createOpen, setCreateOpen] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [busy, setBusy] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<ProjectSummary | null>(null);

  const refresh = useCallback(async (signal?: AbortSignal) => {
    const [p, r] = await Promise.all([listProjects(signal), listRuns({}, signal)]);
    if (p.status === 'error') { setError(p.error); setProjects([]); return; }
    setError(null);
    setProjects(p.data.projects);
    setRuns(r.status === 'ok' ? r.data.runs : []);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void refresh(controller.signal);
    return () => controller.abort();
  }, [refresh]);

  async function submitCreate() {
    if (!name.trim()) return;
    setBusy(true);
    const result = await createProject({ name: name.trim(), description: description.trim() || null });
    setBusy(false);
    if (result.status === 'error') { setError(result.error); return; }
    setCreateOpen(false);
    setName('');
    setDescription('');
    void refresh();
  }

  async function confirmDelete() {
    if (!pendingDelete) return;
    const result = await deleteProject(pendingDelete.id);
    setPendingDelete(null);
    if (result.status === 'error') { setError(result.error); return; }
    void refresh();
  }

  const unassigned = runs.filter((r) => r.project_id === null);

  return (
    <>
      <Card
        title="Projects"
        subtitle="Group stored runs into research projects. Server-stored, not browser-local."
        accent
        actions={
          <Button onClick={() => setCreateOpen(true)}
                  iconLeft={<Icon name="folder" size={15} />}
                  data-testid="new-project">
            New project
          </Button>
        }
      >
        {error && (
          <Alert tone="danger" title="Projects unavailable">
            <p>{error.message}</p>
            {error.detail && <p className="mono wp__detail">{error.detail}</p>}
          </Alert>
        )}

        {projects === null && <SkeletonBlock lines={3} />}

        {projects !== null && projects.length === 0 && !error && (
          <EmptyState title="No projects yet" testId="projects-empty">
            Projects group stored runs so related work stays together. This list
            shows only projects you have created — it is never populated with
            examples.
          </EmptyState>
        )}

        {projects !== null && projects.length > 0 && (
          <DataTable
            caption="Projects"
            head={[
              { key: 'name', label: 'Project' },
              { key: 'runs', label: 'Runs', numeric: true },
              { key: 'origin', label: 'Origin' },
              { key: 'updated', label: 'Updated' },
              { key: 'act', label: '' },
            ]}
          >
            {projects.map((p) => (
              <tr key={p.id} data-testid={`project-row-${p.id}`}>
                <th scope="row">
                  <span className="wp__runname">{p.name}</span>
                  {p.description && <span className="wp__sub">{p.description}</span>}
                </th>
                <td className="is-numeric">{p.run_count}</td>
                <td>
                  {p.origin === 'demo'
                    ? <Badge tone="warn">Demo</Badge>
                    : <Badge tone="neutral">Mine</Badge>}
                </td>
                <td className="wp__when">
                  {new Date(p.updated_at).toLocaleDateString()}
                </td>
                <td>
                  <div className="wp__rowactions">
                    <Button size="sm" variant="secondary"
                            onClick={() => navigate(`/history?project=${p.id}`)}>
                      View runs
                    </Button>
                    <Button size="sm" variant="ghost"
                            onClick={() => setPendingDelete(p)}
                            data-testid={`delete-project-${p.id}`}>
                      Delete
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </DataTable>
        )}

        {unassigned.length > 0 && (
          <p className="wp__note wp__spaced">
            {unassigned.length} stored run
            {unassigned.length === 1 ? ' is' : 's are'} not assigned to a project.
            Open a run from <strong>Simulation History</strong> to attach it.
          </p>
        )}
      </Card>

      <Dialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="New project"
        footer={
          <>
            <Button variant="ghost" onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button onClick={submitCreate} disabled={busy || !name.trim()}
                    data-testid="confirm-create-project">
              Create project
            </Button>
          </>
        }
      >
        <TextField id="project-name" label="Project name" required
                   value={name} onChange={(e) => setName(e.target.value)} />
        <TextField id="project-desc" label="Description" value={description}
                   onChange={(e) => setDescription(e.target.value)}
                   help="Optional. What this project is investigating." />
      </Dialog>

      <Dialog
        open={pendingDelete !== null}
        onClose={() => setPendingDelete(null)}
        title="Delete this project?"
        footer={
          <>
            <Button variant="ghost" onClick={() => setPendingDelete(null)}>Cancel</Button>
            <Button variant="danger" onClick={confirmDelete}
                    data-testid="confirm-delete-project">
              Delete project
            </Button>
          </>
        }
      >
        <p className="wp__body">
          <strong>{pendingDelete?.name}</strong> will be removed.
        </p>
        <Alert tone="info" title="Your calculated runs are safe">
          Deleting a project does not delete its runs. The{' '}
          {pendingDelete?.run_count ?? 0} run
          {pendingDelete?.run_count === 1 ? '' : 's'} in this project will simply
          become unassigned and stay in Simulation History.
        </Alert>
      </Dialog>
    </>
  );
}
