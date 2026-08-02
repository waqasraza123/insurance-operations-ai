import { getBackendStatus } from "@/lib/backend-health";

export default async function Home() {
  const backendStatus = await getBackendStatus();

  return (
    <main>
      <p className="eyebrow">Release 1 foundation</p>
      <h1>Insurance Operations AI</h1>
      <p className="summary">
        The frontend, API, and worker boundaries are ready for the first
        approved product slice.
      </p>
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
