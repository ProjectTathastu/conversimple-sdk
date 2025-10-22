"""
Dispatcher for managing multiple Conversimple agents.

The dispatcher establishes a lightweight control-plane connection to the
platform, listens for `conversation_ready` events, and spins up dedicated
`ConversimpleAgent` instances for each conversation. Agents are discovered
dynamically by scanning the current working directory for classes that
inherit from `ConversimpleAgent` and expose an `agent_id` attribute.
"""

import asyncio
import contextlib
import importlib.util
import inspect
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Dict, Optional, Type

from .agent import ConversimpleAgent
from .connection import WebSocketConnection

logger = logging.getLogger(__name__)


@dataclass
class RegisteredAgent:
    """Information about a discovered agent implementation."""

    agent_id: str
    cls: Type[ConversimpleAgent]
    module_name: str
    file_path: Path


class AgentRegistry:
    """
    Discovers Conversimple agent classes within a directory.

    Any class that inherits from `ConversimpleAgent` and defines an `agent_id`
    attribute (or `AGENT_ID` constant) will be registered.
    """

    def __init__(self, search_path: Path):
        self.search_path = Path(search_path)
        self._agents: Dict[str, RegisteredAgent] = {}

    @property
    def agents(self) -> Dict[str, RegisteredAgent]:
        return dict(self._agents)

    def discover(self) -> None:
        """Scan the search path for agent classes."""
        if not self.search_path.exists():
            logger.warning("Agent registry search path does not exist: %s", self.search_path)
            return

        for python_file in self._iter_python_files(self.search_path):
            try:
                module = self._load_module(python_file)
            except Exception as exc:
                logger.exception("Failed to load module %s: %s", python_file, exc)
                continue

            self._register_module_agents(module, python_file)

    def get(self, agent_id: str) -> Optional[RegisteredAgent]:
        """Retrieve a registered agent by id."""
        return self._agents.get(agent_id)

    # Internal helpers -----------------------------------------------------

    def _iter_python_files(self, root: Path):
        """Yield .py files within the root directory (non-recursive)."""
        for entry in sorted(root.iterdir()):
            if entry.is_dir():
                # Allow packages with __init__.py by loading their __init__.
                init_file = entry / "__init__.py"
                if init_file.exists():
                    yield init_file
                continue

            if entry.suffix == ".py" and entry.name not in {"__init__.py"}:
                yield entry

    def _load_module(self, file_path: Path) -> ModuleType:
        """Dynamically import a Python module from a file."""
        module_name = f"dispatcher_auto.{file_path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Unable to create import spec for {file_path}")

        module = importlib.util.module_from_spec(spec)
        loader = spec.loader
        assert loader is not None  # For mypy
        sys.modules[module_name] = module
        loader.exec_module(module)
        return module

    def _register_module_agents(self, module: ModuleType, file_path: Path) -> None:
        """Inspect module for agent classes and register them."""
        for name, obj in inspect.getmembers(module, inspect.isclass):
            if not issubclass(obj, ConversimpleAgent) or obj is ConversimpleAgent:
                continue

            agent_id = getattr(obj, "agent_id", None) or getattr(obj, "AGENT_ID", None)
            if not agent_id:
                logger.debug(
                    "Skipping agent %s in %s: missing agent_id attribute",
                    name,
                    file_path,
                )
                continue

            if agent_id in self._agents:
                existing = self._agents[agent_id]
                logger.warning(
                    "Duplicate agent_id %s found in %s (already registered by %s)",
                    agent_id,
                    file_path,
                    existing.file_path,
                )
                continue

            self._agents[agent_id] = RegisteredAgent(
                agent_id=agent_id,
                cls=obj,
                module_name=module.__name__,
                file_path=file_path,
            )
            logger.info("Registered agent %s (%s) from %s", agent_id, name, file_path)


@dataclass
class AgentSession:
    """Runtime information about a spawned agent instance."""

    agent_id: str
    conversation_id: str
    agent: ConversimpleAgent
    task: asyncio.Task


