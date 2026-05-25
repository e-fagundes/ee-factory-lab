# Enterprise Adaptation Guide

This lab is intentionally local, but the pattern maps cleanly to enterprise platform engineering.

## Private Automation Hub

Replace Galaxy download with private Automation Hub. Guardrails can enforce approved namespaces, signed collections, and support ownership per automation domain.

## Private Container Registry

Replace Quay.io with Quay Enterprise, Harbor, Artifactory, ECR, ACR, or GCR. Keep credentials in Kubernetes Secrets or an external secrets manager.

## Enterprise SSO

Add OIDC/SAML through an ingress controller, API gateway, or application middleware. Propagate user identity into request metadata and approval records.

## RBAC

Map permissions by role:

- Requester: create and view own requests.
- Domain owner: approve domain-specific generated files.
- Platform team: manage base image policy and taxonomy.
- Release approver: approve publish.

## Approval Workflows

Move the two local approval gates into a workflow engine, ITSM approval, or GitHub environment protection rule. Keep the same semantics: generated files approval first, registry publish approval later.

## Audit Logging

Persist audit events for create, validate, generate, approve, build, publish, and clone-new-version actions. Send events to SIEM or a central audit store.

## ServiceNow Integration

The request form can create or update a ServiceNow RITM/Change. The important shift is that the RITM becomes workflow metadata, not the place where engineers manually build EEs.

## Policy Engines

OPA, Kyverno, or Conftest can enforce base image policy, disallowed packages, namespace ownership, and required approvals. Deterministic policy must remain authoritative over LLM suggestions.

## Image Scanning

Add Trivy, Clair, Grype, Prisma, or enterprise scanner integration after build and before publish. OSV.dev is useful for dependency intelligence, but production image scanning should inspect the built artifact.

## Signed Images

Use Cosign or Sigstore to sign approved images. Record signature metadata with the EE request.

## GitOps

Store platform manifests in Git and reconcile them with Argo CD or Flux. Generated EE files can also be committed to a controlled repository after approval.

## AAP Integration

After publish, register or update the Execution Environment in Ansible Automation Platform and configure image pull credentials for controller or automation mesh nodes.
