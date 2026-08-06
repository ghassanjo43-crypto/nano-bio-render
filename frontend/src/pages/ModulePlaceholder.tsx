/**
 * Honest placeholder for a module that is not yet available.
 *
 * Rules: state the true status, describe what the module will provide and the
 * workflow it will offer, and point at a module that does work. Never render a
 * score, chart, table of results, project, activity row or AI output. Never
 * render a button that looks functional but does nothing.
 */

import { Link } from 'react-router-dom';
import { Alert, Badge, Button, Card } from '../design-system/components';
import { Icon, type IconName } from '../shell/Icon';
import { STATUS_META, findNavItem, type NavItem } from '../shell/navigation';
import './ModulePlaceholder.css';

export default function ModulePlaceholder({ item }: { item: NavItem }) {
  const meta = STATUS_META[item.status];
  const related = item.relatedKey ? findNavItem(item.relatedKey) : undefined;
  const notOperational = item.status === 'not_operational';

  return (
    <div className="ph">
      <Card className="ph__main">
        <div data-testid="module-placeholder">
          <div className="ph__head">
            <span className="ph__icon" aria-hidden="true">
              <Icon name={item.icon as IconName} size={26} />
            </span>
            <div className="ph__headtext">
              <div className="ph__titlerow">
                <h2 className="ph__title">{item.label}</h2>
                <span data-testid="module-status">
                  <Badge tone={meta.tone} dot>{meta.label}</Badge>
                </span>
              </div>
              <p className="ph__summary">{item.summary}</p>
            </div>
          </div>

          <Alert
            tone={notOperational ? 'danger' : 'info'}
            title={notOperational
              ? 'This module cannot run in the current build'
              : 'This module has not been migrated yet'}
          >
            <p>
              <strong>No data is shown here.</strong>{' '}
              {notOperational
                ? 'Rather than displaying placeholder figures that could be mistaken '
                  + 'for findings, this page shows nothing until the module genuinely works.'
                : 'This page is deliberately empty rather than populated with example '
                  + 'values. It will show real results once the module is migrated and verified.'}
            </p>
          </Alert>

          {item.workflow && (
            <section className="ph__workflow" aria-labelledby={`wf-${item.key}`}>
              <h3 className="ph__subhead" id={`wf-${item.key}`}>Planned workflow</h3>
              <ol className="ph__steps">
                {item.workflow.map((s, i) => (
                  <li key={s}>
                    <span className="ph__stepn" aria-hidden="true">{i + 1}</span>
                    <span>{s}</span>
                  </li>
                ))}
              </ol>
            </section>
          )}

          {item.key === 'ai-co-designer' && (
            <div className="ph__notice" data-testid="ai-notice">
              <h3 className="ph__subhead">Why this is unavailable</h3>
              <p>
                The optimisation engine cannot currently run. An earlier version
                of this screen displayed ranked candidate designs, score metrics,
                sensitivity curves and an audit trail — <strong>all of which were
                fixed placeholder values, not the output of any optimisation</strong>.
                They were removed and will not be restored.
              </p>
              <p>
                The feature returns only once the engine executes for real and
                every candidate can be traced to the run, objectives and
                constraints that produced it.
              </p>
            </div>
          )}
        </div>
      </Card>

      <aside className="ph__aside">
        <Card title="Status">
          <dl className="ph__status">
            <div>
              <dt>Availability</dt>
              <dd><Badge tone={meta.tone} dot>{meta.label}</Badge></dd>
            </div>
            <div>
              <dt>Scientific output</dt>
              <dd>None produced</dd>
            </div>
            <div>
              <dt>Stored data</dt>
              <dd>None</dd>
            </div>
          </dl>
        </Card>

        {related && (
          <Card title="Available instead">
            <p className="ph__relatedtext">{related.summary}</p>
            <Link to={related.path} className="ph__relatedlink">
              <Button variant="secondary" fullWidth
                      iconRight={<Icon name="arrow-right" size={15} />}>
                Open {related.label}
              </Button>
            </Link>
          </Card>
        )}

        <Card title="Research use only">
          <p className="ph__relatedtext">
            When this module becomes available, its outputs will remain
            computational research-planning results: not experimentally
            validated, not clinically validated, and not a substitute for
            wet-lab testing.
          </p>
        </Card>
      </aside>
    </div>
  );
}
