/**
 * NanoBio Studio design-system components.
 *
 * Small, strictly typed, composable primitives. Every component consumes design
 * tokens only — no hard-coded colours or spacing. Accessibility is built in
 * rather than added later: labels are associated, errors are linked via
 * `aria-describedby`, status is conveyed by text as well as colour, and every
 * interactive element has a visible focus state.
 */

import {
  forwardRef,
  useEffect,
  useId,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
} from 'react';
import './components.css';

/* ======================================================================== */
/* Button                                                                    */
/* ======================================================================== */

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
export type ButtonSize = 'sm' | 'md' | 'lg';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Shows a spinner and disables the control. */
  loading?: boolean;
  /** Decorative leading glyph. */
  iconLeft?: ReactNode;
  iconRight?: ReactNode;
  fullWidth?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  function Button(
    { variant = 'primary', size = 'md', loading = false, iconLeft, iconRight,
      fullWidth, children, className = '', disabled, ...rest },
    ref,
  ) {
    return (
      <button
        ref={ref}
        className={`ds-btn ds-btn--${variant} ds-btn--${size} ${
          fullWidth ? 'ds-btn--full' : ''
        } ${className}`}
        disabled={disabled || loading}
        aria-busy={loading || undefined}
        {...rest}
      >
        {loading && <span className="ds-btn__spinner" aria-hidden="true" />}
        {!loading && iconLeft && <span className="ds-btn__icon" aria-hidden="true">{iconLeft}</span>}
        <span className="ds-btn__label">{children}</span>
        {!loading && iconRight && <span className="ds-btn__icon" aria-hidden="true">{iconRight}</span>}
      </button>
    );
  },
);

/* ======================================================================== */
/* Card                                                                      */
/* ======================================================================== */

export interface CardProps {
  children: ReactNode;
  className?: string;
  /** Renders a header band with a title and optional actions. */
  title?: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  /** Removes body padding for tables and full-bleed content. */
  flush?: boolean;
  accent?: boolean;
  as?: 'div' | 'section' | 'article';
  'aria-labelledby'?: string;
}

export function Card({
  children, className = '', title, subtitle, actions, flush, accent,
  as: Tag = 'section', ...rest
}: CardProps) {
  return (
    <Tag className={`ds-card ${accent ? 'ds-card--accent' : ''} ${className}`} {...rest}>
      {(title || actions) && (
        <header className="ds-card__head">
          <div className="ds-card__headings">
            {title && <h2 className="ds-card__title">{title}</h2>}
            {subtitle && <p className="ds-card__subtitle">{subtitle}</p>}
          </div>
          {actions && <div className="ds-card__actions">{actions}</div>}
        </header>
      )}
      <div className={`ds-card__body ${flush ? 'ds-card__body--flush' : ''}`}>
        {children}
      </div>
    </Tag>
  );
}

/* ======================================================================== */
/* Badge                                                                     */
/* ======================================================================== */

export type BadgeTone = 'neutral' | 'accent' | 'success' | 'warn' | 'danger' | 'info';

export function Badge({
  children, tone = 'neutral', dot = false, className = '',
}: {
  children: ReactNode;
  tone?: BadgeTone;
  /** Adds a status dot so meaning is not carried by colour alone. */
  dot?: boolean;
  className?: string;
}) {
  return (
    <span className={`ds-badge ds-badge--${tone} ${className}`}>
      {dot && <span className="ds-badge__dot" aria-hidden="true" />}
      {children}
    </span>
  );
}

/* ======================================================================== */
/* Alert                                                                     */
/* ======================================================================== */

export function Alert({
  tone = 'info', title, children, icon, className = '', role,
}: {
  tone?: 'info' | 'success' | 'warn' | 'danger';
  title?: ReactNode;
  children?: ReactNode;
  icon?: ReactNode;
  className?: string;
  role?: 'alert' | 'status' | 'note';
}) {
  const glyph = icon ?? { info: 'ℹ', success: '✓', warn: '!', danger: '✕' }[tone];
  return (
    <div
      className={`ds-alert ds-alert--${tone} ${className}`}
      role={role === 'note' ? undefined : role ?? (tone === 'danger' ? 'alert' : 'status')}
    >
      <span className="ds-alert__icon" aria-hidden="true">{glyph}</span>
      <div className="ds-alert__content">
        {title && <p className="ds-alert__title">{title}</p>}
        {children && <div className="ds-alert__body">{children}</div>}
      </div>
    </div>
  );
}

