import fractions
import os
import ssl
import sys
import json
import asyncio
import logging
import pyaudiowpatch as pyaudio
from dataclasses import dataclass, field
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack, RTCIceCandidate
import websockets

import numpy as np
from av import AudioFrame

# Adding root reference
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

from config import SIGNALING_SERVER
from servers.logging_config import get_logger
from servers.includes.enums import MessageType


class CustomAudioTrack(MediaStreamTrack):
    """
    By Default: Uses Microphone
    """
    kind = "audio"

    def __init__(self, rate=48000, channels=2, frames_per_buffer=960):
        super().__init__()
        self.rate = rate
        self.channels = channels
        self.frames_per_buffer = frames_per_buffer

        self._timestamp = 0

        self.pa = pyaudio.PyAudio()

        self.stream_parameters = {
            "format": pyaudio.paInt16,
            "channels": self.channels,
            "rate": self.rate,
            "input": True,
            "frames_per_buffer": self.frames_per_buffer
        }

        self.open_stream()

    def open_stream(self):
        logger.debug(f"Opening the stream with parameters: {self.stream_parameters}")
        self.stream = self.pa.open(**self.stream_parameters)

    def stream_read(self):
        data = np.frombuffer(self.stream.read(self.frames_per_buffer), 
                             dtype=np.int16)
        data = data.reshape(-1, 1).T
        return data

    async def recv(self):
        data = self.stream_read()

        self._timestamp += self.frames_per_buffer
        pts = self._timestamp
        time_base = fractions.Fraction(1, self.rate)
        
        audio_frame = AudioFrame.from_ndarray(data, format='s16', layout='stereo')
        audio_frame.sample_rate = self.rate
        audio_frame.pts = pts
        audio_frame.time_base = time_base

        return audio_frame

    def __del__(self):
        self.stream.stop_stream()
        self.stream.close()
        self.pa.terminate()

class MicrophoneAudioTrack(CustomAudioTrack):
    pass

class LoopbackAudioTrack(CustomAudioTrack):
    def open_stream(self):

        device_index = self.pa.get_default_wasapi_loopback().get("index")
        device = self.pa.get_device_info_by_index(device_index)
        logger.debug(f"Found Loopback device: {device}")

        self.stream_parameters["input_device_index"] = device_index
        return super().open_stream()

@dataclass
class WinClient:
    name: str
    id: int = None
    remotePeers: dict = field(default_factory=dict)
    peerConnection: RTCPeerConnection = None

    def to_dict(self) -> dict:
        return {"name": self.name, "id": self.id}

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @staticmethod
    def from_payload(user_dict):
        return WinClient(name=user_dict["name"], id=user_dict["id"])


logger = get_logger(__name__, logging.DEBUG)
win_streamer = WinClient(name="<b>Win Client</b>")


async def send_message(websocket, message_type: MessageType, payload):
        message = {"type": message_type.value, "payload": payload}
        
        logger.debug(f"[WebSocket] Broadcasting message {message_type.value}: {message}")
        await websocket.send(json.dumps(message))

async def send_message_to(websocket, message_type: MessageType, target: WinClient, payload):
    message = {"type": message_type.value, "target": target.to_dict(), "payload": payload}

    logger.debug(f"[WebSocket] Sending direct message {message_type.value} to {target.name}: {message}")
    await websocket.send(json.dumps(message))


############


async def process_confirm_id(websocket):
    while True:
        await send_message(websocket, MessageType.CONFIRM_ID, {"name": win_streamer.name})
        response = json.loads(await websocket.recv())
        logger.info(f"Server response: {response}")

        if response["type"] == MessageType.CONFIRM_ID.value:
            win_streamer.id = response["payload"]["user"]["id"]
            logger.info(f"Client ID confirmed: {win_streamer.id}")
            break

        logger.warning(f"Unexpected message received while waiting for CONFIRM_ID: {response}")

    logger.info(f"Success: CONFIRM_ID. Full user: {win_streamer.to_dict()}")
    
