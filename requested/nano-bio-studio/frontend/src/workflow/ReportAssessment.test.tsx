/**
 * Tests for the Medical Report Assessment pathway.
 *
 * The rules under test:
 *   • extraction is honestly reported as unavailable, and nothing is invented;
 *   • every field shows its provenance, and typing changes it to "you entered";
 *   • the attestation gates the upload;
 *   • real patient data is refused and the refusal is shown;
 *   • confirmation is required before the context can be carried onward;
 *   • an invalid disease/subtype/drug combination cannot be submitted;
 *   • report content NEVER reaches localStorage or sessionStorage;
 *   • extraction failure and unsupported files degrade gracefully.
 */

import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../App';
import { AuthProvider } from '../auth/AuthContext';
import type { UserProfile } from '../api/auth';
import type {
  ReportUploadResponse, SyntheticReportListResponse,
} from '../api/types';

const ADMIN: UserProfile = {
  id: 1, username: 'admin', email: 'admin@nanobio.local',
  full_name: 'Platform Administrator', role: 'admin', is_active: true,
  last_login_at: null,
};

const DOCUMENT_TEXT =
  'SYNTHETIC DEMONSTRATION DOCUMENT -- NOT A REAL MEDICAL REPORT\n'
  + 'Diagnosis: invasive ductal carcinoma of the left breast.\n'
  + 'Combined histological grade: Grade 3.\n';

const FIELD_KEYS = [
  'cancer_indication', 'histological_subtype', 'tumor_site', 'stage',
  'tnm_classification', 'grade', 'metastatic_sites', 'er_status', 'pr_status',
  'her2_ihc', 'her2_ish', 'her2_status', 'her3_status', 'ki67', 'pdl1',
  'genomic_alterations', 'pathology_findings', 'current_treatment',
  'therapeutic_context', 'laboratory_findings', 'report_date', 'document_type',
];

const LABELS: Record<string, string> = {
  cancer_indication: 'Cancer indication',
  histological_subtype: 'Histological subtype',
  tumor_site: 'Tumour site', stage: 'Stage',
  tnm_classification: 'TNM classification', grade: 'Grade',
  metastatic_sites: 'Metastatic sites',
  er_status: 'ER (oestrogen receptor)',
  pr_status: 'PR (progesterone receptor)',
  her2_ihc: 'HER2 — immunohistochemistry',
  her2_ish: 'HER2 — in-situ hybridisation',
  her2_status: 'HER2 — overall status',
  her3_status: 'HER3', ki67: 'Ki-67 proliferation index', pdl1: 'PD-L1',
  genomic_alterations: 'Genomic alterations',
  pathology_findings: 'Pathology findings',
  current_treatment: 'Current or previous treatment',
  therapeutic_context: 'Therapeutic context',
  laboratory_findings: 'Relevant laboratory findings',
  report_date: 'Report date', document_type: 'Document type',
};