/* ======================================================================== */
/* Tooltip                                                                   */
/* ======================================================================== */

/**
 * Accessible tooltip. Content is exposed to assistive technology through
 * `aria-describedby`, and opens on hover *and* keyboard focus.
 */
export function Tooltip({
  content, children, side = 'top',
}: {
  content: ReactNode;
  children: ReactNode;
  side?: 'top' | 'bottom';
}) {
  const id = useId();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open]);

  return (
    <span className="ds-tooltip">
      <span
        className="ds-tooltip__trigger"
        aria-describedby={open ? id : undefined}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
      >
        {children}
      </span>
      {open && (
        <span role="tooltip" id={id} className={`ds-tooltip__bubble ds-tooltip__bubble--${side}`}>
          {content}
        </span>
      )}
    </span>
  );
}

/** An inline "?" affordance that carries a scientific definition. */
export function InfoHint({ label, children }: { label: string; children: ReactNode }) {
  return (
    <Tooltip content={children}>
      <button type="button" className="ds-hint" aria-label={`About ${label}`}>
        ?
      </button>
    </Tooltip>
  );
}

/* ======================================================================== */
/* Form fields                                                               */
/* ======================================================================== */

interface FieldShellProps {
  id: string;
  label: string;
  unit?: string;
  required?: boolean;
  error?: string;
  help?: ReactNode;
  hint?: ReactNode;
  children: ReactNode;
}

function FieldShell({ id, label, unit, required, error, help, hint, children }: FieldShellProps) {
  const describedBy = [error ? `${id}-error` : null, help ? `${id}-help` : null]
    .filter(Boolean)
    .join(' ');
  // The <label> element deliberately contains ONLY the field name. Units,
  // required/optional chips and the info hint sit beside it, so the accessible
  // name stays clean ("Password", not "Password optional ?") for both screen
  // readers and label-based queries.
  return (
    <div className={`ds-field ${error ? 'ds-field--error' : ''}`} data-described={describedBy || undefined}>
      <div className="ds-field__labelrow">
        <label className="ds-field__label" htmlFor={id}>{label}</label>
        {unit && <span className="ds-field__unit">{unit}</span>}
        {required
          ? <span className="ds-field__req" title="Required">required</span>
          : <span className="ds-field__opt">optional</span>}
        {hint && <span className="ds-field__hint">{hint}</span>}
      </div>
      {children}
      {help && !error && <p className="ds-field__help" id={`${id}-help`}>{help}</p>}
      {error && (
        <p className="ds-field__error" id={`${id}-error`} role="alert">
          <span aria-hidden="true">✕ </span>{error}
        </p>
      )}
    </div>
  );
}

export interface TextFieldProps
  extends Omit<InputHTMLAttributes<HTMLInputElement>, 'id' | 'size'> {
  id: string;
  label: string;
  unit?: string;
  error?: string;
  help?: ReactNode;
  hint?: ReactNode;
}

export function TextField({
  id, label, unit, error, help, hint, required, className = '', ...rest
}: TextFieldProps) {
  const describedBy = [error ? `${id}-error` : null, help ? `${id}-help` : null]
    .filter(Boolean).join(' ') || undefined;
  return (
    <FieldShell id={id} label={label} unit={unit} required={required} error={error} help={help} hint={hint}>
      <input
        id={id}
        name={id}
        className={`ds-input ${className}`}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        aria-required={required || undefined}
        {...rest}
      />
    </FieldShell>
  );
}

export interface SelectFieldProps
  extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'id'> {
  id: string;
  label: string;
  unit?: string;
  error?: string;
  help?: ReactNode;
  hint?: ReactNode;
  options: ReadonlyArray<{ value: string; label: string }>;
}

