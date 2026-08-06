/**
 * The one study list, parameterised by pathway.
 *
 * My Studies, Patient Assessments, Research Designs and Simulation History are
 * four views of the same stored records, not four modules. They share this
 * component and differ only in the pathway they filter on and the words around
 * the table. Duplicating the list four times to fill the menu would guarantee
 * four different notions of what a study is.
 *
 * Every row is a record the backend actually holds. Nothing here is seeded,
 * sampled or invented: an empty list renders an empty state, never fabricated
 * "recent activity".
 *
 * Demo-generated and synthetic-input studies are labelled on every row, so a
 * demonstration can never be mistaken for the user's own research work.
 *
 * No patient identifier appears in this component. `report_assessment_id` is an
 * opaque integer and is deliberately never rendered as a person.
 */

import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { deleteRun, listRuns } from '../../api/client';
import type { RunSummary, WorkspaceErrorResponse } from '../../api/types';
import {
  Alert, Badge, Button, Card, DataTable, Dialog, EmptyState, SelectField,
  SkeletonBlock,
} from '../../design-system/components';
import { Icon } from '../../shell/Icon';
import type { StudyPathway } from '../../shell/navigation';
import './WorkspacePages.css';

const STATUS_TONE = {
  complete: 'success',
  partial: 'warn',
  blocked: 'neutral',
} as const;

const STATUS_LABEL = {
  complete: 'All engines ran',
  partial: 'Some engines ran',
  blocked: 'Nothing calculated',
} as const;

export const PATHWAY_LABEL: Record<StudyPathway, string> = {
  patient_assessment: 'Patient assessment',
  research_design: 'Research design',
  demo_scenario: 'Demonstration',
};

const PATHWAY_TONE = {
  patient_assessment: 'info',
  research_design: 'accent',
  demo_scenario: 'warn',
} as const;

/**
 * Describe a pathway without assuming the server sent a known one.
 *
 * A record stored before pathways existed, or returned by an older backend,
 * carries no pathway. The honest answer is "not recorded" — not a guess, and
 * not a crash. TypeScript cannot enforce this: the value crosses the network
 * as `unknown` and is only asserted to be a `StudyPathway` at the boundary.
 */
function describePathway(pathway: StudyPathway | undefined) {
  if (pathway && pathway in PATHWAY_LABEL) {
    return { label: PATHWAY_LABEL[pathway], tone: PATHWAY_TONE[pathway] };
  }
  return { label: 'Not recorded', tone: 'neutral' as const };
}

export interface StudyListPageProps {
  /** Restrict the list to one pathway. Omit to show every study. */
  pathway?: StudyPathway;
  title: string;
  subtitle: string;
  /** Shown when the list is empty. Must not imply results exist. */
  emptyTitle: string;
  emptyBody: string;
  testId: string;
  /** Show the origin filter. Pointless on a single-pathway list. */
  showPathwayColumn?: boolean;
}

