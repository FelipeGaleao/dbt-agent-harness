"""Google ADK Runtime Engine for executing agent sessions."""

from __future__ import annotations

import os
from typing import Generator, List, Optional
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from harness.adapters.google_adk import create_adk_agent
from harness.core.config import HarnessConfig, get_config
from harness.core.contracts import SessionStatus
from harness.sessions.store import SQLiteSessionStore


class ADKRuntime:
    """Manages agent execution, message streaming, and session coordination via Google ADK."""

    def __init__(
        self,
        session_id: str,
        user_id: str = "default_user",
        model: str = "gemini-2.5-flash",
        config: Optional[HarnessConfig] = None,
    ) -> None:
        self.config = config or get_config()
        self.session_id = session_id
        self.user_id = user_id
        self.model = model

        # Ensure harness persistent session exists
        self.session_store = SQLiteSessionStore(self.config)
        session = self.session_store.get_session(session_id)
        if not session:
            self.session_store.create_session(
                session_id=session_id,
                objective="Interactive dbt engineering session via Google ADK Runtime",
            )

        # Build agent and bind tools
        self.agent, self.registry, self.services = create_adk_agent(
            session_id=session_id,
            model=model,
            config=self.config,
        )

        # ADK conversational session service
        self.session_service = InMemorySessionService()

        # Runner
        self.runner = Runner(
            agent=self.agent,
            app_name="dbt_agent_harness",
            session_service=self.session_service,
            auto_create_session=True,
        )

    def send_message(self, text: str) -> Generator[str, None, None]:
        """
        Sends a user prompt to the ADK Runner and yields text responses / tool call updates.
        Updates harness session status accordingly.
        """
        session = self.session_store.get_session(self.session_id)
        if session:
            session.status = SessionStatus.IN_PROGRESS
            self.session_store.save_session(session)

        content = types.Content(
            role="user",
            parts=[types.Part.from_text(text=text)],
        )

        try:
            events = self.runner.run(
                user_id=self.user_id,
                session_id=self.session_id,
                new_message=content,
            )

            for event in events:
                # Event might contain text, tool calls, or status updates
                if hasattr(event, "text") and event.text:
                    yield event.text
                elif hasattr(event, "content") and event.content:
                    for part in getattr(event.content, "parts", []):
                        if getattr(part, "text", None):
                            yield part.text
                        elif getattr(part, "function_call", None):
                            fc = part.function_call
                            yield f"\n[ADK Tool Call: {fc.name}({fc.args})]\n"

        except Exception as e:
            err_msg = f"ADK Runtime Execution Error: {e}"
            if session:
                session.outstanding_errors.append(err_msg)
                self.session_store.save_session(session)
            yield f"\n❌ {err_msg}\n"

