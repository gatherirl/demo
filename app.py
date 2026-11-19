"""
GatherRhiza Labs — Human-Scale AI demo, v2
==========================================

A single-file Streamlit demo that matches the Mozilla Foundation "Human-Scale AI"
proposal: five co-operating agents, a KAMI (one small local model for one place),
an auditable consent ledger, a machine-enforceable creative commons, and the
grant's own success metrics.

Run:
    streamlit run app_v2.py

Optional: point at a real local model in LM Studio (OpenAI-compatible server):
    LOCAL_MODEL_URL=http://localhost:1234/v1 streamlit run app_v2.py

With no model running, every agent falls back to a scripted, inspectable
generator so the demo never breaks and never calls the cloud.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import streamlit as st

try:  # optional: only needed for a real LM Studio connection
    import requests
except Exception:  # pragma: no cover
    requests = None


# =============================================================================
# CONFIG — edit these, everything else is derived
# =============================================================================

APP_NAME = "GatherRhiza Labs"
CLUB_NAME = "Gather IRL Rock Club"
KAMI_NAME = "girl-rock-club-01"
LOCAL_MODEL_URL = os.getenv("LOCAL_MODEL_URL", "http://localhost:1234/v1").rstrip("/")

# Energy figures are MODELLED order-of-magnitude comparisons, not measurements.
# Local: 7B model on a Mac mini, ~15 W, ~12 tokens/sec.
# Cloud counterfactual: a frontier model behind a datacenter, ~2,000 W, ~40 tok/s.
LOCAL_WATTS = 15.0
LOCAL_TOKENS_PER_SEC = 12.0
CLOUD_WATTS = 2000.0
CLOUD_TOKENS_PER_SEC = 40.0

SCOPES: Dict[str, str] = {
    "contact": "Club may message you about gatherings",
    "presence": "Other members may see that you attended",
    "connections": "Club may suggest you to members who share your interests",
    "artifacts": "Your co-creations may be shared under the club's commons rules",
    "learning": "Your feedback may be used to improve this club's KAMI",
}

GENRES = [
    "indie folk", "acoustic", "punk", "garage rock", "shoegaze",
    "post-punk", "soul", "hip hop", "jazz", "experimental",
]

LICENSES: Dict[str, Dict[str, bool]] = {
    "CC BY 4.0": {"attribution": True, "commercial": True, "ai_training": True, "share_alike": False},
    "CC BY-SA 4.0": {"attribution": True, "commercial": True, "ai_training": True, "share_alike": True},
    "CC BY-NC-SA 4.0": {"attribution": True, "commercial": False, "ai_training": False, "share_alike": True},
    "Club commons (custom)": {"attribution": True, "commercial": False, "ai_training": False, "share_alike": True},
}

REQUESTERS = [
    "Club member",
    "Local nonprofit",
    "Local venue",
    "Brand / advertiser",
    "AI training pipeline",
]

LISTINGS: List[Dict[str, Any]] = [
    {
        "id": "dcf",
        "title": "Daisy Chain Fields pre-party",
        "when": "Fri Nov 20, 7:00 PM",
        "venue": "Laundromat on Church Ave",
        "genres": ["indie folk", "acoustic", "shoegaze"],
        "price": 8.0,
        "artist_share": 0.8,
        "accessibility": "Step-free, quiet room available",
        "note": "Fan-run, unofficial, all ages",
    },
    {
        "id": "lounge",
        "title": "Wednesday Listening Lounge",
        "when": "Wed Nov 25, 6:30 PM",
        "venue": "Community Center, Room B",
        "genres": ["soul", "jazz", "indie folk"],
        "price": 5.0,
        "artist_share": 0.7,
        "accessibility": "Step-free, ASL on request",
        "note": "Recurring; bring one record",
    },
    {
        "id": "garage",
        "title": "Garage Rock Night",
        "when": "Sat Nov 28, 8:00 PM",
        "venue": "Basement on E 18th",
        "genres": ["garage rock", "punk", "post-punk"],
        "price": 10.0,
        "artist_share": 0.75,
        "accessibility": "Stairs only",
        "note": "Three local bands, all door money split",
    },
    {
        "id": "zine",
        "title": "Zine + Tape Swap",
        "when": "Sun Dec 6, 2:00 PM",
        "venue": "Flatbush Library meeting room",
        "genres": ["experimental", "hip hop", "acoustic"],
        "price": 0.0,
        "artist_share": 1.0,
        "accessibility": "Step-free, seated, low-sensory hour first",
        "note": "Free; trade, don't buy",
    },
]

FEEDBACK_SEED = [
    ("Ava", 9, "Loved that it was small. I actually talked to three people instead of shouting over a crowd."),
    ("Ben", 6, "Good set, but it started late and I couldn't tell where the door money went."),
    ("Cleo", 10, "The quiet room saved me. I would come every week if it stayed this size."),
    ("Dev", 7, "Would be better with one acoustic act before the loud band. My ears were done by 9."),
    ("Emi", 8, "I came alone and someone introduced me to two people into shoegaze. That never happens."),
    ("Marco", 4, "Too loud for me after 9, and I left before the last band."),
]


# =============================================================================
# CORE: ledger, consent, members
# =============================================================================

class Ledger:
    """Append-only, hash-chained record of every agent decision and consent change.

    This is the artefact a community can inspect: not a log the vendor keeps for
    you, but a receipt book the club owns.
    """

    def __init__(self) -> None:
        self.entries: List[Dict[str, Any]] = []
        self._head = "genesis"

    def append(
        self,
        actor: str,
        action: str,
        decision: str = "allow",
        subject: str = "",
        detail: str = "",
    ) -> Dict[str, Any]:
        body = {
            "ts": datetime.now().strftime("%H:%M:%S"),
            "actor": actor,
            "action": action,
            "decision": decision,
            "subject": subject,
            "detail": detail,
        }
        payload = json.dumps(body, sort_keys=True)
        digest = hashlib.sha256((self._head + payload).encode()).hexdigest()
        entry = {**body, "prev": self._head[:12], "seal": digest[:12]}
        self.entries.append(entry)
        self._head = digest
        return entry

    def verify(self) -> Tuple[bool, int]:
        """Recompute the chain. Returns (intact, first_broken_index)."""
        head = "genesis"
        for i, e in enumerate(self.entries):
            body = {k: e[k] for k in ("ts", "actor", "action", "decision", "subject", "detail")}
            digest = hashlib.sha256((head + json.dumps(body, sort_keys=True)).encode()).hexdigest()
            if e["seal"] != digest[:12]:
                return False, i
            head = digest
        return True, -1


@dataclass
class Member:
    id: str
    name: str
    interests: List[str]
    consent: Dict[str, bool]
    is_artist: bool = False
    joined: str = ""

    def scoped_view(self, scope: str) -> Optional[Dict[str, Any]]:
        """An agent never sees a full member record.

        It receives the minimum projection allowed by the member's consent for
        that purpose — and nothing at all if consent is absent.
        """
        if not self.consent.get(scope, False):
            return None
        base = {"id": self.id, "name": self.name}
        if scope == "connections":
            base["interests"] = list(self.interests)
        return base


def default_consent(**overrides: bool) -> Dict[str, bool]:
    consent = {scope: True for scope in SCOPES}
    consent.update(overrides)
    return consent


@dataclass
class Club:
    members: Dict[str, Member]
    ledger: Ledger
    kami: "KAMI"
    event: Optional[Dict[str, Any]] = None
    trace: List[Dict[str, Any]] = field(default_factory=list)
    proposals: List[Dict[str, Any]] = field(default_factory=list)
    feedback: List[Dict[str, Any]] = field(default_factory=list)
    works: List[Dict[str, Any]] = field(default_factory=list)
    history: List[Dict[str, Any]] = field(default_factory=list)
    invites: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    adopted: List[Dict[str, Any]] = field(default_factory=list)
    discoveries: List[Dict[str, Any]] = field(default_factory=list)
    connections_made: int = 0
    connection_pairs: set = field(default_factory=set)
    energy: Dict[str, float] = field(
        default_factory=lambda: {"tokens": 0.0, "joules": 0.0, "cloud_joules": 0.0}
    )

    # -- helpers -------------------------------------------------------------
    def member_list(self) -> List[Member]:
        return list(self.members.values())

    def get(self, member_id: str) -> Optional[Member]:
        return self.members.get(member_id)

    def note(self, agent: str, action: str, decision: str, detail: str) -> None:
        self.trace.append(
            {"agent": agent, "action": action, "decision": decision, "detail": detail,
             "at": datetime.now().strftime("%H:%M:%S")}
        )

    def record_model_call(self, tokens: int, source: str) -> None:
        tokens = max(tokens, 0)
        local_seconds = tokens / LOCAL_TOKENS_PER_SEC
        cloud_seconds = tokens / CLOUD_TOKENS_PER_SEC
        self.energy["tokens"] += tokens
        self.energy["joules"] += local_seconds * LOCAL_WATTS
        self.energy["cloud_joules"] += cloud_seconds * CLOUD_WATTS

    def dollars_to_artists(self) -> float:
        # Every closed gathering is appended to history exactly once, so the
        # total comes from history alone; adding the live event would double it.
        return round(sum(h.get("raised", 0.0) for h in self.history), 2)

    def returning_rate(self) -> Tuple[float, int]:
        counts: Dict[str, int] = {}
        for h in self.history:
            for mid in h.get("attendees", []):
                counts[mid] = counts.get(mid, 0) + 1
        if not counts:
            return 0.0, 0
        returning = sum(1 for c in counts.values() if c >= 2)
        return returning / len(counts), returning


# =============================================================================
# LOCAL MODEL (KAMI)
# =============================================================================

class KAMI:
    """One small model, one place.

    'KAMI' = Knowledge Artefact Management Intelligence (Civic.AI): a model a
    group runs that serves one place, practice or network of people. Here it is
    an optional 7B model in LM Studio, with a scripted fallback so the demo is
    honest about when no model is running.
    """

    def __init__(self, name: str, url: str) -> None:
        self.name = name
        self.url = url
        self.connected: Optional[bool] = None
        self.model_id = ""
        self.error = ""

    def probe(self) -> bool:
        if requests is None:
            self.connected, self.error = False, "requests not installed"
            return False
        try:
            r = requests.get(f"{self.url}/models", timeout=1.2)
            r.raise_for_status()
            data = r.json().get("data", [])
            self.model_id = data[0].get("id", "local model") if data else "local model"
            self.connected, self.error = True, ""
        except Exception as exc:  # noqa: BLE001 - demo must never crash
            self.connected, self.error = False, str(exc)[:120]
        return bool(self.connected)

    def generate(self, system: str, prompt: str, fallback: str, max_tokens: int = 200) -> Dict[str, Any]:
        """Return {text, tokens, source}. Never raises."""
        if self.connected:
            try:
                r = requests.post(
                    f"{self.url}/chat/completions",
                    json={
                        "model": self.model_id,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.7,
                        "max_tokens": max_tokens,
                    },
                    timeout=12,
                )
                r.raise_for_status()
                text = r.json()["choices"][0]["message"]["content"].strip()
                return {"text": text, "tokens": int(len(text.split()) * 1.35), "source": "local model"}
            except Exception as exc:  # noqa: BLE001
                self.error = str(exc)[:120]
                self.connected = False
        return {"text": fallback, "tokens": int(len(fallback.split()) * 1.35), "source": "scripted"}


# =============================================================================
# AGENTS — the five named in the grant, plus the artist ledger
# =============================================================================

class BaseAgent:
    name = "Agent"

    def __init__(self, club: Club) -> None:
        self.club = club

    def _model(self, system: str, prompt: str, fallback: str) -> str:
        out = self.club.kami.generate(system, prompt, fallback)
        self.club.record_model_call(out["tokens"], out["source"])
        return out["text"]

    def _allow(self, member: Member, scope: str, purpose: str) -> bool:
        ok = bool(member.consent.get(scope, False))
        self.club.ledger.append(
            actor=self.name,
            action=purpose,
            decision="allow" if ok else "blocked",
            subject=member.id,
            detail=f"scope={scope}",
        )
        self.club.note(self.name, purpose, "allow" if ok else "blocked",
                       f"{member.name} · scope={scope}")
        return ok


class PrivacyManager(BaseAgent):
    """Turns consent into a runtime boundary, with a receipt for every check."""

    name = "Privacy Manager"

    def can_contact(self, member: Member) -> bool:
        return self._allow(member, "contact", "check_contact")

    def can_suggest_connection(self, a: Member, b: Member) -> bool:
        # Both sides must opt in. One opt-out is enough to stop the suggestion.
        ok = bool(a.consent.get("connections") and b.consent.get("connections"))
        self.club.ledger.append(
            actor=self.name, action="check_connection",
            decision="allow" if ok else "blocked", subject=f"{a.id}+{b.id}",
            detail="scope=connections (mutual, required)",
        )
        return ok

    def can_publish(self, member: Member) -> bool:
        return self._allow(member, "artifacts", "check_artifact_rights")


class EventDiscoveryAgent(BaseAgent):
    """Finds gatherings worth showing up to, from local listings — and says why."""

    name = "Event Discovery Agent"

    def run(self) -> List[Dict[str, Any]]:
        ranked: List[Dict[str, Any]] = []
        for listing in LISTINGS:
            shared: Dict[str, List[str]] = {}
            for m in self.club.member_list():
                overlap = sorted(set(m.interests) & set(listing["genres"]))
                if overlap:
                    shared[m.name] = overlap
            score = sum(len(v) for v in shared.values()) + (1 if listing["price"] <= 8 else 0)
            ranked.append({**listing, "score": score, "shared": shared,
                           "matches": len(shared)})
        ranked.sort(key=lambda x: (-x["score"], x["price"]))
        self.club.discoveries = ranked

        top = ranked[0]
        blurb = self._model(
            "You are a neighborhood music club's local agent. Be concrete and brief.",
            f"Write one sentence inviting members who like {', '.join(top['genres'])} "
            f"to '{top['title']}' at {top['venue']}. No hype.",
            f"{top['title']} is at {top['venue']} — {top['matches']} members share this taste.",
        )
        self.club.note(self.name, "rank_listings", "allow",
                       f"{len(ranked)} local listings scored; top = {top['title']}")
        self.club.ledger.append(self.name, "rank_listings", "allow", "local listings",
                                f"top={top['id']}")
        return ranked


class InvitationAgent(BaseAgent):
    """Drafts and sends invitations — only to members who opted into contact."""

    name = "Invitation Agent"

    def invite_all(self, event: Dict[str, Any]) -> Tuple[int, int]:
        sent = blocked = 0
        for m in self.club.member_list():
            if not self.club.get(m.id):
                continue
            if not PrivacyManager(self.club).can_contact(m):
                self.club.invites[m.id] = {
                    "status": "blocked",
                    "reason": "opted out of contact",
                    "text": "",
                }
                blocked += 1
                continue
            fallback = (
                f"Hi {m.name} — {event['title']} is {event['when']} at {event['venue']}. "
                f"Small room, ${event['fee']:.0f} at the door and it goes to the artists. "
                f"Your {', '.join(m.interests[:2])} taste is why I thought of you. "
                "No pressure — come if it feels right."
            )
            text = self._model(
                "You write short, warm invitations for a neighborhood music club. "
                "Never pressure, never invent details, maximum 55 words.",
                f"Invite {m.name}, who likes {', '.join(m.interests)}, to {event['title']} "
                f"({event['when']}, {event['venue']}, ${event['fee']:.0f}).",
                fallback,
            )
            self.club.invites[m.id] = {"status": "sent", "reason": "", "text": text}
            sent += 1
        event["status"] = "invited"
        self.club.ledger.append(self.name, "send_invitations", "allow", event["title"],
                                f"sent={sent} blocked={blocked}")
        self.club.note(self.name, "send_invitations", "allow",
                       f"{sent} sent · {blocked} blocked by consent")
        return sent, blocked


class ConnectionAgent(BaseAgent):
    """Suggests introductions, never exchanges contact details, explains itself."""

    name = "Connection Agent"

    def suggest(self, viewer: Member, attendees: List[Member]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for other in attendees:
            if other.id == viewer.id:
                continue
            if not PrivacyManager(self.club).can_suggest_connection(viewer, other):
                continue
            shared = sorted(set(viewer.interests) & set(other.interests))
            if not shared:
                continue
            pair = tuple(sorted((viewer.id, other.id)))
            if pair in self.club.connection_pairs:
                continue
            nudge = self._model(
                "You write one gentle sentence suggesting an introduction at a small "
                "music gathering. You never share contact details.",
                f"{viewer.name} and {other.name} both like {', '.join(shared)}. "
                "Suggest the host introduce them.",
                f"You and {other.name} both gravitate to {', '.join(shared)} — "
                "ask the host to introduce you at the break.",
            )
            out.append({"with": other.name, "shared": shared, "nudge": nudge})
            self.club.connection_pairs.add(pair)
            self.club.connections_made += 1
        self.club.note(self.name, "suggest_connections", "allow",
                       f"{len(out)} introductions for {viewer.name}")
        return out


class CommunityLearningAgent(BaseAgent):
    """Reads feedback, proposes changes — and cannot adopt them itself."""

    name = "Community Learning Agent"

    THEMES = {
        "size & intimacy": ["small", "crowd", "quiet", "alone", "talked"],
        "timing": ["late", "start", "time", "early"],
        "money transparency": ["money", "door", "paid", "went"],
        "accessibility & sensory": ["quiet room", "ears", "loud", "sensory", "seated"],
        "introductions": ["introduced", "alone", "met", "people"],
    }

    def synthesize(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        texts = [(m.name, m.consent.get("learning", False), t) for m, _, t in
                 [(self.club.get(x["member_id"]), x["score"], x["text"])
                  for x in self.club.feedback if self.club.get(x["member_id"])]]
        usable = [t for _, ok, t in texts if ok]
        excluded = sum(1 for _, ok, _ in texts if not ok)

        themes: List[Dict[str, Any]] = []
        for theme, words in self.THEMES.items():
            hits = [t for t in usable if any(w in t.lower() for w in words)]
            if hits:
                themes.append({"theme": theme, "count": len(hits),
                               "evidence": hits[0][:90]})

        self.club.ledger.append(self.name, "synthesize_feedback", "allow",
                                "club feedback", f"used={len(usable)} excluded={excluded}")
        self.club.note(self.name, "synthesize_feedback", "allow",
                       f"{len(themes)} themes from {len(usable)} opt-in notes")
        return themes, self._proposals(themes)

    def _proposals(self, themes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        proposals: List[Dict[str, Any]] = []
        names = {t["theme"] for t in themes}
        if "size & intimacy" in names or "introductions" in names:
            proposals.append({"id": "cap25", "text": "Cap gatherings at 25 people and keep the quiet room.",
                              "why": "Members name smallness as the reason they talked to anyone."})
        if "timing" in names:
            proposals.append({"id": "start", "text": "Start on the hour; put the acoustic act first.",
                              "why": "Late starts and loud-first setlists came up repeatedly."})
        if "money transparency" in names:
            proposals.append({"id": "split", "text": "Project the door split on the wall before the set.",
                              "why": "People asked where the money went, not for lower prices."})
        if "accessibility & sensory" in names:
            proposals.append({"id": "sensory", "text": "Keep a low-sensory hour and ASL on request as standing rules.",
                              "why": "The quiet room changed whether members could attend at all."})
        if not proposals:
            proposals.append({"id": "ask", "text": "Run one more listening session before changing anything.",
                              "why": "Not enough signal to propose a change."})
        for p in proposals:
            p["status"] = "proposed"
            p["yes"] = 0
        return proposals


class CreativeCommonsAgent(BaseAgent):
    """Stores co-creations with provenance and enforces the club's usage rules."""

    name = "Creative Commons Agent"

    def can_store(self, creator: Member) -> bool:
        return PrivacyManager(self.club).can_publish(creator)

    def check_use(self, work: Dict[str, Any], requester: str, purpose: str) -> Dict[str, Any]:
        rules = LICENSES[work["license"]]
        reasons: List[str] = []
        allow = True

        if requester == "AI training pipeline" and not rules["ai_training"]:
            allow = False
            reasons.append("the club's charter forbids use as training data")
        if requester.startswith("Brand") and not rules["commercial"]:
            allow = False
            reasons.append("the licence is non-commercial")
        if requester == "Local venue" and rules["share_alike"]:
            reasons.append("share-alike applies to any reuse")
        if rules["attribution"]:
            reasons.append(f"credit {work['creator']} and link back to the club archive")

        decision = "allow" if allow else "deny"
        self.club.ledger.append(self.name, "license_check", decision, work["title"],
                                f"requester={requester}; purpose={purpose}")
        self.club.note(self.name, "license_check", decision, f"{work['title']} ← {requester}")
        return {"allow": allow, "decision": decision.upper(), "reasons": reasons,
                "license": work["license"]}


