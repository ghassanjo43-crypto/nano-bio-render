/**
 * Tests for the guided Nanoparticle Design workflow.
 *
 * Coverage carried over from the pre-redesign suite — validation, empty state,
 * error state, request shape, no-fabricated-results — retargeted at the stepped
 * workflow. The assertions about scientific honesty are unchanged.
 */

import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { DesignScoreResponse } from '../../api/types';
import DesignPage from './DesignPage';

const OK_RESPONSE: DesignScoreResponse = {
  design_impact_score: { delivery: 87.52475247524752, toxicity: 0.8, cost: 80.75 },
  score_version: 'design-impact-adapter-0.1.0',
  component_scores: {
    delivery: { value: 87.52475247524752, scale: '0-100 (higher is better)', meaning: 'Predicted delivery performance.' },
    toxicity: { value: 0.8, scale: '0-10 (lower is better)', meaning: 'Predicted toxicity burden.' },
    cost: { value: 80.75, scale: '0-100 (lower is better)', meaning: 'Relative cost indicator.' },
  },
  normalized_inputs: { Size: 100, Charge: -5, Encapsulation: 85 },
  warnings: ['Optional fields not provided; canonical defaults applied: PDI'],
  prediction_basis: 'rule_based_physicochemical_heuristic',
  evidence_level: 'literature_informed_unvalidated',
  validation_status: 'not_experimentally_validated',
  limitations: ['Computational research-planning result only.'],
  scientific_source: 'core.scoring.compute_impact',
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status, headers: { 'Content-Type': 'application/json' },
  });
}

function mockFetch(handler: (url: string) => Response) {
  return vi.fn(async (input: RequestInfo | URL) => handler(String(input)));
}

function renderPage() {
  return render(<MemoryRouter><DesignPage /></MemoryRouter>);
}

/** Advance the workflow to the review step. */
async function goToReview(user: ReturnType<typeof userEvent.setup>) {
  for (let i = 0; i < 4; i += 1) {
    await user.click(screen.getByRole('button', { name: /Continue/i }));
  }
}

beforeEach(() => {
  vi.stubGlobal('fetch', mockFetch((url) =>
    url.endsWith('/health') ? json({ status: 'healthy' }) : json(OK_RESPONSE)));
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('initial render', () => {
  it('shows the workflow and the first step', () => {
    renderPage();
    expect(screen.getByRole('heading', { name: /Formulation workflow/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Core properties/i })).toBeInTheDocument();
  });

  it('shows the research-use notice', () => {
    renderPage();
    expect(screen.getByText(/Computational research use only/i)).toBeInTheDocument();
    expect(screen.getByText(/not experimentally validated/i)).toBeInTheDocument();
  });

  it('shows an empty state rather than a result card', () => {
    renderPage();
    expect(screen.getByTestId('empty-state')).toBeInTheDocument();
    expect(screen.queryByTestId('result-card')).not.toBeInTheDocument();
  });

  it('marks required and optional fields', () => {
    renderPage();
    expect(screen.getAllByText('required').length).toBeGreaterThanOrEqual(3);
    expect(screen.getAllByText('optional').length).toBeGreaterThanOrEqual(1);
  });
});

describe('no fabricated results before execution', () => {
  it('renders no scientific numbers in the result panel', () => {
    const { container } = renderPage();
    const panel = container.querySelector('.design__results');
    expect(panel).not.toBeNull();
    expect(panel!.textContent).not.toMatch(/\d+\.\d+/);
    expect(screen.queryByTestId('score-version')).not.toBeInTheDocument();
  });

  it('never shows the retired hard-coded scores', () => {
    const { container } = renderPage();
    const text = container.textContent ?? '';
    for (const banned of ['94.2', '91.5', '89.8', '87.3', '84.9']) {
      expect(text).not.toContain(banned);
    }
  });
});

describe('validation', () => {
  it('blocks progress and reports an invalid size', async () => {
    const user = userEvent.setup();
    renderPage();

    const size = screen.getByRole('textbox', { name: 'Particle size' });
    await user.clear(size);
    await user.type(size, '-5');
    await user.click(screen.getByRole('button', { name: /Continue/i }));

    expect(await screen.findByText(/must be greater than 0/i)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Core properties/i })).toBeInTheDocument();
  });

  it('rejects an out-of-range encapsulation value', async () => {
    const user = userEvent.setup();
    renderPage();

    const encap = screen.getByRole('textbox', { name: 'Encapsulation efficiency' });
    await user.clear(encap);
    await user.type(encap, '150');
    await user.click(screen.getByRole('button', { name: /Continue/i }));

    expect(await screen.findByText(/100 % or less/i)).toBeInTheDocument();
  });

  it('reports a missing required field', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.clear(screen.getByRole('textbox', { name: 'Surface charge (zeta potential)' }));
    await user.click(screen.getByRole('button', { name: /Continue/i }));

    expect(await screen.findByText(/is required/i)).toBeInTheDocument();
  });

  it('does not call the API while validation fails', async () => {
    const user = userEvent.setup();
    renderPage();

    await user.clear(screen.getByRole('textbox', { name: 'Particle size' }));
    await user.click(screen.getByRole('button', { name: /Continue/i }));
    await screen.findByText(/is required/i);

    const calls = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls;
    expect(calls.filter((c) => String(c[0]).includes('/design/score'))).toHaveLength(0);
  });
});

