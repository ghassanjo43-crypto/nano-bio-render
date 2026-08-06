/**
 * Dashboard — workspace command centre.
 *
 * Honesty rules enforced structurally:
 *  - No invented counts, rates, projects, simulations or activity.
 *  - Module availability is derived from the navigation model, so the dashboard
 *    cannot claim a module works when the menu says otherwise.
 *  - "Recent activity" renders an onboarding empty state because no activity
 *    store exists yet. It is never seeded with example rows.
 */

import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import {
  Alert, Badge, Button, Card, EmptyState, SectionHeading,
} from '../design-system/components';
import { Icon, type IconName } from '../shell/Icon';
import {
  NAV_ITEMS, STATUS_META, visibleNavItems, type NavItem,
} from '../shell/navigation';
import './DashboardPage.css';

interface ValidationRow { term: string; value: string; flag?: boolean }

const VALIDATION_ROWS: readonly ValidationRow[] = [
  { term: 'Prediction basis', value: 'Rule-based physicochemical heuristics' },
  { term: 'Evidence level', value: 'Literature-informed, unvalidated' },
  { term: 'Experimental validation', value: 'None', flag: true },
  { term: 'Composite overall score', value: 'Not implemented — pending review' },
  { term: 'Uncertainty quantification', value: 'Not implemented' },
];

