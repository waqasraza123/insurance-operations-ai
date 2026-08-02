import Link from "next/link";

import { getBackendStatus } from "@/lib/backend-health";
import { parsePublicEnvironment } from "@/lib/environment";

export default async function Home() {
  const backendStatus = await getBackendStatus();
  const environment = parsePublicEnvironment(process.env);

  return (
    <main>
      <p className="eyebrow">Release 1 foundation</p>
      <h1>Insurance Operations AI</h1>
      <p className="summary">
        Test a time-boxed, two-way AI conversation for synthetic insurance
        intake. Confirmed details become a customer record only after review.
      </p>
      {environment.conversationAiEnabled ? (
        <Link className="primary-link" href="/voice-test">
          Test Voice AI
        </Link>
      ) : (
        <p className="feature-disabled">
          Voice AI is disabled in this environment.
        </p>
      )}
      <section aria-labelledby="runtime-status">
        <h2 id="runtime-status">Runtime status</h2>
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
            <dd>Run its readiness check separately</dd>
          </div>
        </dl>
      </section>
    </main>
  );
}