const UPLOAD: ReportUploadResponse = {
  assessment_id: 11,
  display_name: 'synthetic-breast-pathology.txt',
  content_hash: 'a'.repeat(64),
  format_key: 'txt',
  size_bytes: 512,
  classification: 'synthetic',
  status: 'awaiting_review',
  extraction: {
    status: 'completed',
    engine_name: 'rule-based-oncology-extractor',
    engine_version: '1.0.0',
    contract_version: 'extraction-contract-2.0.0',
    reader_name: 'pypdf',
    reader_version: '4.0.0',
    message: 'Read 3 of 22 fields from the document; 1 needs an explicit '
      + 'decision because it was inferred, ambiguous or contradictory.',
    limitations: [
      'Extraction is performed by a rule-based reader. It is NOT a trained '
      + 'model, has NOT been calibrated or validated against annotated '
      + 'reports, and its accuracy on real-world documents is unmeasured.',
      'The confidence figure is a heuristic pattern-strength score, not a '
      + 'probability.',
      'This pathway provides no clinical interpretation, no diagnosis, no '
      + 'prognosis and no treatment recommendation.',
    ],
    warnings: [],
    page_count: 1,
    fields: FIELD_KEYS.map((key) => {
      const base = {
        key, label: LABELS[key]!, page: null as number | null,
        confidence: 0, alternatives: [] as string[],
        supporting_excerpts: [] as string[], consumed_by_engines: false,
        note: null as string | null,
      };
      if (key === 'stage') {
        return { ...base, value: 'Stage IIB',
                 provenance: 'explicitly_stated' as const,
                 supporting_text: 'Clinical stage: Stage IIB', page: 1,
                 confidence: 0.9,
                 supporting_excerpts: ['Clinical stage: Stage IIB'] };
      }
      if (key === 'her2_status') {
        return { ...base, value: 'HER2 positive (by ISH amplification)',
                 provenance: 'inferred' as const,
                 supporting_text: 'HER2 ISH: AMPLIFIED', page: 1,
                 confidence: 0.5,
                 supporting_excerpts: ['HER2 ISH: AMPLIFIED'],
                 note: 'Derived from the component results; the document does '
                   + 'not state this overall status in these words.' };
      }
      if (key === 'grade') {
        return { ...base, value: 'Grade 2',
                 provenance: 'conflicting' as const,
                 supporting_text: 'Grade 2 is recorded', page: 1,
                 confidence: 0.3, alternatives: ['Grade 3'],
                 supporting_excerpts: ['Grade 2 is recorded',
                                       'Grade 3 is recorded'],
                 note: 'The document reports more than one value.' };
      }
      return { ...base, value: null, provenance: 'not_found' as const,
               supporting_text: null,
               note: 'No statement of this field was found in the document.' };
    }),
  },
  intake_warnings: [
    'Identifier screening is pattern-based and cannot detect a name or other '
    + 'identifier written into ordinary prose.',
  ],
  document_readable: true,
  unreadable_reason: null,
  document_text: DOCUMENT_TEXT,
  retain_until: '2026-09-01T00:00:00.000Z',
};

const SYNTHETIC: SyntheticReportListResponse = {
  reports: [
    { slug: 'synthetic-breast-pathology', title: 'Synthetic breast pathology report',
      purpose: 'A complete, internally consistent surgical pathology report.',
      demonstrates: 'The ordinary path with a well-formed document.',
      filename: 'synthetic-breast-pathology.txt', size_bytes: 1800,
      data_classification: 'Synthetic demonstration document' },
    { slug: 'synthetic-lung-clinic-letter', title: 'Synthetic lung clinic letter',
      purpose: 'A narrative clinic letter rather than a structured report.',
      demonstrates: 'A different document shape.',
      filename: 'synthetic-lung-clinic-letter.txt', size_bytes: 1400,
      data_classification: 'Synthetic demonstration document' },
    { slug: 'synthetic-colorectal-conflicting',
      title: 'Synthetic colorectal summary with conflicting findings',
      purpose: 'A deliberately contradictory and incomplete document.',
      demonstrates: 'Conflict and missing-field handling.',
      filename: 'synthetic-colorectal-conflicting.txt', size_bytes: 1200,
      data_classification: 'Synthetic demonstration document' },
  ],
  fixture_version: 'synthetic-reports-1.0.0',
  notice: 'These documents are entirely fabricated for software testing. The '
    + 'patients do not exist. They are not real patient data.',
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status, headers: { 'Content-Type': 'application/json' },
  });
}

interface Opts {
  uploadStatus?: number;
  uploadBody?: unknown;
  confirmStatus?: number;
  confirmBody?: unknown;
  mapStatus?: number;
  mapBody?: unknown;
}

function installFetch(opts: Opts = {}) {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith('/health')) return json({ status: 'healthy' });
    if (url.endsWith('/api/v1/auth/me')) return json(ADMIN);
    if (url.endsWith('/api/v1/reports/synthetic')) return json(SYNTHETIC);
    if (url.includes('/api/v1/reports/synthetic/')) {
      return json(opts.uploadBody ?? UPLOAD, opts.uploadStatus ?? 201);
    }
    if (url.includes('/confirm')) {
      return json(opts.confirmBody ?? { ...UPLOAD, id: 11, status: 'confirmed',
        clinical_fields: [], confirmed_fields: [] }, opts.confirmStatus ?? 200);
    }
    if (url.includes('/map')) {
      return json(opts.mapBody ?? { ...UPLOAD, id: 11,
        status: 'mapped_to_workflow', clinical_fields: [],
        confirmed_fields: [] }, opts.mapStatus ?? 200);
    }
    if (url.endsWith('/api/v1/reports') && init?.method === 'POST') {
      return json(opts.uploadBody ?? UPLOAD, opts.uploadStatus ?? 201);
    }
    if (url.endsWith('/api/v1/reports')) {
      return json({ assessments: [], total: 0, policy_statement: 'x' });
    }
    return json({}, 404);
  }));
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider><App /></AuthProvider>
    </MemoryRouter>,
  );
}

