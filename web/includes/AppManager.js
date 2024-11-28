class AppManager {
    constructor(webSocketUrl, logger = console) {
        this.logger = logger;

        // WebSocket Client
        this.webSocketClient = new WebSocketClient(webSocketUrl, this.logger);

        // RTC Config
        this.rtcConfig = {
            iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
        };

        // Local Stream
        this.localStream = null;

        // Remote Users
        this.remoteUsers = new Map(); // Key: User ID, Value: User object
        this.dataChannels = new Map();

        // Call State
        this.isCallActive = false;

        // WebSocket onOpen Callback
        this.webSocketClient.onOpen = () => this.onWebSocketOpen();
    }

    async start() {
        this.logger.info("[AppManager] Starting application...");

        // Register WebSocket handlers
        this.registerWebSocketHandlers();

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
            serverConnectButton.hidden = true;

            // One-time start call button
            const startCallHandler = async () => {
                await this.startLocalStream();
            
                // Додаємо локальний стрім до current_user
                current_user.stream = this.localStream;
            
                this.isCallActive = true; // Enable call-related actions
            
                // Надсилаємо JOIN-повідомлення на сервер
                this.webSocketClient.send(MessageType.JOIN, {
                    user: current_user.getInfo()
                });
            
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

            const remoteUser = User.fromPayload(payload.user);
            this.logger.info('[AppManager] New client joined', remoteUser);

            if (!this.remoteUsers.has(remoteUser.id)) {
                this.remoteUsers.set(remoteUser.id, remoteUser);

                const peerConnection = this.createPeerConnection(remoteUser);
                remoteUser.setPeerConnection(peerConnection);

                const offer = await peerConnection.createOffer();
                await peerConnection.setLocalDescription(offer);

                this.webSocketClient.send(MessageType.OFFER, {
                    user: current_user.getInfo(),
                    sdp: offer.sdp,
                    target: remoteUser.id
                });
            }
            else {
                this.logger.warn(`[AppManager] JOIN message ignored as user already joined`, remoteUser)
            }
        });

        this.webSocketClient.registerHandler(MessageType.OFFER, async (payload) => {
            let remoteUser = this.remoteUsers.get(payload.user.id);
        
            // Якщо клієнт ще не існує, створити його
            if (!remoteUser) {
                this.logger.info(`[AppManager] OFFER received from new user. Adding user to remoteUsers.`);
                remoteUser = User.fromPayload(payload.user);
                this.remoteUsers.set(remoteUser.id, remoteUser);
            }
        
            // Створення PeerConnection для цього клієнта
            const peerConnection = this.createPeerConnection(remoteUser);
            remoteUser.setPeerConnection(peerConnection);
        
            try {
                // Встановлюємо Remote Description
                await peerConnection.setRemoteDescription(new RTCSessionDescription({ type: "offer", sdp: payload.sdp }));
        
                // Обробка відкладених кандидатів
                if (remoteUser.pendingCandidates) {
                    for (const candidate of remoteUser.pendingCandidates) {
                        await peerConnection.addIceCandidate(new RTCIceCandidate(candidate));
                        this.logger.info(`[AppManager] Processed pending ICE candidate for user: ${remoteUser.name}`);
                    }
                    remoteUser.pendingCandidates = [];
                }
        
                // Генеруємо Answer
                const answer = await peerConnection.createAnswer();
                await peerConnection.setLocalDescription(answer);
        
                // Надсилаємо Answer назад ініціатору
                this.webSocketClient.send(MessageType.ANSWER, {
                    user: current_user.getInfo(),
                    sdp: answer.sdp,
                });
        
                this.logger.info(`[AppManager] Answer sent to user: ${remoteUser.name} (${remoteUser.id})`);
            } catch (error) {
                this.logger.error(`[AppManager] Failed to process OFFER from ${remoteUser.name}: ${error}`);
            }
        });

        this.webSocketClient.registerHandler(MessageType.ANSWER, async (payload) => {
            const remoteUser = this.remoteUsers.get(payload.user.id);
            if (!remoteUser || !remoteUser.getPeerConnection()) {
                this.logger.warn(`[AppManager] ANSWER received, but no PeerConnection exists for user: ${payload.user.name}`);
                return;
            }
        
            const peerConnection = remoteUser.getPeerConnection();
        
            // Перевірка стану
            if (peerConnection.signalingState !== 'have-local-offer') {
                this.logger.warn(`[AppManager] Skipping ANSWER. Current signalingState: ${peerConnection.signalingState}`);
                return;
            }
        
            try {
                await peerConnection.setRemoteDescription(new RTCSessionDescription({ type: "answer", sdp: payload.sdp }));
                this.logger.info(`[AppManager] Remote description set successfully for user: ${remoteUser.name}`);
        
                // Обробка відкладених кандидатів
                if (remoteUser.pendingCandidates) {
                    for (const candidate of remoteUser.pendingCandidates) {
                        await peerConnection.addIceCandidate(new RTCIceCandidate(candidate));
                        this.logger.info(`[AppManager] Processed pending ICE candidate for user: ${remoteUser.name}`);
                    }
                    remoteUser.pendingCandidates = [];
                }
            } catch (error) {
                this.logger.error(`[AppManager] Failed to set remote description for ${remoteUser.name}: ${error}`);
            }
        });

        this.webSocketClient.registerHandler(MessageType.CANDIDATE, async (payload) => {
            const remoteUser = this.remoteUsers.get(payload.user.id);
            if (!remoteUser || !remoteUser.getPeerConnection()) {
                this.logger.warn(`[AppManager] CANDIDATE received, but no PeerConnection exists for user: ${payload.user.name}`);
                return;
            }
        
            const peerConnection = remoteUser.getPeerConnection();
        
            // Перевірка наявності RemoteDescription
            if (!peerConnection.remoteDescription) {
                this.logger.warn(`[AppManager] Storing ICE candidate for later processing. User: ${remoteUser.name}`);
                remoteUser.pendingCandidates = remoteUser.pendingCandidates || [];
                remoteUser.pendingCandidates.push(payload.candidate);
                return;
            }
        
            try {
                await peerConnection.addIceCandidate(new RTCIceCandidate(payload.candidate));
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
                this.webSocketClient.send(MessageType.CANDIDATE, {
                    user: current_user.getInfo(),
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
            // remoteUser.setDataChannel(event.channel);
            this.setupDataChannel(remoteUser, event.channel)
            // remoteUser.getDataChannel().onmessage = (e) => {
            // event.channel.onmessage = (e) => {
            //     this.logger.info(`[AppManager] Message received from ${remoteUser.name}: ${e.data}`);
            // };
        };
    
        if (this.localStream) {
            this.localStream.getTracks().forEach((track) => peerConnection.addTrack(track, this.localStream));
        }
    
        // Створення DataChannel для ініціатора
        const dataChannel = peerConnection.createDataChannel("chat");
        remoteUser.setDataChannel(dataChannel);
    
        dataChannel.onopen = () => {
            this.logger.info(`[AppManager] DataChannel opened with ${remoteUser.name}`);
        };
    
        dataChannel.onclose = () => {
            this.logger.info(`[AppManager] DataChannel closed with ${remoteUser.name}`);
        };
    
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
    
        this.dataChannels.set(remoteUser.id, dataChannel);
    }

    sendMessage(userId, message) {
        const remoteUser = this.remoteUsers.get(userId);
        if (!remoteUser) {
            this.logger.warn(`[AppManager] Cannot send message. User with ID ${userId} not found.`);
            return;
        }
    
        const dataChannel = remoteUser.getDataChannel();
        if (!dataChannel || dataChannel.readyState !== "open") {
            this.logger.warn(`[AppManager] Cannot send message. DataChannel not open for user ID: ${userId}`);
            return;
        }
    
        dataChannel.send(message);
        this.logger.info(`[AppManager] Message sent to ${userId}: ${message}`);
    }

    displayMessage(remoteUser, message) {
        const chatMessages = document.getElementById('chatMessages');
        if (!chatMessages) {
            this.logger.warn(`[AppManager] Chat messages container not found.`);
            return;
        }
    
        // Визначаємо, чи це повідомлення від поточного користувача
        const isCurrentUser = remoteUser.id === current_user.id;
    
        // Створюємо елемент повідомлення
        const messageElement = document.createElement('p');
        const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        messageElement.textContent = `[${time}] ${isCurrentUser ? "You" : remoteUser.name}: ${message}`;
        messageElement.className = isCurrentUser ? "user-message" : "remote-message";
    
        // Додаємо повідомлення в контейнер
        chatMessages.appendChild(messageElement);
    
        // Скрол до останнього повідомлення
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
        
        // Оновлюємо або створюємо аудіо-елемент
        let audioElement = document.getElementById(`audio-${remoteUser.id}`);
        if (!audioElement) {
            audioElement = document.createElement('audio');
            audioElement.id = `audio-${remoteUser.id}`;
            audioElement.autoplay = true;
            audioElement.controls = false;
            userContainer.appendChild(audioElement);
        }
        
        // Прив'язуємо потік
        if (remoteUser.stream) {
            audioElement.srcObject = remoteUser.stream;
            if (isCurrentUser) {
                audioElement.muted = true; // Заглушуємо локальне аудіо
            }
        } else {
            this.logger.warn(`[AppManager] No stream available for user ${remoteUser.name}`);
        }
        
        // Додаємо контрол для регулювання гучності
        let volumeSlider = document.getElementById(`volume-${remoteUser.id}`);
        if (!volumeSlider) {
            volumeSlider = document.createElement('input');
            volumeSlider.type = 'range';
            volumeSlider.min = '0';
            volumeSlider.max = '1';
            volumeSlider.step = '0.01';
            volumeSlider.id = `volume-${remoteUser.id}`;
            volumeSlider.style.marginTop = '10px';
            
            // Додати прослуховування змін гучності
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
        
        // Встановлюємо початкову гучність
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
            // Отримуємо оригінальний стрім
            const originalStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
            this.logger.info("[AppManager] Local stream initialized.");
    
            // Ініціалізуємо аудіо-контекст
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
    
            // Джерело для оригінального стріму
            const source = this.audioContext.createMediaStreamSource(originalStream);
    
            // Налаштовуємо gainNode для регулювання гучності
            this.gainNode = this.audioContext.createGain();
            source.connect(this.gainNode);
    
            // Створюємо новий потік для передачі
            const destination = this.audioContext.createMediaStreamDestination();
            this.gainNode.connect(destination);
    
            // Зберігаємо стріми
            this.localStream = destination.stream; // Потік для передачі іншим
            current_user.stream = originalStream; // Потік для локального відтворення
    
            // Додаємо локальне аудіо до UI
            this.createAudioElementForUser(current_user, true);
        } catch (error) {
            this.logger.error("[AppManager] Failed to initialize local stream:", error);
        }
    }
}