/**
 * Evidence & Validation.
 *
 * Reports the **verified status of each module**, read from the single
 * navigation registry that also drives the sidebar and every module page. There
 * is one status per module, in one place, so the menu, the placeholder page and
 * this table cannot disagree.
 *
 * This page reports no scientific result of any kind. It is a statement about
 * what is built and connected, not about what any engine calculated. The
 * scientific blockers it lists are the ones recorded in
 * `docs/MODULE_INVENTORY.md`; none of them is resolved by this page existing.
 */

import { Badge, Card, DataTable } from '../design-system/components';
import {
  NAV_GROUPS, STATUS_META, type ModuleStatus,
} from '../shell/navigation';
import './workspace/WorkspacePages.css';

/** What each status permits the interface to display. */
const WHAT_IT_MAY_SHOW: Record<ModuleStatus, string> = {
  operational:
    'Calculated output, from a genuine engine, with its version recorded.',
  limited_prototype:
    'Calculated output, with its stated limitation shown alongside it.',
  calibration_required:
    'No result. The engine runs but its constants are uncalibrated.',
  migration_in_progress:
    'No result. The legacy implementation exists but is not connected.',
  not_operational:
    'No result of any kind. An honest unavailable state only.',
};

export default function EvidencePage() {
  const modules = NAV_GROUPS.flatMap(
    (g) => g.items.map((item) => ({ group: g.label, item })));

  const counts = modules.reduce<Record<string, number>>((acc, { item }) => {
    acc[item.status] = (acc[item.status] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <>
      <Card
        title="Evidence & Validation"
        subtitle={
          'The verified build status of every module. This page reports what is '
          + 'connected — it reports no scientific result and validates no model.'
        }
        accent
      >
        <div className="wp__filters" data-testid="evidence-counts">
          {(Object.keys(STATUS_META) as ModuleStatus[]).map((status) => (
            <span key={status} className="wp__countchip">
              <Badge tone={STATUS_META[status].tone} dot>
                {STATUS_META[status].label}
              </Badge>
              <strong>{counts[status] ?? 0}</strong>
            </span>
          ))}
        </div>

        <DataTable
          caption="Module status"
          head={[
            { key: 'module', label: 'Module' },
            { key: 'group', label: 'Section' },
            { key: 'status', label: 'Status' },
            { key: 'shows', label: 'What it may display' },
            { key: 'summary', label: 'Verified position' },
          ]}
        >
          {modules.map(({ group, item }) => (
            <tr key={item.key} data-testid={`evidence-row-${item.key}`}>
              <th scope="row">{item.label}</th>
              <td className="wp__when">{group}</td>
              <td>
                <Badge tone={STATUS_META[item.status].tone} dot>
                  {STATUS_META[item.status].label}
                </Badge>
              </td>
              <td>{WHAT_IT_MAY_SHOW[item.status]}</td>
              <td>{item.summary}</td>
            </tr>
          ))}
        </DataTable>
      </Card>

      <Card title="What this page is not">
        <p className="wp__body">
          Nothing here constitutes scientific validation. No model on this
          platform has been validated against experimental or clinical outcome
          data. A module marked <strong>Operational</strong> means its genuine
          engine is connected and its version is recorded with every result — it
          does not mean the model is accurate, calibrated, or fit for clinical
          use.
        </p>
        <p className="wp__body">
          The recorded scientific blockers are maintained in the repository at{' '}
          <span className="mono">docs/MODULE_INVENTORY.md</span>. They are not
          resolved, and no output on this platform should be used to make a
          treatment decision.
        </p>
      </Card>
    </>
  );
}