# =============================================================================
# SEED STATE
# =============================================================================

def new_club() -> Club:
    ledger = Ledger()
    now = datetime.now() - timedelta(days=120)
    # Fifteen members. Each consent scope has at least one member who has
    # switched it off, so every agent has a refusal case to demonstrate.
    members = {
        "ava": Member("ava", "Ava", ["indie folk", "acoustic"], default_consent()),
        "ben": Member("ben", "Ben", ["punk", "garage rock"], default_consent(presence=False)),
        "cleo": Member("cleo", "Cleo", ["indie folk", "shoegaze"], default_consent()),
        "dev": Member("dev", "Dev", ["acoustic", "garage rock"], default_consent(connections=False)),
        "emi": Member("emi", "Emi", ["shoegaze", "indie folk"], default_consent()),
        "frank": Member("frank", "Frank", ["soul", "jazz"], default_consent(contact=False), is_artist=True),
        "gina": Member("gina", "Gina", ["post-punk", "garage rock"], default_consent()),
        "hana": Member("hana", "Hana", ["jazz", "soul"], default_consent(), is_artist=True),
        "ivo": Member("ivo", "Ivo", ["experimental", "hip hop"], default_consent()),
        "jules": Member("jules", "Jules", ["indie folk", "shoegaze"], default_consent()),
        "kai": Member("kai", "Kai", ["hip hop", "soul"], default_consent()),
        "lena": Member("lena", "Lena", ["acoustic", "jazz"], default_consent(), is_artist=True),
        "marco": Member("marco", "Marco", ["punk", "post-punk"], default_consent(learning=False)),
        "nia": Member("nia", "Nia", ["soul", "hip hop"], default_consent()),
        "omar": Member("omar", "Omar", ["experimental", "acoustic"], default_consent(artifacts=False)),
    }
    for i, m in enumerate(members.values()):
        m.joined = (now + timedelta(days=i * 6)).strftime("%b %d")

    ledger.append("club", "charter_adopted", "allow", CLUB_NAME,
                  "small · intentional · tailored")

    club = Club(members=members, ledger=ledger, kami=KAMI(KAMI_NAME, LOCAL_MODEL_URL))

    # Six months of plausible club history so the metrics are not all zero.
    club.history = [
        {"date": "Jun 18", "attendees": ["ava", "ben", "cleo", "gina"], "raised": 96.0},
        {"date": "Jul 16", "attendees": ["ava", "ben", "emi", "hana", "ivo", "jules"],
         "raised": 110.0},
        {"date": "Aug 20", "attendees": ["ava", "cleo", "dev", "emi", "gina", "kai", "lena"],
         "raised": 140.0},
        {"date": "Sep 17", "attendees": ["ava", "ben", "cleo", "emi", "hana", "jules",
                                          "marco", "nia"], "raised": 128.0},
        {"date": "Oct 15", "attendees": ["ava", "cleo", "dev", "emi", "frank", "gina", "ivo",
                                          "kai", "lena", "omar"], "raised": 160.0},
    ]
    club.works = [
        {"title": "Room B, side A", "creator": "Emi", "type": "Live recording",
         "license": "CC BY-NC-SA 4.0", "added": "Oct 16"},
        {"title": "Daisy chain crown zine", "creator": "Cleo", "type": "Zine",
         "license": "Club commons (custom)", "added": "Oct 18"},
    ]
    for m, score, text in FEEDBACK_SEED:
        mid = next((k for k, v in members.items() if v.name == m), None)
        if mid:
            club.feedback.append({"member_id": mid, "score": score, "text": text})
    return club


