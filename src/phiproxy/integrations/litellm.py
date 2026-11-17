"""LiteLLM proxy guardrail: mask requests before they leave, unmask replies.

config.yaml::

    guardrails:
      - guardrail_name: phiproxy
        litellm_params:
          guardrail: phiproxy.integrations.litellm.PhiproxyGuardrail
          mode: [pre_call, post_call]
          default_on: true
          redis_url: os.environ/PHIPROXY_REDIS_URL   # optional; in-memory if unset
          date_mode: token                          # or "shift"
          allow: ["Harborview Reproductive Centre", "613-555-0100", "@harborview.example.org"]
          staff: ["Jocelyn Paré", "Will Barnes"]    # see phiproxy.staff

    litellm_settings:
      turn_off_message_logging: true   # keep unmasked replies out of LiteLLM logs

Per request, clients may send (in ``metadata``):
  * ``session_id`` - keeps tokens stable across turns of one conversation
  * ``phiproxy_known`` - identifiers you already hold, e.g.
    ``{"names": ["Sarah Chen"], "phones": ["416-555-0142"], "dates_of_birth": ["1990-03-05"]}``.
    It is removed from the request before anything is forwarded.

Fail closed: if masking fails, or the request holds images/audio/files the
policy does not allow, the request is rejected and nothing is sent.
Clients cannot switch this guardrail off through request metadata unless
``allow_client_opt_out: true`` is configured.
"""

from __future__ import annotations

import importlib
import inspect
import logging
import os
import uuid
from typing import Any, AsyncGenerator, Callable, ClassVar, Optional

from litellm.integrations.custom_guardrail import CustomGuardrail, get_session_id_from_request_data
from litellm.types.guardrails import GuardrailEventHooks

from ..detectors.known import KnownEntities
from ..masker import Masker, PhiproxyError, Policy, StreamUnmasker
from ..vault import InMemoryVault, RedisVault

log = logging.getLogger("phiproxy")

# Request fields that carry conversation content, across the routes LiteLLM serves
# (chat/completions, /v1/messages, /v1/responses, text completions).
_CONTENT_KEYS = ("messages", "system", "input", "instructions", "prompt")
_SESSION_KEY = "phiproxy_session_id"
_KNOWN_KEY = "phiproxy_known"


def _load_callable(path: str) -> Callable[..., Any]:
    module, _, attr = path.replace(":", ".").rpartition(".")
    return getattr(importlib.import_module(module), attr)


def _as_list(v: Any) -> tuple[str, ...]:
    """A YAML list, or one comma-separated string (e.g. from an environment variable)."""
    if not v:
        return ()
    if isinstance(v, str):
        return tuple(x.strip() for x in v.split(",") if x.strip())
    return tuple(str(x) for x in v)


def _as_bool(v: Any) -> bool:
    return v if isinstance(v, bool) else str(v).strip().lower() in ("1", "true", "yes", "on")


