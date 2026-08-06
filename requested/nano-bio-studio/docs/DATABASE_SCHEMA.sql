-- ===========================================================================
-- NanoBio Studio — database schema and safe sample records
-- ===========================================================================
--
-- WHY THIS FILE EXISTS
-- The live databases are NOT included in the archive. Between them they hold
-- bcrypt password hashes, 148 session token hashes, 213 authentication audit
-- rows with IP addresses and user agents, and 16 medical-report assessment
-- records. None of that may travel in a source archive.
--
-- This file carries the full schema plus a few synthetic sample rows, so the
-- structure can be inspected and a development database recreated without any
-- real credential or personal data.
--
-- HOW TO RECREATE A DEVELOPMENT DATABASE
--   The FastAPI backend creates its tables at startup:
--       cd nanobio_studio_backend
--       python -m uvicorn nanobio_studio.app.vertical_slice:app --port 8000
--   Then create an administrator (it prompts; nothing is hard-coded):
--       python scripts/create_admin.py --username admin --email you@example.org
--   Seed the synthetic demonstration scenarios:
--       python scripts/demo_data.py seed
--
-- Every sample row below is synthetic. No row came from a real user, a real
-- patient or a real experiment.
-- ===========================================================================

-- ----------------------------------------------------------------------
-- CURRENT APPLICATION — auth, workspace and report schema
-- Created by SQLAlchemy at startup; used by the FastAPI backend.
-- ----------------------------------------------------------------------

CREATE TABLE auth_audit_log (
	id INTEGER NOT NULL, 
	event VARCHAR(32) NOT NULL, 
	user_id INTEGER, 
	username_attempted VARCHAR(64), 
	ip_address VARCHAR(64), 
	user_agent VARCHAR(512), 
	detail TEXT, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES auth_users (id) ON DELETE SET NULL
);

-- rows in the live database: 213
-- sensitive columns (never exported): detail, ip_address, user_agent, username_attempted

CREATE TABLE auth_sessions (
	id INTEGER NOT NULL, 
	token_hash VARCHAR(64) NOT NULL, 
	user_id INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	last_activity_at DATETIME NOT NULL, 
	expires_at DATETIME NOT NULL, 
	ip_address VARCHAR(64), 
	user_agent VARCHAR(512), 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES auth_users (id) ON DELETE CASCADE
);

-- rows in the live database: 148
-- sensitive columns (never exported): ip_address, token_hash, user_agent

CREATE TABLE auth_users (
	id INTEGER NOT NULL, 
	username VARCHAR(64) NOT NULL, 
	email VARCHAR(255), 
	full_name VARCHAR(255), 
	password_hash TEXT NOT NULL, 
	role VARCHAR(32) NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	created_at DATETIME NOT NULL, 
	last_login_at DATETIME, 
	PRIMARY KEY (id)
);

-- rows in the live database: 2
-- sensitive columns (never exported): email, password_hash

CREATE TABLE report_assessments (
	id INTEGER NOT NULL, 
	owner_id INTEGER NOT NULL, 
	display_name VARCHAR(160) NOT NULL, 
	content_hash VARCHAR(64) NOT NULL, 
	format_key VARCHAR(16) NOT NULL, 
	media_type VARCHAR(80) NOT NULL, 
	size_bytes INTEGER NOT NULL, 
	classification VARCHAR(32) NOT NULL, 
	attested BOOLEAN NOT NULL, 
	policy_version VARCHAR(48) NOT NULL, 
	fixture_slug VARCHAR(80), 
	status VARCHAR(32) NOT NULL, 
	extraction_status VARCHAR(48) NOT NULL, 
	extraction_engine VARCHAR(80) NOT NULL, 
	extraction_engine_version VARCHAR(48) NOT NULL, 
	extraction_contract_version VARCHAR(48) NOT NULL, 
	confirmed_fields_json TEXT, 
	extraction_result_json TEXT, 
	mapped_disease VARCHAR(120), 
	mapped_subtype VARCHAR(160), 
	mapped_drug VARCHAR(160), 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	retain_until DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(owner_id) REFERENCES auth_users (id) ON DELETE CASCADE
);

-- rows in the live database: 16
-- sensitive columns (never exported): content_hash

CREATE TABLE report_audit_log (
	id INTEGER NOT NULL, 
	event VARCHAR(32) NOT NULL, 
	user_id INTEGER, 
	assessment_id INTEGER, 
	content_hash VARCHAR(64), 
	detail VARCHAR(500), 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES auth_users (id) ON DELETE SET NULL
);

-- rows in the live database: 45
-- sensitive columns (never exported): content_hash, detail

CREATE TABLE report_documents (
	id INTEGER NOT NULL, 
	assessment_id INTEGER NOT NULL, 
	content BLOB NOT NULL, 
	text_content TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(assessment_id) REFERENCES report_assessments (id) ON DELETE CASCADE
);

-- rows in the live database: 16