def ensure_state() -> Club:
    if "club_v2" not in st.session_state:
        st.session_state["club_v2"] = new_club()
    return st.session_state["club_v2"]


# =============================================================================
# STYLE
# =============================================================================

# theme.css is the shared presentation layer with app.py. The additions below
# only cover component classes this demo introduces, and every colour has a
# fallback so the app still renders sensibly if the stylesheet is ever missing.
THEME_FILE = Path(__file__).with_name("theme.css")

FALLBACK_THEME = """<style>
:root{--gr-ink:#21150f;--gr-muted:#675b56;--gr-cream:#fff8ef;--gr-paper:#fffdf8;
 --gr-peach:#fff2e5;--gr-mint:#eaf8ef;--gr-green:#0c7a63;--gr-deep:#075746;
 --gr-purple:#7131c4;--gr-rust:#944011;--gr-rule:#e5d8ca;
 --gr-font:Manrope,Arial,sans-serif;--gr-display:"Instrument Serif",Georgia,serif;
 --gr-xs:.8125rem;--gr-card-radius:1.25rem;--gr-shadow:0 10px 30px rgb(49 25 12/.045);}
body,.stApp{background:var(--gr-cream);color:var(--gr-ink);font-family:var(--gr-font);}
[data-testid="stMainBlockContainer"]{max-width:74rem;padding:2rem 1.5rem 3rem;}
.gr-masthead{display:flex;justify-content:space-between;align-items:center;gap:1rem;
 border-bottom:1px solid var(--gr-rule);padding-bottom:.875rem;margin-bottom:1.1rem;}
.gr-brand{display:inline-flex;align-items:center;gap:.625rem;font-weight:800;}
.gr-mark{width:1.6rem;height:1.6rem;border-radius:50%;background:var(--gr-green);}
.gr-hero{display:grid;grid-template-columns:minmax(0,1.37fr) minmax(0,1fr);gap:1.5rem;
 border:1px solid var(--gr-rule);border-radius:1.75rem;background:var(--gr-paper);
 padding:2rem;margin-bottom:.75rem;}
.gr-hero .gr-kicker{width:fit-content;margin:0 0 .85rem;padding:.4rem .72rem;border-radius:999px;
 color:var(--gr-deep);background:var(--gr-mint);font-size:var(--gr-xs);font-weight:800;
 text-transform:uppercase;letter-spacing:.09em;}
.gr-hero h1{margin:0 0 .85rem;font:400 clamp(2.5rem,2rem + 2vw,3.5rem)/.98 var(--gr-display);}
.gr-hero h1 em{color:var(--gr-green);font-style:normal;}
.gr-hero p{max-width:48ch;color:var(--gr-muted);line-height:1.65;}
.gr-network{border-radius:var(--gr-card-radius);background:var(--gr-peach);min-height:8rem;}
@media (max-width:620px){.gr-hero{grid-template-columns:1fr;}}
</style>"""