export default function StudyListPage({
  pathway, title, subtitle, emptyTitle, emptyBody, testId,
  showPathwayColumn = true,
}: StudyListPageProps) {
  const navigate = useNavigate();
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [error, setError] = useState<WorkspaceErrorResponse | null>(null);
  const [disease, setDisease] = useState('');
  const [status, setStatus] = useState('');
  const [selected, setSelected] = useState<number[]>([]);
  const [pendingDelete, setPendingDelete] = useState<RunSummary | null>(null);

  const refresh = useCallback(async (signal?: AbortSignal) => {
    const result = await listRuns({ pathway, disease, status }, signal);
    if (result.status === 'error') {
      setError(result.error);
      setRuns([]);
      return;
    }
    setError(null);
    setRuns(result.data.runs);
  }, [pathway, disease, status]);

  useEffect(() => {
    const controller = new AbortController();
    void refresh(controller.signal);
    return () => controller.abort();
  }, [refresh]);

  // Filter options come from the records actually returned, so the control can
  // never offer an indication for which nothing is stored.
  const diseases = Array.from(
    new Set((runs ?? []).map((r) => r.disease).filter(Boolean) as string[]));

  function toggle(id: number) {
    setSelected((prev) => prev.includes(id)
      ? prev.filter((x) => x !== id)
      : prev.length >= 4 ? prev : [...prev, id]);
  }

  async function confirmDelete() {
    if (!pendingDelete) return;
    const result = await deleteRun(pendingDelete.id);
    setPendingDelete(null);
    if (result.status === 'error') { setError(result.error); return; }
    setSelected((prev) => prev.filter((x) => x !== pendingDelete.id));
    void refresh();
  }

  return (
    <>
      <Card
        title={title}
        subtitle={subtitle}
        accent
        actions={
          <Button
            disabled={selected.length < 2}
            onClick={() => navigate(`/compare?ids=${selected.join(',')}`)}
            iconLeft={<Icon name="compare" size={15} />}
            data-testid="compare-selected"
          >
            Compare {selected.length > 0 ? `(${selected.length})` : ''}
          </Button>
        }
      >
        <div className="wp__filters">
          <SelectField
            id="filter-disease" label="Indication" value={disease}
            onChange={(e) => setDisease(e.target.value)}
            options={[{ value: '', label: 'All indications' },
                      ...diseases.map((d) => ({ value: d, label: d }))]}
          />
          <SelectField
            id="filter-status" label="Status" value={status}
            onChange={(e) => setStatus(e.target.value)}
            options={[
              { value: '', label: 'Any status' },
              { value: 'complete', label: 'All engines ran' },
              { value: 'partial', label: 'Some engines ran' },
              { value: 'blocked', label: 'Nothing calculated' },
            ]}
          />
        </div>

        {error && (
          <Alert tone="danger" title="Studies unavailable">
            <p>{error.message}</p>
            {error.detail && <p className="mono wp__detail">{error.detail}</p>}
          </Alert>
        )}

        {runs === null && <SkeletonBlock lines={4} />}

        {runs !== null && runs.length === 0 && !error && (
          <EmptyState title={emptyTitle} testId={`${testId}-empty`}>
            {emptyBody}
            <div className="wp__emptyactions">
              <Button variant="secondary" onClick={() => navigate('/demo')}
                      iconLeft={<Icon name="flask" size={15} />}>
                Open the Demo Workspace
              </Button>
              <Button onClick={() => navigate('/start')}
                      iconRight={<Icon name="arrow-right" size={15} />}>
                Start a new study
              </Button>
            </div>
          </EmptyState>
        )}

        {runs !== null && runs.length > 0 && (
          <DataTable
            caption={title}
            head={[
              { key: 'sel', label: 'Compare', width: '84px' },
              { key: 'name', label: 'Study' },
              ...(showPathwayColumn
                ? [{ key: 'pathway', label: 'Pathway' }]
                : []),
              { key: 'context', label: 'Indication' },
              { key: 'engines', label: 'Engines' },
              { key: 'status', label: 'Status' },
              { key: 'when', label: 'Created' },
              { key: 'act', label: '' },
            ]}
          >
            {runs.map((r) => (
              <tr key={r.id} data-testid={`run-row-${r.id}`}>
                <td>
                  <label className="wp__check">
                    <input
                      type="checkbox"
                      checked={selected.includes(r.id)}
                      onChange={() => toggle(r.id)}
                      aria-label={`Select ${r.name} for comparison`}
                      disabled={!selected.includes(r.id) && selected.length >= 4}
                    />
                  </label>
                </td>
                <th scope="row">
                  <span className="wp__runname">{r.name}</span>
                  {r.inputs_are_synthetic && (
                    <Badge tone="warn" className="wp__originbadge">
                      Synthetic inputs
                    </Badge>
                  )}
                </th>
                {showPathwayColumn && (
                  <td>
                    <Badge tone={describePathway(r.pathway).tone}>
                      {describePathway(r.pathway).label}
                    </Badge>
                    {r.research_purpose && (
                      <span className="wp__sub">{r.research_purpose}</span>
                    )}
                  </td>
                )}
                <td>
                  {r.disease ?? <span className="wp__none">not recorded</span>}
                  {r.subtype && <span className="wp__sub">{r.subtype}</span>}
                </td>
                <td>
                  <ul className="wp__englist">
                    {r.has_design_result && <li>Design score</li>}
                    {r.has_pk_result && <li>PK simulation</li>}
                    {!r.has_design_result && !r.has_pk_result && (
                      <li className="wp__none">none</li>
                    )}
                  </ul>
                </td>
                <td>
                  <Badge tone={STATUS_TONE[r.status]} dot>
                    {STATUS_LABEL[r.status]}
                  </Badge>
                </td>
                <td className="wp__when">
                  {new Date(r.created_at).toLocaleString()}
                </td>
                <td>
                  <div className="wp__rowactions">
                    <Button size="sm" variant="secondary"
                            onClick={() => navigate(`/studies/${r.id}`)}>
                      Open
                    </Button>
                    <Button size="sm" variant="ghost"
                            onClick={() => setPendingDelete(r)}
                            data-testid={`delete-run-${r.id}`}>
                      Delete
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </DataTable>
        )}
      </Card>

      <Dialog
        open={pendingDelete !== null}
        onClose={() => setPendingDelete(null)}
        title="Delete this study?"
        footer={
          <>
            <Button variant="ghost" onClick={() => setPendingDelete(null)}>
              Cancel
            </Button>
            <Button variant="danger" onClick={confirmDelete}
                    data-testid="confirm-delete-run">
              Delete study
            </Button>
          </>
        }
      >
        <p className="wp__body">
          <strong>{pendingDelete?.name}</strong> and its stored inputs and
          results will be permanently removed. This cannot be undone, and the
          calculation would have to be re-run to recover it.
        </p>
      </Dialog>
    </>
  );
}