CREATE TABLE workspace_demo_templates (
	id INTEGER NOT NULL, 
	slug VARCHAR(100) NOT NULL, 
	fixture_version VARCHAR(64) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	purpose TEXT NOT NULL, 
	disease VARCHAR(120) NOT NULL, 
	subtype VARCHAR(160) NOT NULL, 
	drug VARCHAR(160) NOT NULL, 
	payload_json TEXT NOT NULL, 
	technical BOOLEAN NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_demo_template_slug UNIQUE (slug)
);

-- rows in the live database: 7

CREATE TABLE workspace_projects (
	id INTEGER NOT NULL, 
	owner_id INTEGER NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	description TEXT, 
	origin VARCHAR(16) NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(owner_id) REFERENCES auth_users (id) ON DELETE CASCADE
);

-- rows in the live database: 0

CREATE TABLE workspace_runs (
	id INTEGER NOT NULL, 
	owner_id INTEGER NOT NULL, 
	project_id INTEGER, 
	name VARCHAR(200) NOT NULL, 
	origin VARCHAR(16) NOT NULL, 
	demo_scenario_slug VARCHAR(100), 
	demo_fixture_version VARCHAR(64), 
	disease VARCHAR(120), 
	subtype VARCHAR(160), 
	drug VARCHAR(160), 
	status VARCHAR(16) NOT NULL, 
	design_inputs_json TEXT, 
	pk_inputs_json TEXT, 
	design_result_json TEXT, 
	pk_result_json TEXT, 
	design_score_version VARCHAR(64), 
	pk_calculation_version VARCHAR(64), 
	engines_run TEXT NOT NULL, 
	engines_not_run TEXT NOT NULL, 
	created_at DATETIME NOT NULL, pathway VARCHAR(32) NOT NULL DEFAULT 'research_design', research_purpose VARCHAR(80) NULL, inputs_are_synthetic BOOLEAN NOT NULL DEFAULT 0, report_assessment_id INTEGER NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(owner_id) REFERENCES auth_users (id) ON DELETE CASCADE, 
	FOREIGN KEY(project_id) REFERENCES workspace_projects (id) ON DELETE SET NULL
);

-- rows in the live database: 5

-- Sample rows from workspace_demo_templates (synthetic demonstration data)
INSERT INTO "workspace_demo_templates" (id, slug, fixture_version, name, purpose, disease, subtype, drug, payload_json, technical, created_at, updated_at) VALUES (1, 'breast-her2-targeted', 'demo-scenarios-1.0.0', 'Breast cancer — HER2-targeted stealth nanoparticle', 'Demonstrates a well-formed, actively-targeted design running the full connected path: design impact score plus a complete pharmacokinetic profile. Use it to see…(truncated)', 'Breast Cancer', 'HER2-enriched (ER-, PR-, HER2+)', 'Trastuzumab (Herceptin)', '{"assumptions": ["All nanoparticle and pharmacokinetic values are synthetic demonstration inputs. They are not measurements and not literature values for any sp…(truncated)', 0, '2026-07-31 06:35:41.473066', '2026-07-31 06:35:41.473070');
INSERT INTO "workspace_demo_templates" (id, slug, fixture_version, name, purpose, disease, subtype, drug, payload_json, technical, created_at, updated_at) VALUES (2, 'lung-nsclc-checkpoint', 'demo-scenarios-1.0.0', 'Lung cancer — NSCLC passive-targeting carrier', 'A passively-targeted design with no ligand, to contrast with the actively-targeted breast scenario. Shows how the scoring function reports its fixed passive-tar…(truncated)', 'Lung Cancer', 'Non-Small Cell Lung Cancer (NSCLC)', 'Pembrolizumab', '{"assumptions": ["All nanoparticle and pharmacokinetic values are synthetic demonstration inputs. They are not measurements and not literature values for any sp…(truncated)', 0, '2026-07-31 06:35:41.473072', '2026-07-31 06:35:41.473072');