CSS_ADDITIONS = """<style>
[data-testid="stAppViewContainer"]{background:var(--gr-cream,#fff8ef);}
.gr-card{background:var(--gr-paper,#fffdf8);border:1px solid var(--gr-rule,#e5d8ca);
 border-radius:var(--gr-card-radius,.95rem);padding:1rem 1.1rem;margin:.55rem 0;
 box-shadow:var(--gr-shadow,0 1px 2px rgb(0 0 0 / .04));}
.gr-card h4{margin:0 0 .3rem;font:700 1rem/1.3 var(--gr-font,system-ui);color:var(--gr-ink,#21150f);}
.gr-card.dend{border-left:4px solid var(--gr-rust,#944011);background:var(--gr-peach,#fff2e5);}
.gr-card.dallow{border-left:4px solid var(--gr-green,#0c7a63);background:var(--gr-mint,#eaf8ef);}
.gr-card .gr-small{color:var(--gr-muted,#675b56);}
.gr-badges{display:flex;flex-wrap:wrap;gap:.4rem;margin:.9rem 0 0;}
.gr-badge{font:700 var(--gr-xs,.8rem)/1.5 var(--gr-font,system-ui);
 border:1px solid var(--gr-rule,#e5d8ca);border-radius:999px;padding:.2rem .6rem;
 color:var(--gr-deep,#075746);background:var(--gr-paper,#fffdf8);}
.gr-badge.on{border-color:#bcd8c6;background:var(--gr-mint,#eaf8ef);}
.gr-badge.off{border-color:#ecd4c9;background:var(--gr-peach,#fff2e5);color:var(--gr-rust,#944011);}
.gr-stop{background:var(--gr-deep,#075746);color:#fdf9f2;
 border-radius:var(--gr-card-radius,1rem);padding:1.2rem 1.3rem;}
.gr-stop h3{color:#fff;margin:.1rem 0 .4rem;font:400 1.7rem/1.1 var(--gr-display,Georgia);}
.gr-stop p{color:#d8e8e2;margin:0;}
.gr-step{display:inline-block;font:800 var(--gr-xs,.75rem)/1.4 var(--gr-font,system-ui);
 letter-spacing:.12em;text-transform:uppercase;color:var(--gr-rust,#944011);margin-bottom:.2rem;}
.gr-mono{font:600 .76rem/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;
 background:var(--gr-paper,#fffdf8);border:1px solid var(--gr-rule,#e5d8ca);
 border-radius:.6rem;padding:.5rem .6rem;overflow-x:auto;white-space:pre-wrap;}
.stSidebar .gr-brand .gr-mark{width:1.7rem;height:1.7rem;}
div[data-testid="stMetricValue"]{font-family:var(--gr-display,Georgia);}
</style>"""