export function SelectField({
  id, label, unit, error, help, hint, required, options, className = '', ...rest
}: SelectFieldProps) {
  const describedBy = [error ? `${id}-error` : null, help ? `${id}-help` : null]
    .filter(Boolean).join(' ') || undefined;
  return (
    <FieldShell id={id} label={label} unit={unit} required={required} error={error} help={help} hint={hint}>
      <div className="ds-select-wrap">
        <select
          id={id}
          name={id}
          className={`ds-input ds-select ${className}`}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          {...rest}
        >
          {options.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        <span className="ds-select__chevron" aria-hidden="true">▾</span>
      </div>
    </FieldShell>
  );
}

/** Password input with an accessible show/hide toggle. */
export function PasswordField({
  id, label, error, help, required, value, onChange, autoComplete, disabled,
}: {
  id: string;
  label: string;
  error?: string;
  help?: ReactNode;
  required?: boolean;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  autoComplete?: string;
  disabled?: boolean;
}) {
  const [visible, setVisible] = useState(false);
  const describedBy = [error ? `${id}-error` : null, help ? `${id}-help` : null]
    .filter(Boolean).join(' ') || undefined;
  return (
    <FieldShell id={id} label={label} required={required} error={error} help={help}>
      <div className="ds-password">
        <input
          id={id}
          name={id}
          type={visible ? 'text' : 'password'}
          className="ds-input"
          value={value}
          onChange={onChange}
          autoComplete={autoComplete}
          disabled={disabled}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          aria-required={required || undefined}
        />
        <button
          type="button"
          className="ds-password__toggle"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? 'Hide password' : 'Show password'}
          aria-pressed={visible}
          disabled={disabled}
        >
          {visible ? 'Hide' : 'Show'}
        </button>
      </div>
    </FieldShell>
  );
}

/* ======================================================================== */
/* Multi-select chips                                                        */
/* ======================================================================== */

export function ChipGroup({
  id, label, options, value, onChange, help, hint,
}: {
  id: string;
  label: string;
  options: readonly string[];
  value: readonly string[];
  onChange: (next: string[]) => void;
  help?: ReactNode;
  hint?: ReactNode;
}) {
  const toggle = (opt: string) => {
    onChange(value.includes(opt) ? value.filter((v) => v !== opt) : [...value, opt]);
  };
  return (
    <fieldset className="ds-field ds-chipgroup" aria-describedby={help ? `${id}-help` : undefined}>
      <legend className="ds-field__labelrow">
        <span className="ds-field__label">{label}</span>
        <span className="ds-field__opt">optional</span>
        {hint && <span className="ds-field__hint">{hint}</span>}
      </legend>
      <div className="ds-chipgroup__list">
        {options.map((opt) => {
          const active = value.includes(opt);
          return (
            <button
              key={opt}
              type="button"
              className={`ds-chip ${active ? 'ds-chip--on' : ''}`}
              aria-pressed={active}
              onClick={() => toggle(opt)}
            >
              <span className="ds-chip__check" aria-hidden="true">{active ? '✓' : '+'}</span>
              {opt}
            </button>
          );
        })}
      </div>
      {help && <p className="ds-field__help" id={`${id}-help`}>{help}</p>}
    </fieldset>
  );
}

/* ======================================================================== */
/* Skeleton                                                                  */
/* ======================================================================== */

export function Skeleton({
  width = '100%', height = 14, radius = 'var(--radius-sm)', className = '',
}: { width?: string | number; height?: string | number; radius?: string; className?: string }) {
  return (
    <span
      className={`ds-skeleton ${className}`}
      style={{ width, height, borderRadius: radius }}
      aria-hidden="true"
    />
  );
}

export function SkeletonBlock({ lines = 3 }: { lines?: number }) {
  return (
    <div className="ds-skeleton-block" role="status" aria-label="Loading">
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} width={i === lines - 1 ? '62%' : '100%'} height={12} />
      ))}
      <span className="sr-only">Loading…</span>
    </div>
  );
}

/* ======================================================================== */
/* Empty state                                                               */
/* ======================================================================== */

export function EmptyState({
  icon, title, children, action, tone = 'neutral', testId,
}: {
  icon?: ReactNode;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
  tone?: 'neutral' | 'info';
  testId?: string;
}) {
  return (
    <div className={`ds-empty ds-empty--${tone}`} data-testid={testId}>
      {icon && <div className="ds-empty__icon" aria-hidden="true">{icon}</div>}
      <p className="ds-empty__title">{title}</p>
      {children && <div className="ds-empty__body">{children}</div>}
      {action && <div className="ds-empty__action">{action}</div>}
    </div>
  );
}

