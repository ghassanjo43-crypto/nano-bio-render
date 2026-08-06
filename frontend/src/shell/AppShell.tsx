/**
 * Authenticated application shell.
 *
 * Layout: fixed header, collapsible grouped sidebar, scrolling content region.
 * At tablet width the sidebar collapses to icons; at mobile width it becomes an
 * off-canvas drawer with a focus-trapping overlay.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { checkHealth } from '../api/client';
import { unreadNotificationCount } from '../api/notificationClient';
import { useAuth } from '../auth/AuthContext';
import { Badge, Button, Dialog, Tooltip } from '../design-system/components';
import { useWorkflow } from '../workflow/WorkflowContext';
import { BrandMark, Icon, type IconName } from './Icon';
import { OrganizationSwitcher } from '../organizations/OrganizationSwitcher';
import StudyContextBar, { type StudyContext } from './StudyContextBar';
import { STATUS_META, activeNavKeyForPath, isStudyWorkflowActive,
  pageTitleForPath, visibleGroups }
  from './navigation';
import './AppShell.css';

const ROLE_LABEL: Record<string, string> = {
  admin: 'Administrator',
  researcher: 'Researcher',
  viewer: 'Viewer',
};

const MOBILE_BREAKPOINT = 900;

export default function AppShell() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [collapsed, setCollapsed] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [signOutOpen, setSignOutOpen] = useState(false);
  const [apiUp, setApiUp] = useState<boolean | null>(null);
  const [unreadNotifications, setUnreadNotifications] = useState(0);

  const menuRef = useRef<HTMLDivElement>(null);
  const { session, hasResumableSession } = useWorkflow();

  const groups = visibleGroups(user?.role);
  // One resolution per render, shared by every nav row and the breadcrumbs, so
  // the sidebar and the trail cannot disagree about where the user is.
  //
  // The pathway is part of the input because /workflow/* is shared by all three
  // pathways: the route alone cannot say whether the user is in a patient
  // assessment or a research design. Only the study knows.
  const navContext = { pathway: session.pathway };
  const activeKey = activeNavKeyForPath(location.pathname, navContext);

  // The study context header appears only where a study is genuinely open.
  // Elsewhere there is no study, and asserting one would be false.
  const studyContext: StudyContext | undefined =
    isStudyWorkflowActive(location.pathname) && hasResumableSession
      ? {
          pathway: session.pathway,
          name: session.name,
          disease: session.selection.disease || undefined,
          // Demonstration inputs are synthetic by definition. This flag is
          // never set from an assumption about a user's own data.
          synthetic: session.pathway === 'demo_scenario',
        }
      : undefined;

  /* Poll the backend so the status indicator reflects reality. */
  useEffect(() => {
    let alive = true;
    const probe = () => { checkHealth().then((ok) => { if (alive) setApiUp(ok); }); };
    probe();
    const t = window.setInterval(probe, 30_000);
    return () => { alive = false; window.clearInterval(t); };
  }, []);

  useEffect(() => {
    let alive = true;
    const probe = () => unreadNotificationCount().then((result) => {
      if (alive && result.status === 'ok') setUnreadNotifications(result.data.unread_count);
    });
    void probe();
    const timer = window.setInterval(probe, 30_000);
    window.addEventListener('nanobio:notifications-changed', probe);
    return () => {
      alive = false;
      window.clearInterval(timer);
      window.removeEventListener('nanobio:notifications-changed', probe);
    };
  }, [location.pathname]);

  /* Close the mobile drawer whenever the route changes. */
  useEffect(() => { setDrawerOpen(false); }, [location.pathname]);

  /* Dismiss the profile menu on outside click or Escape. */
  useEffect(() => {
    if (!menuOpen) return;
    const onDown = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setMenuOpen(false); };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [menuOpen]);

  const handleSignOut = useCallback(async () => {
    setSignOutOpen(false);
    await signOut();
    navigate('/login', { replace: true });
  }, [signOut, navigate]);

  const toggleSidebar = () => {
    if (window.innerWidth <= MOBILE_BREAKPOINT) setDrawerOpen((v) => !v);
    else setCollapsed((v) => !v);
  };

  const initials = (user?.full_name || user?.username || '?')
    .split(' ').slice(0, 2).map((s) => s.charAt(0).toUpperCase()).join('');

  // Never contains the study name: the title reaches the browser tab and the
  // session history, and the name is user-supplied text.
  const pageTitle = pageTitleForPath(location.pathname);

  return (
    <div className={`shell ${collapsed ? 'shell--collapsed' : ''} ${drawerOpen ? 'shell--drawer' : ''}`}>
      <a className="skip-link" href="#main-content">Skip to main content</a>

      {/* ------------------------------------------------------- sidebar */}
      <aside className="shell__sidebar" id="app-sidebar">
        <div className="shell__brand">
          <BrandMark size={30} />
          <span className="shell__brand-text">
            <span className="shell__brand-name">NanoBio Studio</span>
            <span className="shell__brand-sub">Research Platform</span>
          </span>
        </div>

        <nav className="shell__nav" aria-label="Main navigation">
          {groups.map((group) => (
            <div className="shell__navgroup" key={group.id}>
              <p className="shell__navgroup-label" aria-hidden={collapsed}>{group.label}</p>
              <ul>
                {group.items.map((item) => {
                  const meta = STATUS_META[item.status];
                  // Active state comes from the centralized route-family
                  // resolver, NOT from NavLink's exact-path matching. The design
                  // workflow spans /start and every /workflow/* route, so exact
                  // matching dropped the indicator the moment the user left the
                  // session gate. Resolving here also guarantees exactly one
                  // principal item is ever active.
                  const isActive = activeKey === item.key;
                  // A plain Link, not NavLink: NavLink derives `aria-current`
                  // from its OWN exact-path matching and overrides the prop, so
                  // it would strip the attribute on every route the resolver
                  // considers active but NavLink does not (/workflow/* above
                  // all). Two competing sources of truth; the resolver wins.
                  const link = (
                    <Link
                      to={item.path}
                      className={`shell__navlink ${isActive ? 'is-active' : ''}`}
                      aria-current={isActive ? 'page' : undefined}
                      aria-label={collapsed ? `${item.label} — ${meta.label}` : undefined}
                    >
                      <span className="shell__navicon"><Icon name={item.icon as IconName} /></span>
                      <span className="shell__navlabel">{item.label}</span>
                      {/* Active state must not rest on colour alone. */}
                      {isActive && <span className="sr-only"> (current page)</span>}
                      {item.status !== 'operational' && (
                        <span
                          className={`shell__navdot shell__navdot--${meta.tone}`}
                          title={meta.label}
                        >
                          <span className="sr-only">{meta.label}</span>
                        </span>
                      )}
                    </Link>
                  );
                  return (
                    <li key={item.key}>
                      {collapsed
                        ? <Tooltip content={`${item.label} — ${meta.label}`} side="bottom">{link}</Tooltip>
                        : link}
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>

        <div className="shell__sidebar-foot">
          <button
            type="button"
            className="shell__collapse"
            onClick={() => setCollapsed((v) => !v)}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            aria-expanded={!collapsed}
            aria-controls="app-sidebar"
          >
            <Icon name={collapsed ? 'chevron-right' : 'chevron-left'} size={16} />
            <span className="shell__navlabel">Collapse</span>
          </button>
        </div>
      </aside>

      {drawerOpen && (
        <div
          className="shell__scrim"
          onClick={() => setDrawerOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* -------------------------------------------------------- header */}
      <header className="shell__header">
        <div className="shell__header-left">
          <button
            type="button"
            className="shell__menubtn"
            onClick={toggleSidebar}
            aria-label="Toggle navigation"
            aria-controls="app-sidebar"
            aria-expanded={drawerOpen}
            data-testid="sidebar-toggle"
          >
            <Icon name="menu" size={19} />
          </button>
          <div className="shell__titleblock">
            <h1 className="shell__pagetitle">{pageTitle}</h1>
          </div>
        </div>

        <div className="shell__header-right">
          <OrganizationSwitcher />
          <Link className="shell__notifications" to="/notifications"
                aria-label={`Notifications, ${unreadNotifications} unread`}>
            <Icon name="bell" size={19} />
            {unreadNotifications > 0 && <span className="shell__notification-count">
              {unreadNotifications > 99 ? '99+' : unreadNotifications}
            </span>}
          </Link>
          <span
            className={`shell__api shell__api--${apiUp === null ? 'unknown' : apiUp ? 'up' : 'down'}`}
            data-testid="backend-status"
            title={apiUp ? 'Scientific API reachable' : 'Scientific API unreachable'}
          >
            <span className="shell__api-dot" aria-hidden="true" />
            <span className="shell__api-text">
              {apiUp === null ? 'Checking API' : apiUp ? 'API connected' : 'API unreachable'}
            </span>
          </span>

          <Badge tone="warn" className="shell__usebadge">Research use only</Badge>

          <div className="shell__user" ref={menuRef}>
            <button
              type="button"
              className="shell__userbtn"
              onClick={() => setMenuOpen((v) => !v)}
              aria-expanded={menuOpen}
              aria-haspopup="menu"
              data-testid="user-menu-button"
            >
              <span className="shell__avatar" aria-hidden="true">{initials}</span>
              <span className="shell__usermeta">
                <span className="shell__username" data-testid="user-name">
                  {user?.full_name || user?.username}
                </span>
                <span className="shell__userrole" data-testid="user-role">
                  {ROLE_LABEL[user?.role ?? ''] ?? user?.role}
                </span>
              </span>
            </button>

            {menuOpen && (
              <div className="shell__dropdown" role="menu">
                <div className="shell__dropdown-head">
                  <span className="shell__avatar shell__avatar--lg" aria-hidden="true">{initials}</span>
                  <div>
                    <p className="shell__dropdown-name">{user?.full_name || user?.username}</p>
                    {user?.email && <p className="shell__dropdown-email">{user.email}</p>}
                    <Badge tone="accent" className="shell__dropdown-role">
                      {ROLE_LABEL[user?.role ?? ''] ?? user?.role}
                    </Badge>
                  </div>
                </div>
                <button
                  type="button" role="menuitem" className="shell__dropdown-item"
                  onClick={() => { setMenuOpen(false); navigate('/settings'); }}
                >
                  <Icon name="user" size={16} /> Profile &amp; settings
                </button>
                {/* Reachable in two clicks from anywhere. Somebody who thinks
                    their account is compromised should not have to find this
                    in a settings tree — the session list is what answers "am I
                    signed in somewhere I should not be?". */}
                <button
                  type="button" role="menuitem" className="shell__dropdown-item"
                  onClick={() => { setMenuOpen(false); navigate('/account/security'); }}
                  data-testid="account-security-link"
                >
                  <Icon name="shield" size={16} /> Account security
                </button>
                <button
                  type="button" role="menuitem"
                  className="shell__dropdown-item shell__dropdown-item--danger"
                  onClick={() => { setMenuOpen(false); setSignOutOpen(true); }}
                  data-testid="logout-button"
                >
                  <Icon name="logout" size={16} /> Sign out
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* ------------------------------------------------------- content */}
      <main className="shell__content" id="main-content" tabIndex={-1}>
        <div className="shell__content-inner" key={location.pathname}>
          <StudyContextBar context={studyContext} />
          <Outlet />
        </div>
      </main>

      <Dialog
        open={signOutOpen}
        onClose={() => setSignOutOpen(false)}
        title="Sign out of NanoBio Studio?"
        footer={
          <>
            <Button variant="secondary" onClick={() => setSignOutOpen(false)}>Stay signed in</Button>
            <Button variant="danger" onClick={handleSignOut} data-testid="confirm-logout">
              Sign out
            </Button>
          </>
        }
      >
        <p>
          Your session will be closed on the server. Any unsaved design inputs on
          the current page will be lost.
        </p>
      </Dialog>
    </div>
  );
}
