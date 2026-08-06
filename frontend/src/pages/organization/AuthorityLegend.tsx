/**
 * The one thing these screens must not let a user get wrong.
 *
 * "Administrator" and "Approver" are not two points on one ladder. An
 * administrator manages people and access and cannot approve a single
 * experiment; an approver holds scientific authority on named studies and
 * cannot add or remove anybody. A reader who takes "Administrator" to mean
 * "can do everything, including approve" has misunderstood the distinction the
 * whole access model rests on — and would then read an approval as having come
 * from the most privileged account rather than from an independent scientist.
 *
 * So authority is never rendered as a single role column. It is rendered as
 * two visually distinct things, with the kind named in words rather than
 * carried by colour, and this component is the shared vocabulary for it.
 */

import { Badge } from '../../design-system/components';
import { isAdministrativeRole, roleLabel } from '../../api/organizationClient';

/** Which ladder a role belongs to. */
export type AuthorityKind = 'authority' | 'scientific' | 'read-only';

export function authorityKind(role: string): AuthorityKind {
  if (isAdministrativeRole(role)) return 'authority';
  if (role === 'auditor') return 'read-only';
  return 'scientific';
}

const KIND_LABEL: Record<AuthorityKind, string> = {
  authority: 'Organization authority',
  scientific: 'Scientific eligibility',
  'read-only': 'Read-only',
};

/**
 * One role, labelled with the kind of authority it is.
 *
 * The kind is in the text, not only in the colour. A colour-only distinction
 * between "manages access" and "approves evidence" is invisible to a
 * colour-blind reader and to anybody printing the page for an audit file.
 */
export function RoleBadge({ role, testId }: {
  role: string; testId?: string;
}) {
  const kind = authorityKind(role);
  const tone = kind === 'authority' ? 'warn'
    : kind === 'scientific' ? 'accent' : 'neutral';
  return (
    <span className="org-role-badge" data-testid={testId}>
      <span className="org-role-badge__kind">{KIND_LABEL[kind]}</span>
      <Badge tone={tone} dot>{roleLabel(role)}</Badge>
    </span>
  );
}

/** Explains the separation once per screen, above the tables. */
export function AuthorityLegend() {
  return (
    <div className="org-legend" data-testid="authority-legend">
      <p className="org-legend__lead">
        <strong>Organization authority and scientific authority are separate.</strong>{' '}
        Holding one never grants the other.
      </p>
      <dl className="org-legend__grid">
        <div>
          <dt><Badge tone="warn" dot>Organization authority</Badge></dt>
          <dd>
            Owners and administrators add and remove people, change roles and
            end collaborations. They <strong>cannot</strong> submit, review or
            approve any experiment.
          </dd>
        </div>
        <div>
          <dt><Badge tone="accent" dot>Scientific eligibility</Badge></dt>
          <dd>
            Researchers, laboratory contributors, reviewers and approvers are
            <em> eligible</em> for scientific work. Capability comes only from
            an explicit assignment on a named study.
          </dd>
        </div>
        <div>
          <dt><Badge tone="neutral" dot>Read-only</Badge></dt>
          <dd>
            Auditors read records and access history and can change nothing at
            all, which is what makes the role suitable for an audit.
          </dd>
        </div>
      </dl>
    </div>
  );
}