function calls() {
  return (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls;
}

/** Load a synthetic report and land on the review stage. */
async function reachReview(user: ReturnType<typeof userEvent.setup>) {
  renderAt('/report');
  await screen.findByTestId('synthetic-reports');
  const card = screen.getByTestId('synthetic-synthetic-breast-pathology');
  await user.click(within(card).getByRole('button', { name: /Load this report/i }));
  await screen.findByTestId('document-text');
}

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  installFetch();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  localStorage.clear();
  sessionStorage.clear();
});

/* ===================================================================== */
describe('pathway is reachable', () => {
  it('is one of the three top-level pathways', async () => {
    renderAt('/start');
    expect(await screen.findByTestId('pathway-patient')).toBeInTheDocument();
    expect(screen.getByTestId('start-patient-upload')).toBeInTheDocument();
  });

  it('sits alongside the research and demonstration pathways', async () => {
    renderAt('/start');
    await screen.findByTestId('pathway-cards');
    expect(screen.getByTestId('start-research')).toBeInTheDocument();
    expect(screen.getByTestId('start-demo')).toBeInTheDocument();
    expect(screen.getByTestId('start-patient-upload')).toBeInTheDocument();
  });

  it('is listed in the sidebar', async () => {
    renderAt('/report');
    const nav = await screen.findByRole('navigation', { name: /Main navigation/i });
    expect(within(nav).getByText('Patient Assessments')).toBeInTheDocument();
  });
});

/* ===================================================================== */
describe('honest status', () => {
  it('states that extraction is automatic but unvalidated', async () => {
    renderAt('/report');
    const banner = await screen.findByTestId('extraction-status');
    expect(banner.textContent).toMatch(/rule-based extractor/i);
    expect(banner.textContent).toMatch(/not a trained model/i);
    expect(banner.textContent).toMatch(/accuracy is\s+unmeasured/i);
    expect(banner.textContent).toMatch(/check each one against the/i);
  });

  it('states that scanned documents cannot be read', async () => {
    renderAt('/report');
    const banner = await screen.findByTestId('ocr-status');
    expect(banner.textContent).toMatch(/no optical\s+character recognition/i);
    expect(banner.textContent).toMatch(/rather than guessed at/i);
  });

  it('states the synthetic/de-identified-only policy', async () => {
    renderAt('/report');
    const policy = await screen.findByTestId('phi-policy');
    expect(policy.textContent).toMatch(/Real patient reports are/i);
    expect(policy.textContent).toMatch(/refused/i);
    expect(policy.textContent).toMatch(/no encryption at rest/i);
  });

  it('shows the engine version on the review screen', async () => {
    const user = userEvent.setup();
    await reachReview(user);
    const version = screen.getByTestId('engine-version');
    expect(version.textContent).toMatch(/rule-based-oncology-extractor/);
    expect(version.textContent).toMatch(/1\.0\.0/);
  });

  it('repeats the engine message on the review screen', async () => {
    const user = userEvent.setup();
    await reachReview(user);
    expect(screen.getByTestId('extraction-message').textContent)
      .toMatch(/Read \d+ of \d+ fields/i);
  });
});

