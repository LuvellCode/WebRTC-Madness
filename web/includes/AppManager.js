class AppManager {
    constructor(webSocketUrl, logger = console) {
        this.logger = logger;

        // WebSocket Client
        this.webSocketClient = new WebSocketClient(webSocketUrl, this.logger);

        // RTC Config
        this.rtcConfig = RTC_CONFIG;

        // Local Stream
        this.localStream = null;

        // Remote Users
        this.remotePeers = new Map(); // Key: User ID, Value: User object

        // Call State
        this.isCallActive = false;        
    }

    async start() {
        this.logger.info("[AppManager] Starting application...");

        serverConnectButton.hidden = true;

        // Register WebSocket handlers
        this.registerWebSocketHandlers();

        // WebSocket onOpen Callback
        this.webSocketClient.onOpen = () => this.onWebSocketOpen();

        // Connect WebSocket
        this.webSocketClient.connect();
    }

    async onWebSocketOpen() {
        // Handshake with signaling server
        this.webSocketClient.send(MessageType.CONFIRM_ID, { name: current_user.name });
    }

    registerWebSocketHandlers() {
        this.webSocketClient.registerHandler(MessageType.CONFIRM_ID, async (payload) => {
            this.logger.info("[AppManager] CONFIRM_ID received:", payload);

            // Update current user info
            current_user = User.fromPayload(payload.user);

            // UI Updates
            startCallButton.hidden = false;

            // One-time start call button
            const startCallHandler = async () => {
                await this.startLocalStream();
            
                // Add local stream to curr_user (why tho)
                current_user.stream = this.localStream;
            
                this.isCallActive = true; // Enable call-related actions
            
                // Send JOIN
                this.webSocketClient.send(MessageType.JOIN, {});
                
                startCallButton.hidden = true;
                muteSelfButton.hidden = false;
            
                startCallButton.removeEventListener('click', startCallHandler);
            };
            startCallButton.addEventListener('click', startCallHandler);
        });

        this.webSocketClient.registerHandler(MessageType.JOIN, async (payload) => {
            if (!this.isCallActive) {
                this.logger.warn('[AppManager] JOIN message ignored as call is not active.');
                return;
            }

            let remoteUser = User.fromPayload(payload.user);
            this.logger.info('[AppManager] New client joined', remoteUser);

            if (!this.remotePeers.has(remoteUser.id)) {
                this.remotePeers.set(remoteUser.id, remoteUser);

                this.createPeerConnection(remoteUser);

                const offer = await remoteUser.peerConnection.createOffer();
                await remoteUser.peerConnection.setLocalDescription(offer);

                this.webSocketClient.send_to(MessageType.OFFER, remoteUser, {sdp: offer.sdp});
            }
            else {
                this.logger.warn(`[AppManager] JOIN message ignored as user already joined`, remoteUser)
            }
        });

        this.webSocketClient.registerHandler(MessageType.OFFER, async (payload) => {
            let remoteUser = this.remotePeers.get(payload.user.id);
        
            // Create user if not found
            if (!remoteUser) {
                this.logger.info(`[AppManager] OFFER received from new user. Adding user to remotePeers.`);
                remoteUser = User.fromPayload(payload.user);
                this.remotePeers.set(remoteUser.id, remoteUser);
            }
        
            this.logger.log("Before creating conn", remoteUser);
        
            // Create PeerConnection for remoteUser
            this.createPeerConnection(remoteUser);
        
            const peerConnection = remoteUser.peerConnection; // Extracting the created connection
            this.logger.log("After creating conn", remoteUser);
        
            try {
                // Setting Offer
                await peerConnection.setRemoteDescription(
                    new RTCSessionDescription({ type: "offer", sdp: payload.sdp })
                );
        
                // Trickle RPC issue: handling pending candidates
                if (remoteUser.pendingCandidates) {
                    for (const candidate of remoteUser.pendingCandidates) {
                        await peerConnection.addIceCandidate(new RTCIceCandidate(candidate));
                        this.logger.info(`[AppManager] Processed pending ICE candidate for user: ${remoteUser.name}`);
                    }
                    remoteUser.pendingCandidates = [];
                }
        
                const answer = await peerConnection.createAnswer();

                await peerConnection.setLocalDescription(answer);
        
                // Replying to OFFER with ANSWER
                this.webSocketClient.send_to(MessageType.ANSWER, remoteUser, {sdp: answer.sdp});
        
                this.logger.info(`[AppManager] Answer sent to user: ${remoteUser.name} (${remoteUser.id})`);
            } catch (error) {
                this.logger.error(`[AppManager] Failed to process OFFER from ${remoteUser.name}: ${error}`);
            }
        });

        this.webSocketClient.registerHandler(MessageType.ANSWER, async (payload) => {
            const remoteUser = this.remotePeers.get(payload.user.id);
            if (!remoteUser || !remoteUser.getPeerConnection()) {
                this.logger.warn(`[AppManager] ANSWER received, but no PeerConnection exists for user: ${payload.user.name}`);
                return;
            }
        
            try {
                await remoteUser.peerConnection.setRemoteDescription(new RTCSessionDescription({ type: "answer", sdp: payload.sdp }));
                this.logger.info(`[AppManager] Remote description set successfully for user: ${remoteUser.name}`);
        
                // Trickle RPC issue: handling pending candidates
                if (remoteUser.pendingCandidates) {
                    for (const candidate of remoteUser.pendingCandidates) {
                        await remoteUser.peerConnection.addIceCandidate(new RTCIceCandidate(candidate));
                        this.logger.info(`[AppManager] Processed pending ICE candidate for user: ${remoteUser.name}`);
                    }
                    remoteUser.pendingCandidates = [];
                }

            } catch (error) {
                this.logger.error(`[AppManager] Failed to set remote description for ${remoteUser.name}: ${error}`);
            }
        });

        this.webSocketClient.registerHandler(MessageType.CANDIDATE, async (payload) => {
            const remoteUser = this.remotePeers.get(payload.user.id);
            if (!remoteUser || !remoteUser.peerConnection) {
                this.logger.warn(`[AppManager] CANDIDATE received, but no PeerConnection exists for user: ${payload.user.name}`);
                return;
            }

            try {

                if (!remoteUser.peerConnection.remoteDescription) {
                    // In case of Trickle RTC we should postpone the ICE Candidates processing.
                    // They can leak before actually answering and establishing the P2P connection
                    this.logger.warn(`[AppManager] Storing ICE candidate for later processing. User: ${remoteUser.name}`);
                    remoteUser.pendingCandidates = remoteUser.pendingCandidates || [];
                    remoteUser.pendingCandidates.push(payload.candidate);
                    return;
                }

                if (!payload.candidate) {
                    await remoteUser.peerConnection.addIceCandidate(null)
                } else {
                    await remoteUser.peerConnection.addIceCandidate(payload.candidate)
                }
            
                this.logger.info(`[AppManager] Added ICE candidate for user: ${remoteUser.name}`);
            } catch (error) {
                this.logger.error(`[AppManager] Failed to add ICE candidate for ${remoteUser.name}: ${error}`);
            }
        });
    }

    createPeerConnection(remoteUser) {
        const peerConnection = new RTCPeerConnection(this.rtcConfig);
    
        peerConnection.onicecandidate = (event) => {
            if (event.candidate) {
                this.webSocketClient.send_to(MessageType.CANDIDATE, remoteUser, {
                    candidate: event.candidate,
                });
            }
        };
    
        peerConnection.ontrack = (event) => {
            this.logger.info(`[AppManager] Track received from user: ${remoteUser.name}`);
            remoteUser.stream = event.streams[0];
            this.createAudioElementForUser(remoteUser);
        };
    
        peerConnection.ondatachannel = (event) => {
            this.logger.info(`[AppManager] DataChannel received from ${remoteUser.name}`);
            this.setupDataChannel(remoteUser, event.channel);
        };
    
        if (this.localStream) {
            this.localStream.getTracks().forEach((track) => peerConnection.addTrack(track, this.localStream));
        }

        if (!remoteUser.dataChannel) {
            const dataChannel = peerConnection.createDataChannel("chat");
            this.setupDataChannel(remoteUser, dataChannel);
            this.logger.info(`[AppManager] DataChannel initialized for user: ${remoteUser.name}`);
        }
    
        remoteUser.setPeerConnection(peerConnection);
        this.logger.info(`[AppManager] PeerConnection created for user: ${remoteUser.name}`);
        return peerConnection;
    }

    setupDataChannel(remoteUser, dataChannel) {
        dataChannel.onopen = () => {
            this.logger.info(`[AppManager] DataChannel opened with ${remoteUser.name}`);
        };
    
        dataChannel.onclose = () => {
            this.logger.info(`[AppManager] DataChannel closed with ${remoteUser.name}`);
        };
    
        dataChannel.onmessage = (event) => {
            const message = event.data;
            this.logger.info(`[AppManager] Message received from ${remoteUser.name}: ${message}`);
            this.displayMessage(remoteUser, message);
        };
    
        remoteUser.dataChannel = dataChannel;
    }

    broadcastMessageToChannel(message) {
        for (const remoteUserId of app.remotePeers.keys()) {
            app.sendMessage(remoteUserId, message);
        }
        chatInput.value = "";
        app.displayMessage(current_user, message);
    }

    sendMessage(userId, message) {
        const remoteUser = this.remotePeers.get(userId);
        if (!remoteUser) {
            this.logger.warn(`[AppManager] Cannot send message. User with ID ${userId} not found.`);
            return;
        }
    
        const dataChannel = remoteUser.dataChannel;
        if (!dataChannel || dataChannel.readyState !== "open") {
            this.logger.warn(`[AppManager] Cannot send message. DataChannel not open for user ID: ${userId}`);
            return;
        }
    
        try {
            dataChannel.send(message);
            this.logger.info(`[AppManager] Message sent to ${userId}: ${message}`);
        } catch (error) {
            this.logger.error(`[AppManager] Failed to send message to ${userId}: ${error}`);
        }
    }

    displayMessage(remoteUser, message) {
        const chatMessages = document.getElementById('chatMessages');
        if (!chatMessages) {
            this.logger.warn(`[AppManager] Chat messages container not found.`);
            return;
        }
    
        const isCurrentUser = remoteUser.id === current_user.id;
    
        const messageElement = document.createElement('p');
        const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        messageElement.textContent = `[${time}] ${isCurrentUser ? "You" : remoteUser.name}: ${message}`;
        messageElement.className = isCurrentUser ? "user-message" : "remote-message";
    
        chatMessages.appendChild(messageElement);

        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    createAudioElementForUser(remoteUser, isCurrentUser = false) {
        const clientGrid = document.getElementById('clientGrid');
        let userContainer = document.getElementById(`client-${remoteUser.id}`);
        
        if (!userContainer) {
            userContainer = document.createElement('div');
            userContainer.className = 'client';
            userContainer.id = `client-${remoteUser.id}`;
            userContainer.innerHTML = `<p>${remoteUser.name}</p>`;
            clientGrid.appendChild(userContainer);
        }
        
        // Create or Update the user Audio
        let audioElement = document.getElementById(`audio-${remoteUser.id}`);
        if (!audioElement) {
            audioElement = document.createElement('audio');
            audioElement.id = `audio-${remoteUser.id}`;
            audioElement.autoplay = true;
            audioElement.controls = false;
            userContainer.appendChild(audioElement);
        }
        
        // Using the stream
        if (remoteUser.stream) {
            audioElement.srcObject = remoteUser.stream;
            if (isCurrentUser) {
                audioElement.muted = true; // Mute if local
            }
        } else {
            this.logger.warn(`[AppManager] No stream available for user ${remoteUser.name}`);
        }
        
        // Volume Control
        let volumeSlider = document.getElementById(`volume-${remoteUser.id}`);
        if (!volumeSlider) {
            volumeSlider = document.createElement('input');
            volumeSlider.type = 'range';
            volumeSlider.min = '0';
            volumeSlider.max = '1';
            volumeSlider.step = '0.01';
            volumeSlider.id = `volume-${remoteUser.id}`;
            volumeSlider.style.marginTop = '10px';
            
            volumeSlider.addEventListener('input', () => {
                const volume = parseFloat(volumeSlider.value);
                if (isCurrentUser) {
                    this.gainNode.gain.value = volume;
                    this.logger.info(`[AppManager] Updated local volume: ${volume}`);
                } else {
                    audioElement.volume = volume;
                    this.logger.info(`[AppManager] Updated remote user volume: ${remoteUser.name} to ${volume}`);
                }
            });
        
            userContainer.appendChild(volumeSlider);
        }
        
        if (isCurrentUser) {
            volumeSlider.value = this.gainNode.gain.value;
        } else {
            volumeSlider.value = audioElement.volume;
        }
    }
    
    
    removeUserElement(userId) {
        const userContainer = document.getElementById(`client-${userId}`);
        if (userContainer) {
            userContainer.remove();
            this.logger.info(`[AppManager] Removed user element for user ID: ${userId}`);
        } else {
            this.logger.warn(`[AppManager] Attempted to remove non-existent user element for ID: ${userId}`);
        }
    }

    async startLocalStream() {
        try {
            // Get current_user stream
            const originalStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
            this.logger.info("[AppManager] Local stream initialized.");
            
            const audioTracks = originalStream.getAudioTracks();
            const videoTracks = originalStream.getVideoTracks();
            if (audioTracks.length > 0) {
                this.logger.info(`Using audio device: ${audioTracks[0].label}`);
            }
            if (videoTracks.length > 0) {
                this.logger.info(`Using video device: ${videoTracks[0].label}`);
            }

            // Initialization
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
    
            // Source. We will use gainNode to change the output stream only so the user won't hear it
            const source = this.audioContext.createMediaStreamSource(originalStream);
    
            this.gainNode = this.audioContext.createGain();
            source.connect(this.gainNode);
    
            const destination = this.audioContext.createMediaStreamDestination();
            this.gainNode.connect(destination);
    
            this.localStream = destination.stream;
            current_user.stream = originalStream;
    
            this.createAudioElementForUser(current_user, true);
        } catch (error) {
            this.logger.error("[AppManager] Failed to initialize local stream:", error);
        }
    }
}