def load_styles() -> None:
    if THEME_FILE.exists():
        theme = f"<style>{THEME_FILE.read_text(encoding='utf-8')}</style>"
    else:
        theme = FALLBACK_THEME
    st.markdown(theme + CSS_ADDITIONS, unsafe_allow_html=True)


def html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def card(title: str, body: str, tone: str = "", small: str = "") -> None:
    cls = {"deny": "dend", "allow": "dallow"}.get(tone, "")
    extra = f'<div class="gr-small">{small}</div>' if small else ""
    html(f'<div class="gr-card {cls}"><h4>{title}</h4><div>{body}</div>{extra}</div>')


def sidebar(club: Club) -> str:
    with st.sidebar:
        html(f'<div class="gr-brand"><span class="gr-mark"></span>{APP_NAME}</div>')
        st.caption("Sovereign agentic infrastructure for hyperlocal gathering")

        page = st.radio(
            "Demo path",
            [
                "Start here",
                "1 · Club & consent",
                "2 · Discover",
                "3 · Invite",
                "4 · Gather (human)",
                "5 · Reflect",
                "6 · Commons",
                "7 · Impact",
                "8 · How it works",
            ],
            label_visibility="collapsed",
        )

        st.divider()
        st.markdown("**KAMI**")
        st.caption(f"`{club.kami.name}` · one model, one place")

        if st.button("Check local model", width="stretch"):
            club.kami.probe()
        if club.kami.connected:
            html(f'<div class="gr-badge on">● local model · {club.kami.model_id[:28]}</div>')
        else:
            html('<div class="gr-badge off">○ scripted fallback · no cloud calls</div>')
            st.caption(f"LM Studio at {LOCAL_MODEL_URL}")

        st.divider()
        st.markdown("**This session**")
        j = club.energy["joules"]
        cj = max(club.energy["cloud_joules"], 1e-9)
        st.metric("Energy used", f"{j:.1f} J", help="Modelled: 15 W at 12 tokens/sec.")
        st.caption(
            f"{club.energy['tokens']:.0f} tokens · {100 * j / cj:.2f}% of the modelled "
            "frontier-cloud equivalent"
        )

        st.divider()
        if st.button("Reset demo", width="stretch"):
            del st.session_state["club_v2"]
            st.rerun()

    return page


# =============================================================================
# ACT 0 — START HERE
# =============================================================================

def act_start(club: Club) -> None:
    html(f"""
<section class="gr-hero" aria-labelledby="gr-title">
  <div class="gr-hero-copy">
    <p class="gr-kicker">Gather IRL Rock Club · Flatbush, Brooklyn</p>
    <h1 id="gr-title">Human-Scale <em>AI</em>, running in the room</h1>
    <p>Five small agents do the before and the after — find the gig, invite the right
    people, remember what worked, keep the commons. The gathering itself stays human.
    Everything here runs on a local model, with a receipt for every decision.</p>
    <div class="gr-badges">
      <span class="gr-badge on">● no cloud API calls</span>
      <span class="gr-badge">7B params · ~15 W</span>
      <span class="gr-badge">{len(club.members)} members · 1 neighborhood</span>
      <span class="gr-badge">open source</span>
    </div>
    <p class="gr-note">Simulated invitations · local model with scripted fallback</p>
  </div>
  <div class="gr-network" aria-hidden="true"></div>
</section>
""")

    st.write("")
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        st.markdown("#### The five-minute path")
        st.markdown(
            "1. **Club & consent** — every member sets five separate scopes.\n"
            "2. **Discover** — the agent ranks real local listings and shows its reasons.\n"
            "3. **Invite** — watch it refuse to message the member who opted out.\n"
            "4. **Gather** — the agents stop. A human runs the room.\n"
            "5. **Reflect** — feedback becomes proposals; members decide.\n"
            "6. **Commons** — a licence checker that actually says no.\n"
            "7. **Impact** — the grant's own success metrics, live."
        )
    with c2:
        st.markdown("#### What is different here")
        st.markdown(
            "- **One model per place** (a KAMI), not one model for everyone.\n"
            "- **Consent is code**: agents get a scoped view, never the raw record.\n"
            "- **Agents propose; people decide** — a hard rule in the architecture.\n"
            "- **The gathering is the unit of work**, and AI is locked out of it.\n"
            "- **Receipts, not logging**: a hash-chained ledger the club owns."
        )

    st.divider()
    st.markdown("#### Live state")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Gatherings", len(club.history) + (1 if club.event and club.event.get("status") == "gathered" else 0))
    rate, _ = club.returning_rate()
    m2.metric("Returning members", f"{rate * 100:.0f}%", help="Consistency of attendance, not attrition")
    m3.metric("To artists", f"${club.dollars_to_artists():,.0f}")
    m4.metric("Works in commons", len(club.works))

    st.info(
        "Figures for power and cost are labelled models, not measurements. "
        "With LM Studio running, the same code path calls a real 7B model; "
        "otherwise it uses a scripted generator so the demo never depends on the cloud."
    )


# =============================================================================
# ACT 1 — CLUB & CONSENT
# =============================================================================

def act_club(club: Club) -> None:
    st.subheader("1 · The club and its consent")
    st.caption("Every member controls five separate purposes. An agent that needs a purpose "
               "it was not granted gets nothing — not a redacted record, nothing.")

    members = club.member_list()
    rows = []
    for m in members:
        row = {"Member": m.name, "Artist": m.is_artist}
        row.update({scope: m.consent.get(scope, False) for scope in SCOPES})
        rows.append(row)
    df = pd.DataFrame(rows)

    edited = st.data_editor(
        df,
        hide_index=True,
        width="stretch",
        disabled=["Member", "Artist"],
        column_config={
            scope: st.column_config.CheckboxColumn(help=desc)
            for scope, desc in SCOPES.items()
        },
        key=f"consent_matrix_{len(members)}",
    )

    if st.button("Save consent changes", type="primary"):
        changes = 0
        for i, m in enumerate(members):
            row = edited.iloc[i]
            for scope in SCOPES:
                new = bool(row[scope])
                if new != m.consent.get(scope, False):
                    m.consent[scope] = new
                    changes += 1
                    club.ledger.append(
                        actor=m.name,
                        action=f"consent.{scope}",
                        decision="allow" if new else "withdraw",
                        subject=m.id,
                        detail=f"set to {new}",
                    )
        if changes:
            st.success(f"{changes} consent change(s) written to the ledger.")
        else:
            st.caption("No changes to save.")

    with st.form("add_member_v2", clear_on_submit=True):
        c1, c2 = st.columns([1, 2])
        name = c1.text_input("Name")
        interests = c2.multiselect("Interests", GENRES, default=["indie folk"])
        artist = st.checkbox("This person is a local artist")
        if st.form_submit_button("Add member"):
            if not name.strip():
                st.warning("A name helps the demo make sense.")
            elif len(club.members) >= 24:
                st.warning("This demo caps at 24 members. Small is the point.")
            else:
                mid = name.strip().lower().replace(" ", "_")[:12] + "_" + uuid.uuid4().hex[:4]
                club.members[mid] = Member(
                    mid, name.strip(), sorted(set(interests)) or ["indie folk"],
                    default_consent(), is_artist=artist, joined=datetime.now().strftime("%b %d"),
                )
                club.ledger.append(name.strip(), "member_joined", "allow", mid, "consent defaults on")
                st.rerun()

    st.divider()
    with st.expander("Audit ledger — every decision, hash-chained"):
        intact, broken = club.ledger.verify()
        if intact:
            st.success(f"Chain intact · {len(club.ledger.entries)} entries")
        else:
            st.error(f"Chain broken at entry {broken}")
        view = pd.DataFrame(club.ledger.entries[-14:])[::-1]
        st.dataframe(view, hide_index=True, width="stretch")
        st.caption("Each entry's seal is the hash of the previous seal plus its own contents. "
                   "Hand this file to the community and they can verify nothing was rewritten.")