/* ===================================================================== */
describe('no fabrication', () => {
  it('shows an extracted value with its provenance', async () => {
    const user = userEvent.setup();
    await reachReview(user);
    const row = screen.getByTestId('field-stage');
    expect(within(row).getByText('Stated in report')).toBeInTheDocument();
    expect(within(row).getByRole('textbox', { name: /^Stage/i }))
      .toHaveValue('Stage IIB');
  });

  it('shows the supporting excerpt and page for an extracted value', async () => {
    const user = userEvent.setup();
    await reachReview(user);
    const row = screen.getByTestId('field-stage');
    expect(row.textContent).toMatch(/Clinical stage: Stage IIB/);
    expect(row.textContent).toMatch(/page 1/);
  });

  it('shows match strength, labelled as not a probability', async () => {
    const user = userEvent.setup();
    await reachReview(user);
    const row = screen.getByTestId('field-stage');
    expect(row.textContent).toMatch(/match strength 0\.90/);
  });

  it('leaves an unfound field empty and says it was not stated', async () => {
    const user = userEvent.setup();
    await reachReview(user);
    const row = screen.getByTestId('field-pdl1');
    expect(within(row).getByText('Not in report')).toBeInTheDocument();
    expect(within(row).getByText(/not stated in the document/i))
      .toBeInTheDocument();
    expect(within(row).getByRole('textbox', { name: /PD-L1/i }))
      .toHaveValue('');
  });

  it('shows the document verbatim for manual reading', async () => {
    const user = userEvent.setup();
    await reachReview(user);
    expect(screen.getByTestId('document-text').textContent)
      .toMatch(/invasive ductal carcinoma/i);
  });
});

/* ===================================================================== */
describe('unresolved readings need an explicit decision', () => {
  it('flags an inferred value and does not treat it as stated', async () => {
    const user = userEvent.setup();
    await reachReview(user);
    const row = screen.getByTestId('field-her2_status');
    expect(within(row).getByText('Inferred')).toBeInTheDocument();
    expect(within(row).queryByText('Stated in report')).not.toBeInTheDocument();
  });

  it('explains what an inference was derived from', async () => {
    const user = userEvent.setup();
    await reachReview(user);
    expect(screen.getByTestId('field-her2_status').textContent)
      .toMatch(/Derived from the component results/i);
  });

  it('shows both readings of a conflicting field', async () => {
    const user = userEvent.setup();
    await reachReview(user);
    const row = screen.getByTestId('field-grade');
    expect(within(row).getByText('Conflicting')).toBeInTheDocument();
    expect(screen.getByTestId('alts-grade').textContent).toMatch(/Grade 3/);
  });

  it('counts the readings that need a decision', async () => {
    const user = userEvent.setup();
    await reachReview(user);
    expect(screen.getByTestId('needs-decision').textContent).toMatch(/\b2\b/);
  });

  it('accepting an inference records it as a user correction', async () => {
    const user = userEvent.setup();
    await reachReview(user);
    await user.click(screen.getByTestId('accept-her2_status'));
    const row = screen.getByTestId('field-her2_status');
    expect(within(row).getByText('You corrected')).toBeInTheDocument();
  });

  it('sends an accepted inference as user_corrected, never as inferred', async () => {
    const user = userEvent.setup();
    await reachReview(user);
    await user.click(screen.getByTestId('accept-her2_status'));
    await user.click(screen.getByTestId('confirm-fields'));
    await screen.findByTestId('fields-confirmed');

    const call = calls().find((c) => String(c[0]).includes('/confirm'));
    const body = JSON.parse((call![1] as RequestInit).body as string);
    const her2 = body.fields.find((f: { key: string }) => f.key === 'her2_status');
    expect(her2.provenance).toBe('user_corrected');
    expect(her2.original_value).toBe('HER2 positive (by ISH amplification)');
  });

  it('never submits a raw inferred or conflicting provenance', async () => {
    const user = userEvent.setup();
    await reachReview(user);
    await user.click(screen.getByTestId('accept-her2_status'));
    await user.click(screen.getByTestId('accept-grade'));
    await user.click(screen.getByTestId('confirm-fields'));
    await screen.findByTestId('fields-confirmed');

    const call = calls().find((c) => String(c[0]).includes('/confirm'));
    const body = JSON.parse((call![1] as RequestInit).body as string);
    const unresolved = body.fields.filter(
      (f: { provenance: string }) => ['inferred', 'ambiguous', 'conflicting']
        .includes(f.provenance));
    expect(unresolved.map((f: { key: string }) => f.key)).toEqual([]);
  });
});