class ConversimpleDispatcher:
    """
    Coordinates agent instances based on conversation lifecycle events.

    Usage:
        dispatcher = ConversimpleDispatcher(api_key, platform_url)
        await dispatcher.start()
    """

    def __init__(
        self,
        api_key: str,
        platform_url: str = "ws://localhost:4000/sdk/websocket",
        search_path: Optional[Path] = None,
        customer_id: Optional[str] = None,
    ):
        self.api_key = api_key
        self.platform_url = platform_url
        self.customer_id = customer_id
        self.search_path = search_path or Path.cwd()

        self.registry = AgentRegistry(self.search_path)
        self.registry.discover()

        self.connection = WebSocketConnection(
            url=self.platform_url,
            api_key=self.api_key,
            customer_id=self.customer_id or self._derive_customer_id(api_key),
            max_reconnect_attempts=None,
        )
        self.connection.set_message_handler(self._handle_platform_message)
        self.connection.set_connection_handler(self._handle_connection_event)

        self.active_sessions: Dict[str, AgentSession] = {}

    async def start(self) -> None:
        """Connect dispatcher control plane to the platform."""
        logger.info("Starting Conversimple dispatcher (search path: %s)", self.search_path)
        await self.connection.connect()

    async def stop(self) -> None:
        """Disconnect dispatcher and stop all managed agents."""
        logger.info("Stopping Conversimple dispatcher, shutting down %d sessions", len(self.active_sessions))

        stop_tasks = [self._stop_session(session.conversation_id) for session in list(self.active_sessions.values())]
        if stop_tasks:
            await asyncio.gather(*stop_tasks, return_exceptions=True)

        await self.connection.disconnect()

    # Internal handlers ----------------------------------------------------

    async def _handle_platform_message(self, event: str, payload: Dict) -> None:
        """Route incoming control-plane events."""
        if event == "conversation_ready":
            await self._handle_conversation_ready(payload)
        elif event == "conversation_lifecycle":
            await self._handle_conversation_lifecycle(payload)
        elif event == "connection_warning":
            logger.warning("Dispatcher received connection warning: %s", payload.get("message"))
        elif event == "config_update":
            logger.debug("Config update received (ignored by dispatcher)")
        else:
            logger.debug("Dispatcher ignoring event %s", event)

    async def _handle_conversation_ready(self, payload: Dict) -> None:
        """Spawn an agent for the provided conversation."""
        conversation_id = payload.get("conversation_id")
        agent_id = payload.get("agent_id")

        if not conversation_id:
            logger.warning("conversation_ready event missing conversation_id: %s", payload)
            return

        if not agent_id:
            logger.warning("conversation_ready %s missing agent_id; cannot dispatch", conversation_id)
            return

        if conversation_id in self.active_sessions:
            logger.info("Conversation %s already has an active agent", conversation_id)
            return

        registered = self.registry.get(agent_id)
        if not registered:
            logger.error("No agent registered for agent_id %s (conversation %s)", agent_id, conversation_id)
            return

        agent_instance = registered.cls(
            api_key=self.api_key,
            customer_id=self.customer_id,
            platform_url=self.platform_url,
        )

        task = asyncio.create_task(self._run_agent(agent_instance, conversation_id, agent_id, payload))
        self.active_sessions[conversation_id] = AgentSession(
            agent_id=agent_id,
            conversation_id=conversation_id,
            agent=agent_instance,
            task=task,
        )

    async def _handle_conversation_lifecycle(self, payload: Dict) -> None:
        """Stop agent when the conversation ends."""
        if payload.get("event") != "conversation_ended":
            return

        conversation_id = payload.get("conversation_id")
        if not conversation_id:
            return

        await self._stop_session(conversation_id)

    async def _run_agent(
        self,
        agent: ConversimpleAgent,
        conversation_id: str,
        agent_id: str,
        payload: Dict,
    ) -> None:
        """Start agent for a conversation and handle failures."""
        try:
            logger.info("Starting agent %s for conversation %s", agent_id, conversation_id)
            await agent.start(conversation_id=conversation_id)
            logger.info("Agent %s connected for conversation %s", agent_id, conversation_id)
        except Exception:
            logger.exception("Agent %s failed to start for conversation %s", agent_id, conversation_id)
            self.active_sessions.pop(conversation_id, None)

    async def _stop_session(self, conversation_id: str) -> None:
        """Stop and remove agent session for a conversation."""
        session = self.active_sessions.pop(conversation_id, None)
        if not session:
            return

        logger.info("Stopping agent %s for conversation %s", session.agent_id, conversation_id)

        try:
            await session.agent.stop()
        except Exception:
            logger.exception("Error stopping agent %s for conversation %s", session.agent_id, conversation_id)

        if not session.task.done():
            session.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await session.task

    async def _handle_connection_event(self, event: str, data=None) -> None:
        """Log dispatcher connection lifecycle events."""
        if event == "connected":
            logger.info("Dispatcher control connection established")
        elif event == "disconnected":
            logger.info("Dispatcher control connection closed")
        elif event == "permanent_error":
            logger.error("Dispatcher encountered permanent error: %s", data)
        elif event == "error":
            logger.error("Dispatcher connection error: %s", data)

    def _derive_customer_id(self, api_key: str) -> str:
        """Reuse agent hashing logic to derive customer id."""
        import hashlib

        return hashlib.md5(api_key.encode()).hexdigest()[:12]


async def run_dispatcher(api_key: str, platform_url: str, search_path: Optional[Path] = None) -> None:
    """Convenience helper to run dispatcher until interrupted."""
    dispatcher = ConversimpleDispatcher(api_key=api_key, platform_url=platform_url, search_path=search_path)
    await dispatcher.start()

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, stopping dispatcher")
    finally:
        await dispatcher.stop()
