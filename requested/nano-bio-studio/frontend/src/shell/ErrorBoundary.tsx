/**
 * Top-level error boundary.
 *
 * Without one, a single render-time throw anywhere in the tree causes React to
 * unmount everything, leaving a completely blank page with no explanation — the
 * user cannot tell a crash from a hang, from a logged-out state, from a server
 * being down. That happened in development after a hot-module reload left a
 * stale module behind, and it would be far worse in production.
 *
 * This component turns that into a readable state: what failed, the technical
 * detail for a bug report, and the two actions that actually help (a full
 * reload, which discards any stale module, and a route back to safety).
 *
 * Scientific-honesty note: a boundary must NEVER swallow an error and render a
 * plausible-looking page in its place. A crashed calculation view has no result,
 * and this says so rather than substituting one.
 */

import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
  componentStack: string | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null, componentStack: null };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Kept in the console so the stack is available for a bug report even
    // after the UI has recovered.
    console.error('[NanoBio Studio] render error:', error, info.componentStack);
    this.setState({ componentStack: info.componentStack ?? null });
  }

  private handleReload = () => {
    // A full reload rather than a state reset: the usual cause in development
    // is a stale hot-reloaded module, which only a fresh document discards.
    window.location.reload();
  };

  private handleHome = () => {
    window.location.href = '/start';
  };

  render() {
    const { error, componentStack } = this.state;
    if (!error) return this.props.children;

    return (
      <div className="eb" role="alert" data-testid="error-boundary">
        <div className="eb__panel">
          <p className="eb__eyebrow">Something went wrong</p>
          <h1 className="eb__title">This page could not be displayed</h1>
          <p className="eb__body">
            The interface hit an unexpected error while rendering. Nothing was
            calculated or saved, and no result is being shown in place of the
            one that failed.
          </p>
          <p className="eb__body">
            If this appeared right after the application was updated, a full
            reload usually resolves it — the browser may be holding a stale
            copy of part of the app.
          </p>

          <div className="eb__actions">
            <button type="button" className="eb__btn eb__btn--primary"
                    onClick={this.handleReload}>
              Reload the page
            </button>
            <button type="button" className="eb__btn" onClick={this.handleHome}>
              Go to the design session
            </button>
          </div>

          <details className="eb__details">
            <summary>Technical detail</summary>
            <p className="eb__mono">{error.name}: {error.message}</p>
            {componentStack && (
              <pre className="eb__stack">{componentStack.trim()}</pre>
            )}
          </details>
        </div>
      </div>
    );
  }
}