# =============================================================================
# ACT 2 — DISCOVER
# =============================================================================

def act_discover(club: Club) -> None:
    st.subheader("2 · Discover what is already happening nearby")
    st.caption("The Event Discovery Agent reads a local listing board — not an ad auction — "
               "and explains each ranking.")

    if st.button("Run the discovery agent", type="primary"):
        club.discoveries = EventDiscoveryAgent(club).run()

    if not club.discoveries:
        st.info("Run the agent to rank this week's local listings.")
        return

    top = club.discoveries[0]
    card(
        f"Top pick · {top['title']}",
        f"{top['when']} · {top['venue']}<br>"
        f"<span class='gr-small'>{top['accessibility']} · ${top['price']:.0f} door · "
        f"{int(top['artist_share'] * 100)}% to artists</span>",
        tone="allow",
        small=f"{top['matches']} members share this taste",
    )

    table = pd.DataFrame([
        {
            "Listing": d["title"],
            "When": d["when"],
            "Venue": d["venue"],
            "Match": f"{d['matches']} members",
            "Shared tastes": ", ".join(sorted({g for v in d["shared"].values() for g in v})),
            "$ door": d["price"],
            "To artists": f"{int(d['artist_share'] * 100)}%",
        }
        for d in club.discoveries
    ])
    st.dataframe(table, hide_index=True, width="stretch")

    with st.expander("Why this order?"):
        for d in club.discoveries:
            names = ", ".join(f"{n} ({', '.join(v)})" for n, v in d["shared"].items())
            st.markdown(f"- **{d['title']}** — overlap score {d['score']}: {names or 'no overlap'}")

    choice = st.selectbox("Create a gathering from", [d["title"] for d in club.discoveries])
    picked = next(d for d in club.discoveries if d["title"] == choice)
    if st.button("Choose this gathering"):
        club.event = {
            "title": picked["title"],
            "when": picked["when"],
            "venue": picked["venue"],
            "fee": picked["price"],
            "artist_share": picked["artist_share"],
            "status": "draft",
            "listing": picked["id"],
            "attendees": [],
            "raised": 0.0,
        }
        club.invites = {}
        club.ledger.append("Event Discovery Agent", "select_gathering", "allow",
                           picked["id"], picked["title"])
        st.success(f"'{picked['title']}' is now a draft gathering. Go to step 3.")


# =============================================================================
# ACT 3 — INVITE
# =============================================================================

def act_invite(club: Club) -> None:
    st.subheader("3 · Invite — and watch consent hold")
    if not club.event:
        st.warning("Choose a gathering in step 2 first.")
        return

    event = club.event
    c1, c2, c3 = st.columns(3)
    event["when"] = c1.text_input("When", event["when"])
    event["venue"] = c2.text_input("Venue", event["venue"])
    event["fee"] = c3.number_input("Door ($)", 0.0, 40.0, float(event["fee"]), step=1.0)

    if st.button("Draft invitations", type="primary"):
        sent, blocked = InvitationAgent(club).invite_all(event)
        st.success(f"{sent} invitation(s) drafted · {blocked} blocked by consent.")
        if blocked:
            st.caption("Open the blocked card below — this is the feature, not a failure.")

    if not club.invites:
        st.info("Draft invitations to see per-member consent enforcement.")
        return

    blocked = [m for m in club.member_list()
               if club.invites.get(m.id, {}).get("status") == "blocked"]
    sent = [m for m in club.member_list()
            if club.invites.get(m.id, {}).get("status") == "sent"]

    for m in blocked:
        card(
            f"Blocked · {m.name}",
            "No message was generated. This member turned off <em>contact</em>.",
            tone="deny",
            small="Privacy Manager → deny · receipt in ledger",
        )

    if sent:
        with st.expander(f"{len(sent)} invitations drafted — read one", expanded=False):
            for m in sent:
                inv = club.invites[m.id]
                st.markdown(f"**{m.name}** · invitation drafted")
                html(f'<div class="gr-card"><div>{inv["text"]}</div>'
                     f'<div class="gr-small">sent by the local model · contact consent on</div></div>')

    st.divider()
    invited = [m for m in club.member_list() if club.invites.get(m.id, {}).get("status") == "sent"]
    if invited:
        st.markdown("##### Connection nudges (mutual opt-in only)")
        st.caption("The agent suggests an introduction and a reason to come — never a phone number. "
                   "Dev has connections switched off, so no suggestion may name him.")
        nudge_for = st.selectbox("Nudge for", [m.name for m in invited], key="nudge_for")
        if st.button("Suggest introductions"):
            viewer = next(m for m in invited if m.name == nudge_for)
            suggestions = ConnectionAgent(club).suggest(viewer, invited)
            if not suggestions:
                st.info("No new eligible introductions: either no shared taste, or consent is off.")
            for s in suggestions:
                card(
                    f"{nudge_for} ↔ {s['with']}",
                    f"Shared: {', '.join(s['shared'])}<br>{s['nudge']}",
                    tone="allow",
                    small="the host makes the introduction; no contact details exchanged",
                )
            st.caption("Run it again: pairs already suggested are not counted twice.")
    if invited:
        coming = st.multiselect(
            "Who is coming? (simulated RSVPs)",
            [m.name for m in invited],
            default=[m.name for m in invited if m.consent.get("presence", True)][:4],
        )
        if st.button("Lock attendance and hand off to the host"):
            ids = [m.id for m in invited if m.name in coming]
            event["attendees"] = ids
            event["status"] = "gathering"
            club.ledger.append("Invitation Agent", "handoff", "allow", event["title"],
                               f"{len(ids)} attendees; agents paused")
            club.note("Invitation Agent", "handoff", "allow",
                      f"{len(ids)} attendees · human host takes over")
            st.success("Attendance locked. The agents are now off. Go to step 4.")


# =============================================================================
# ACT 4 — GATHER
# =============================================================================

