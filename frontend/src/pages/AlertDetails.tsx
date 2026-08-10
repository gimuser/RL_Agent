import { Link, useParams } from "react-router-dom";
import { EmptyState } from "../components/ui/EmptyState";
import { PageHeader } from "../components/ui/PageHeader";
import { QueryState } from "../components/ui/QueryState";
import { StatusBadge } from "../components/ui/StatusBadge";
import { useApi } from "../hooks/useApi";
import { alertsService } from "../services/alerts.service";
import { decisionsService } from "../services/decisions.service";
import { formatDateTime } from "../utils/format";

const notProvided = "Not provided by API";

export function AlertDetailsPage() {
  const { id = "" } = useParams();
  const alert = useApi(() => alertsService.getAlert(id));
  const decisions = useApi(decisionsService.getDecisions);

  return (
    <>
      <PageHeader eyebrow="ALERT INVESTIGATION" title={`Alert ${id || "details"}`} description="Only fields supplied by the current alert and decision APIs are populated." actions={<Link className="button button--quiet" to="/alerts">← Back to alerts</Link>} />
      <QueryState state={alert}>
        {(data) => {
          const linkedDecision = decisions.data?.find((decision) => String(decision.incident_id) === String(data.id));
          return <div className="detail-grid">
            <section className="panel detail-panel">
              <div className="panel__header"><div><p className="eyebrow">ALERT INFORMATION</p><h2>{data.title}</h2></div><StatusBadge value={data.severity} /></div>
              <dl className="detail-list">
                <Detail label="Alert ID" value={String(data.id)} />
                <Detail label="Severity" value={data.severity} />
                <Detail label="Source" value={data.source} />
                <Detail label="Alert type" value={notProvided} muted />
                <Detail label="Timestamp" value={notProvided} muted />
                <Detail label="Destination" value={notProvided} muted />
                <Detail label="Threat score" value={notProvided} muted />
                <Detail label="Asset criticality" value={notProvided} muted />
                <Detail label="Business criticality" value={notProvided} muted />
                <Detail label="MITRE ATT&CK technique" value={notProvided} muted />
              </dl>
            </section>
            <section className="panel decision-panel">
              <div className="panel__header"><div><p className="eyebrow">RL AGENT DECISION</p><h2>Decision record</h2></div></div>
              {decisions.isLoading ? <p className="muted">Checking linked decision…</p> : linkedDecision ? <dl className="detail-list">
                <Detail label="Action" value={linkedDecision.action} />
                <Detail label="Decision ID" value={String(linkedDecision.id)} />
                <Detail label="Timestamp" value={formatDateTime(linkedDecision.timestamp)} />
                <Detail label="Priority" value={notProvided} muted />
                <Detail label="Confidence" value={notProvided} muted />
                <Detail label="Reward" value={notProvided} muted />
                <Detail label="Processing time" value={notProvided} muted />
              </dl> : <EmptyState title="No linked decision found" description="The decision API has not returned a record linked to this alert." compact />}
              <div className="action-unavailable"><strong>Human actions are not enabled</strong><p>The current API exposes no approval, escalation, reassignment, delay, or close endpoint. No action is simulated here.</p></div>
            </section>
            <section className="panel detail-panel detail-panel--full">
              <div className="panel__header"><div><p className="eyebrow">STATE VECTOR</p><h2>Features available to the interface</h2></div></div>
              <div className="state-vector"><Feature label="Severity" value={data.severity} available /><Feature label="Alert title" value={data.title} available /><Feature label="Source" value={data.source} available /><Feature label="Alert type" value={notProvided} /><Feature label="Asset criticality" value={notProvided} /><Feature label="Threat score" value={notProvided} /><Feature label="Analyst load" value={notProvided} /><Feature label="Historical alerts" value={notProvided} /><Feature label="Playbook availability" value={notProvided} /><Feature label="Business criticality" value={notProvided} /></div>
              <p className="panel-note">The API currently does not return explanation factors. The dashboard therefore shows supplied state features only and does not infer an explanation.</p>
            </section>
          </div>;
        }}
      </QueryState>
    </>
  );
}

function Detail({ label, value, muted = false }: { label: string; value: string; muted?: boolean }) {
  return <div><dt>{label}</dt><dd className={muted ? "not-provided" : ""}>{value}</dd></div>;
}
function Feature({ label, value, available = false }: { label: string; value: string; available?: boolean }) {
  return <div className="feature"><div><span>{label}</span><strong>{value}</strong></div><span className={available ? "feature__available" : "not-provided"}>{available ? "Available" : "Unavailable"}</span></div>;
}