describe('workflow navigation', () => {
  it('preserves inputs when moving between steps', async () => {
    const user = userEvent.setup();
    renderPage();

    const size = screen.getByRole('textbox', { name: 'Particle size' });
    await user.clear(size);
    await user.type(size, '123');

    await user.click(screen.getByRole('button', { name: /Continue/i }));
    expect(await screen.findByRole('heading', { name: /Surface characteristics/i })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /^Back$/i }));
    expect((screen.getByRole('textbox', { name: 'Particle size' }) as HTMLInputElement).value).toBe('123');
  });

  it('reaches the review step and summarises supplied vs default values', async () => {
    const user = userEvent.setup();
    renderPage();
    await goToReview(user);

    const review = await screen.findByTestId('review-step');
    expect(review).toBeInTheDocument();
    expect(within(review).getAllByText('default').length).toBeGreaterThan(0);
    expect(review.textContent).toMatch(/parameters supplied/i);
  });
});

describe('successful calculation', () => {
  it('renders the score returned by the API', async () => {
    const user = userEvent.setup();
    renderPage();
    await goToReview(user);
    await user.click(screen.getByRole('button', { name: /Calculate Score/i }));

    expect(await screen.findByTestId('result-card')).toBeInTheDocument();
    // Each value is rendered twice: once in the gauge readout and once in the
    // comparison bar, so the number is always available as text.
    expect(screen.getAllByText('87.52').length).toBeGreaterThan(0);
    expect(screen.getAllByText('0.80').length).toBeGreaterThan(0);
    expect(screen.getAllByText('80.75').length).toBeGreaterThan(0);
  });

  it('renders provenance and validation status', async () => {
    const user = userEvent.setup();
    renderPage();
    await goToReview(user);
    await user.click(screen.getByRole('button', { name: /Calculate Score/i }));

    await screen.findByTestId('result-card');
    expect(screen.getByTestId('score-version')).toHaveTextContent('design-impact-adapter-0.1.0');
    expect(screen.getByText('not_experimentally_validated')).toBeInTheDocument();
    expect(screen.getByText('rule_based_physicochemical_heuristic')).toBeInTheDocument();
    expect(screen.getByText('literature_informed_unvalidated')).toBeInTheDocument();
  });

  it('does not present a composite overall score', async () => {
    const user = userEvent.setup();
    renderPage();
    await goToReview(user);
    await user.click(screen.getByRole('button', { name: /Calculate Score/i }));

    const card = await screen.findByTestId('result-card');
    expect(card.textContent).toMatch(/No single composite score is/i);
  });

  it('exposes chart values as text for accessibility', async () => {
    const user = userEvent.setup();
    renderPage();
    await goToReview(user);
    await user.click(screen.getByRole('button', { name: /Calculate Score/i }));

    await screen.findByTestId('result-card');
    const charts = screen.getAllByRole('img');
    expect(charts.length).toBeGreaterThanOrEqual(3);
    expect(charts.some((g) => (g.getAttribute('aria-label') ?? '').includes('87.52'))).toBe(true);
  });

  it('shows warnings returned by the engine', async () => {
    const user = userEvent.setup();
    renderPage();
    await goToReview(user);
    await user.click(screen.getByRole('button', { name: /Calculate Score/i }));

    await screen.findByTestId('result-card');
    await user.click(screen.getByRole('tab', { name: /Warnings/i }));
    expect(screen.getByTestId('warnings')).toBeInTheDocument();
  });

  it('posts only the supplied fields', async () => {
    const user = userEvent.setup();
    renderPage();
    await goToReview(user);
    await user.click(screen.getByRole('button', { name: /Calculate Score/i }));
    await screen.findByTestId('result-card');

    const calls = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls;
    const call = calls.find((c) => String(c[0]).includes('/design/score'));
    expect(call).toBeDefined();
    const body = JSON.parse((call![1] as RequestInit).body as string);
    expect(body).toEqual({ size_nm: 100, charge_mv: -5, encapsulation_percent: 85 });
  });

  it('sends credentials so the session cookie is used', async () => {
    const user = userEvent.setup();
    renderPage();
    await goToReview(user);
    await user.click(screen.getByRole('button', { name: /Calculate Score/i }));
    await screen.findByTestId('result-card');

    const calls = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls;
    const call = calls.find((c) => String(c[0]).includes('/design/score'));
    expect((call![1] as RequestInit).credentials).toBe('include');
  });
});

