import { Link } from 'react-router-dom';
import { Card } from '../design-system/components';
import './HelpPage.css';

export default function HelpPage() {
  return (
    <div className="help-page" data-testid="help-page">
      <header className="help-page__intro">
        <p className="help-page__eyebrow">Documentation</p>
        <h2>Help &amp; Tutorial</h2>
        <p>
          Find your way through NanoBio Studio, understand how studies are
          organised, and locate account and access guidance.
        </p>
      </header>

      <div className="help-page__grid">
        <Card title="Start a study">
          <p>
            Choose a research, patient-assessment, or demonstration pathway.
            Each pathway records how the study began before entering the shared
            design workflow.
          </p>
          <Link to="/start">Open Start New Study</Link>
        </Card>

        <Card title="Review your work">
          <p>
            Use My Studies for saved work, Validation Registry for experiments,
            and Notifications for workflow events that need your attention.
          </p>
          <ul>
            <li><Link to="/studies">Open My Studies</Link></li>
            <li><Link to="/validation">Open Validation Registry</Link></li>
            <li><Link to="/notifications">Open Notifications</Link></li>
          </ul>
        </Card>

        <Card title="Account and access">
          <p>
            Review active sessions and change your password from Account
            security. Organization access and study assignments determine which
            records and actions are available to you.
          </p>
          <ul>
            <li><Link to="/account/security">Open Account security</Link></li>
            <li><Link to="/organization">Open Organization</Link></li>
          </ul>
        </Card>

        <Card title="Using results responsibly">
          <p>
            Check the status and limitations shown with each result. Preserve
            candidate-version identity when reviewing simulations, evidence,
            reports, exports, and approval records.
          </p>
          <Link to="/scientific-readiness">Open Scientific Readiness</Link>
        </Card>
      </div>
    </div>
  );
}