def act_gather(club: Club) -> None:
    st.subheader("4 · The gathering belongs to the people in the room")
    if not club.event or club.event.get("status") not in {"gathering", "gathered"}:
        st.warning("Lock attendance in step 3 first.")
        return

    event = club.event
    html(f"""
<div class="gr-stop">
  <div class="gr-kicker" style="color:#c9b9a4">Agency over automation</div>
  <h3>All five agents are paused.</h3>
  <p>No nudges, no scoring, no recording. The host runs the room; the model is idle.
  This middle hour is the part the technology is designed to protect.</p>
</div>
""")

    st.write("")
    st.markdown(f"**{event['title']}** · {event['when']} · {event['venue']} · "
                f"{len(event['attendees'])} people")
    st.markdown("##### Host checklist (human, not automated)")
    checks = [
        "Welcome people at the door; say where the door money goes.",
        "Introduce two people who have not met.",
        "Offer the quiet room before the loud set.",
        "Ask one person to record nothing but a setlist on paper.",
        "Close with: what should we keep, what should we change?",
    ]
    done = [st.checkbox(c, key=f"chk_{i}") for i, c in enumerate(checks)]

    if st.button("Gathering finished → hand back to the agents", type="primary"):
        artist_cut = round(event["fee"] * len(event["attendees"]) * event["artist_share"], 2)
        event["raised"] = artist_cut
        event["status"] = "gathered"
        club.history.append({
            "date": datetime.now().strftime("%b %d"),
            "attendees": list(event["attendees"]),
            "raised": artist_cut,
        })
        club.ledger.append("Host", "gathering_closed", "allow", event["title"],
                           f"${artist_cut:.2f} to artists")
        st.success(f"${artist_cut:.2f} recorded to the artist ledger. Feedback opens in step 5.")


# =============================================================================
# ACT 5 — REFLECT
# =============================================================================

def act_reflect(club: Club) -> None:
    st.subheader("5 · Learn, propose, then let the community decide")
    st.caption("The agent may read only feedback from members who opted into learning. "
               "It can propose; it cannot adopt.")

    usable = [f for f in club.feedback if club.get(f["member_id"]) and
              club.get(f["member_id"]).consent.get("learning", False)]
    with st.expander(f"Feedback the agent may use ({len(usable)} notes)", expanded=False):
        for f in club.feedback:
            m = club.get(f["member_id"])
            blocked = not m.consent.get("learning", False)
            html(f'<div class="gr-card {"dend" if blocked else ""}">'
                 f'<h4>{m.name} · {f["score"]}/10</h4><div>{f["text"]}</div>'
                 f'<div class="gr-small">{"excluded — learning consent off" if blocked else "included"}</div></div>')

    with st.form("feedback_v2", clear_on_submit=True):
        c1, c2 = st.columns([1, 3])
        who = c1.selectbox("Member", [m.name for m in club.member_list()])
        score = c1.slider("Belonging", 1, 10, 8)
        text = c2.text_area("What worked, what did not?")
        if st.form_submit_button("Add feedback"):
            mid = next(m.id for m in club.member_list() if m.name == who)
            club.feedback.append({"member_id": mid, "score": score, "text": text})
            st.rerun()

    if st.button("Run the Community Learning Agent", type="primary"):
        themes, proposals = CommunityLearningAgent(club).synthesize()
        club.proposals = proposals
        if themes:
            st.markdown("##### Themes")
            st.dataframe(pd.DataFrame(themes), hide_index=True, width="stretch")

    if club.proposals:
        st.markdown("##### Proposals")
        quorum = math.ceil(0.6 * len(club.members))
        st.caption(f"Adoption needs {quorum} support votes (60% of {len(club.members)} members).")
        for p in club.proposals:
            if p["status"] == "adopted":
                card(f"Adopted · {p['text']}", p["why"], tone="allow",
                     small=f"{p['yes']} votes · recorded in ledger")
                continue
            with st.container(border=True):
                st.markdown(f"**{p['text']}**")
                st.caption(p["why"])
                votes = st.slider("Support votes", 0, len(club.members), p["yes"], key=f"vote_{p['id']}")
                if st.button("Record community decision", key=f"adopt_{p['id']}"):
                    p["yes"] = votes
                    if votes >= quorum:
                        p["status"] = "adopted"
                        club.adopted.append(p)
                        club.ledger.append("Community", "adopt_proposal", "allow", p["id"],
                                           f"{votes} votes")
                        st.rerun()
                    else:
                        st.warning(f"{votes} is short of the {quorum}-vote quorum. The agent does not decide.")


# =============================================================================
# ACT 6 — COMMONS
# =============================================================================

def act_commons(club: Club) -> None:
    st.subheader("6 · A commons with rules a machine can enforce")
    st.caption("Co-creations carry provenance and a licence. The same agent answers "
               "'may I use this?' — including when the answer is no.")

    left, right = st.columns([1, 1], gap="large")

    with left:
        st.markdown("##### Add a co-creation")
        with st.form("work_v2", clear_on_submit=True):
            title = st.text_input("Title", placeholder="Setlist, recording, zine…")
            creator = st.selectbox("Creator", [m.name for m in club.member_list()])
            kind = st.selectbox("Type", ["Live recording", "Zine", "Setlist", "Photo", "Song"])
            lic = st.selectbox("Licence", list(LICENSES))
            if st.form_submit_button("Archive it"):
                m = next(m for m in club.member_list() if m.name == creator)
                if not CreativeCommonsAgent(club).can_store(m):
                    st.error(f"{m.name} has not granted artefact rights. Nothing was stored.")
                elif not title.strip():
                    st.warning("Give it a title so it can be attributed.")
                else:
                    club.works.append({
                        "title": title.strip(), "creator": creator, "type": kind,
                        "license": lic, "added": datetime.now().strftime("%b %d"),
                    })
                    club.ledger.append("Creative Commons Agent", "archive_work", "allow",
                                       title.strip(), f"license={lic}")
                    st.rerun()

        st.markdown("##### In the archive")
        for w in club.works:
            html(f'<div class="gr-card"><h4>{w["title"]}</h4>'
                 f'<div class="gr-small">{w["type"]} · {w["creator"]} · {w["license"]} · '
                 f'added {w["added"]}</div></div>')

    with right:
        st.markdown("##### Usage request")
        if not club.works:
            st.info("Archive a work first.")
            return
        work_title = st.selectbox("Work", [w["title"] for w in club.works])
        requester = st.selectbox("Who is asking", REQUESTERS)
        purpose = st.text_input("Purpose", "Play it before a local film screening")
        if st.button("Check the club's rules", type="primary"):
            work = next(w for w in club.works if w["title"] == work_title)
            result = CreativeCommonsAgent(club).check_use(work, requester, purpose)
            tone = "allow" if result["allow"] else "deny"
            card(
                f'{result["decision"]} · {work_title}',
                f'Requester: {requester}<br>Licence: {result["license"]}<br>'
                + "<br>".join(f"· {r}" for r in result["reasons"]),
                tone=tone,
                small="receipt written to the ledger",
            )

        with st.expander("The club's custom rules"):
            st.markdown(
                "- **Attribution** always, linking to the club archive.\n"
                "- **No commercial use** without a community vote.\n"
                "- **No AI training**, including by this club's own agents.\n"
                "- **Share-alike**: anything built on a work stays in the commons.\n"
                "- Members can withdraw a work; the archive keeps a tombstone, not the file."
            )


# =============================================================================
# ACT 7 — IMPACT
# =============================================================================

