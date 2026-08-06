/**
 * The organization switcher.
 *
 * Shows organization *authority* separately from scientific assignment, and
 * never merges the two. "Administrator" and "Approver" appear in different
 * places with different wording, because a user who reads "Administrator" and
 * concludes they can approve evidence has misunderstood the one distinction the
 * whole access model rests on.
 */

import { useEffect, useRef, useState } from 'react';

import {
  PROBLEM_MESSAGE, useOrganization, type OrganizationSummary,
} from './OrganizationContext';
import './OrganizationSwitcher.css';

const ADMINISTRATIVE_ROLES = new Set(['owner', 'administrator']);

function roleLabel(role: string): string {
  return role.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

/** One row in the menu. */
function OrganizationOption(
  { organization, isActive, onSelect }: {
    organization: OrganizationSummary;
    isActive: boolean;
    onSelect: (id: number) => void;
  },
) {
  const administrative = ADMINISTRATIVE_ROLES.has(organization.your_role);
  return (
    <li role="none">
      <button
        type="button"
        role="menuitemradio"
        aria-checked={isActive}
        className={`org-option${isActive ? ' org-option--active' : ''}`}
        onClick={() => onSelect(organization.id)}
      >
        <span className="org-option__name">{organization.name}</span>
        <span className="org-option__meta">
          <span
            className={`org-badge${administrative
              ? ' org-badge--admin' : ' org-badge--science'}`}
            data-testid={`org-role-${organization.id}`}
          >
            {administrative ? 'Access' : 'Scientific'}
            {': '}
            {roleLabel(organization.your_role)}
          </span>
          {organization.awaiting_confirmation && (
            <span className="org-badge org-badge--warning">
              Awaiting confirmation
            </span>
          )}
        </span>
      </button>
    </li>
  );
}

export function OrganizationSwitcher() {
  const {
    organizations, active, activeId, problem, loading, select,
  } = useOrganization();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Close on outside click and on Escape. Both are expected of a menu, and
  // their absence is the commonest accessibility failure in this pattern.
  useEffect(() => {
    if (!open) return undefined;
    const onDown = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  if (loading && organizations.length === 0) {
    return (
      <div className="org-switcher org-switcher--loading" aria-busy="true">
        <span className="org-switcher__label">Loading workspace…</span>
      </div>
    );
  }

  // A single organization is not a choice, so it is shown as a label rather
  // than a control that implies there is somewhere else to go.
  const sole = organizations.length === 1 ? organizations[0] : undefined;
  if (sole && problem === 'none') {
    return (
      <div className="org-switcher org-switcher--single">
        <span className="org-switcher__eyebrow">Organization</span>
        <span className="org-switcher__name" data-testid="active-organization">
          {sole.name}
        </span>
      </div>
    );
  }

  const blocking = problem !== 'none' ? PROBLEM_MESSAGE[problem] : null;

  return (
    <div className="org-switcher" ref={containerRef}>
      <span className="org-switcher__eyebrow">Organization</span>

      <button
        type="button"
        className="org-switcher__trigger"
        aria-haspopup="menu"
        aria-expanded={open}
        data-testid="organization-switcher"
        onClick={() => setOpen((v) => !v)}
        disabled={organizations.length === 0}
      >
        <span data-testid="active-organization">
          {active ? active.name : 'Select an organization'}
        </span>
        <span aria-hidden="true" className="org-switcher__caret">▾</span>
      </button>

      {blocking && (
        <p
          className={`org-switcher__problem org-switcher__problem--${problem}`}
          role="status"
          data-testid={`organization-problem-${problem}`}
        >
          <strong>{blocking.title}.</strong> {blocking.body}
        </p>
      )}

      {open && organizations.length > 0 && (
        <ul className="org-switcher__menu" role="menu"
            aria-label="Switch organization">
          {organizations.map((organization) => (
            <OrganizationOption
              key={organization.id}
              organization={organization}
              isActive={organization.id === activeId}
              onSelect={(id) => {
                setOpen(false);
                select(id);
              }}
            />
          ))}
        </ul>
      )}

      {active && (
        <p className="org-switcher__note">
          Records are never shared between organizations. Your role here grants
          {ADMINISTRATIVE_ROLES.has(active.your_role)
            ? ' access administration only — not scientific authority.'
            : ' only what your study assignments allow.'}
        </p>
      )}
    </div>
  );
}