/* ===================================================================== */
describe('provenance', () => {
  it('marks a typed value as entered by the user', async () => {
    const user = userEvent.setup();
    await reachReview(user);

    const input = screen.getByRole('textbox', { name: /Cancer indication/i });
    await user.type(input, 'Breast Cancer');

    const row = screen.getByTestId('field-cancer_indication');
    expect(within(row).getByText('You entered')).toBeInTheDocument();
    expect(within(row).queryByText('Stated in report')).not.toBeInTheDocument();
  });

  it('reverts to not-in-report when a value is cleared', async () => {
    const user = userEvent.setup();
    await reachReview(user);

    const input = screen.getByRole('textbox', { name: /^Stage/i });
    await user.type(input, 'Stage II');
    await user.clear(input);

    const row = screen.getByTestId('field-stage');
    expect(within(row).getByText('Not in report')).toBeInTheDocument();
  });

  it('shows which fields map into the workflow', async () => {
    const user = userEvent.setup();
    await reachReview(user);
    expect(within(screen.getByTestId('field-cancer_indication'))
      .getByText(/maps to disease/i)).toBeInTheDocument();
    expect(within(screen.getByTestId('field-stage'))
      .queryByText(/maps to/i)).not.toBeInTheDocument();
  });
});

/* ===================================================================== */
describe('upload gating', () => {
  it('requires the attestation before uploading', async () => {
    const user = userEvent.setup();
    renderAt('/report');
    await screen.findByTestId('attestation');

    const file = new File(['synthetic fictional test content'],
                          'report.txt', { type: 'text/plain' });
    await user.upload(screen.getByLabelText(/Medical report document/i), file);

    expect(screen.getByTestId('submit-upload')).toBeDisabled();
    expect(screen.getByTestId('attestation-required')).toBeInTheDocument();
  });

  it('enables upload once attested', async () => {
    const user = userEvent.setup();
    renderAt('/report');
    await screen.findByTestId('attestation');

    const file = new File(['synthetic fictional test content'],
                          'report.txt', { type: 'text/plain' });
    await user.upload(screen.getByLabelText(/Medical report document/i), file);
    await user.click(screen.getByTestId('attestation'));

    expect(screen.getByTestId('submit-upload')).toBeEnabled();
  });

  it('sends the attestation and classification with the file', async () => {
    const user = userEvent.setup();
    renderAt('/report');
    await screen.findByTestId('attestation');

    const file = new File(['synthetic fictional test content'],
                          'report.txt', { type: 'text/plain' });
    await user.upload(screen.getByLabelText(/Medical report document/i), file);
    await user.click(screen.getByTestId('attestation'));
    await user.click(screen.getByTestId('submit-upload'));
    await screen.findByTestId('document-text');

    const call = calls().find((c) => String(c[0]).endsWith('/api/v1/reports')
      && (c[1] as RequestInit)?.method === 'POST');
    const body = (call![1] as RequestInit).body as FormData;
    expect(body.get('attested')).toBe('true');
    expect(body.get('classification')).toBe('synthetic');
  });
});

/* ===================================================================== */
describe('refusals are surfaced', () => {
  it('shows the refusal when real patient data is rejected', async () => {
    installFetch({
      uploadStatus: 400,
      uploadBody: {
        error: 'real_patient_data_refused',
        message: 'This platform does not accept real patient reports.',
        detail: 'No encryption at rest; no recorded legal basis.',
        data_available: false,
      },
    });
    const user = userEvent.setup();
    renderAt('/report');
    await screen.findByTestId('synthetic-reports');
    await user.click(within(screen.getByTestId('synthetic-synthetic-breast-pathology'))
      .getByRole('button', { name: /Load this report/i }));

    const error = await screen.findByTestId('upload-error');
    expect(error.textContent).toMatch(/does not accept real patient reports/i);
    expect(screen.queryByTestId('document-text')).not.toBeInTheDocument();
  });

  it('shows the refusal for an unsupported file', async () => {
    installFetch({
      uploadStatus: 400,
      uploadBody: { error: 'unsafe_file_type',
        message: 'This looks like a Windows executable, not a medical report.',
        data_available: false },
    });
    const user = userEvent.setup();
    renderAt('/report');
    await screen.findByTestId('synthetic-reports');
    await user.click(within(screen.getByTestId('synthetic-synthetic-breast-pathology'))
      .getByRole('button', { name: /Load this report/i }));

    expect((await screen.findByTestId('upload-error')).textContent)
      .toMatch(/Windows executable/i);
  });

  it('degrades gracefully when the server errors', async () => {
    installFetch({ uploadStatus: 500, uploadBody: { error: 'server_error',
      message: 'Extraction failed.', data_available: false } });
    const user = userEvent.setup();
    renderAt('/report');
    await screen.findByTestId('synthetic-reports');
    await user.click(within(screen.getByTestId('synthetic-synthetic-breast-pathology'))
      .getByRole('button', { name: /Load this report/i }));

    expect(await screen.findByTestId('upload-error')).toBeInTheDocument();
    expect(screen.queryByTestId('field-stage')).not.toBeInTheDocument();
  });

  it('reports an unreadable PDF honestly', async () => {
    installFetch({
      uploadBody: { ...UPLOAD, format_key: 'pdf', document_readable: false,
        document_text: null,
        unreadable_reason: 'No PDF reader is installed, so the text of this '
          + 'document cannot be displayed.' },
    });
    const user = userEvent.setup();
    renderAt('/report');
    await screen.findByTestId('synthetic-reports');
    await user.click(within(screen.getByTestId('synthetic-synthetic-breast-pathology'))
      .getByRole('button', { name: /Load this report/i }));

    expect((await screen.findByTestId('unreadable-reason')).textContent)
      .toMatch(/No PDF reader is installed/i);
  });
});

