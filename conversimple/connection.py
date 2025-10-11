"""
WebSocket connection manager for Conversimple platform.

Handles WebSocket communication with the platform including:
- Phoenix WebSocket connection with customer authentication
- Auto-reconnection with exponential backoff
- Message routing and protocol handling
- Heartbeat maintenance
"""

import asyncio
import json
import logging
import time
from typing import Dict, Optional, Callable, Any
from urllib.parse import urlencode

import websockets
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK

logger = logging.getLogger(__name__)


class ConnectionError(Exception):
    """Base exception for connection errors."""
    pass


class PermanentConnectionError(ConnectionError):
    """Raised for permanent connection failures that should not be retried."""
    def __init__(self, message: str, error_code: Optional[str] = None):
        super().__init__(message)
        self.error_code = error_code


class TransientConnectionError(ConnectionError):
    """Raised for transient connection failures that can be retried."""
    pass


class WebSocketConnection:
    """
    WebSocket connection manager for platform communication.
    
    Implements the Phoenix WebSocket protocol with customer authentication
    and automatic reconnection capabilities.
    """

    def __init__(
        self,
        url: str,
        api_key: str,
        customer_id: str,
        heartbeat_interval: int = 30,
        max_reconnect_attempts: Optional[int] = None,
        reconnect_backoff: float = 2.0,
        max_backoff: float = 300.0,
        total_retry_duration: Optional[float] = None,
        enable_circuit_breaker: bool = True
    ):
        """
        Initialize WebSocket connection manager with enhanced retry and circuit breaker.

        Args:
            url: WebSocket URL for platform connection
            api_key: Customer authentication token
            customer_id: Customer identifier
            heartbeat_interval: Heartbeat interval in seconds (default: 30)
            max_reconnect_attempts: Maximum reconnection attempts (None = infinite, default: None for production)
            reconnect_backoff: Base backoff multiplier for exponential backoff (default: 2.0)
            max_backoff: Maximum backoff time in seconds (default: 300s = 5min)
            total_retry_duration: Maximum total time to retry in seconds (None = no limit, default: None)
            enable_circuit_breaker: Enable circuit breaker for permanent failures (default: True)
        """
        self.url = url
        self.api_key = api_key
        self.customer_id = customer_id
        self.heartbeat_interval = heartbeat_interval
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_backoff = reconnect_backoff
        self.max_backoff = max_backoff
        self.total_retry_duration = total_retry_duration
        self.enable_circuit_breaker = enable_circuit_breaker
        
        # Connection state
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.connected = False
        self.reconnect_attempts = 0
        self.last_heartbeat = 0
        self.first_retry_time: Optional[float] = None
        self.circuit_breaker_open = False
        self.last_permanent_error: Optional[str] = None
        
        # Message handling
        self.message_handler: Optional[Callable[[str, Dict], None]] = None
        self.connection_handler: Optional[Callable[[str, Any], None]] = None
        
        # Background tasks
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.message_task: Optional[asyncio.Task] = None
        
        # Phoenix WebSocket protocol state
        self.channel_joined = False
        self.message_ref_counter = 0

    def set_message_handler(self, handler: Callable[[str, Dict], None]) -> None:
        """Set handler for incoming platform messages."""
        self.message_handler = handler

    def set_connection_handler(self, handler: Callable[[str, Any], None]) -> None:  
        """Set handler for connection events."""
        self.connection_handler = handler

    async def connect(self) -> None:
        """Connect to the platform WebSocket."""
        connection_params = {
            "customer_id": self.customer_id,
            "auth_token": self.api_key
        }
        
        connection_url = f"{self.url}?{urlencode(connection_params)}"
        
        logger.info(f"Connecting to platform: {self.customer_id}")
        
        try:
            self.websocket = await websockets.connect(
                connection_url,
                subprotocols=["phoenix-websocket"]
            )

            self.connected = True
            self.reconnect_attempts = 0
            self.first_retry_time = None

            logger.info("✅ WebSocket connected successfully")
            
            # Join customer channel
            await self._join_channel()
            
            # Start background tasks
            await self._start_background_tasks()
            
            # Notify connection handler
            if self.connection_handler:
                await self.connection_handler("connected")
                
        except Exception as e:
            logger.error(f"Failed to connect to platform: {e}")
            await self._handle_connection_error(e)

    async def disconnect(self) -> None:
        """Disconnect from the platform."""
        logger.info("Disconnecting from platform")
        
        self.connected = False
        
        # Cancel background tasks
        await self._stop_background_tasks()
        
        # Close WebSocket
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
            
        self.channel_joined = False
        
        # Notify connection handler
        if self.connection_handler:
            await self.connection_handler("disconnected")

    async def send_message(self, event: str, payload: Dict) -> None:
        """Send message to platform via Phoenix channel."""
        if not self.connected or not self.channel_joined:
            logger.warning(f"Cannot send message {event}: not connected")
            return
            
        # Phoenix WebSocket message format (as JSON object)
        message = {
            "join_ref": None,  # join_ref (not used for regular messages)
            "ref": self._next_message_ref(),
            "topic": f"customer:{self.customer_id}",
            "event": event,
            "payload": payload
        }
        
        try:
            await self.websocket.send(json.dumps(message))
            logger.debug(f"Sent message: {event}")
            
        except Exception as e:
            logger.error(f"Failed to send message {event}: {e}")
            await self._handle_connection_error(e)

    async def _join_channel(self) -> None:
        """Join the customer channel using Phoenix protocol."""
        join_ref = self._next_message_ref()
        message_ref = self._next_message_ref()
        
        # Phoenix channel join message (as JSON object)
        message = {
            "join_ref": join_ref,
            "ref": message_ref,
            "topic": f"customer:{self.customer_id}",
            "event": "phx_join",
            "payload": {}
        }
        
        logger.info(f"Joining channel: customer:{self.customer_id}")
        
        try:
            await self.websocket.send(json.dumps(message))
            
            # Wait for join confirmation
            response = await self.websocket.recv()
            response_data = json.loads(response)
            
            # Handle both array and object response formats
            if isinstance(response_data, list):
                # Phoenix sends responses as arrays: [join_ref, ref, topic, event, payload]
                if (len(response_data) >= 5 and 
                    response_data[3] == "phx_reply" and
                    response_data[4].get("status") == "ok"):
                    
                    self.channel_joined = True
                    logger.info("Channel joined successfully")
                else:
                    raise Exception(f"Channel join failed: {response_data}")
            elif isinstance(response_data, dict):
                # Handle object format if Phoenix ever changes
                if (response_data.get("event") == "phx_reply" and
                    response_data.get("payload", {}).get("status") == "ok"):
                    
                    self.channel_joined = True
                    logger.info("Channel joined successfully")
                else:
                    raise Exception(f"Channel join failed: {response_data}")
            else:
                raise Exception(f"Unexpected response format: {response_data}")
                
        except Exception as e:
            logger.error(f"Failed to join channel: {e}")
            raise

    async def _start_background_tasks(self) -> None:
        """Start background tasks for heartbeat and message handling."""
        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self.message_task = asyncio.create_task(self._message_loop())

    async def _stop_background_tasks(self) -> None:
        """Stop background tasks."""
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
                
        if self.message_task:
            self.message_task.cancel()
            try:
                await self.message_task
            except asyncio.CancelledError:
                pass

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeat messages to platform."""
        while self.connected:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                
                if self.connected and self.channel_joined:
                    await self.send_message("heartbeat", {})
                    self.last_heartbeat = time.time()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")

    async def _message_loop(self) -> None:
        """Handle incoming messages from platform.""" 
        while self.connected:
            try:
                message = await self.websocket.recv()
                await self._handle_message(message)
                
            except (ConnectionClosedError, ConnectionClosedOK):
                logger.info("WebSocket connection closed")
                break
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Message handling error: {e}")
                await self._handle_connection_error(e)

    async def _handle_message(self, raw_message: str) -> None:
        """Handle incoming WebSocket message."""
        try:
            message_data = json.loads(raw_message)
            
            # Phoenix WebSocket message format: [join_ref, ref, topic, event, payload]
            if isinstance(message_data, list) and len(message_data) >= 4:
                event = message_data[3]
                payload = message_data[4] if len(message_data) > 4 else {}
                
                # Handle Phoenix-specific events
                if event == "phx_reply":
                    await self._handle_phoenix_reply(payload)
                elif event == "phx_error":
                    logger.error(f"Phoenix error: {payload}")
                else:
                    # Forward platform events to message handler
                    if self.message_handler:
                        await self.message_handler(event, payload)
            elif isinstance(message_data, dict):
                # Handle object format messages (future compatibility)
                event = message_data.get("event")
                payload = message_data.get("payload", {})
                
                if event == "phx_reply":
                    await self._handle_phoenix_reply(payload)
                elif event == "phx_error":
                    logger.error(f"Phoenix error: {payload}")
                elif event and self.message_handler:
                    await self.message_handler(event, payload)
                else:
                    logger.debug(f"Received message without event: {message_data}")
            else:
                logger.warning(f"Invalid message format (expected array or object): {message_data}")
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode message: {e}")
        except Exception as e:
            logger.error(f"Message processing error: {e}")
            logger.debug(f"Raw message that caused error: {raw_message}")
            logger.debug(f"Parsed message data: {message_data if 'message_data' in locals() else 'Failed to parse'}")

    async def _handle_phoenix_reply(self, payload: Dict) -> None:
        """Handle Phoenix reply messages."""
        status = payload.get("status")
        
        if status == "ok":
            logger.debug("Phoenix operation successful")
        elif status == "error":
            reason = payload.get("response", {}).get("reason", "unknown")
            logger.error(f"Phoenix operation failed: {reason}")

    async def _handle_connection_error(self, error: Exception) -> None:
        """Handle connection errors with circuit breaker and intelligent retry logic."""
        logger.error(f"❌ Connection error: {error}")

        self.connected = False
        self.channel_joined = False

        # Stop background tasks
        await self._stop_background_tasks()

        # Classify error as permanent or transient
        is_permanent, error_code = self._classify_error(error)

        if is_permanent and self.enable_circuit_breaker:
            # Open circuit breaker for permanent failures
            self.circuit_breaker_open = True
            self.last_permanent_error = f"{error_code}: {str(error)}"
            logger.error(f"🚫 Circuit breaker opened: {self.last_permanent_error}")
            logger.error(f"🚫 Will NOT retry connection due to permanent failure")

            # Notify connection handler of permanent failure
            if self.connection_handler:
                await self.connection_handler("permanent_error", {
                    "error": error,
                    "error_code": error_code,
                    "message": str(error)
                })
            return

        # For transient errors, attempt reconnection
        if self._should_retry():
            await self._attempt_reconnection()
        else:
            logger.error(f"🚫 Reconnection abandoned after {self.reconnect_attempts} attempts")
            if self.connection_handler:
                await self.connection_handler("error", error)

    async def _attempt_reconnection(self) -> None:
        """Attempt to reconnect with exponential backoff and intelligent retry limits."""
        self.reconnect_attempts += 1

        # Track first retry time for total duration limit
        if self.first_retry_time is None:
            self.first_retry_time = time.time()

        # Calculate backoff with jitter
        backoff_time = self._calculate_backoff()

        # Log retry attempt with context
        attempt_info = f"{self.reconnect_attempts}"
        if self.max_reconnect_attempts is not None:
            attempt_info += f"/{self.max_reconnect_attempts}"

        elapsed = time.time() - self.first_retry_time if self.first_retry_time else 0
        duration_info = ""
        if self.total_retry_duration is not None:
            duration_info = f" (elapsed: {elapsed:.1f}s / {self.total_retry_duration}s)"

        logger.info(f"🔄 Attempting reconnection #{attempt_info} in {backoff_time:.1f}s{duration_info}")

        await asyncio.sleep(backoff_time)

        # Check if we should still retry (limits may have been reached during sleep)
        if not self._should_retry():
            logger.error(f"🚫 Retry limit reached, abandoning reconnection")
            if self.connection_handler:
                await self.connection_handler("error", Exception("Retry limit exceeded"))
            return

        try:
            await self.connect()
            # Reset retry state on successful connection
            self.reconnect_attempts = 0
            self.first_retry_time = None
            logger.info("✅ Reconnection successful, retry state reset")

        except Exception as e:
            logger.error(f"❌ Reconnection attempt #{self.reconnect_attempts} failed: {e}")

            # Classify the error
            is_permanent, error_code = self._classify_error(e)

            if is_permanent and self.enable_circuit_breaker:
                # Open circuit breaker and stop retrying
                self.circuit_breaker_open = True
                self.last_permanent_error = f"{error_code}: {str(e)}"
                logger.error(f"🚫 Circuit breaker opened during retry: {self.last_permanent_error}")

                if self.connection_handler:
                    await self.connection_handler("permanent_error", {
                        "error": e,
                        "error_code": error_code,
                        "message": str(e)
                    })
                return

            # For transient errors, check if we should continue retrying
            if self._should_retry():
                await self._attempt_reconnection()
            else:
                logger.error(f"🚫 Giving up after {self.reconnect_attempts} attempts")
                if self.connection_handler:
                    await self.connection_handler("error", e)

    def _next_message_ref(self) -> str:
        """Generate next message reference for Phoenix protocol."""
        self.message_ref_counter += 1
        return str(self.message_ref_counter)

    def _classify_error(self, error: Exception) -> tuple[bool, Optional[str]]:
        """
        Classify error as permanent or transient.

        Returns:
            Tuple of (is_permanent, error_code)
        """
        error_str = str(error).lower()
        error_type = type(error).__name__

        # Permanent errors that should not be retried
        permanent_patterns = [
            ("authentication_failed", "AUTH_FAILED"),
            ("invalid_credentials", "AUTH_FAILED"),
            ("customer_suspended", "CUSTOMER_SUSPENDED"),
            ("missing_credentials", "AUTH_FAILED"),
            ("invalid_api_key", "AUTH_FAILED"),
            ("unauthorized", "AUTH_FAILED"),
            ("forbidden", "FORBIDDEN"),
            ("not authorized", "AUTH_FAILED"),
        ]

        for pattern, code in permanent_patterns:
            if pattern in error_str:
                logger.error(f"🚫 Permanent connection error detected: {pattern} ({code})")
                return (True, code)

        # Check for HTTP status codes in exception
        if hasattr(error, 'status_code'):
            status = error.status_code
            if status in [401, 403]:  # Unauthorized, Forbidden
                logger.error(f"🚫 Permanent connection error: HTTP {status}")
                return (True, f"HTTP_{status}")
            elif status in [400]:  # Bad Request
                logger.error(f"🚫 Permanent connection error: HTTP {status}")
                return (True, f"HTTP_{status}")

        # Transient errors that can be retried
        logger.debug(f"🔄 Transient connection error detected: {error_type}")
        return (False, None)

    def _should_retry(self) -> bool:
        """
        Determine if connection should be retried based on circuit breaker and limits.

        Returns:
            True if retry should be attempted, False otherwise
        """
        # Check circuit breaker
        if self.enable_circuit_breaker and self.circuit_breaker_open:
            logger.error(f"🚫 Circuit breaker open due to: {self.last_permanent_error}")
            return False

        # Check max attempts limit
        if self.max_reconnect_attempts is not None:
            if self.reconnect_attempts >= self.max_reconnect_attempts:
                logger.error(f"🚫 Max reconnection attempts reached: {self.reconnect_attempts}/{self.max_reconnect_attempts}")
                return False

        # Check total retry duration limit
        if self.total_retry_duration is not None and self.first_retry_time is not None:
            elapsed = time.time() - self.first_retry_time
            if elapsed >= self.total_retry_duration:
                logger.error(f"🚫 Total retry duration exceeded: {elapsed:.1f}s / {self.total_retry_duration}s")
                return False

        return True

    def _calculate_backoff(self) -> float:
        """
        Calculate exponential backoff with jitter and max limit.

        Returns:
            Backoff time in seconds
        """
        if self.reconnect_attempts == 0:
            return 1.0

        # Exponential backoff: base * (backoff_multiplier ^ attempt)
        backoff = 1.0 * (self.reconnect_backoff ** (self.reconnect_attempts - 1))

        # Apply max backoff limit
        backoff = min(backoff, self.max_backoff)

        # Add jitter (±20%) to prevent thundering herd
        import random
        jitter = backoff * 0.2 * (random.random() * 2 - 1)
        backoff = backoff + jitter

        return max(1.0, backoff)  # Ensure minimum 1 second