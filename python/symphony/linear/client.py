"""Async Linear GraphQL client — fetch issues and execute raw queries."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import httpx

from ..models import BlockerRef, Issue

logger = logging.getLogger(__name__)

_PAGE_SIZE = 50
_NETWORK_TIMEOUT = 30.0

# ---------------------------------------------------------------------------
# GraphQL documents
# ---------------------------------------------------------------------------

_POLL_QUERY = """
query SymphonyLinearPoll(
  $projectSlug: String!
  $stateNames: [String!]!
  $first: Int!
  $relationFirst: Int!
  $after: String
) {
  issues(
    filter: {
      project: { slugId: { eq: $projectSlug } }
      state: { name: { in: $stateNames } }
    }
    first: $first
    after: $after
  ) {
    nodes {
      id
      identifier
      title
      description
      priority
      state { name }
      branchName
      url
      labels { nodes { name } }
      inverseRelations(first: $relationFirst) {
        nodes {
          type
          issue { id identifier state { name } }
        }
      }
      createdAt
      updatedAt
    }
    pageInfo { hasNextPage endCursor }
  }
}
"""

_BY_IDS_QUERY = """
query SymphonyLinearIssuesById($ids: [ID!]!, $first: Int!, $relationFirst: Int!) {
  issues(filter: { id: { in: $ids } }, first: $first) {
    nodes {
      id
      identifier
      title
      description
      priority
      state { name }
      branchName
      url
      labels { nodes { name } }
      inverseRelations(first: $relationFirst) {
        nodes {
          type
          issue { id identifier state { name } }
        }
      }
      createdAt
      updatedAt
    }
  }
}
"""


# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------

class LinearClientError(Exception):
    def __init__(self, kind: str, detail=None):
        self.kind = kind
        self.detail = detail
        super().__init__(f"{kind}: {detail}")


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class LinearClient:
    def __init__(self, api_key: str, endpoint: str = "https://api.linear.app/graphql"):
        self._api_key = api_key
        self._endpoint = endpoint

    def _headers(self) -> dict:
        return {
            "Authorization": self._api_key,
            "Content-Type": "application/json",
        }

    async def _graphql(self, query: str, variables: dict) -> dict:
        payload = {"query": query, "variables": variables}
        try:
            async with httpx.AsyncClient(timeout=_NETWORK_TIMEOUT) as client:
                resp = await client.post(self._endpoint, json=payload, headers=self._headers())
        except httpx.RequestError as exc:
            raise LinearClientError("linear_api_request", str(exc)) from exc

        if resp.status_code != 200:
            body_preview = resp.text[:500]
            logger.error(f"linear_api_status status={resp.status_code} body={body_preview!r}")
            raise LinearClientError("linear_api_status", resp.status_code)

        body = resp.json()
        if "errors" in body:
            raise LinearClientError("linear_graphql_errors", body["errors"])
        return body

    async def graphql_raw(self, query: str, variables: dict) -> dict:
        """Execute a raw GraphQL operation; returns the full response body (for linear_graphql tool)."""
        payload = {"query": query, "variables": variables}
        try:
            async with httpx.AsyncClient(timeout=_NETWORK_TIMEOUT) as client:
                resp = await client.post(self._endpoint, json=payload, headers=self._headers())
        except httpx.RequestError as exc:
            raise LinearClientError("linear_api_request", str(exc)) from exc
        if resp.status_code != 200:
            raise LinearClientError("linear_api_status", resp.status_code)
        return resp.json()

    async def fetch_candidate_issues(
        self, project_slug: str, active_states: list[str]
    ) -> list[Issue]:
        issues: list[Issue] = []
        after: Optional[str] = None

        while True:
            body = await self._graphql(
                _POLL_QUERY,
                {
                    "projectSlug": project_slug,
                    "stateNames": active_states,
                    "first": _PAGE_SIZE,
                    "relationFirst": _PAGE_SIZE,
                    "after": after,
                },
            )
            page = (body.get("data") or {}).get("issues") or {}
            nodes = page.get("nodes") or []
            for raw in nodes:
                issue = _normalize_issue(raw)
                if issue:
                    issues.append(issue)

            page_info = page.get("pageInfo") or {}
            if not page_info.get("hasNextPage"):
                break
            end_cursor = page_info.get("endCursor")
            if not end_cursor:
                raise LinearClientError("linear_missing_end_cursor")
            after = end_cursor

        return issues

    async def fetch_issues_by_states(
        self, project_slug: str, state_names: list[str]
    ) -> list[Issue]:
        if not state_names:
            return []
        body = await self._graphql(
            _POLL_QUERY,
            {
                "projectSlug": project_slug,
                "stateNames": state_names,
                "first": _PAGE_SIZE,
                "relationFirst": _PAGE_SIZE,
                "after": None,
            },
        )
        nodes = ((body.get("data") or {}).get("issues") or {}).get("nodes") or []
        return [i for raw in nodes if (i := _normalize_issue(raw))]

    async def fetch_issue_states_by_ids(self, issue_ids: list[str]) -> list[Issue]:
        if not issue_ids:
            return []
        results: list[Issue] = []
        for start in range(0, len(issue_ids), _PAGE_SIZE):
            batch = issue_ids[start : start + _PAGE_SIZE]
            body = await self._graphql(
                _BY_IDS_QUERY,
                {"ids": batch, "first": len(batch), "relationFirst": _PAGE_SIZE},
            )
            nodes = ((body.get("data") or {}).get("issues") or {}).get("nodes") or []
            for raw in nodes:
                issue = _normalize_issue(raw)
                if issue:
                    results.append(issue)
        return results


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def _normalize_issue(raw: dict) -> Optional[Issue]:
    if not isinstance(raw, dict):
        return None
    issue_id = raw.get("id")
    identifier = raw.get("identifier")
    title = raw.get("title")
    if not (issue_id and identifier and title):
        return None

    state_name = (raw.get("state") or {}).get("name") or ""

    label_nodes = ((raw.get("labels") or {}).get("nodes")) or []
    labels = [
        n["name"].lower()
        for n in label_nodes
        if isinstance(n, dict) and isinstance(n.get("name"), str)
    ]

    blockers: list[BlockerRef] = []
    for rel in ((raw.get("inverseRelations") or {}).get("nodes") or []):
        if not isinstance(rel, dict):
            continue
        if (rel.get("type") or "").strip().lower() != "blocks":
            continue
        bi = rel.get("issue") or {}
        blockers.append(
            BlockerRef(
                id=bi.get("id"),
                identifier=bi.get("identifier"),
                state=(bi.get("state") or {}).get("name"),
            )
        )

    priority = raw.get("priority")
    if not isinstance(priority, int):
        priority = None

    return Issue(
        id=issue_id,
        identifier=identifier,
        title=title,
        description=raw.get("description"),
        priority=priority,
        state=state_name,
        branch_name=raw.get("branchName"),
        url=raw.get("url"),
        labels=labels,
        blocked_by=blockers,
        created_at=_parse_dt(raw.get("createdAt")),
        updated_at=_parse_dt(raw.get("updatedAt")),
    )


def _parse_dt(value) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None
