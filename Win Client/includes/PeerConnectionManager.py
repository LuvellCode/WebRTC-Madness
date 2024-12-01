
from typing import Callable
from aiortc import MediaStreamTrack, RTCPeerConnection
from includes.classes.BetterLog import BetterLog
from includes.classes.clients import RemoteClient

class PeerConnectionManager(BetterLog):
    def __init__(self, logger, on_channel_open:Callable, on_channel_close:Callable, on_channel_message:Callable):
        super().__init__(logger)

        self.on_channel_open = on_channel_open
        self.on_channel_close = on_channel_close
        self.on_channel_message = on_channel_message
    
    async def create_pc(self, remote_user:RemoteClient, audio_track: MediaStreamTrack):
        self.log_debug("Creating Peer Connection..")
        pc_remote = RTCPeerConnection()
        pc_remote.addTrack(audio_track)
        pc_remote.on("iceconnectionstatechange", lambda: self.log_info(f"ICE state: {pc_remote.iceConnectionState}"))

        data_channel = pc_remote.createDataChannel("chat")
        self.log_info(f"Data Channel Created")


        @data_channel.on("open")
        async def on_open():
            self.log_info(f"Opening for user {remote_user.name} ({remote_user.id})...")
            await self.on_channel_open(data_channel, remote_user)
            self.log_info(f"Opened for user {remote_user.name} ({remote_user.id})")

        @data_channel.on("close")
        async def on_close():
            self.log_info(f"Closing for user {remote_user.name} ({remote_user.id}).")
            await self.on_channel_close(data_channel, remote_user)
            self.log_info(f"Closed for user {remote_user.name} ({remote_user.id})")

        @data_channel.on("message")
        async def on_message(message):
            self.log_info(f"Message Processing from {remote_user.name}: {message}")
            await self.on_channel_message(data_channel, remote_user, message)
            self.log_info(f"Message Processed for {remote_user.name}")

        return pc_remote, data_channel