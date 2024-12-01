import json
import logging
import ssl

import websockets

from servers.includes.enums import MessageType
from includes.classes.BetterLog import BetterLog
from includes.classes.clients import RemoteClient


class WebSocketClient(BetterLog):
    def __init__(self, signaling_server: str, ssl_context: ssl.SSLContext, logger:logging.Logger):
        super().__init__(logger)

        self.signaling_server = signaling_server
        self.ssl_context = ssl_context
        self.websocket = None

    def connect(self):
        self.log_info(f"Connecting to signaling server {self.signaling_server}")
        conn = websockets.connect(self.signaling_server, ssl=self.ssl_context)
        self.log_info("Connected.")
        return conn

    async def close(self):
        if self.websocket:
            await self.websocket.close()
            self.log_info("Connection closed.")

    """
    Messaging
    """

    async def _send_message(self, message:dict):
        self.log_debug(f"Sending message: {message}")
        await self.websocket.send(json.dumps(message))

    async def broadcast(self, message_type: MessageType, payload: dict):
        message = {"type": message_type.value, "payload": payload}
        await self._send_message(message)

    async def send_to(self, target: RemoteClient, message_type: MessageType, payload):
        message = {"type": message_type.value, "target": target.to_dict(), "payload": payload}
        await self._send_message(message)

    async def recv(self):
        return await self.websocket.recv()
       