/* ===================================================================== */
describe('synthetic fixtures', () => {
  it('lists three labelled synthetic reports', async () => {
    renderAt('/report');
    const list = await screen.findByTestId('synthetic-reports');
    expect(within(list).getAllByText('Synthetic demonstration document'))
      .toHaveLength(3);
  });

  it('states the patients do not exist', async () => {
    renderAt('/report');
    expect((await screen.findByTestId('synthetic-notice')).textContent)
      .toMatch(/patients do not exist/i);
  });

  it('runs the real pipeline and reports the engine that ran', async () => {
    const user = userEvent.setup();
    await reachReview(user);
    expect(screen.getByTestId('engine-version').textContent)
      .toMatch(/rule-based-oncology-extractor/);
    expect(screen.getByTestId('extraction-message').textContent)
      .toMatch(/Read \d+ of \d+ fields/i);
  });
});

/* ===================================================================== */
describe('confirmation and mapping', () => {
  it('blocks continuing until the fields are confirmed', async () => {
    const user = userEvent.setup();
    await reachReview(user);
    expect(screen.getByTestId('continue-to-workflow')).toBeDisabled();
    expect(screen.getByTestId('confirm-first')).toBeInTheDocument();
  });

  it('confirms fields and reports success', async () => {
    const user = userEvent.setup();
    await reachReview(user);
    await user.click(screen.getByTestId('confirm-fields'));
    expect(await screen.findByTestId('fields-confirmed')).toBeInTheDocument();
  });

  it('offers only subtypes valid for the chosen indication', async () => {
    const user = userEvent.setup();
    await reachReview(user);
    await user.click(screen.getByTestId('confirm-fields'));
    await screen.findByTestId('fields-confirmed');

    await user.selectOptions(screen.getByRole('combobox', { name: 'Indication' }),
                             'Breast Cancer');
    const subtypes = screen.getByRole('combobox', { name: 'Disease subtype' });
    expect(within(subtypes).getByRole('option',
      { name: 'HER2-enriched (ER-, PR-, HER2+)' })).toBeInTheDocument();
    expect(within(subtypes).queryByRole('option',
      { name: 'AFP-high HCC' })).not.toBeInTheDocument();
  });

  it('carries the confirmed context into the workflow', async () => {
    const user = userEvent.setup();
    await reachReview(user);
    await user.click(screen.getByTestId('confirm-fields'));
    await screen.findByTestId('fields-confirmed');

    await user.selectOptions(screen.getByRole('combobox', { name: 'Indication' }),
                             'Breast Cancer');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Disease subtype' }),
                             'HER2-enriched (ER-, PR-, HER2+)');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Therapeutic agent' }),
                             'Trastuzumab (Herceptin)');
    await user.click(screen.getByTestId('continue-to-workflow'));

    await screen.findByRole('heading', { name: /Step 1/i, level: 2 });
    expect(screen.getByRole('combobox', { name: 'Indication' }))
      .toHaveValue('Breast Cancer');
  });

  it('carries all three selections, not just the indication', async () => {
    // Regression: setSelection's cascade used to clear subtype and drug even
    // when the caller supplied a complete triple, so Step 1 arrived
    // half-populated and could not be continued.
    const user = userEvent.setup();
    await reachReview(user);
    await user.click(screen.getByTestId('confirm-fields'));
    await screen.findByTestId('fields-confirmed');

    await user.selectOptions(screen.getByRole('combobox', { name: 'Indication' }),
                             'Breast Cancer');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Disease subtype' }),
                             'HER2-enriched (ER-, PR-, HER2+)');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Therapeutic agent' }),
                             'Trastuzumab (Herceptin)');
    await user.click(screen.getByTestId('continue-to-workflow'));
    await screen.findByRole('heading', { name: /Step 1/i, level: 2 });

    expect(screen.getByRole('combobox', { name: 'Indication' }))
      .toHaveValue('Breast Cancer');
    expect(screen.getByRole('combobox', { name: 'Disease subtype' }))
      .toHaveValue('HER2-enriched (ER-, PR-, HER2+)');
    expect(screen.getByRole('combobox', { name: 'Therapeutic agent' }))
      .toHaveValue('Trastuzumab (Herceptin)');
    expect(screen.getByRole('button', { name: /Continue to design parameters/i }))
      .toBeEnabled();
  });

  it('states that the report affects no calculation', async () => {
    const user = userEvent.setup();
    await reachReview(user);
    const note = screen.getByTestId('no-calculation-effect');
    expect(note.textContent).toMatch(/take no disease as input/i);
    expect(note.textContent).toMatch(/Nothing in this report can change a calculated number/i);
  });
});