export default function DashboardPage() {
  const { user } = useAuth();
  const items = visibleNavItems(user?.role);

  const operational = items.filter((i) => i.status === 'operational' && i.key !== 'home');
  const unavailable = items.filter((i) => i.status !== 'operational');
  const availableCount = NAV_ITEMS.filter((i) => i.status === 'operational').length;
  const pct = Math.round((availableCount / NAV_ITEMS.length) * 100);

  // Use the whole display name: splitting on the first token mangles names
  // like "Platform Administrator" into "Platform".
  const displayName = user?.full_name || user?.username || '';

  return (
    <div className="dash">
      {/* ------------------------------------------------------- hero */}
      <section className="dash__hero">
        <div className="dash__hero-text">
          <p className="eyebrow">Research workspace</p>
          <h2 className="dash__hero-title">
            Welcome{displayName ? `, ${displayName}` : ''}
          </h2>
          <p className="dash__hero-body">
            Design nanoparticle formulations and evaluate them with the canonical
            scientific engine. Every result carries its inputs, model version,
            evidence level and limitations so it can be reproduced and reviewed.
          </p>
          <div className="dash__hero-actions">
            <Link to="/start" data-testid="quick-action-design">
              <Button size="lg" iconRight={<Icon name="arrow-right" size={16} />}>
                Open design workflow
              </Button>
            </Link>
            <Link className="dash__hero-link" to="/assessments">
              Explore scientific assessments
            </Link>
          </div>
        </div>
        <div className="dash__hero-visual" aria-hidden="true">
          <svg viewBox="0 0 260 200">
            <defs>
              <radialGradient id="dashGlow" cx="50%" cy="45%">
                <stop offset="0%" stopColor="#7ad4e8" stopOpacity="0.42" />
                <stop offset="100%" stopColor="#0d8ba6" stopOpacity="0" />
              </radialGradient>
            </defs>
            <circle cx="130" cy="98" r="86" fill="url(#dashGlow)" />
            {[0, 45, 90, 135].map((r) => (
              <ellipse key={r} cx="130" cy="98" rx="88" ry="38" fill="none"
                       stroke="#7ad4e8" strokeOpacity="0.28" strokeWidth="1"
                       transform={`rotate(${r} 130 98)`} />
            ))}
            <circle cx="130" cy="98" r="26" fill="#0a6c82" fillOpacity="0.5"
                    stroke="#7ad4e8" strokeOpacity="0.55" strokeWidth="1.4" />
            <circle cx="205" cy="62" r="5" fill="#7ad4e8" fillOpacity="0.7" />
            <circle cx="58" cy="132" r="4" fill="#7ad4e8" fillOpacity="0.55" />
          </svg>
        </div>
      </section>

      <Alert tone="warn" title="Computational research use only" role="note">
        All outputs are modelled, rule-based results intended for research
        planning. They are <strong>not experimentally validated</strong>, not
        clinically validated, and are not regulatory approval predictions,
        diagnoses or treatment recommendations.
      </Alert>

      {/* ------------------------------------------------------- grid */}
      <div className="dash__grid">
        <Card
          className="dash__span2"
          title="Available modules"
          subtitle="These run real calculations against the scientific engine."
        >
          {operational.length === 0 ? (
            <EmptyState title="No modules available" />
          ) : (
            <ul className="dash__modules" data-testid="available-modules">
              {operational.map((m) => (
                <li key={m.key}>
                  <Link to={m.path} className="dash__module">
                    <span className="dash__module-icon">
                      <Icon name={m.icon as IconName} size={20} />
                    </span>
                    <span className="dash__module-text">
                      <span className="dash__module-name">
                        {m.label}
                        <Badge tone="success" dot>Operational</Badge>
                      </span>
                      <span className="dash__module-desc">{m.summary}</span>
                    </span>
                    <Icon name="chevron-right" size={16} className="dash__module-chev" />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Platform migration status">
          <p className="dash__muted">
            The platform is migrating from the legacy application one verified
            module at a time.
          </p>
          <div className="dash__progress">
            <div className="dash__progress-track">
              <div className="dash__progress-fill" style={{ width: `${pct}%` }} />
            </div>
            <p className="dash__progress-text" data-testid="migration-progress">
              <strong>{availableCount} of {NAV_ITEMS.length}</strong> modules available
            </p>
          </div>
          <ul className="dash__legend">
            {(['operational', 'limited_prototype', 'migration_in_progress',
               'calibration_required', 'not_operational'] as const).map((s) => (
              <li key={s}>
                <span className={`dash__legend-dot dash__legend-dot--${STATUS_META[s].tone}`} />
                {STATUS_META[s].label}
              </li>
            ))}
          </ul>
        </Card>

        <Card title="Scientific validation status">
          <dl className="dash__kv">
            {VALIDATION_ROWS.map((r) => (
              <div key={r.term}>
                <dt>{r.term}</dt>
                <dd className={r.flag ? 'is-flag' : undefined}>{r.value}</dd>
              </div>
            ))}
          </dl>
          <p className="dash__muted dash__small">
            Results support research planning and must be confirmed by
            laboratory work.
          </p>
        </Card>

        <Card
          className="dash__span2"
          title="Recent activity"
          subtitle="Populated from stored records once persistence is available."
        >
          <EmptyState
            testId="activity-empty"
            icon={<Icon name="clock" size={22} />}
            title="No activity recorded yet"
            action={
              <Link to="/start">
                <Button variant="secondary" size="sm"
                        iconRight={<Icon name="arrow-right" size={15} />}>
                  Start a design session
                </Button>
              </Link>
            }
          >
            Design and simulation history is not stored yet, so there is nothing
            to display. This panel stays empty rather than showing example
            entries that could be mistaken for real work.
          </EmptyState>
        </Card>

        <Card title="Not yet available" subtitle="Honest status for each module.">
          <ul className="dash__pending" data-testid="unavailable-modules">
            {unavailable.map((m: NavItem) => (
              <li key={m.key}>
                <Link to={m.path} className="dash__pending-row">
                  <span className="dash__pending-name">{m.label}</span>
                  <Badge tone={STATUS_META[m.status].tone} dot>
                    {STATUS_META[m.status].label}
                  </Badge>
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <SectionHeading
        eyebrow="Getting started"
        title="How a calculation works"
        description="Three steps from formulation parameters to a traceable, reviewable result."
      />
      <ol className="dash__steps">
        {[
          { n: 1, t: 'Describe the formulation', b: 'Core properties, surface chemistry and targeting configuration, with units and definitions inline.' },
          { n: 2, t: 'Review before calculating', b: 'Confirm exactly which values will be sent and which canonical defaults will apply.' },
          { n: 3, t: 'Read the result in context', b: 'Component scores with model version, evidence level, warnings and limitations attached.' },
        ].map((s) => (
          <li key={s.n} className="dash__step">
            <span className="dash__step-n">{s.n}</span>
            <div>
              <p className="dash__step-title">{s.t}</p>
              <p className="dash__step-body">{s.b}</p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
