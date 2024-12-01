import json
from includes.WebSocketClient import WebSocketClient
from includes.PeerConnectionManager import PeerConnectionManager

from includes.classes.BetterLog import BetterLog
from includes.classes.clients import LocalClient, RemoteClient
from servers.includes.enums import MessageType

from aiortc import MediaStreamTrack, RTCSessionDescription, RTCIceCandidate

class SignalingHandler(BetterLog):
    def __init__(self, wsc: WebSocketClient, current_client:LocalClient, peer_connection_manager:PeerConnectionManager, logger):
        super().__init__(logger)

        self.wsc = wsc
        self.current_client = current_client
        self.peer_connection_manager = peer_connection_manager

    async def process_confirm_id(self):
        while True:
            await self.wsc.broadcast(MessageType.CONFIRM_ID, {"name": self.current_client.name})
            response = json.loads(await self.wsc.recv())
            self.log_info(f"Server response: {response}")

            if response["type"] == MessageType.CONFIRM_ID.value:
                self.current_client.id = response["payload"]["user"]["id"]
                self.log_info(f"Client ID confirmed: {self.current_client.id}")
                break

            self.log_warn(f"Unexpected message received while waiting for CONFIRM_ID: {response}")

        self.log_info(f"Success: CONFIRM_ID. Full user: {self.current_client.to_dict()}")

    async def handle_join(self, payload: dict, audio_track: MediaStreamTrack):
        # Handle new client joining
        remote_user = RemoteClient.from_payload(payload["user"])
        
        self.log_info(f"New peer joined: {remote_user.name} ({remote_user.id})")
        
        pc_remote, data_channel = await self.peer_connection_manager.create_pc(remote_user, audio_track)
        
        remote_user.peerConnection = pc_remote
        remote_user.data_channel = data_channel
        self.current_client.remotePeers[remote_user.id] = remote_user

        offer = await pc_remote.createOffer()
        await pc_remote.setLocalDescription(offer)
        self.log_info("Created offer for remote peer")

        # Send answer back
        await self.wsc.send_to(remote_user, MessageType.OFFER, payload={"sdp": offer.sdp})
        self.log_info(f"Sent offer to {remote_user.name}")

    async def handle_offer(self, payload, audio_track: MediaStreamTrack):
        remote_user = RemoteClient.from_payload(payload["user"])
        
        pc_remote, data_channel = await self.peer_connection_manager.create_pc(remote_user, audio_track)

        remote_user.peerConnection = pc_remote
        remote_user.data_channel = data_channel
        self.current_client.remotePeers[remote_user.id] = remote_user

        await remote_user.peerConnection.setRemoteDescription(RTCSessionDescription(sdp=payload["sdp"], type="offer"))

        answer = await remote_user.peerConnection.createAnswer()
        await remote_user.peerConnection.setLocalDescription(answer)
        self.log_info("Generated answer for incoming offer")

        # Send answer back
        await self.wsc.send_to(remote_user, MessageType.ANSWER, payload={"sdp": answer.sdp})
        self.log_info(f"Sent answer to {remote_user.name}")

    async def handle_answer(self, payload):
        remote_user = self.current_client.remotePeers.get(payload["user"]["id"])
        if remote_user and remote_user.peerConnection:
            await remote_user.peerConnection.setRemoteDescription(RTCSessionDescription(sdp=payload["sdp"], type="answer"))
            self.log_info(f"Answer processed for {remote_user.name}")

    async def handle_candidate(self,payload):
        # Handle ICE candidates
        candidate:dict = payload["candidate"]
        remote_user = self.current_client.remotePeers.get(payload["user"]["id"])

        if remote_user and remote_user.peerConnection:

            rtc_candidate = RTCIceCandidate(
                component=1,
                foundation=candidate["candidate"].split(" ")[0],
                ip=candidate["candidate"].split(" ")[4],
                port=int(candidate["candidate"].split(" ")[5]),
                priority=int(candidate["candidate"].split(" ")[3]),
                protocol=candidate["candidate"].split(" ")[2],
                type=candidate["candidate"].split(" ")[7],
                sdpMid=candidate.get("sdpMid"),
                sdpMLineIndex=candidate.get("sdpMLineIndex"),
            )

            await remote_user.peerConnection.addIceCandidate(rtc_candidate)
            self.log_info(f"ICE candidate added for {remote_user.name}")