-- Sample rows from workspace_runs (synthetic demonstration data)
INSERT INTO "workspace_runs" (id, owner_id, project_id, name, origin, demo_scenario_slug, demo_fixture_version, disease, subtype, drug, status, design_inputs_json, pk_inputs_json, design_result_json, pk_result_json, design_score_version, pk_calculation_version, engines_run, engines_not_run, created_at, pathway, research_purpose, inputs_are_synthetic, report_assessment_id) VALUES (7, 2, NULL, 'Untitled design', 'USER', NULL, NULL, 'Breast Cancer', 'HER2-enriched (ER-, PR-, HER2+)', 'Trastuzumab (Herceptin)', 'PARTIAL', '{"size_nm": 100, "charge_mv": -5, "encapsulation_percent": 85}', NULL, '{"design_impact_score": {"delivery": 87.52475247524752, "toxicity": 0.8, "cost": 80.75}, "score_version": "design-impact-adapter-0.1.0", "component_scores": {"d…(truncated)', NULL, 'design-impact-adapter-0.1.0', NULL, 'Design impact score (core.scoring.compute_impact)', 'Pharmacokinetic simulation	Required inputs were incomplete, so the engine was not called.
Scientific assessments	The assessment engines are not connected to thi…(truncated)', '2026-08-02 12:47:45.537342', 'PATIENT_ASSESSMENT', NULL, 0, NULL);
INSERT INTO "workspace_runs" (id, owner_id, project_id, name, origin, demo_scenario_slug, demo_fixture_version, disease, subtype, drug, status, design_inputs_json, pk_inputs_json, design_result_json, pk_result_json, design_score_version, pk_calculation_version, engines_run, engines_not_run, created_at, pathway, research_purpose, inputs_are_synthetic, report_assessment_id) VALUES (8, 2, NULL, 'Liver cancer (HCC) — GalNAc hepatocyte-targeted particle', 'DEMO', 'liver-hcc-galnac', 'demo-scenarios-1.0.0', 'Liver Cancer (HCC)', 'AFP-high HCC', 'Sorafenib', 'COMPLETE', '{"size_nm": 100, "charge_mv": -5, "encapsulation_percent": 85, "pdi": 0.15, "hydrodynamic_size_nm": 120, "surface_coating": ["PEG (Stealth)"], "coating_thicknes…(truncated)', '{"dose_mg_kg": 3, "kabs_per_h": 0.5, "kel_per_h": 0.1, "k12_per_h": 0.2, "k21_per_h": 0.05, "duration_h": 48, "time_step_h": 0.1}', '{"design_impact_score": {"delivery": 90.6930693069307, "toxicity": 0.8, "cost": 100}, "score_version": "design-impact-adapter-0.1.0", "component_scores": {"deli…(truncated)', '{"concentration_time": {"time_h": [0, 0.1, 0.2, 0.30000000000000004, 0.4, 0.5, 0.6000000000000001, 0.7000000000000001, 0.8, 0.9, 1, 1.1, 1.2000000000000002, 1.3…(truncated)', 'design-impact-adapter-0.1.0', 'pk-two-compartment-adapter-0.1.0', 'Design impact score (core.scoring.compute_impact)
Pharmacokinetic simulation (utils.pk_model)', 'Scientific assessments	The assessment engines are not connected to this workflow.', '2026-08-02 13:38:06.168360', 'DEMO_SCENARIO', NULL, 1, NULL);

-- ----------------------------------------------------------------------
-- LEGACY STREAMLIT — users.db
-- Used only by the legacy Streamlit application (auth.py).
-- ----------------------------------------------------------------------

CREATE TABLE activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            action TEXT NOT NULL,
            details TEXT,
            ip_address TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (username) REFERENCES users(username)
        );

-- rows in the live database: 9
-- sensitive columns (never exported): ip_address

CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT,
                    password_hash BLOB NOT NULL,
                    role TEXT DEFAULT 'viewer',
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP
                , last_activity TIMESTAMP, session_start TIMESTAMP);

-- rows in the live database: 1
-- sensitive columns (never exported): email, password_hash

-- ----------------------------------------------------------------------
-- LEGACY STREAMLIT — trial_registry.db
-- Synthetic simulation records from the legacy application.
-- ----------------------------------------------------------------------

CREATE TABLE trial_sequences (
            date TEXT,
            disease_code TEXT,
            next_sequence INTEGER DEFAULT 1,
            PRIMARY KEY (date, disease_code)
        );

-- rows in the live database: 0

CREATE TABLE trials (
            trial_id TEXT PRIMARY KEY,
            disease_subtype TEXT,
            disease_name TEXT,
            drug_name TEXT,
            np_size_nm INTEGER,
            np_charge_mv INTEGER,
            np_peg_percent REAL,
            np_zeta_potential REAL,
            np_pdi REAL,
            treatment_dose_mgkg REAL,
            treatment_route TEXT,
            treatment_frequency TEXT,
            treatment_duration_days INTEGER,
            trial_outcomes TEXT,
            trial_notes TEXT,
            creation_timestamp TEXT,
            status TEXT DEFAULT 'Active',
            notes TEXT,
            export_path TEXT
        );

-- rows in the live database: 1

-- Sample rows from trials (synthetic demonstration data)
INSERT INTO "trials" (trial_id, disease_subtype, disease_name, drug_name, np_size_nm, np_charge_mv, np_peg_percent, np_zeta_potential, np_pdi, treatment_dose_mgkg, treatment_route, treatment_frequency, treatment_duration_days, trial_outcomes, trial_notes, creation_timestamp, status, notes, export_path) VALUES ('T-031', 'hcc_l', 'Hepatocellular Carcinoma', '50', 100, -5, 85.0, -30.0, 1.2, 10.0, 'IV', 'Once', 1, 'Successful simulation', NULL, '2026-07-30T18:13:17.794089+00:00', 'Active', 'Material: Lipid NP', NULL);