async def create_pc(remote_user:WinClient, audio_track: MediaStreamTrack):
    pc_remote = RTCPeerConnection()
    pc_remote.addTrack(audio_track)
    pc_remote.on("iceconnectionstatechange", lambda: logger.info(f"ICE state: {pc_remote.iceConnectionState}"))

    # Створюємо DataChannel
    data_channel = pc_remote.createDataChannel("chat")
    logger.info("DataChannel created")

    # Налаштування подій DataChannel
    @data_channel.on("open")
    def on_open():
        data_channel.send("Hey! it's me, uber Windows Client")
        logger.info("DataChannel is open")

    @data_channel.on("close")
    def on_close():
        logger.info("DataChannel is closed")

    @data_channel.on("message")
    def on_message(message):
        logger.debug(f"DataChannel received message from {remote_user.name}: {message}")

    return pc_remote

async def handle_join(websocket, payload: dict, audio_track: MediaStreamTrack):
    # Handle new client joining
    remote_user = WinClient.from_payload(payload["user"])
    win_streamer.remotePeers[remote_user.id] = remote_user
    logger.info(f"New peer joined: {remote_user.name} ({remote_user.id})")
    
    pc_remote = await create_pc(remote_user, audio_track)
    
    win_streamer.remotePeers[remote_user.id].peerConnection = pc_remote

    offer = await pc_remote.createOffer()
    await pc_remote.setLocalDescription(offer)
    logger.info("Created offer for remote peer")

    await send_message_to(websocket, MessageType.OFFER, target=remote_user, payload={"sdp": offer.sdp})
    logger.info(f"Sent offer to {remote_user.name}")

async def handle_offer(websocket, payload, audio_track: MediaStreamTrack):
    remote_user = WinClient.from_payload(payload["user"])
    
    remote_user.peerConnection = await create_pc(remote_user, audio_track)

    win_streamer.remotePeers[remote_user.id] = remote_user
    await remote_user.peerConnection.setRemoteDescription(RTCSessionDescription(sdp=payload["sdp"], type="offer"))

    answer = await remote_user.peerConnection.createAnswer()
    await remote_user.peerConnection.setLocalDescription(answer)
    logger.info("Generated answer for incoming offer")

    # Send answer back
    await send_message_to(websocket, MessageType.ANSWER, target=remote_user, payload={"sdp": answer.sdp})
    logger.info(f"Sent answer to {remote_user.name}")

async def handle_answer(payload):
    remote_user = win_streamer.remotePeers.get(payload["user"]["id"])
    if remote_user and remote_user.peerConnection:
        await remote_user.peerConnection.setRemoteDescription(RTCSessionDescription(sdp=payload["sdp"], type="answer"))
        logger.info(f"Answer processed for {remote_user.name}")

async def handle_candidate(payload):
    # Handle ICE candidates
    candidate = payload["candidate"]
    remote_user = win_streamer.remotePeers.get(payload["user"]["id"])

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
        logger.info(f"ICE candidate added for {remote_user.name}")

###########

async def signaling_client():

    ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    ssl_context.load_verify_locations("server.crt")
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_REQUIRED

    async with websockets.connect(SIGNALING_SERVER, ssl=ssl_context) as websocket:
        logger.info("Connected to signaling server")

        # Confirm client identity
        await process_confirm_id(websocket)
        
        audio_track = LoopbackAudioTrack()
        logger.info("Audio track created")

        await send_message(websocket, MessageType.JOIN, {})

        # Start signaling loop
        async for message in websocket:
            response:dict = json.loads(message)
            logger.debug(f"Received signaling message: {response}")

            message_type = MessageType(response["type"])
            payload = response.get("payload", {})

            match message_type:
                case MessageType.JOIN:
                    await handle_join(websocket, payload, audio_track)
                case MessageType.OFFER:
                    await handle_offer(websocket, payload, audio_track)
                case MessageType.ANSWER:
                    await handle_answer(payload)
                case MessageType.CANDIDATE:
                    await handle_candidate(payload)
                case _:
                    logger.warning(f"Unhandled message type: {message_type}")
        logger.info("WebRTC connection closed")


if __name__ == "__main__":
    asyncio.run(signaling_client())