def act_impact(club: Club) -> None:
    st.subheader("7 · The grant's success metrics, measured by the club")

    rate, returning = club.returning_rate()
    gatherings = len(club.history)
    gov = (len(club.adopted) / len(club.proposals)) if club.proposals else None

    m1, m2, m3 = st.columns(3)
    m1.metric("Gatherings held", gatherings, help="Target: weekly by month 12")
    m2.metric("Returning members", f"{rate * 100:.0f}%", f"{returning} people, 2+ times")
    m3.metric("Dollars to artists", f"${club.dollars_to_artists():,.0f}")

    m4, m5, m6 = st.columns(3)
    m4.metric("Introductions made", club.connections_made)
    m5.metric("Works in the commons", len(club.works))
    m6.metric(
        "Governance participation",
        f"{gov * 100:.0f}%" if gov is not None else "—",
        help="Adopted proposals ÷ proposals raised. Run step 5 to populate.",
    )

    st.divider()
    left, right = st.columns(2, gap="large")

    with left:
        st.markdown("##### Energy, modelled")
        j = club.energy["joules"]
        cj = club.energy["cloud_joules"]
        html(f"""<div class="gr-card">
          <h4>{j:.1f} joules this session</h4>
          <div>Same tokens on a frontier cloud stack, modelled: <b>{cj:,.0f} J</b>.</div>
          <div class="gr-small">Local ratio {100 * j / max(cj, 1e-9):.2f}%. Assumptions:
          15 W / 12 tok/s local; 2,000 W / 40 tok/s cloud. A comparison model, not a meter.</div>
        </div>""")
        st.caption("The point is not the exact number. It is that a club can compute its own "
                   "AI bill in joules and choose a smaller model.")

    with right:
        st.markdown("##### One node in a network")
        st.markdown(
            f"**{CLUB_NAME}** · {len(club.members)} members · {gatherings} gatherings\n\n"
            "**Brooklyn Baton Twirling Club** · pilot node · adds one shared practice: "
            "*a quiet hour before every session*"
        )
        st.caption("What crosses the link: counts, themes, and reusable templates. "
                   "What never crosses: names, attendance, messages, works.")

    st.divider()
    payload = {
        "club": CLUB_NAME,
        "kami": club.kami.name,
        "generated": datetime.now().isoformat(timespec="seconds"),
        "metrics": {
            "gatherings": gatherings,
            "returning_rate": round(rate, 3),
            "dollars_to_artists": club.dollars_to_artists(),
            "introductions": club.connections_made,
            "works": len(club.works),
            "governance_participation": round(gov, 3) if gov is not None else None,
        },
        "consent_snapshot": {m.id: m.consent for m in club.member_list()},
        "adopted": [p["text"] for p in club.adopted],
        "ledger": club.ledger.entries,
    }
    st.download_button(
        "Download the club's record (JSON)",
        data=json.dumps(payload, indent=2, default=str),
        file_name="gatherrhiza_club_record.json",
        mime="application/json",
    )
    st.caption("The export is the accountability artefact: consent, decisions and metrics in one "
               "file the community can take to another host.")


# =============================================================================
# ACT 8 — HOW IT WORKS
# =============================================================================

def act_how(club: Club) -> None:
    st.subheader("8 · How it works, and what is genuinely new")

    st.markdown("##### Architecture")
    st.code(
        """                         ┌──────────────────────────┐
                         │  KAMI  girl-rock-club-01 │
                         │  7B · local · no cloud   │
                         └────────────┬─────────────┘
                                      │
   ┌───────────────┬──────────────────┼──────────────────┬────────────────┐
   │               │                  │                  │                │
┌──▼───────┐ ┌─────▼──────┐ ┌─────────▼───────┐ ┌────────▼──────┐ ┌───────▼───────┐
│ Discovery│ │  Privacy   │ │   Connection    │ │   Community   │ │   Creative    │
│  Agent   │ │  Manager   │ │     Agent       │ │   Learning    │ │   Commons     │
└──┬───────┘ └─────┬──────┘ └─────────┬───────┘ └────────┬──────┘ └───────┬───────┘
   │               │                  │                  │                │
   └───────────────┴──────────┬───────┴──────────────────┴────────────────┘
                              │
                   ┌──────────▼───────────┐
                   │  Consent ledger      │
                   │  hash-chained, local │
                   └──────────┬───────────┘
                              │
                   ┌──────────▼───────────┐
                   │   THE GATHERING      │
                   │   humans only        │
                   │   agents paused      │
                   └──────────────────────┘""",
        language="text",
    )

    st.markdown("##### Five agents, five deliberate limits")
    st.dataframe(
        pd.DataFrame([
            ["Event Discovery", "Ranks local listings, explains the ranking",
             "Cannot buy placement or run an ad auction"],
            ["Privacy Manager", "Checks consent before every disclosure",
             "Cannot read a field the member did not grant"],
            ["Connection Agent", "Suggests introductions with shared taste",
             "Never exchanges contact details; both sides must opt in"],
            ["Community Learning", "Turns feedback into proposals",
             "Cannot adopt a proposal; quorum decides"],
            ["Creative Commons", "Stores provenance, answers usage requests",
             "Cannot override the licence or the charter"],
        ], columns=["Agent", "Does", "Refuses"]),
        hide_index=True,
        width="stretch",
    )

    st.markdown("##### Novel approaches to building AI systems")
    st.markdown(
        "**1. KAMI as the unit of deployment.** Not a global assistant, but one model per "
        "place, chartered by the people it serves and versioned like a public utility.\n\n"
        "**2. Consent as an execution boundary, not a settings page.** Agents receive a "
        "*scoped projection* of a member — and `None` without consent. Privacy is enforced "
        "before inference, so the model never sees what it may not use.\n\n"
        "**3. Propose-only agents with a quorum gate.** The learning agent writes proposals "
        "into a queue; a 60% community vote adopts them. The architecture makes "
        "'AI decides' impossible rather than discouraged.\n\n"
        "**4. Event-native computing.** The gathering is the unit of work. The system is "
        "designed around a scheduled period in which it must be silent.\n\n"
        "**5. Machine-enforceable commons.** Community licensing rules are compiled into a "
        "checker, so 'no AI training, no ads, share-alike' are executable, not aspirational.\n\n"
        "**6. Federated learning without a central model.** Nodes share themes and templates, "
        "never records — replication without a platform in the middle.\n\n"
        "**7. Right-sized inference.** Small model for language, deterministic rules for "
        "privacy, money and licensing. Only the part that needs language gets a model.\n\n"
        "**8. Energy as a first-class budget.** Every call is metered in joules against a "
        "cloud counterfactual, so a club can see the cost of its own automation."
    )

    st.markdown("##### Honest limits")
    st.markdown(
        "- Invitations and RSVPs are simulated; no messages leave this machine.\n"
        "- Energy and cost are models with stated assumptions, not measurements.\n"
        "- The 7B model is optional. Without LM Studio the text is scripted, and the UI says so.\n"
        f"- {len(club.members)} members is a demonstration of the mechanism, not evidence of product-community fit."
    )


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    st.set_page_config(page_title="GatherRhiza Labs · Human-Scale AI", page_icon="🎸",
                       layout="wide", initial_sidebar_state="expanded")
    load_styles()
    club = ensure_state()

    if club.kami.connected is None:
        club.kami.probe()

    page = sidebar(club)

    html(f'<header class="gr-masthead"><div class="gr-brand"><span class="gr-mark" '
         f'aria-hidden="true"></span>{APP_NAME}</div>'
         f'<div class="gr-small">{CLUB_NAME} · Flatbush, Brooklyn</div></header>')

    if page == "Start here":
        act_start(club)
    elif page.endswith("Club & consent"):
        act_club(club)
    elif page.endswith("Discover"):
        act_discover(club)
    elif page.endswith("Invite"):
        act_invite(club)
    elif page.endswith("Gather (human)"):
        act_gather(club)
    elif page.endswith("Reflect"):
        act_reflect(club)
    elif page.endswith("Commons"):
        act_commons(club)
    elif page.endswith("Impact"):
        act_impact(club)
    elif page.endswith("How it works"):
        act_how(club)


main()
