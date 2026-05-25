"use client";

import {
  AlertTriangle,
  CheckCircle2,
  Clipboard,
  FileCode2,
  GitBranch,
  History,
  Loader2,
  Play,
  Plus,
  RefreshCw,
  Rocket,
  Settings,
  ShieldCheck,
  Terminal,
  Trash2
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";

type Severity = "BLOCKER" | "WARNING" | "INFO";

type Finding = {
  severity: Severity;
  code: string;
  message: string;
  field?: string | null;
};

type CollectionInput = {
  name: string;
  version: string;
};

type EERequestPayload = {
  ee_name: string;
  description: string;
  purpose: string;
  automation_domain: string;
  base_image: string;
  ansible_core_version: string;
  ansible_runner_version: string;
  collections: CollectionInput[];
  python_dependencies: string[];
  system_dependencies: string[];
  image_tag: string;
  registry_namespace: string;
  publish_target: string;
  source?: string;
  change_summary?: string | null;
  parent_request_id?: string | null;
  allow_unpinned: boolean;
  custom_base_image: boolean;
  override_justification: {
    allow_unpinned?: string | null;
    custom_base_image?: string | null;
    broad_domain_scope?: string | null;
  };
};

type EERequestRecord = EERequestPayload & {
  id: string;
  status: string;
  approval_status: string;
  build_status: string;
  publish_status: string;
  build_job_name?: string | null;
  validation_findings: Finding[];
  compatibility_findings: Finding[];
  vulnerability_findings: Finding[];
  generated_files?: Record<string, string>;
  workspace_path?: string | null;
  registry_target?: string | null;
  image_digest?: string | null;
  created_at: string;
  updated_at: string;
};

type GeneratedFile = {
  name: string;
  content: string;
};

type DomainsResponse = {
  domains: Record<string, { description: string }>;
  collection_domains: Record<string, string>;
};

type BaseImagesResponse = {
  allowed_base_images: string[];
};

type LogResponse = {
  validation_log: string;
  build_log: string;
  publish_log: string;
};

type ApiErrorBody = {
  detail?: string | Array<{ message?: string; code?: string }> | Record<string, unknown>;
  message?: string;
};

type SectionId = "dashboard" | "create" | "files" | "history" | "approvals" | "settings";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

const sectionItems: Array<{ id: SectionId; label: string; icon: typeof ShieldCheck }> = [
  { id: "dashboard", label: "Dashboard", icon: Rocket },
  { id: "create", label: "Request", icon: ShieldCheck },
  { id: "files", label: "Review", icon: FileCode2 },
  { id: "history", label: "History", icon: History },
  { id: "approvals", label: "Build & Publish", icon: CheckCircle2 },
  { id: "settings", label: "Settings", icon: Settings }
];

const initialForm: EERequestPayload = {
  ee_name: "",
  description: "",
  purpose: "",
  automation_domain: "",
  base_image: "",
  ansible_core_version: "",
  ansible_runner_version: "",
  collections: [],
  python_dependencies: [],
  system_dependencies: [],
  image_tag: "",
  registry_namespace: "",
  publish_target: "quay.io",
  allow_unpinned: false,
  custom_base_image: false,
  override_justification: {
    allow_unpinned: null,
    custom_base_image: null,
    broad_domain_scope: null
  }
};

export default function Home() {
  const [activeSection, setActiveSection] = useState<SectionId>("dashboard");
  const [form, setForm] = useState<EERequestPayload>(initialForm);
  const [domains, setDomains] = useState<DomainsResponse | null>(null);
  const [baseImages, setBaseImages] = useState<string[]>([]);
  const [requests, setRequests] = useState<EERequestRecord[]>([]);
  const [selectedRequest, setSelectedRequest] = useState<EERequestRecord | null>(null);
  const [generatedFiles, setGeneratedFiles] = useState<GeneratedFile[]>([]);
  const [selectedFileName, setSelectedFileName] = useState("execution-environment.yml");
  const [compatibilityMarkdown, setCompatibilityMarkdown] = useState("");
  const [vulnerabilityMarkdown, setVulnerabilityMarkdown] = useState("");
  const [logs, setLogs] = useState<LogResponse | null>(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busyAction, setBusyAction] = useState("");
  const [nextTag, setNextTag] = useState("0.1.1");
  const [changeSummary, setChangeSummary] = useState("Refresh dependencies and rebuild as a new approved image tag.");

  const currentFindings = selectedRequest?.validation_findings ?? [];
  const compatibilityFindings = selectedRequest?.compatibility_findings ?? [];
  const vulnerabilityFindings = selectedRequest?.vulnerability_findings ?? [];
  const readinessFindings = dedupeFindings(
    [...currentFindings, ...compatibilityFindings, ...vulnerabilityFindings].filter(
      (finding) => finding.severity !== "INFO"
    )
  );
  const blockers = currentFindings.filter((finding) => finding.severity === "BLOCKER").length;
  const warnings = currentFindings.filter((finding) => finding.severity === "WARNING").length;
  const vulnerabilityWarnings = vulnerabilityFindings.filter((finding) => finding.severity !== "INFO").length;
  const imageRef = selectedRequest?.registry_target ?? buildImageRef(form);
  const selectedFile = generatedFiles.find((file) => file.name === selectedFileName) ?? generatedFiles[0];
  const buildCommands = selectedRequest ? buildTestCommands(selectedRequest) : "";
  const buildWorkspace = selectedRequest ? `data/builds/${selectedRequest.id}` : undefined;
  const generatedArtifactsExist = Boolean(
    selectedRequest?.generated_files && Object.keys(selectedRequest.generated_files).length
  );
  const generatedFilesAvailable = Boolean(generatedFiles.length || generatedArtifactsExist);

  const mappedDomains = useMemo(() => {
    if (!domains) {
      return [];
    }
    return form.collections.map((collection) => ({
      collection: collection.name,
      domain: domains.collection_domains[collection.name] ?? "unmapped"
    }));
  }, [domains, form.collections]);
  const distinctMappedDomains = new Set(mappedDomains.map((item) => item.domain).filter((domain) => domain !== "unmapped"));
  const showBroadScopeWarning = distinctMappedDomains.size > 1 || form.collections.length > 4;
  const nextAction = getNextAction(selectedRequest, generatedArtifactsExist, Boolean(generatedFiles.length), blockers);

  useEffect(() => {
    void loadReferenceData();
    void refreshRequests();
  }, []);

  useEffect(() => {
    if (selectedRequest) {
      setNextTag(suggestNextTag(selectedRequest.image_tag));
    }
  }, [selectedRequest?.id, selectedRequest?.image_tag]);

  useEffect(() => {
    if (activeSection === "approvals" && selectedRequest) {
      void loadLogsForRequest(selectedRequest.id);
    }
  }, [activeSection, selectedRequest?.id]);

  useEffect(() => {
    if (activeSection === "files" && selectedRequest && generatedArtifactsExist && generatedFiles.length === 0 && !busyAction) {
      void loadGeneratedFiles(selectedRequest, "files");
    }
  }, [activeSection, selectedRequest?.id]);

  async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {})
      }
    });
    if (!response.ok) {
      const body = await response.text();
      throw new Error(formatApiError(body, response.status));
    }
    return (await response.json()) as T;
  }

  async function runAction(label: string, action: () => Promise<void>) {
    setBusyAction(label);
    setError("");
    setNotice("");
    try {
      await action();
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "Unexpected error");
    } finally {
      setBusyAction("");
    }
  }

  async function loadReferenceData() {
    await runAction("Loading reference data", async () => {
      const [domainResponse, baseImageResponse] = await Promise.all([
        apiFetch<DomainsResponse>("/api/v1/domains"),
        apiFetch<BaseImagesResponse>("/api/v1/base-images")
      ]);
      setDomains(domainResponse);
      setBaseImages(baseImageResponse.allowed_base_images);
    });
  }

  async function refreshRequests() {
    const records = await apiFetch<EERequestRecord[]>("/api/v1/ee-requests");
    setRequests(records);
    if (!selectedRequest && records.length > 0) {
      setSelectedRequest(records[records.length - 1]);
    }
  }

  async function loadLogsForRequest(requestId: string) {
    try {
      const logResponse = await apiFetch<LogResponse>(`/api/v1/ee-requests/${requestId}/logs`);
      setLogs(logResponse);
    } catch {
      setLogs(null);
    }
  }

  function startNewRequest() {
    setForm(initialForm);
    setSelectedRequest(null);
    setGeneratedFiles([]);
    setCompatibilityMarkdown("");
    setVulnerabilityMarkdown("");
    setLogs(null);
    setError("");
    setNotice("Ready for a new EE request.");
    setActiveSection("create");
  }

  async function submitRequest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await runAction("Creating request", async () => {
      const payload = normalizePayload(form);
      const created = await apiFetch<EERequestRecord>("/api/v1/ee-requests", {
        method: "POST",
        body: JSON.stringify(payload)
      });
      setSelectedRequest(created);
      setGeneratedFiles([]);
      setCompatibilityMarkdown("");
      setVulnerabilityMarkdown("");
      setLogs(null);
      setNotice(`Request ${created.ee_name} created.`);
      await refreshRequests();
    });
  }

  async function validateSelected() {
    if (!selectedRequest) {
      return;
    }
    await runAction("Validating request", async () => {
      await apiFetch(`/api/v1/ee-requests/${selectedRequest.id}/validate`, { method: "POST" });
      const refreshed = await apiFetch<EERequestRecord>(`/api/v1/ee-requests/${selectedRequest.id}`);
      setSelectedRequest(refreshed);
      setNotice("Validation completed.");
      await refreshRequests();
    });
  }

  async function generateSelected() {
    if (!selectedRequest) {
      return;
    }
    await runAction("Generating files", async () => {
      const generated = await apiFetch<{ files: GeneratedFile[] }>(`/api/v1/ee-requests/${selectedRequest.id}/generate`, {
        method: "POST"
      });
      const report = await apiFetch<{ markdown: string }>(
        `/api/v1/ee-requests/${selectedRequest.id}/compatibility-report`
      );
      const vulnerabilityReport = await apiFetch<{ markdown: string }>(
        `/api/v1/ee-requests/${selectedRequest.id}/vulnerability-report`
      );
      const refreshed = await apiFetch<EERequestRecord>(`/api/v1/ee-requests/${selectedRequest.id}`);
      setGeneratedFiles(generated.files);
      setSelectedFileName(generated.files[0]?.name ?? "execution-environment.yml");
      setCompatibilityMarkdown(report.markdown);
      setVulnerabilityMarkdown(vulnerabilityReport.markdown);
      setSelectedRequest(refreshed);
      setActiveSection("files");
      setNotice("Generated files are ready for review.");
      await refreshRequests();
    });
  }

  async function loadGeneratedFiles(request: EERequestRecord, sectionOverride?: SectionId) {
    setSelectedRequest(request);
    setGeneratedFiles([]);
    setCompatibilityMarkdown("");
    setVulnerabilityMarkdown("");
    setLogs(null);
    await runAction("Opening request", async () => {
      const refreshed = await apiFetch<EERequestRecord>(`/api/v1/ee-requests/${request.id}`);
      setSelectedRequest(refreshed);
      if (!refreshed.generated_files || Object.keys(refreshed.generated_files).length === 0) {
        setActiveSection("create");
        setNotice(`Request ${refreshed.ee_name}:${refreshed.image_tag} selected. Generate files before opening previews.`);
        return;
      }
      const generated = await apiFetch<{ files: GeneratedFile[] }>(`/api/v1/ee-requests/${request.id}/generated-files`);
      const [report, vulnerabilityReport, logResponse] = await Promise.all([
        apiFetch<{ markdown: string }>(`/api/v1/ee-requests/${request.id}/compatibility-report`),
        apiFetch<{ markdown: string }>(`/api/v1/ee-requests/${request.id}/vulnerability-report`),
        apiFetch<LogResponse>(`/api/v1/ee-requests/${request.id}/logs`)
      ]);
      setGeneratedFiles(generated.files);
      setSelectedFileName(generated.files[0]?.name ?? "execution-environment.yml");
      setCompatibilityMarkdown(report.markdown);
      setVulnerabilityMarkdown(vulnerabilityReport.markdown);
      setLogs(logResponse);
      const nextSection = sectionOverride ?? chooseSectionForRequest(refreshed);
      setActiveSection(nextSection);
      setNotice(`Loaded ${refreshed.ee_name}:${refreshed.image_tag}.`);
    });
  }

  function runNextAction() {
    if (nextAction.action === "load-generated-files" && selectedRequest) {
      void loadGeneratedFiles(selectedRequest, "files");
      return;
    }
    setActiveSection(nextAction.section);
  }

  async function runVulnerabilityScan() {
    if (!selectedRequest) {
      return;
    }
    await runAction("Running vulnerability scan", async () => {
      const report = await apiFetch<{ markdown: string }>(`/api/v1/ee-requests/${selectedRequest.id}/vulnerability-scan`, {
        method: "POST"
      });
      const refreshed = await apiFetch<EERequestRecord>(`/api/v1/ee-requests/${selectedRequest.id}`);
      setVulnerabilityMarkdown(report.markdown);
      setSelectedRequest(refreshed);
      setActiveSection("files");
      setNotice("OSV.dev vulnerability scan completed.");
      await refreshRequests();
    });
  }

  async function approveGeneratedFiles() {
    if (!selectedRequest) {
      return;
    }
    if (!generatedFiles.length && (!selectedRequest.generated_files || Object.keys(selectedRequest.generated_files).length === 0)) {
      setError("Generate files before approving them.");
      setActiveSection("create");
      return;
    }
    await runAction("Approving generated files", async () => {
      await apiFetch(`/api/v1/ee-requests/${selectedRequest.id}/approve-generated-files`, { method: "POST" });
      const refreshed = await apiFetch<EERequestRecord>(`/api/v1/ee-requests/${selectedRequest.id}`);
      setSelectedRequest(refreshed);
      setNotice("Generated files approved.");
      await refreshRequests();
    });
  }

  async function startBuild() {
    if (!selectedRequest) {
      return;
    }
    if (selectedRequest.approval_status !== "GENERATED_FILES_APPROVED") {
      setError("Approve generated files before building.");
      setActiveSection("files");
      return;
    }
    await runAction("Starting build", async () => {
      const response = await apiFetch<{ status: string; message?: string }>(`/api/v1/ee-requests/${selectedRequest.id}/build`, {
        method: "POST",
        body: JSON.stringify({ mode: "stage_for_approval", use_kubernetes: true })
      });
      const refreshed = await apiFetch<EERequestRecord>(`/api/v1/ee-requests/${selectedRequest.id}`);
      setSelectedRequest(refreshed);
      await loadLogsForRequest(selectedRequest.id);
      setActiveSection("approvals");
      setNotice(`${response.status}: ${response.message ?? "Build orchestration request accepted."}`);
      await refreshRequests();
    });
  }

  async function refreshBuildStatus() {
    if (!selectedRequest) {
      return;
    }
    await runAction("Refreshing build status", async () => {
      await apiFetch(`/api/v1/ee-requests/${selectedRequest.id}/build-status`);
      const [refreshed, logResponse] = await Promise.all([
        apiFetch<EERequestRecord>(`/api/v1/ee-requests/${selectedRequest.id}`),
        apiFetch<LogResponse>(`/api/v1/ee-requests/${selectedRequest.id}/logs`)
      ]);
      setSelectedRequest(refreshed);
      setLogs(logResponse);
      setNotice("Build status refreshed from workspace metadata.");
      await refreshRequests();
    });
  }

  async function approvePublish() {
    if (!selectedRequest) {
      return;
    }
    if (selectedRequest.approval_status !== "GENERATED_FILES_APPROVED") {
      setError("Approve generated files and start a build before approving publication.");
      setActiveSection("files");
      return;
    }
    await runAction("Approving publish", async () => {
      await apiFetch(`/api/v1/ee-requests/${selectedRequest.id}/approve-publish`, { method: "POST" });
      const refreshed = await apiFetch<EERequestRecord>(`/api/v1/ee-requests/${selectedRequest.id}`);
      setSelectedRequest(refreshed);
      await loadLogsForRequest(selectedRequest.id);
      setNotice("Publish approved.");
      await refreshRequests();
    });
  }

  async function publishImage() {
    if (!selectedRequest) {
      return;
    }
    if (selectedRequest.publish_status !== "PUBLISH_APPROVED") {
      setError("Approve publish before pushing to the registry.");
      setActiveSection("approvals");
      return;
    }
    await runAction("Publishing image", async () => {
      const response = await apiFetch<{ status: string }>(`/api/v1/ee-requests/${selectedRequest.id}/publish`, {
        method: "POST"
      });
      const refreshed = await apiFetch<EERequestRecord>(`/api/v1/ee-requests/${selectedRequest.id}`);
      setSelectedRequest(refreshed);
      await loadLogsForRequest(selectedRequest.id);
      setNotice(`Publish endpoint responded: ${response.status}. Use Refresh build status to follow the job.`);
      await refreshRequests();
    });
  }

  async function createNewVersion() {
    if (!selectedRequest) {
      return;
    }
    await runAction("Creating new version", async () => {
      const created = await apiFetch<EERequestRecord>(`/api/v1/ee-requests/${selectedRequest.id}/new-version`, {
        method: "POST",
        body: JSON.stringify({ image_tag: nextTag, change_summary: changeSummary })
      });
      setSelectedRequest(created);
      setGeneratedFiles([]);
      setCompatibilityMarkdown("");
      setVulnerabilityMarkdown("");
      setActiveSection("create");
      setNotice(`Created new tagged request ${created.ee_name}:${created.image_tag}.`);
      await refreshRequests();
    });
  }

  async function generateDocs() {
    if (!selectedRequest) {
      return;
    }
    await runAction("Generating docs", async () => {
      const response = await apiFetch<{ content: string }>(`/api/v1/ee-requests/${selectedRequest.id}/generate-docs`, {
        method: "POST"
      });
      setGeneratedFiles((files) => {
        const remaining = files.filter((file) => file.name !== "generated-readme.md");
        return [...remaining, { name: "generated-readme.md", content: response.content }];
      });
      setSelectedFileName("generated-readme.md");
      setNotice("Generated README refreshed.");
    });
  }

  function updateCollection(index: number, field: keyof CollectionInput, value: string) {
    setForm((current) => ({
      ...current,
      collections: current.collections.map((collection, collectionIndex) =>
        collectionIndex === index ? { ...collection, [field]: value } : collection
      )
    }));
  }

  function removeCollection(index: number) {
    setForm((current) => ({
      ...current,
      collections: current.collections.filter((_, collectionIndex) => collectionIndex !== index)
    }));
  }

  function updateDependency(kind: "python_dependencies" | "system_dependencies", index: number, value: string) {
    setForm((current) => ({
      ...current,
      [kind]: current[kind].map((dependency, dependencyIndex) => (dependencyIndex === index ? value : dependency))
    }));
  }

  function removeDependency(kind: "python_dependencies" | "system_dependencies", index: number) {
    setForm((current) => ({
      ...current,
      [kind]: current[kind].filter((_, dependencyIndex) => dependencyIndex !== index)
    }));
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <Rocket size={22} />
          <div>
            <strong>EE Factory Lab</strong>
            <span>IDP capability</span>
          </div>
        </div>
        <nav className="section-nav" aria-label="Portal sections">
          {sectionItems.map((item) => {
            const Icon = item.icon;
            return (
              <button
                className={activeSection === item.id ? "nav-item active" : "nav-item"}
                key={item.id}
                onClick={() => setActiveSection(item.id)}
                type="button"
              >
                <Icon size={17} />
                {item.label}
              </button>
            );
          })}
        </nav>
      </aside>

      <section className="workspace">
        <header className="workspace-header">
          <div>
            <p className="eyebrow">Create a specialized Ansible Execution Environment image</p>
            <h1>Purpose-driven EE request workspace</h1>
          </div>
          <div className="header-actions">
            <button className="secondary-button" onClick={() => void refreshRequests()} type="button">
              <RefreshCw size={16} />
              Refresh
            </button>
            {activeSection === "create" ? (
              <button className="primary-button" form="ee-request-form" type="submit">
                {busyAction === "Creating request" ? <Loader2 className="spin" size={16} /> : <Plus size={16} />}
                Create request
              </button>
            ) : (
              <button className="primary-button" onClick={startNewRequest} type="button">
                <Plus size={16} />
                New EE request
              </button>
            )}
          </div>
        </header>

        {busyAction && <div className="notice info">{busyAction}...</div>}
        {notice && <div className="notice success">{notice}</div>}
        {error && <div className="notice error">{error}</div>}

        <section className="status-strip">
          <StatusMetric label="Selected request" value={selectedRequest?.ee_name ?? "Draft"} />
          <StatusMetric label="Status" value={selectedRequest?.status ?? "Not submitted"} />
          <StatusMetric label="Blockers" value={String(blockers)} tone={blockers ? "danger" : "ok"} />
          <StatusMetric label="Warnings" value={String(warnings)} tone={warnings ? "warning" : "ok"} />
          <StatusMetric label="Security findings" value={String(vulnerabilityWarnings)} tone={vulnerabilityWarnings ? "warning" : "ok"} />
        </section>

        {activeSection === "dashboard" && (
          <section className="two-column">
            <div className="main-panel">
              <PanelHeader
                title="Platform dashboard"
                subtitle="A local IDP view for request, validation, build, approval, and publication status."
              />
              <div className="dashboard-grid">
                <StatusMetric label="Total requests" value={String(requests.length)} />
                <StatusMetric
                  label="Generated"
                  value={String(requests.filter((request) => request.status.includes("GENERATED")).length)}
                  tone="ok"
                />
                <StatusMetric
                  label="Queued or built"
                  value={String(requests.filter((request) => request.build_status !== "NOT_STARTED").length)}
                />
                <StatusMetric
                  label="Publish approved"
                  value={String(requests.filter((request) => request.publish_status === "PUBLISH_APPROVED").length)}
                  tone="warning"
                />
              </div>
              <div className="next-action-panel">
                <div>
                  <span>Recommended next action</span>
                  <strong>{nextAction.title}</strong>
                  <p>{nextAction.description}</p>
                </div>
                <button className="primary-button" onClick={runNextAction} type="button">
                  {nextAction.cta}
                </button>
              </div>
              <div className="workflow-list">
                {[
                  "Create a narrow EE request with a declared domain.",
                  "Validate guardrails and review compatibility findings.",
                  "Generate and approve the exact build files.",
                  "Create the Kubernetes build job and inspect logs.",
                  "Approve publication before Quay.io push.",
                  "Create a new tagged request for every meaningful change."
                ].map((item, index) => (
                  <div className="workflow-step" key={item}>
                    <span>{index + 1}</span>
                    <p>{item}</p>
                  </div>
                ))}
              </div>
              <div className="button-row">
                <button className="primary-button" onClick={startNewRequest} type="button">
                  <Plus size={16} />
                  New EE request
                </button>
                <button className="secondary-button" onClick={() => setActiveSection("history")} type="button">
                  <History size={16} />
                  Open history
                </button>
              </div>
            </div>
            <aside className="side-panel">
              <PanelHeader title="Latest request" subtitle="Use this as your current working context." />
              {selectedRequest ? (
                <dl className="settings-list compact">
                  <div>
                    <dt>Name</dt>
                    <dd>{selectedRequest.ee_name}</dd>
                  </div>
                  <div>
                    <dt>Domain</dt>
                    <dd>{selectedRequest.automation_domain}</dd>
                  </div>
                  <div>
                    <dt>Tag</dt>
                    <dd>{selectedRequest.image_tag}</dd>
                  </div>
                  <div>
                    <dt>Status</dt>
                    <dd>{selectedRequest.status}</dd>
                  </div>
                  <div>
                    <dt>Image</dt>
                    <dd>{selectedRequest.registry_target}</dd>
                  </div>
                </dl>
              ) : (
                <EmptyState text="Create the first EE request to populate the dashboard." />
              )}
            </aside>
          </section>
        )}

        {activeSection === "create" && (
          <section className="two-column">
            <form className="main-panel" id="ee-request-form" onSubmit={(event) => void submitRequest(event)}>
              <PanelHeader
                title="Request details"
                subtitle="Declare a narrow automation domain and pin the dependencies needed for that domain."
              />
              <div className="field-grid">
                <TextField label="EE name" value={form.ee_name} onChange={(value) => setForm({ ...form, ee_name: value })} />
                <TextField
                  label="Image tag"
                  value={form.image_tag}
                  onChange={(value) => setForm({ ...form, image_tag: value })}
                />
                <TextField
                  label="Description"
                  value={form.description}
                  onChange={(value) => setForm({ ...form, description: value })}
                  wide
                />
                <TextField
                  label="Business / technical purpose"
                  value={form.purpose}
                  onChange={(value) => setForm({ ...form, purpose: value })}
                  wide
                />
                <DomainField
                  label="Automation domain"
                  value={form.automation_domain}
                  options={Object.keys(domains?.domains ?? { windows: {}, vmware: {}, servicenow: {}, general: {} })}
                  onChange={(value) => setForm({ ...form, automation_domain: value })}
                />
                <SelectField
                  label="Base image"
                  value={form.base_image}
                  options={baseImages}
                  onChange={(value) => setForm({ ...form, base_image: value })}
                />
                <TextField
                  label="ansible-core"
                  value={form.ansible_core_version}
                  onChange={(value) => setForm({ ...form, ansible_core_version: value })}
                />
                <TextField
                  label="ansible-runner"
                  value={form.ansible_runner_version}
                  onChange={(value) => setForm({ ...form, ansible_runner_version: value })}
                />
                <TextField
                  label="Registry namespace"
                  value={form.registry_namespace}
                  onChange={(value) => setForm({ ...form, registry_namespace: value })}
                />
                <TextField
                  label="Publish target"
                  value={form.publish_target}
                  onChange={(value) => setForm({ ...form, publish_target: value })}
                />
              </div>

              <div className="editor-section">
                <div className="section-title-row">
                  <h2>Collections</h2>
                  <button
                    className="ghost-button"
                    onClick={() =>
                      setForm({ ...form, collections: [...form.collections, { name: "", version: "" }] })
                    }
                    type="button"
                  >
                    <Plus size={15} />
                    Add collection
                  </button>
                </div>
                <div className="stack">
                  {form.collections.map((collection, index) => (
                    <div className="row-editor" key={`${collection.name}-${index}`}>
                      <TextField
                        label="Name"
                        value={collection.name}
                        onChange={(value) => updateCollection(index, "name", value)}
                      />
                      <TextField
                        label="Pinned version"
                        value={collection.version}
                        onChange={(value) => updateCollection(index, "version", value)}
                      />
                      <IconButton label="Remove collection" onClick={() => removeCollection(index)}>
                        <Trash2 size={16} />
                      </IconButton>
                    </div>
                  ))}
                  {!form.collections.length && <p className="muted">Add at least one pinned collection.</p>}
                </div>
              </div>

              <DependencyEditor
                items={form.python_dependencies}
                label="Python dependencies"
                placeholder="pywinrm==0.5.0"
                onAdd={() => setForm({ ...form, python_dependencies: [...form.python_dependencies, ""] })}
                onRemove={(index) => removeDependency("python_dependencies", index)}
                onUpdate={(index, value) => updateDependency("python_dependencies", index, value)}
              />

              <DependencyEditor
                items={form.system_dependencies}
                label="System dependencies"
                placeholder="krb5-devel"
                onAdd={() => setForm({ ...form, system_dependencies: [...form.system_dependencies, ""] })}
                onRemove={(index) => removeDependency("system_dependencies", index)}
                onUpdate={(index, value) => updateDependency("system_dependencies", index, value)}
              />
            </form>

            <aside className="side-panel">
              <PanelHeader title="Governance" subtitle="Deterministic checks guide the request before build." />
              {showBroadScopeWarning && (
                <div className="broad-warning">
                  <AlertTriangle size={18} />
                  This EE appears to combine multiple disconnected automation domains. In enterprise environments, this can
                  increase dependency conflict risk and reduce maintainability.
                </div>
              )}
              <div className="domain-map">
                {mappedDomains.map((item) => (
                  <div className="domain-map-row" key={item.collection}>
                    <span>{item.collection || "unnamed collection"}</span>
                    <strong>{item.domain}</strong>
                  </div>
                ))}
              </div>
              <FindingList findings={currentFindings} />
              <div className="button-row">
                <button
                  className="secondary-button"
                  disabled={!selectedRequest || Boolean(busyAction)}
                  onClick={() => void validateSelected()}
                  type="button"
                >
                  <ShieldCheck size={16} />
                  Validate
                </button>
                <button
                  className="primary-button"
                  disabled={!selectedRequest || Boolean(busyAction)}
                  onClick={() => void generateSelected()}
                  type="button"
                >
                  <FileCode2 size={16} />
                  Generate files
                </button>
              </div>
            </aside>
          </section>
        )}

        {activeSection === "files" && (
          <section className="two-column">
            <div className="main-panel">
              <PanelHeader
                title="Review generated files"
                subtitle="Inspect generated build inputs, compatibility findings, and security findings before approval."
              />
              {generatedFiles.length > 0 ? (
                <>
                  <div className="file-tabs">
                    {generatedFiles.map((file) => (
                      <button
                        className={file.name === selectedFile?.name ? "file-tab active" : "file-tab"}
                        key={file.name}
                        onClick={() => setSelectedFileName(file.name)}
                        type="button"
                      >
                        {file.name}
                      </button>
                    ))}
                  </div>
                  <pre className="code-preview">{selectedFile?.content}</pre>
                </>
              ) : (
                <EmptyState text="Generate files from a validated request to review the EE definition." />
              )}
            </div>
            <aside className="side-panel">
              <PanelHeader title="Compatibility report" subtitle="Machine findings rendered for human review." />
              {compatibilityMarkdown ? <pre className="report-preview">{compatibilityMarkdown}</pre> : <EmptyState text="No compatibility report loaded." />}
              <div className="review-security-block">
                <PanelHeader title="Security findings" subtitle="OSV.dev advisories are review input, not the final policy engine." />
                <FindingList findings={vulnerabilityFindings} />
                {vulnerabilityMarkdown && (
                  <details className="log-block">
                    <summary>vulnerability-report.md</summary>
                    <pre>{vulnerabilityMarkdown}</pre>
                  </details>
                )}
              </div>
              <div className="button-row">
                <button
                  className="primary-button"
                  disabled={!generatedFilesAvailable || Boolean(busyAction)}
                  onClick={() => void approveGeneratedFiles()}
                  type="button"
                >
                  <CheckCircle2 size={16} />
                  Approve files
                </button>
                <button
                  className="secondary-button"
                  disabled={!selectedRequest || Boolean(busyAction)}
                  onClick={() => void startBuild()}
                  type="button"
                >
                  <Play size={16} />
                  Build
                </button>
                <button
                  className="secondary-button"
                  disabled={!selectedRequest || Boolean(busyAction)}
                  onClick={() => void runVulnerabilityScan()}
                  type="button"
                >
                  <ShieldCheck size={16} />
                  Security scan
                </button>
                <button
                  className="secondary-button"
                  disabled={!selectedRequest || Boolean(busyAction)}
                  onClick={() => void generateDocs()}
                  type="button"
                >
                  <FileCode2 size={16} />
                  Generate docs
                </button>
              </div>
            </aside>
          </section>
        )}

        {activeSection === "history" && (
          <section className="main-panel">
            <PanelHeader title="Build history" subtitle="Requests created during local lab testing." />
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>EE</th>
                    <th>Domain</th>
                    <th>Status</th>
                    <th>Tag</th>
                    <th>Updated</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {requests.map((request) => (
                    <tr key={request.id}>
                      <td>{request.ee_name}</td>
                      <td>{request.automation_domain}</td>
                      <td><StatusPill value={request.status} /></td>
                      <td>{request.image_tag}</td>
                      <td>{new Date(request.updated_at).toLocaleString()}</td>
                      <td>
                        <button className="table-button" onClick={() => void loadGeneratedFiles(request)} type="button">
                          Open
                        </button>
                      </td>
                    </tr>
                  ))}
                  {!requests.length && (
                    <tr>
                      <td colSpan={6}>No requests yet.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {activeSection === "approvals" && (
          <section className="two-column">
            <div className="main-panel">
              <PanelHeader title="Build & publish" subtitle="Run the Kubernetes build, inspect logs, and publish only after approval." />
              <ReadinessPanel
                findings={readinessFindings}
                generatedFilesAvailable={generatedFilesAvailable}
                imageRef={imageRef}
                request={selectedRequest}
              />
              <div className="approval-grid">
                <ApprovalStep
                  title="Generated files"
                  status={selectedRequest?.approval_status ?? "PENDING"}
                  actionLabel="Approve generated files"
                  disabled={!generatedFilesAvailable || Boolean(busyAction)}
                  onAction={() => void approveGeneratedFiles()}
                />
                <ApprovalStep
                  title="Publish to registry"
                  status={selectedRequest?.publish_status ?? "NOT_REQUESTED"}
                  actionLabel="Approve publish"
                  disabled={!selectedRequest || Boolean(busyAction)}
                  onAction={() => void approvePublish()}
                />
              </div>
              <div className="image-reference">
                <span>{imageRef}</span>
                <button
                  className="icon-text-button"
                  onClick={() => void navigator.clipboard.writeText(imageRef)}
                  type="button"
                >
                  <Clipboard size={15} />
                  Copy
                </button>
              </div>
              <div className="button-row">
                <button
                  className="secondary-button"
                  disabled={!selectedRequest || Boolean(busyAction)}
                  onClick={() => void startBuild()}
                  type="button"
                >
                  <Play size={16} />
                  Start build
                </button>
                <button
                  className="secondary-button"
                  disabled={!selectedRequest || Boolean(busyAction)}
                  onClick={() => void refreshBuildStatus()}
                  type="button"
                >
                  <RefreshCw size={16} />
                  Refresh status and logs
                </button>
                <button
                  className="primary-button"
                  disabled={!selectedRequest || Boolean(busyAction)}
                  onClick={() => void publishImage()}
                  type="button"
                >
                  <Rocket size={16} />
                  Publish
                </button>
              </div>
              <BuildStatusPanel request={selectedRequest} />
              <LogsPanel logs={logs} />
              <div className="version-panel">
                <div className="build-guide-title">
                  <GitBranch size={17} />
                  <h3>New tagged version</h3>
                </div>
                <p className="muted">
                  Use this when a Git change or IDP edit should become a new immutable image tag before optional Quay push.
                </p>
                <TextField label="Next tag" value={nextTag} onChange={setNextTag} />
                <TextField label="Change summary" value={changeSummary} onChange={setChangeSummary} wide />
                <button
                  className="secondary-button"
                  disabled={!selectedRequest || Boolean(busyAction)}
                  onClick={() => void createNewVersion()}
                  type="button"
                >
                  <GitBranch size={16} />
                  Create version request
                </button>
              </div>
            </div>
            <aside className="side-panel">
              <OperatorGuide />
              <BuildTestGuide
                commands={buildCommands}
                imageRef={imageRef}
                requestId={selectedRequest?.id}
                workspacePath={buildWorkspace}
              />
            </aside>
          </section>
        )}

        {activeSection === "settings" && (
          <section className="main-panel narrow">
            <PanelHeader title="Settings" subtitle="Local lab defaults. Secrets are configured outside Git." />
            <dl className="settings-list">
              <div>
                <dt>API base URL</dt>
                <dd>{API_BASE_URL}</dd>
              </div>
              <div>
                <dt>Default publish target</dt>
                <dd>Quay.io</dd>
              </div>
              <div>
                <dt>Runtime target</dt>
                <dd>Minikube for the main deployment path</dd>
              </div>
              <div>
                <dt>Development convenience</dt>
                <dd>Docker Compose only for local component development</dd>
              </div>
            </dl>
          </section>
        )}
      </section>
    </main>
  );
}

function formatApiError(body: string, status: number) {
  if (!body) {
    return `Request failed with status ${status}`;
  }
  try {
    const parsed = JSON.parse(body) as ApiErrorBody;
    if (typeof parsed.detail === "string") {
      return parsed.detail;
    }
    if (Array.isArray(parsed.detail)) {
      return parsed.detail.map((item) => item.message ?? item.code ?? JSON.stringify(item)).join(" ");
    }
    if (parsed.message) {
      return parsed.message;
    }
  } catch {
    return body;
  }
  return body;
}

function normalizePayload(form: EERequestPayload): EERequestPayload {
  return {
    ...form,
    collections: form.collections
      .map((collection) => ({ name: collection.name.trim(), version: collection.version.trim() }))
      .filter((collection) => collection.name),
    python_dependencies: form.python_dependencies.map((dependency) => dependency.trim()).filter(Boolean),
    system_dependencies: form.system_dependencies.map((dependency) => dependency.trim()).filter(Boolean)
  };
}

function buildImageRef(form: EERequestPayload) {
  return `${form.publish_target}/${form.registry_namespace}/${form.ee_name}:${form.image_tag}`;
}

function getNextAction(
  request: EERequestRecord | null,
  generatedArtifactsExist: boolean,
  generatedFilesLoaded: boolean,
  blockerCount: number
): { title: string; description: string; cta: string; section: SectionId; action?: "load-generated-files" } {
  if (!request) {
    return {
      title: "Create the first EE request",
      description: "Start with a narrow automation domain, pinned collections, and a unique image tag.",
      cta: "Open request form",
      section: "create"
    };
  }
  if (blockerCount > 0 || request.status === "VALIDATION_BLOCKED") {
    return {
      title: "Resolve blocking guardrails",
      description: "Fix invalid inputs before generating build artifacts.",
      cta: "Review request",
      section: "create"
    };
  }
  if (!generatedArtifactsExist) {
    return {
      title: "Generate review artifacts",
      description: "Create the EE definition, requirements, compatibility report, and vulnerability report.",
      cta: "Open request",
      section: "create"
    };
  }
  if (!generatedFilesLoaded && request.approval_status !== "GENERATED_FILES_APPROVED") {
    return {
      title: "Load generated files",
      description: "Generated artifacts exist in the workspace. Load them into the review screen before approval.",
      cta: "Load review",
      section: "files",
      action: "load-generated-files"
    };
  }
  if (request.approval_status !== "GENERATED_FILES_APPROVED") {
    return {
      title: "Approve generated files",
      description: "Review the generated files and security findings before allowing the build job.",
      cta: "Open review",
      section: "files"
    };
  }
  if (!["BUILT", "PUBLISHED"].includes(request.build_status)) {
    return {
      title: "Run or refresh the build",
      description: "Create the Kubernetes build job or refresh status and logs for the existing one.",
      cta: "Build & publish",
      section: "approvals"
    };
  }
  if (request.publish_status !== "PUBLISHED") {
    return {
      title: "Decide whether to publish",
      description: "Review image metadata and approve Quay publication only when the result is acceptable.",
      cta: "Build & publish",
      section: "approvals"
    };
  }
  return {
    title: "Create a new tagged version",
    description: "Any future dependency or source change should produce a new immutable image tag.",
    cta: "Build & publish",
    section: "approvals"
  };
}

function chooseSectionForRequest(request: EERequestRecord): SectionId {
  if (!request.generated_files || Object.keys(request.generated_files).length === 0) {
    return "create";
  }
  if (
    request.approval_status === "GENERATED_FILES_APPROVED" ||
    request.build_status !== "NOT_STARTED" ||
    request.publish_status !== "NOT_REQUESTED"
  ) {
    return "approvals";
  }
  return "files";
}

function dedupeFindings(findings: Finding[]) {
  const seen = new Set<string>();
  return findings.filter((finding) => {
    const key = `${finding.severity}:${finding.code}:${finding.message}`;
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}

function suggestNextTag(tag: string) {
  const parts = tag.split(".");
  const last = Number(parts[parts.length - 1]);
  if (Number.isInteger(last)) {
    return [...parts.slice(0, -1), String(last + 1)].join(".");
  }
  return `${tag}-next`;
}

function buildTestCommands(request: EERequestRecord) {
  const imageCommand = request.registry_target
    ? `# Optional: build the local image after the context is created\n.\\scripts\\test-build-image.ps1 -RequestId ${request.id} -BuildImage`
    : "";
  const podmanStartCommand = request.registry_target
    ? `# Optional: start Podman machine automatically, then build\n.\\scripts\\test-build-image.ps1 -RequestId ${request.id} -BuildImage -StartPodmanMachine`
    : "";

  return [
    "# Run from the repository root",
    "# Creates context/Containerfile with ansible-builder",
    `.\\scripts\\test-build-image.ps1 -RequestId ${request.id}`,
    imageCommand,
    podmanStartCommand
  ]
    .filter(Boolean)
    .join("\n");
}

function PanelHeader({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div className="panel-header">
      <h2>{title}</h2>
      <p>{subtitle}</p>
    </div>
  );
}

function ReadinessPanel({
  request,
  findings,
  generatedFilesAvailable,
  imageRef
}: {
  request: EERequestRecord | null;
  findings: Finding[];
  generatedFilesAvailable: boolean;
  imageRef: string;
}) {
  const blockingFindings = findings.filter((finding) => finding.severity === "BLOCKER");
  const warningFindings = findings.filter((finding) => finding.severity === "WARNING");
  const visibleFindings = [...blockingFindings, ...warningFindings].slice(0, 4);
  const generatedApproved = request?.approval_status === "GENERATED_FILES_APPROVED";
  const buildStarted = Boolean(request?.build_job_name || ["BUILT", "PUBLISHED", "JOB_CREATED", "JOB_ALREADY_EXISTS"].includes(request?.build_status ?? ""));
  const publishApproved = request?.publish_status === "PUBLISH_APPROVED" || request?.publish_status === "PUBLISHED";

  return (
    <div className="readiness-panel">
      <div className="build-guide-title">
        <ShieldCheck size={17} />
        <h3>Pre-build readiness</h3>
      </div>
      <div className="readiness-grid">
        <ReadinessItem label="Generated files" ready={generatedFilesAvailable} value={generatedFilesAvailable ? "Ready" : "Missing"} />
        <ReadinessItem label="File approval" ready={generatedApproved} value={request?.approval_status ?? "Not selected"} />
        <ReadinessItem label="Build job" ready={buildStarted} value={request?.build_status ?? "Not started"} />
        <ReadinessItem label="Publish gate" ready={publishApproved} value={request?.publish_status ?? "Not requested"} />
      </div>
      <dl className="settings-list compact">
        <div>
          <dt>Image</dt>
          <dd>{imageRef || "Create or select a request first"}</dd>
        </div>
        <div>
          <dt>Digest</dt>
          <dd>{request?.image_digest ?? "Available after build/publish metadata is written"}</dd>
        </div>
      </dl>
      <div className="concern-list">
        {visibleFindings.length > 0 ? (
          visibleFindings.map((finding) => (
            <div className={`concern ${finding.severity.toLowerCase()}`} key={`${finding.code}-${finding.message}`}>
              <strong>{finding.severity}</strong>
              <span>{finding.message}</span>
            </div>
          ))
        ) : (
          <div className="concern info">
            <strong>No blockers detected</strong>
            <span>Validation, compatibility and OSV findings should still be reviewed before approving publication.</span>
          </div>
        )}
        <div className="concern warning">
          <strong>Lab build isolation</strong>
          <span>Minikube uses a privileged Buildah builder for this lab. The project avoids host Docker socket mounting and documents the enterprise trade-off.</span>
        </div>
      </div>
    </div>
  );
}

function ReadinessItem({ label, ready, value }: { label: string; ready: boolean; value: string }) {
  return (
    <div className={ready ? "readiness-item ready" : "readiness-item pending"}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function BuildStatusPanel({ request }: { request: EERequestRecord | null }) {
  return (
    <div className="build-status-panel">
      <div className="build-guide-title">
        <Terminal size={17} />
        <h3>Build status</h3>
      </div>
      <div className="status-card-grid">
        <StatusMetric label="Request" value={request?.status ?? "No request selected"} />
        <StatusMetric label="Build" value={request?.build_status ?? "NOT_STARTED"} />
        <StatusMetric label="Publish" value={request?.publish_status ?? "NOT_REQUESTED"} />
      </div>
      <dl className="settings-list compact">
        <div>
          <dt>Job</dt>
          <dd>{request?.build_job_name ?? "Created after build starts"}</dd>
        </div>
        <div>
          <dt>Digest</dt>
          <dd>{request?.image_digest ?? "Created after image build/publish metadata is saved"}</dd>
        </div>
      </dl>
    </div>
  );
}

function LogsPanel({ logs }: { logs: LogResponse | null }) {
  return (
    <div className="logs-panel">
      <div className="build-guide-title">
        <Terminal size={17} />
        <h3>Workspace logs</h3>
      </div>
      {logs ? (
        <div className="log-grid">
          <LogBlock title="validation.log" content={logs.validation_log} />
          <LogBlock title="build.log" content={logs.build_log} />
          <LogBlock title="publish.log" content={logs.publish_log} />
        </div>
      ) : (
        <EmptyState text="Select a generated request or refresh status to load logs." />
      )}
    </div>
  );
}

function LogBlock({ title, content }: { title: string; content: string }) {
  return (
    <details className="log-block" open={title === "build.log"}>
      <summary>{title}</summary>
      <pre>{content || "(empty)"}</pre>
    </details>
  );
}

function OperatorGuide() {
  return (
    <div className="operator-guide">
      <PanelHeader title="Operator flow" subtitle="Use the gates in order; each image change should become a new tag." />
      <ol>
        <li>Review generated files and compatibility/security findings.</li>
        <li>Approve generated files, then start or refresh the Kubernetes build.</li>
        <li>Approve publish only after image metadata and warnings are acceptable.</li>
        <li>Create a new tagged version for any UI or Git-driven EE change.</li>
      </ol>
    </div>
  );
}

function BuildTestGuide({
  requestId,
  workspacePath,
  imageRef,
  commands
}: {
  requestId?: string;
  workspacePath?: string | null;
  imageRef: string;
  commands: string;
}) {
  return (
    <div className="build-guide">
      <div className="build-guide-title">
        <Terminal size={17} />
        <h3>Build test guide</h3>
      </div>
      <ol>
        <li>Approve generated files before treating them as build input.</li>
        <li>Run the first command to create `context/Containerfile` with `ansible-builder`.</li>
        <li>Use `-BuildImage` when Podman is running, or add `-StartPodmanMachine` to start the local Podman machine.</li>
      </ol>
      <dl>
        <div>
          <dt>Request ID</dt>
          <dd>{requestId ?? "Create or select a request first"}</dd>
        </div>
        <div>
          <dt>Workspace</dt>
          <dd>{workspacePath ?? "Generated after request creation"}</dd>
        </div>
        <div>
          <dt>Image</dt>
          <dd>{imageRef}</dd>
        </div>
      </dl>
      {commands ? (
        <>
          <pre className="command-preview">{commands}</pre>
          <button
            className="icon-text-button"
            onClick={() => void navigator.clipboard.writeText(commands)}
            type="button"
          >
            <Clipboard size={15} />
            Copy commands
          </button>
        </>
      ) : (
        <p className="muted">Create a request to get build test commands.</p>
      )}
    </div>
  );
}

function TextField({
  label,
  value,
  onChange,
  placeholder,
  wide
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  wide?: boolean;
}) {
  return (
    <label className={wide ? "field wide-field" : "field"}>
      <span>{label}</span>
      <input placeholder={placeholder} value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function SelectField({
  label,
  value,
  options,
  onChange
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="" disabled>
          Select {label.toLowerCase()}
        </option>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

function DomainField({
  label,
  value,
  options,
  onChange
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      <input
        list="automation-domain-options"
        placeholder="database, windows, vmware..."
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
      <datalist id="automation-domain-options">
        {options.map((option) => (
          <option key={option} value={option} />
        ))}
      </datalist>
    </label>
  );
}

function DependencyEditor({
  label,
  placeholder,
  items,
  onAdd,
  onUpdate,
  onRemove
}: {
  label: string;
  placeholder: string;
  items: string[];
  onAdd: () => void;
  onUpdate: (index: number, value: string) => void;
  onRemove: (index: number) => void;
}) {
  return (
    <div className="editor-section">
      <div className="section-title-row">
        <h2>{label}</h2>
        <button className="ghost-button" onClick={onAdd} type="button">
          <Plus size={15} />
          Add
        </button>
      </div>
      <div className="stack">
        {items.map((item, index) => (
          <div className="dependency-row" key={`${label}-${index}`}>
            <input placeholder={placeholder} value={item} onChange={(event) => onUpdate(index, event.target.value)} />
            <IconButton label={`Remove ${label}`} onClick={() => onRemove(index)}>
              <Trash2 size={16} />
            </IconButton>
          </div>
        ))}
        {!items.length && <p className="muted">No dependencies declared.</p>}
      </div>
    </div>
  );
}

function IconButton({ label, onClick, children }: { label: string; onClick: () => void; children: React.ReactNode }) {
  return (
    <button aria-label={label} className="icon-button" onClick={onClick} title={label} type="button">
      {children}
    </button>
  );
}

function FindingList({ findings }: { findings: Finding[] }) {
  if (!findings.length) {
    return (
      <div className="finding empty">
        <CheckCircle2 size={17} />
        No guardrail findings for the selected request.
      </div>
    );
  }
  return (
    <div className="finding-list">
      {findings.map((finding) => (
        <div className={`finding ${finding.severity.toLowerCase()}`} key={`${finding.code}-${finding.message}`}>
          <strong>{finding.severity}</strong>
          <span>{finding.message}</span>
        </div>
      ))}
    </div>
  );
}

function StatusMetric({ label, value, tone }: { label: string; value: string; tone?: "ok" | "warning" | "danger" }) {
  return (
    <div className={`status-metric ${tone ?? ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function StatusPill({ value }: { value: string }) {
  return <span className="status-pill">{value}</span>;
}

function ApprovalStep({
  title,
  status,
  actionLabel,
  disabled,
  onAction
}: {
  title: string;
  status: string;
  actionLabel: string;
  disabled: boolean;
  onAction: () => void;
}) {
  return (
    <div className="approval-step">
      <div>
        <strong>{title}</strong>
        <span>{status}</span>
      </div>
      <button className="secondary-button" disabled={disabled} onClick={onAction} type="button">
        <CheckCircle2 size={16} />
        {actionLabel}
      </button>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return <div className="empty-state">{text}</div>;
}
