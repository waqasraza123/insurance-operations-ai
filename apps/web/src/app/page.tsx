import Link from "next/link";

import { getReceptionistSettings } from "@/features/receptionist/api";
import type { ReceptionistSettings } from "@/features/receptionist/contracts";
import { getBackendStatus } from "@/lib/backend-health";
import { parsePublicEnvironment } from "@/lib/environment";

export default async function Home() {
  const environment = parsePublicEnvironment(process.env);
  const [backendStatus, receptionistSettings] = await Promise.all([
    getBackendStatus(),
    environment.demoSandboxEnabled
      ? Promise.resolve(undefined)
      : loadReceptionistSettings(environment.apiBaseUrl),
  ]);
  const agencyName =
    receptionistSettings?.publicName ??
    (environment.demoSandboxEnabled
      ? "Harborline Insurance"
      : "Your insurance agency");

  return (
    <main className="site-shell">
      <nav className="top-nav" aria-label="Primary navigation">
        <span className="brand-link">Insurance Operations AI</span>
        {(environment.conversationAiEnabled ||
          environment.demoSandboxEnabled) && (
          <div className="nav-links">
            {environment.demoSandboxEnabled ? (
              <Link className="text-link" href="/phone-demo">
                Phone demo
              </Link>
            ) : (
              <>
                <Link className="text-link" href="/receptionist-settings">
                  Agency profile
                </Link>
                <Link className="text-link" href="/approved-faqs">
                  Approved FAQs
                </Link>
              </>
            )}
          </div>
        )}
      </nav>

      <section className="hero" aria-labelledby="hero-title">
        <div className="hero-copy">
          <p className="eyebrow">AI front desk for independent agencies</p>
          <h1 id="hero-title">Every new inquiry gets a clear next step.</h1>
          <p className="summary hero-summary">
            A real-time AI receptionist that welcomes prospects, handles
            agency-approved questions, captures structured insurance interest,
            and routes licensed work to your team.
          </p>
          <div className="hero-actions">
            {environment.demoSandboxEnabled ? (
              <Link className="primary-link" href="/phone-demo">
                Call the phone agent
              </Link>
            ) : environment.conversationAiEnabled ? (
              <Link className="primary-link" href="/voice-test">
                Talk to the receptionist
              </Link>
            ) : (
              <p className="feature-disabled">
                Voice AI is disabled in this environment.
              </p>
            )}
            <a className="secondary-link" href="#workflow">
              See the workflow
            </a>
          </div>
          <p className="demo-notice">
            Development showcase · fictional information only · no quotes,
            advice, binding, or coverage decisions
          </p>
        </div>

        <aside className="receptionist-preview" aria-label="Configured agency">
          <div className="preview-status">
            <span className="status-dot" />{" "}
            {environment.demoSandboxEnabled
              ? "Phone receptionist ready"
              : "Browser receptionist configured"}
          </div>
          <p className="preview-label">Now representing</p>
          <h2>{agencyName}</h2>
          {receptionistSettings ? (
            <>
              <blockquote>{receptionistSettings.greeting}</blockquote>
              <p className="preview-detail">
                <strong>Office hours</strong>
                {receptionistSettings.officeHours}
              </p>
              <div className="category-list" aria-label="Supported categories">
                {receptionistSettings.supportedInsuranceCategories.map(
                  (category) => (
                    <span key={category}>{category}</span>
                  ),
                )}
              </div>
            </>
          ) : (
            <p className="section-help">
              Run the development migration and seed to load the agency profile.
            </p>
          )}
        </aside>
      </section>

      <section id="workflow" className="workflow-section">
        <div className="section-intro">
          <p className="eyebrow">One guarded workflow</p>
          <h2>Useful at the front desk. Clear at the boundary.</h2>
        </div>
        <div className="capability-grid">
          <article>
            <span>01</span>
            <h3>Welcome and understand</h3>
            <p>
              The receptionist discloses that it is AI, listens in real time,
              and identifies why the prospect contacted the agency.
            </p>
          </article>
          <article>
            <span>02</span>
            <h3>Capture an actionable intake</h3>
            <p>
              Contact information and insurance interest remain editable until
              the user explicitly confirms the transcript and details.
            </p>
          </article>
          <article>
            <span>03</span>
            <h3>Escalate licensed work</h3>
            <p>
              Quotes, recommendations, binding, claims, and uncertain requests
              are reserved for agency staff instead of improvised by AI.
            </p>
          </article>
        </div>
      </section>

      <section className="runtime-panel" aria-labelledby="runtime-status">
        <div>
          <p className="section-kicker">Development environment</p>
          <h2 id="runtime-status">Runtime status</h2>
        </div>
        <dl>
          <div>
            <dt>Frontend</dt>
            <dd data-status="ready">Ready</dd>
          </div>
          <div>
            <dt>Backend</dt>
            <dd data-status={backendStatus.status}>{backendStatus.label}</dd>
          </div>
          <div>
            <dt>Worker</dt>
            <dd>Readiness checked separately</dd>
          </div>
        </dl>
      </section>
    </main>
  );
}

async function loadReceptionistSettings(
  apiBaseUrl: string,
): Promise<ReceptionistSettings | undefined> {
  try {
    return await getReceptionistSettings(apiBaseUrl);
  } catch {
    return undefined;
  }
}
