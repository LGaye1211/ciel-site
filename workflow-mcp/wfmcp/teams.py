"""Teams notifiers.

Targets are dicts: {"channel": "<logical name>"} or {"user": "<email or upn>"}.
The engine never knows webhook URLs or Graph ids; `channels.yaml` maps logical
names to real destinations so workflow types stay portable across tenants.
"""
from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol

import yaml

from .cards import webhook_payload


class Notifier(Protocol):
    def send(self, target: dict, card: dict, text: str) -> str: ...


@dataclass
class ConsoleNotifier:
    """Dev and test notifier: records every card instead of sending it."""

    sent: list[dict] = field(default_factory=list)
    echo: bool = False

    def send(self, target: dict, card: dict, text: str) -> str:
        self.sent.append({"target": target, "card": card, "text": text})
        if self.echo:
            print(f"[notify {target}] {text}")
        return f"console:{len(self.sent)}"


@dataclass
class WebhookNotifier:
    """Posts Adaptive Cards to Teams Workflows incoming webhooks, one URL per logical channel.

    User targets fall back to `default_channel` because webhooks cannot reach a
    person directly. Use GraphActivityNotifier for per-user pings.
    """

    channels: dict[str, str]
    default_channel: str | None = None
    timeout: float = 10.0

    def send(self, target: dict, card: dict, text: str) -> str:
        name = target.get("channel") or self.default_channel
        if not name or name not in self.channels:
            raise KeyError(f"no webhook configured for channel {name!r}; known: {sorted(self.channels)}")
        body = json.dumps(webhook_payload(card)).encode()
        req = urllib.request.Request(self.channels[name], data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return f"webhook:{name}:{resp.status}"


@dataclass
class GraphActivityNotifier:
    """Per-user Teams activity feed notification via Microsoft Graph (app-only).

    Needs: a registered Teams app whose manifest declares the activity type
    `workflowTask`, installed for the user; an app registration with the
    application permission TeamsActivity.Send; and `token_provider()` returning
    a Graph bearer token. Channel targets are delegated to `fallback`.
    """

    token_provider: Any
    teams_app_id: str
    fallback: Notifier | None = None
    activity_type: str = "workflowTask"
    timeout: float = 10.0

    def send(self, target: dict, card: dict, text: str) -> str:
        user = target.get("user")
        if not user:
            if self.fallback:
                return self.fallback.send(target, card, text)
            raise KeyError("GraphActivityNotifier needs a user target")
        link = next((a["url"] for a in card.get("actions", []) if a.get("type") == "Action.OpenUrl"), None)
        body = {
            "topic": {"source": "text", "value": card["body"][0]["text"], "webUrl": link or "https://teams.microsoft.com"},
            "activityType": self.activity_type,
            "previewText": {"content": text[:200]},
            "templateParameters": [{"name": "title", "value": card["body"][0]["text"]}],
        }
        url = f"https://graph.microsoft.com/v1.0/users/{user}/teamwork/sendActivityNotification"
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.token_provider()}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return f"graph:{user}:{resp.status}"


@dataclass
class RoutingNotifier:
    """Sends user targets to one notifier and channel targets to another."""

    for_users: Notifier
    for_channels: Notifier

    def send(self, target: dict, card: dict, text: str) -> str:
        return (self.for_users if target.get("user") else self.for_channels).send(target, card, text)


def build_notifier_from_config(path: str | None) -> Notifier:
    """channels.yaml:

    channels:
      ops-onboarding: https://prod-XX.westeurope.logic.azure.com/workflows/...
    default_channel: ops-onboarding
    graph:                      # optional, enables per-user activity notifications
      teams_app_id: 00000000-0000-0000-0000-000000000000
      token_env: GRAPH_TOKEN    # env var holding a bearer token (swap for MSAL in prod)
    """
    if not path or not os.path.exists(path):
        return ConsoleNotifier(echo=True)
    cfg = yaml.safe_load(open(path)) or {}
    channels = WebhookNotifier(channels=cfg.get("channels", {}), default_channel=cfg.get("default_channel"))
    graph = cfg.get("graph")
    if graph:
        env = graph.get("token_env", "GRAPH_TOKEN")
        users = GraphActivityNotifier(token_provider=lambda: os.environ[env], teams_app_id=graph["teams_app_id"], fallback=channels)
        return RoutingNotifier(for_users=users, for_channels=channels)
    return channels