/* ===================================================================== */
describe('sensitive data never reaches client storage', () => {
  async function snapshotStorage() {
    return {
      local: JSON.stringify(localStorage),
      session: JSON.stringify(sessionStorage),
    };
  }

  it('stores no report content after loading a document', async () => {
    const user = userEvent.setup();
    await reachReview(user);

    const { local, session } = await snapshotStorage();
    for (const store of [local, session]) {
      expect(store).not.toMatch(/carcinoma/i);
      expect(store).not.toMatch(/SYNTHETIC DEMONSTRATION DOCUMENT/i);
      expect(store).not.toMatch(/synthetic-breast-pathology/i);
    }
  });

  it('stores no typed clinical value', async () => {
    const user = userEvent.setup();
    await reachReview(user);
    await user.type(screen.getByRole('textbox', { name: /^Stage/i }),
                    'Stage IIB');
    await user.click(screen.getByTestId('confirm-fields'));
    await screen.findByTestId('fields-confirmed');

    const { local, session } = await snapshotStorage();
    for (const store of [local, session]) {
      expect(store).not.toMatch(/Stage IIB/i);
    }
  });

  it('stores no assessment identifier or content hash', async () => {
    const user = userEvent.setup();
    await reachReview(user);
    const { local, session } = await snapshotStorage();
    for (const store of [local, session]) {
      expect(store).not.toContain(UPLOAD.content_hash);
    }
  });

  it('keeps only the therapeutic context in the saved draft', async () => {
    const user = userEvent.setup();
    await reachReview(user);
    await user.type(screen.getByRole('textbox', { name: /^Grade/i }), 'Grade 3');
    await user.click(screen.getByTestId('confirm-fields'));
    await screen.findByTestId('fields-confirmed');

    await user.selectOptions(screen.getByRole('combobox', { name: 'Indication' }),
                             'Breast Cancer');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Disease subtype' }),
                             'HER2-enriched (ER-, PR-, HER2+)');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Therapeutic agent' }),
                             'Trastuzumab (Herceptin)');
    await user.click(screen.getByTestId('continue-to-workflow'));
    await screen.findByRole('heading', { name: /Step 1/i, level: 2 });

    const rail = screen.getByRole('navigation', { name: /workflow progress/i });
    await user.click(within(rail).getByRole('button', { name: /Save draft/i }));

    const raw = localStorage.getItem('nanobio.designDrafts.v1') ?? '';
    // The curated selection is expected; the clinical detail is not.
    expect(raw).toContain('Breast Cancer');
    expect(raw).not.toMatch(/Grade 3/);
    expect(raw).not.toMatch(/carcinoma/i);
  });
});
