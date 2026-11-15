"""Photon 2.0 transport: poll incoming iMessages, send text and PNG replies (photonhq-api client)."""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from photon_api import Photon
from photon_api.generated.models import (AttachmentContent, SendAttachmentContent, SendMessageRequest,
                                         SendTextContent, TextContent, UserSnapshot)
from photon_api.rpc_generated import (GetMessageInput, ListMessagesInput, SendMessageHeader, SendMessageInput,
                                      SendMessagePath, UploadAttachmentInput)

from .render import Out

log = logging.getLogger("gos.imessage")

SPLIT_WARNING = ("ANOTHER BOT ANSWERED FIRST (%s). A second copy of Grain of Salt is running on this Photon "
                 "project with its own game state, so players get a mix of two games. Run only one bot per project.")


class AnsweredElsewhere(Exception):
    """Photon already holds a different reply under this send's idempotency key: another copy of this bot, on the
    same Photon project, answered first. Only the other copy's reply reached the player."""


def reused_key(e: Exception) -> bool:
    return "idempotency-key was reused" in str(e).lower()


@dataclass(frozen=True)
class Incoming:
    id: str
    handle: str  # the human's phone/email
    text: str | None  # None for a photo or anything that isn't text
    space_id: str
    agent_id: str
    created_at: str


def iso_z(t: datetime) -> str:
    return t.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class PhotonIO:
    def __init__(self, api_key: str, project_id: str, agent_handle: str | None, state_path: Path):
        self.project, self.agent_handle = project_id, agent_handle
        self.client = Photon(headers={"Authorization": f"Bearer {api_key}"})
        self.state_path = state_path
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        # Start from "now" on first run: never answer old texts from before the bot existed.
        self.cursor: str = state.get("cursor") or iso_z(datetime.now(timezone.utc) - timedelta(seconds=5))
        self.seen: list[str] = state.get("seen", [])

    def close(self) -> None:
        self.client.close()

    def _save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps({"cursor": self.cursor, "seen": self.seen[-500:]}))

    def poll(self) -> list[Incoming]:
        query = {"createdSince": self.cursor, "direction": "received", "order": "asc", "pageSize": 100,
                 "platform": "imessage"}
        found: list[Incoming] = []
        while True:
            page = self.client.projects.list_messages(
                ListMessagesInput.model_validate({"path": {"id": self.project}, "query": query}))
            for item in page.items:
                m = item.root.root
                if m.id in self.seen:
                    continue
                self.seen.append(m.id)
                if m.createdAt > self.cursor:
                    self.cursor = m.createdAt
                if m.status != "received" or not isinstance(m.receivedBy, UserSnapshot):
                    continue
                sender, agent, space = m.sentBy.root, m.receivedBy.root, m.space.root
                if sender.kind != "human" or agent.kind != "agent" or sender.id == agent.id:
                    continue
                if getattr(space, "kind", "direct") != "direct":
                    continue
                content = m.content
                text = content.text if isinstance(content, TextContent) else None
                if isinstance(content, (TextContent, AttachmentContent)):
                    found.append(Incoming(m.id, sender.handle, text, space.id, agent.id, m.createdAt))
            token = page.nextPageToken
            if not isinstance(token, str):
                break
            query["pageToken"] = token
        self._save()
        return found

    def upload_png(self, png: bytes, idem: str) -> str:
        """POST /attachments takes multipart/related: a JSON part (contentType, sizeBytes) then the file bytes."""
        boundary = "gos-" + hashlib.sha256(png).hexdigest()[:24]
        meta = json.dumps({"contentType": "image/png", "sizeBytes": len(png), "filename": "post.png"})
        body = (f"--{boundary}\r\nContent-Type: application/json\r\n\r\n{meta}\r\n"
                f"--{boundary}\r\nContent-Type: image/png\r\n\r\n").encode() + png + f"\r\n--{boundary}--\r\n".encode()
        att = self.client.projects.upload_attachment(UploadAttachmentInput.model_validate({
            "body": body, "path": {"id": self.project},
            "headers": {"content-length": str(len(body)),
                        "content-type": f"multipart/related; boundary={boundary}",
                        "idempotency-key": idem}}))
        return att.id

    def wait_delivered(self, message_id: str | None, timeout_s: float = 8.0) -> None:
        """Sends are queued (202) and can overtake each other; wait for one to land before sending the next."""
        if not message_id:
            time.sleep(0.8)
            return
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            try:
                m = self.client.projects.get_message(GetMessageInput.model_validate(
                    {"path": {"id": self.project, "messageId": message_id}}))
                status = getattr(getattr(m, "root", m), "status", None) if m is not None else None
                if status in ("delivered", "failed"):
                    return
            except Exception:
                pass
            time.sleep(0.35)

    def send(self, space_id: str, agent_id: str, outs: list[Out], key: str) -> None:
        """Send replies in order, one landing before the next. `key` makes each send idempotent (no double texts).
        A failed image is skipped, never the rest of the reply."""
        outs = merge_texts(outs)
        for i, out in enumerate(outs):
            idem = f"gos:{key}:{i}"
            if out.image:
                try:
                    content = SendAttachmentContent(type="attachment",
                                                    attachmentId=self.upload_png(out.image, idem + ":upload"))
                except Exception:
                    log.exception("image upload failed; sending the rest without it")
                    continue
            elif out.text:
                content = SendTextContent(type="text", format="plain", text=out.text)
            else:
                continue
            try:
                sent = self.client.projects.send_message(SendMessageInput(
                    path=SendMessagePath(id=self.project),
                    headers=SendMessageHeader.model_validate({"idempotency-key": idem}),
                    body=SendMessageRequest(spaceId=space_id, senderId=agent_id, content=content)))
            except Exception as e:
                if reused_key(e):
                    raise AnsweredElsewhere(key) from e
                raise
            if i < len(outs) - 1:
                self.wait_delivered(getattr(getattr(sent, "root", sent), "id", None))


def merge_texts(outs: list[Out]) -> list[Out]:
    """Adjacent text bubbles -> one bubble (fewer sends, fewer chances to arrive out of order)."""
    merged: list[Out] = []
    for o in outs:
        if o.text and merged and merged[-1].text and not merged[-1].image:
            merged[-1] = Out(text=f"{merged[-1].text}\n\n{o.text}")
        elif o.text or o.image:
            merged.append(o)
    return merged


def nudge_key(handle: str, day: str) -> str:
    return "nudge:" + hashlib.sha256(f"{handle}:{day}".encode()).hexdigest()[:16]
