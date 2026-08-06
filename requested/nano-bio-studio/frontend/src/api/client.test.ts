/**
 * API client error-shape tests.
 *
 * These exist because of a real crash: FastAPI's `HTTPException(detail={...})`
 * serialises to a nested OBJECT, the client copied it into `error.detail`
 * unchecked, and every component rendering `{error.detail}` blew up the whole
 * page with "Objects are not valid as a React child".
 *
 * The declared type said `string | null`, but the value crosses the network as
 * `unknown`, so TypeScript could not catch it. The boundary must enforce it.
 */

import { describe, expect, it, vi, afterEach } from 'vitest';
import {
  compareRuns, listScenarios, listRuns, scoreDesign, simulatePk, storeRun,
} from './client';

/** The exact body FastAPI returns from `get_current_user` on a missing session. */
const FASTAPI_401 = {
  detail: { error: 'not_authenticated', message: 'Sign in to continue.' },
};

function stubFetch(body: unknown, status: number) {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(body), {
    status, headers: { 'Content-Type': 'application/json' },
  })));
}

const DESIGN = { size_nm: 100, charge_mv: -5, encapsulation_percent: 85 };
const PK = { dose_mg_kg: 3, kabs_per_h: 0.5, kel_per_h: 0.1, k12_per_h: 0.2,
             k21_per_h: 0.05 };

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('detail is always renderable', () => {
  it('never returns an object detail from a FastAPI 401 (workspace)', async () => {
    stubFetch(FASTAPI_401, 401);
    const result = await listScenarios();

    expect(result.status).toBe('error');
    if (result.status !== 'error') return;
    expect(typeof result.error.detail === 'string' || result.error.detail === null)
      .toBe(true);
    expect(typeof result.error.message).toBe('string');
  });

  it('never returns an object detail from a FastAPI 401 (design score)', async () => {
    stubFetch(FASTAPI_401, 401);
    const result = await scoreDesign(DESIGN);

    expect(result.status).toBe('error');
    if (result.status !== 'error') return;
    expect(typeof result.error.detail === 'string' || result.error.detail === null)
      .toBe(true);
  });

  it('never returns an object detail from a FastAPI 401 (PK)', async () => {
    stubFetch(FASTAPI_401, 401);
    const result = await simulatePk(PK);

    expect(result.status).toBe('error');
    if (result.status !== 'error') return;
    expect(typeof result.error.detail === 'string' || result.error.detail === null)
      .toBe(true);
  });

  it('surfaces the envelope message rather than a bare status code', async () => {
    stubFetch(FASTAPI_401, 401);
    const result = await listScenarios();
    if (result.status !== 'error') throw new Error('expected an error');

    expect(result.error.error).toBe('not_authenticated');
    expect(result.error.message).toBe('Sign in to continue.');
  });

  it('flattens an object detail on a flat structured error', async () => {
    stubFetch({ error: 'calculation_failed', message: 'It failed.',
                detail: { reason: 'solver diverged', step: 3 } }, 500);
    const result = await scoreDesign(DESIGN);
    if (result.status !== 'error') throw new Error('expected an error');

    expect(typeof result.error.detail).toBe('string');
    expect(result.error.detail).toContain('solver diverged');
  });

  it('flattens an array detail (FastAPI validation errors)', async () => {
    stubFetch({ detail: [{ loc: ['body', 'size_nm'], msg: 'field required' }] },
              422);
    const result = await scoreDesign(DESIGN);
    if (result.status !== 'error') throw new Error('expected an error');

    expect(typeof result.error.detail === 'string'
           || result.error.detail === null).toBe(true);
  });

  it('keeps a plain string detail untouched', async () => {
    stubFetch({ error: 'invalid_input_value', message: 'Rejected.',
                detail: 'kel_per_h out of range' }, 400);
    const result = await simulatePk(PK);
    if (result.status !== 'error') throw new Error('expected an error');

    expect(result.error.detail).toBe('kel_per_h out of range');
  });

  it('handles every workspace endpoint the same way', async () => {
    stubFetch(FASTAPI_401, 401);
    for (const call of [
      () => listRuns(),
      () => compareRuns([1, 2]),
      () => storeRun({ name: 'x' }),
    ]) {
      const result = await call();
      expect(result.status).toBe('error');
      if (result.status !== 'error') continue;
      expect(typeof result.error.detail === 'string'
             || result.error.detail === null).toBe(true);
    }
  });
});

describe('failure paths still carry no data', () => {
  it('reports no data available on a workspace failure', async () => {
    stubFetch(FASTAPI_401, 401);
    const result = await listScenarios();
    if (result.status !== 'error') throw new Error('expected an error');
    expect(result.error.data_available).toBe(false);
  });

  it('reports no score available on a scoring failure', async () => {
    stubFetch(FASTAPI_401, 401);
    const result = await scoreDesign(DESIGN);
    if (result.status !== 'error') throw new Error('expected an error');
    expect(result.error.score_available).toBe(false);
    expect(result).not.toHaveProperty('data');
  });

  it('reports no results available on a PK failure', async () => {
    stubFetch(FASTAPI_401, 401);
    const result = await simulatePk(PK);
    if (result.status !== 'error') throw new Error('expected an error');
    expect(result.error.results_available).toBe(false);
  });
});