describe('API error handling', () => {
  it('renders a structured error with no score', async () => {
    vi.stubGlobal('fetch', mockFetch((url) =>
      url.endsWith('/health') ? json({ status: 'healthy' }) : json({
        error: 'calculation_failed',
        message: 'The score could not be calculated.',
        detail: 'RuntimeError: boom',
        score_available: false,
      }, 500)));

    const user = userEvent.setup();
    renderPage();
    await goToReview(user);
    await user.click(screen.getByRole('button', { name: /Calculate Score/i }));

    expect(await screen.findByTestId('error-state')).toBeInTheDocument();
    expect(screen.getByText(/Score unavailable/i)).toBeInTheDocument();
    expect(screen.queryByTestId('result-card')).not.toBeInTheDocument();
  });

  it('shows no favourable fallback number on failure', async () => {
    vi.stubGlobal('fetch', mockFetch((url) =>
      url.endsWith('/health') ? json({ status: 'healthy' })
        : json({ error: 'calculation_failed', message: 'failed', score_available: false }, 500)));

    const user = userEvent.setup();
    const { container } = renderPage();
    await goToReview(user);
    await user.click(screen.getByRole('button', { name: /Calculate Score/i }));

    await screen.findByTestId('error-state');
    const panel = container.querySelector('.design__results');
    expect(panel!.textContent).not.toMatch(/\d+\.\d{2}/);
  });

  it('handles a network failure gracefully', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).endsWith('/health')) return json({ status: 'ok' });
      throw new TypeError('Failed to fetch');
    }));

    const user = userEvent.setup();
    renderPage();
    await goToReview(user);
    await user.click(screen.getByRole('button', { name: /Calculate Score/i }));

    expect(await screen.findByTestId('error-state')).toBeInTheDocument();
    expect(screen.getByText(/Could not reach the scoring service/i)).toBeInTheDocument();
  });

  it('treats a 200 without a score as an error', async () => {
    vi.stubGlobal('fetch', mockFetch((url) =>
      url.endsWith('/health') ? json({ status: 'healthy' }) : json({ unexpected: true })));

    const user = userEvent.setup();
    renderPage();
    await goToReview(user);
    await user.click(screen.getByRole('button', { name: /Calculate Score/i }));

    expect(await screen.findByTestId('error-state')).toBeInTheDocument();
    expect(screen.queryByTestId('result-card')).not.toBeInTheDocument();
  });
});