class PhiproxyGuardrail(CustomGuardrail):
    use_native_lifecycle_hooks: ClassVar[bool] = True

    def __init__(
        self,
        redis_url: Optional[str] = None,
        date_mode: str = "token",
        day_first: bool = False,
        allow_images: bool = False,
        allow_audio: bool = False,
        allow_files: bool = False,
        mask_provider_names: bool = False,
        known_entities_provider: Optional[str] = None,
        allow_client_opt_out: bool = False,
        allow: Any = None,
        staff: Any = None,
        staff_need_context: bool = True,
        vault_ttl_seconds: int = 24 * 3600,
        masker: Optional[Masker] = None,
        **kwargs: Any,
    ):
        kwargs.setdefault(
            "supported_event_hooks", [GuardrailEventHooks.pre_call, GuardrailEventHooks.post_call]
        )
        super().__init__(**kwargs)
        if masker is None:
            policy = Policy(
                date_mode="shift" if date_mode == "shift" else "token",
                day_first=_as_bool(day_first),
                allow_images=_as_bool(allow_images),
                allow_audio=_as_bool(allow_audio),
                allow_files=_as_bool(allow_files),
                allow=_as_list(allow),
                staff=_as_list(staff),
                staff_need_context=_as_bool(staff_need_context),
            )
            if _as_bool(mask_provider_names):
                policy.disabled_types = set()
            redis_url = redis_url or os.environ.get("PHIPROXY_REDIS_URL")
            vault = (
                RedisVault(url=redis_url, ttl_seconds=int(vault_ttl_seconds))
                if redis_url
                else InMemoryVault(ttl_seconds=float(vault_ttl_seconds))
            )
            masker = Masker(vault=vault, policy=policy)
        self.masker = masker
        self.allow_client_opt_out = _as_bool(allow_client_opt_out)
        self._known_provider = _load_callable(known_entities_provider) if known_entities_provider else None
        self._warned_raw_stream = False

    # ----------------------------------------------------------------- helpers
    def _runs_on(self, data: dict, event: GuardrailEventHooks) -> bool:
        if self.allow_client_opt_out:
            return bool(self.should_run_guardrail(data=data, event_type=event))
        hooks = self.event_hook
        if hooks is None:
            return True
        if isinstance(hooks, (list, tuple, set)):
            return any(str(getattr(h, "value", h)) == event.value for h in hooks)
        if isinstance(hooks, str) or hasattr(hooks, "value"):
            return str(getattr(hooks, "value", hooks)) == event.value
        return bool(self.should_run_guardrail(data=data, event_type=event))  # Mode objects

    @staticmethod
    def _metadata(data: dict) -> dict:
        md = data.get("metadata")
        if not isinstance(md, dict):
            md = data["metadata"] = {}
        return md

    def _session_id(self, data: dict) -> str:
        md = self._metadata(data)
        sid = md.get(_SESSION_KEY) or get_session_id_from_request_data(data)
        if not sid:
            sid = f"req-{uuid.uuid4().hex}"  # no session given: tokens are per request
        md[_SESSION_KEY] = str(sid)
        return str(sid)

    async def _known(self, data: dict, session_id: str) -> Optional[KnownEntities]:
        found: list[KnownEntities] = []
        for container in (data.get("metadata"), data.get("litellm_metadata")):
            if isinstance(container, dict) and _KNOWN_KEY in container:
                raw = container.pop(_KNOWN_KEY)  # never forward identifiers we were handed
                if isinstance(raw, dict):
                    found.append(KnownEntities.from_dict(raw))
        if self._known_provider is not None:
            res = self._known_provider(session_id=session_id, metadata=dict(self._metadata(data)))
            if inspect.isawaitable(res):
                res = await res
            if isinstance(res, dict):
                res = KnownEntities.from_dict(res)
            if isinstance(res, KnownEntities):
                found.append(res)
        if not found:
            return None
        merged = KnownEntities()
        for k in found:
            merged = KnownEntities(
                names=[*merged.names, *k.names],
                phones=[*merged.phones, *k.phones],
                emails=[*merged.emails, *k.emails],
                dates_of_birth=[*merged.dates_of_birth, *k.dates_of_birth],
                identifiers=[*merged.identifiers, *k.identifiers],
                addresses=[*merged.addresses, *k.addresses],
                other={**merged.other, **k.other},
            )
        return merged

    @staticmethod
    def _reject(message: str) -> Exception:
        try:
            from fastapi import HTTPException  # present in the LiteLLM proxy

            return HTTPException(status_code=400, detail={"error": message, "guardrail": "phiproxy"})
        except ImportError:  # pragma: no cover
            return ValueError(message)

    # ------------------------------------------------------------------- hooks
    async def async_pre_call_hook(self, user_api_key_dict: Any, cache: Any, data: dict, call_type: Any) -> dict:
        if not self._runs_on(data, GuardrailEventHooks.pre_call):
            return data
        session_id = self._session_id(data)
        try:
            known = await self._known(data, session_id)
            for key in _CONTENT_KEYS:
                if key in data and data[key] is not None:
                    data[key] = self.masker.mask_payload(data[key], session_id, known)
        except PhiproxyError as exc:
            raise self._reject(f"phiproxy blocked the request: {exc}") from None
        except Exception as exc:  # fail closed on anything unexpected
            raise self._reject(f"phiproxy could not mask the request ({type(exc).__name__})") from None
        return data

    async def async_post_call_success_hook(self, data: dict, user_api_key_dict: Any, response: Any) -> Any:
        if not self._runs_on(data, GuardrailEventHooks.post_call):
            return response
        session_id = (data.get("metadata") or {}).get(_SESSION_KEY)
        if not session_id:
            return response
        return self._unmask_response(response, session_id)

    async def async_post_call_streaming_iterator_hook(
        self, user_api_key_dict: Any, response: Any, request_data: dict
    ) -> AsyncGenerator[Any, None]:
        session_id = ((request_data or {}).get("metadata") or {}).get(_SESSION_KEY)
        if not session_id or not self._runs_on(request_data or {}, GuardrailEventHooks.post_call):
            async for chunk in response:
                yield chunk
            return

        unmaskers: dict[tuple, StreamUnmasker] = {}

        def um(key: tuple) -> StreamUnmasker:
            if key not in unmaskers:
                unmaskers[key] = self.masker.stream_unmasker(session_id)
            return unmaskers[key]

        pending = None
        async for chunk in response:
            if isinstance(chunk, (bytes, str)):
                if not self._warned_raw_stream:
                    log.warning("phiproxy: raw SSE stream passed through without unmasking")
                    self._warned_raw_stream = True
                if pending is not None:
                    yield pending
                    pending = None
                yield chunk
                continue
            for choice in getattr(chunk, "choices", None) or []:
                delta = getattr(choice, "delta", None)
                if delta is None:
                    continue
                idx = getattr(choice, "index", 0) or 0
                content = getattr(delta, "content", None)
                if isinstance(content, str):
                    delta.content = um((idx, "content")).feed(content)
                for tc in getattr(delta, "tool_calls", None) or []:
                    fn = getattr(tc, "function", None)
                    args = getattr(fn, "arguments", None) if fn is not None else None
                    if isinstance(args, str):
                        fn.arguments = um((idx, "tool", getattr(tc, "index", 0) or 0)).feed(args)
            if pending is not None:
                yield pending
            pending = chunk

        if pending is not None:
            for (idx, kind, *rest), u in unmaskers.items():
                tail = u.flush()
                if not tail:
                    continue
                choice = next((c for c in (getattr(pending, "choices", None) or [])
                               if (getattr(c, "index", 0) or 0) == idx), None)
                delta = getattr(choice, "delta", None) if choice is not None else None
                if delta is None:
                    continue
                if kind == "content":
                    delta.content = (getattr(delta, "content", None) or "") + tail
                else:
                    for tc in getattr(delta, "tool_calls", None) or []:
                        if (getattr(tc, "index", 0) or 0) == rest[0] and getattr(tc, "function", None):
                            tc.function.arguments = (tc.function.arguments or "") + tail
                            break
                    else:
                        log.warning("phiproxy: could not place the last tool-call argument fragment")
            yield pending

    # ------------------------------------------------------------- unmasking
    def _unmask_response(self, response: Any, session_id: str) -> Any:
        if isinstance(response, dict):
            return self.masker.unmask_payload(response, session_id)
        # OpenAI-shaped ModelResponse
        for choice in getattr(response, "choices", None) or []:
            msg = getattr(choice, "message", None)
            if msg is None:
                continue
            for attr in ("content", "reasoning_content"):
                val = getattr(msg, attr, None)
                if isinstance(val, str):
                    setattr(msg, attr, self.masker.unmask(val, session_id))
            for tc in getattr(msg, "tool_calls", None) or []:
                fn = getattr(tc, "function", None)
                if fn is not None and isinstance(getattr(fn, "arguments", None), str):
                    fn.arguments = self.masker.unmask_payload({"arguments": fn.arguments}, session_id)["arguments"]
        # Anthropic-shaped (content blocks) or Responses API (output items)
        for attr in ("content", "output"):
            val = getattr(response, attr, None)
            if isinstance(val, list):
                try:
                    setattr(response, attr, self._unmask_objects(val, session_id))
                except (AttributeError, TypeError):
                    pass
        return response

    def _unmask_objects(self, items: list, session_id: str) -> list:
        out = []
        for it in items:
            if isinstance(it, (dict, list, str)):
                out.append(self.masker.unmask_payload(it, session_id))
                continue
            for attr in ("text", "input", "arguments"):
                val = getattr(it, attr, None)
                if isinstance(val, (str, dict, list)):
                    setattr(it, attr, self.masker.unmask_payload(val, session_id))
            inner = getattr(it, "content", None)
            if isinstance(inner, list):
                setattr(it, "content", self._unmask_objects(inner, session_id))
            out.append(it)
        return out
