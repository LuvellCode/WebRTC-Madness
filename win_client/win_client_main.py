
import os
import ssl
import sys
import json
import asyncio
import logging

from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack, RTCIceCandidate, RTCDataChannel
import websockets

# Adding root reference
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))


from config import SIGNALING_SERVER
from servers.logging_config import get_logger
from servers.includes.enums import MessageType

from includes.audio_tracks import MicrophoneAudioTrack, LoopbackAudioTrack
from includes.MediaController import MediaController, MediaAction
from includes.SignalingHandler import SignalingHandler
from includes.PeerConnectionManager import PeerConnectionManager

from includes.classes.BetterLog import BetterLog
from includes.classes.clients import LocalClient, RemoteClient
from includes.WebSocketClient import WebSocketClient



class SignalingClient(LocalClient):

    def __init__(self, name:str, logger, media_controller:MediaController, wsc: WebSocketClient, audio_track:MediaStreamTrack):
        LocalClient.__init__(self, name=name)
        BetterLog.__init__(self, logger=logger)

        self.media_controller = media_controller
        self.background_np_update = None
        self.wsc = wsc
        self.audio_track = audio_track

    async def initialize(self):
        await self.media_controller.initialize()
        await self.media_controller.get_now_playing()

        self.init_background_task()
        
        return self.background_np_update

    def init_background_task(self):
        self.background_np_update = asyncio.create_task(self.media_controller.on_np_update(self.on_now_playing_update))

    def on_now_playing_update(self, media_info:dict):
        self.broadcast_to_channels({"message":"update: NOW_PLAYING track", "payload": media_info})

    def broadcast_to_channels(self, message):
        self.log_info(f"Broadcasting message to all remote users: {message}")

        for user in self.remotePeers.values():
            self.send_to_user_channel(user, message)
    
    def send_to_user_channel(self, user:RemoteClient, message):
        message = json.dumps(message)

        dc = self.remotePeers[user.id].data_channel

        if dc is not None:
            dc.send(message)

    """
    Channel handlers
    """

    async def on_channel_open(self, data_channel:RTCDataChannel, remote_user: RemoteClient):
        # data_channels[remote_user.id] = data_channel  # removed. Reason: we already add the data_channel to remote_user during handling offers
        data_channel.send("Hey! it's me, uber Windows Client")

    async def on_channel_close(self, data_channel:RTCDataChannel, remote_user: RemoteClient):
        self.remotePeers[remote_user.id].data_channel = None

    async def on_channel_message(self, data_channel:RTCDataChannel, remote_user: RemoteClient, message: str):
        """
        BOT functionality: play/pause the music, etc.
        """
        try:
            action = MediaAction(message)
        except:
            self.log_warn("Couldn't convert the msg to MediaAction")
            return
        
        data_channel.send(f"Handling the Media Action {action.name}")
        result = await self.media_controller._perform_action_async(action)

        if action == MediaAction.NOW_PLAYING:
            data_channel.send(json.dumps(result))

    """
    Main RUN
    """
    async def run(self):
        async with self.wsc.connect() as websocket:
            self.wsc.websocket = websocket

            self.log_debug(self.__dict__)
            peer_connection_manager = PeerConnectionManager(self.logger, self.on_channel_open, self.on_channel_close, self.on_channel_message)
            signaling_handler = SignalingHandler(self.wsc, self, peer_connection_manager, self.logger)

            await signaling_handler.process_confirm_id()

            # When ID is confirmed, we send JOIN request to all peers (send to Signaling Server, which will broadcast it to everyone)
            await self.wsc.broadcast(MessageType.JOIN, {})

            # Start signaling loop
            async for message in websocket:
                # We don't need to validate messages from server since they are trusted.
                message:dict = json.loads(message)
                self.log_debug(f"Received signaling message: {message}")

                message_type = MessageType(message["type"])
                payload = message.get("payload", {})

                match message_type:
                    case MessageType.JOIN:
                        await signaling_handler.handle_join(payload, self.audio_track)
                    case MessageType.OFFER:
                        await signaling_handler.handle_offer(payload, self.audio_track)
                    case MessageType.ANSWER:
                        await signaling_handler.handle_answer(payload)
                    case MessageType.CANDIDATE:
                        await signaling_handler.handle_candidate(payload)
                    case _:
                        self.log_warn(f"Unhandled message type: {message_type}")
            self.log_info("WebRTC connection closed")

async def main():

    logger = get_logger(__name__, logging.DEBUG)

    ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    ssl_context.load_verify_locations("server.crt")
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_REQUIRED


    websocket_client = WebSocketClient(SIGNALING_SERVER, ssl_context, logger)
    media_controller = MediaController(logger)
    audio_track = LoopbackAudioTrack(logger)

    signaling_client = SignalingClient(name="<b>Win Client</b>",logger=logger, media_controller=media_controller, wsc=websocket_client, audio_track=audio_track)
    await signaling_client.initialize()
    
    try:
        await signaling_client.run()
    finally:
        # Halt the task if it still works
        signaling_client.background_np_update.cancel()
        await signaling_client.background_np_update

if __name__ == "__main__":

    asyncio.run(main())