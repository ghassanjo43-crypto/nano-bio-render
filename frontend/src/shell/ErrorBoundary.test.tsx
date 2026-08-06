/**
 * The boundary's job is to make a crash legible.
 *
 * Before it existed, any render-time throw unmounted the whole tree and left a
 * blank page — indistinguishable from a hang, a logged-out state or a dead
 * server. These tests assert it renders an explanation and, critically, that it
 * never substitutes plausible-looking content for the thing that failed.
 */

import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ErrorBoundary } from './ErrorBoundary';

function Boom(): never {
  throw new Error('stale module: loadScenario is not a function');
}

let consoleError: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  // React logs the caught error; silence it so the suite output stays readable.
  consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
});

afterEach(() => {
  consoleError.mockRestore();
});

describe('ErrorBoundary', () => {
  it('renders children normally when nothing throws', () => {
    render(
      <ErrorBoundary>
        <p>healthy content</p>
      </ErrorBoundary>,
    );
    expect(screen.getByText('healthy content')).toBeInTheDocument();
    expect(screen.queryByTestId('error-boundary')).not.toBeInTheDocument();
  });

  it('shows an explanation instead of a blank page when a child throws', () => {
    render(<ErrorBoundary><Boom /></ErrorBoundary>);

    const panel = screen.getByTestId('error-boundary');
    expect(panel).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /could not be displayed/i }))
      .toBeInTheDocument();
    // The page is genuinely non-empty — that is the whole point.
    expect(panel.textContent!.length).toBeGreaterThan(120);
  });

  it('states that nothing was calculated or saved', () => {
    render(<ErrorBoundary><Boom /></ErrorBoundary>);
    expect(screen.getByTestId('error-boundary').textContent)
      .toMatch(/Nothing was calculated or saved/i);
  });

  it('never substitutes a result for the view that failed', () => {
    render(<ErrorBoundary><Boom /></ErrorBoundary>);
    const text = screen.getByTestId('error-boundary').textContent!;
    expect(text).toMatch(/no result is being shown in place of/i);
    // No number that could be mistaken for a calculated value.
    expect(text).not.toMatch(/\d+\.\d+/);
  });

  it('exposes the technical detail for a bug report', () => {
    render(<ErrorBoundary><Boom /></ErrorBoundary>);
    expect(screen.getByText(/loadScenario is not a function/))
      .toBeInTheDocument();
  });

  it('offers a full reload, which discards a stale module', () => {
    render(<ErrorBoundary><Boom /></ErrorBoundary>);
    expect(screen.getByRole('button', { name: /Reload the page/i }))
      .toBeInTheDocument();
    expect(screen.getByRole('button', { name: /design session/i }))
      .toBeInTheDocument();
  });

  it('announces itself to assistive technology', () => {
    render(<ErrorBoundary><Boom /></ErrorBoundary>);
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });
});
