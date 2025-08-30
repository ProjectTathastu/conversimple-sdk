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
        max_reconnect_attempts: int = 5,
        reconnect_backoff: float = 1.0
    ):
        """
        Initialize WebSocket connection manager.
        
        Args:
            url: WebSocket URL for platform connection
            api_key: Customer authentication token
            customer_id: Customer identifier
            heartbeat_interval: Heartbeat interval in seconds
            max_reconnect_attempts: Maximum reconnection attempts
            reconnect_backoff: Base backoff time for reconnection
        """
        self.url = url
        self.api_key = api_key
        self.customer_id = customer_id
        self.heartbeat_interval = heartbeat_interval
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_backoff = reconnect_backoff
        
        # Connection state
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.connected = False
        self.reconnect_attempts = 0
        self.last_heartbeat = 0
        
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
            
            logger.info("WebSocket connected successfully")
            
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
            
        # Phoenix WebSocket message format
        message = [
            None,  # join_ref (not used for regular messages)
            self._next_message_ref(),
            f"customer:{self.customer_id}",
            event,
            payload
        ]
        
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
        
        # Phoenix channel join message
        message = [
            join_ref,
            message_ref, 
            f"customer:{self.customer_id}",
            "phx_join",
            {}
        ]
        
        logger.info(f"Joining channel: customer:{self.customer_id}")
        
        try:
            await self.websocket.send(json.dumps(message))
            
            # Wait for join confirmation
            response = await self.websocket.recv()
            response_data = json.loads(response)
            
            if (len(response_data) >= 5 and 
                response_data[3] == "phx_reply" and
                response_data[4].get("status") == "ok"):
                
                self.channel_joined = True
                logger.info("Channel joined successfully")
            else:
                raise Exception(f"Channel join failed: {response_data}")
                
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
            if len(message_data) >= 4:
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
            else:
                logger.warning(f"Invalid message format: {message_data}")
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode message: {e}")
        except Exception as e:
            logger.error(f"Message processing error: {e}")

    async def _handle_phoenix_reply(self, payload: Dict) -> None:
        """Handle Phoenix reply messages."""
        status = payload.get("status")
        
        if status == "ok":
            logger.debug("Phoenix operation successful")
        elif status == "error":
            reason = payload.get("response", {}).get("reason", "unknown")
            logger.error(f"Phoenix operation failed: {reason}")

    async def _handle_connection_error(self, error: Exception) -> None:
        """Handle connection errors with automatic reconnection."""
        logger.error(f"Connection error: {error}")
        
        self.connected = False
        self.channel_joined = False
        
        # Stop background tasks
        await self._stop_background_tasks()
        
        # Attempt reconnection if under retry limit
        if self.reconnect_attempts < self.max_reconnect_attempts:
            await self._attempt_reconnection()
        else:
            logger.error("Max reconnection attempts reached")
            if self.connection_handler:
                await self.connection_handler("error", error)

    async def _attempt_reconnection(self) -> None:
        """Attempt to reconnect with exponential backoff."""
        self.reconnect_attempts += 1
        backoff_time = self.reconnect_backoff * (2 ** (self.reconnect_attempts - 1))
        
        logger.info(f"Attempting reconnection {self.reconnect_attempts}/{self.max_reconnect_attempts} in {backoff_time}s")
        
        await asyncio.sleep(backoff_time)
        
        try:
            await self.connect()
        except Exception as e:
            logger.error(f"Reconnection attempt {self.reconnect_attempts} failed: {e}")
            
            if self.reconnect_attempts < self.max_reconnect_attempts:
                await self._attempt_reconnection()
            else:
                if self.connection_handler:
                    await self.connection_handler("error", e)

    def _next_message_ref(self) -> str:
        """Generate next message reference for Phoenix protocol."""
        self.message_ref_counter += 1
        return str(self.message_ref_counter)