/* ======================================================================== */
/* Tabs                                                                      */
/* ======================================================================== */

export function Tabs({
  tabs, active, onChange, ariaLabel,
}: {
  tabs: ReadonlyArray<{ id: string; label: string; badge?: ReactNode }>;
  active: string;
  onChange: (id: string) => void;
  ariaLabel: string;
}) {
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});

  const onKeyDown = (e: React.KeyboardEvent) => {
    const i = tabs.findIndex((t) => t.id === active);
    let next = i;
    if (e.key === 'ArrowRight') next = (i + 1) % tabs.length;
    else if (e.key === 'ArrowLeft') next = (i - 1 + tabs.length) % tabs.length;
    else if (e.key === 'Home') next = 0;
    else if (e.key === 'End') next = tabs.length - 1;
    else return;
    e.preventDefault();
    const target = tabs[next];
    if (target) {
      onChange(target.id);
      refs.current[target.id]?.focus();
    }
  };

  return (
    <div className="ds-tabs" role="tablist" aria-label={ariaLabel} onKeyDown={onKeyDown}>
      {tabs.map((t) => (
        <button
          key={t.id}
          ref={(el) => { refs.current[t.id] = el; }}
          role="tab"
          type="button"
          id={`tab-${t.id}`}
          aria-selected={t.id === active}
          aria-controls={`panel-${t.id}`}
          tabIndex={t.id === active ? 0 : -1}
          className={`ds-tab ${t.id === active ? 'ds-tab--active' : ''}`}
          onClick={() => onChange(t.id)}
        >
          {t.label}
          {t.badge}
        </button>
      ))}
    </div>
  );
}

/* ======================================================================== */
/* Data table                                                                */
/* ======================================================================== */

export function DataTable({
  caption, head, children, dense,
}: {
  caption?: string;
  head: ReadonlyArray<{ key: string; label: string; numeric?: boolean; width?: string }>;
  children: ReactNode;
  dense?: boolean;
}) {
  return (
    <div className="ds-table-scroll">
      <table className={`ds-table ${dense ? 'ds-table--dense' : ''}`}>
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr>
            {head.map((h) => (
              <th key={h.key} scope="col" className={h.numeric ? 'is-numeric' : ''}
                  style={h.width ? { width: h.width } : undefined}>
                {h.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

/* ======================================================================== */
/* Dialog                                                                    */
/* ======================================================================== */

export function Dialog({
  open, onClose, title, children, footer, labelledBy, wide,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  labelledBy?: string;
  /** Widens the panel for content-heavy dialogs (tables, long previews). */
  wide?: boolean;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const titleId = useId();

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    panelRef.current?.focus();
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="ds-dialog__overlay" onMouseDown={onClose}>
      <div
        ref={panelRef}
        className={`ds-dialog ${wide ? 'ds-dialog--wide' : ''}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={labelledBy ?? titleId}
        tabIndex={-1}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <h2 className="ds-dialog__title" id={titleId}>{title}</h2>
        <div className="ds-dialog__body">{children}</div>
        {footer && <div className="ds-dialog__footer">{footer}</div>}
      </div>
    </div>
  );
}

/* ======================================================================== */
/* Breadcrumbs                                                               */
/* ======================================================================== */

export function Breadcrumbs({
  items,
}: { items: ReadonlyArray<{ label: string; href?: string }> }) {
  return (
    <nav className="ds-crumbs" aria-label="Breadcrumb">
      <ol>
        {items.map((item, i) => {
          const last = i === items.length - 1;
          return (
            <li key={`${item.label}-${i}`}>
              {item.href && !last
                ? <a href={item.href}>{item.label}</a>
                : <span aria-current={last ? 'page' : undefined}>{item.label}</span>}
              {!last && <span className="ds-crumbs__sep" aria-hidden="true">/</span>}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

/* ======================================================================== */
/* Section heading                                                           */
/* ======================================================================== */

export function SectionHeading({
  eyebrow, title, description, actions, id,
}: {
  eyebrow?: string;
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  id?: string;
}) {
  return (
    <div className="ds-section-head">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h2 className="ds-section-head__title" id={id}>{title}</h2>
        {description && <p className="ds-section-head__desc">{description}</p>}
      </div>
      {actions && <div className="ds-section-head__actions">{actions}</div>}
    </div>
  );
}
