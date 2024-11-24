// Елементи DOM
const statusElement = document.getElementById('status');
const startCallButton = document.getElementById('startCall');
const muteSelfButton = document.getElementById('muteSelf');
const clientGrid = document.getElementById('clientGrid');
const namePopup = document.getElementById('namePopup');
const userNameInput = document.getElementById('userNameInput');
const submitNameButton = document.getElementById('submitNameButton');

// Ім'я користувача
let userName = null;

// WebSocket і RTCPeerConnection
let signalingServer = null;
let peerConnections = {};
let connectedClients = {}; // Список підключених клієнтів
let localStream = null;

// Налаштування STUN-сервера
const rtcConfig = {
    iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
};

// Web Audio Context
let audioContext = null;
let gainNode = null; // Нода для управління гучністю локального потоку

// Обробник для підтвердження імені
submitNameButton.addEventListener('click', () => {
    const inputName = userNameInput.value.trim();
    if (inputName.length > 0) {
        userName = inputName;
        console.log(`[INFO] User name set to: ${userName}`);
        namePopup.style.display = 'none';
        startCallButton.disabled = false;
        muteSelfButton.disabled = false;
    } else {
        alert("Please enter a valid name!");
    }
});

// Обробник кнопки "Start Call"
startCallButton.addEventListener('click', async () => {
    statusElement.innerText = 'Loading WebSocket host...';

    fetch('/config')
        .then(response => {
            if (!response.ok) {
                throw new Error("Failed to load config");
            }
            return response.json();
        })
        .then(async config => {
            const websocketHost = config.websocket_host;
            console.log(`[INFO] WebSocket Host: ${websocketHost}`);
            statusElement.innerText = `WebSocket Host: ${websocketHost}`;

            audioContext = new (window.AudioContext || window.webkitAudioContext)();

            signalingServer = new WebSocket(websocketHost);
            signalingServer.onopen = async () => {
                console.log("[INFO] Connected to signaling server");
                statusElement.innerText = 'Connected to signaling server!';
                
                if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                    console.error("[ERROR] getUserMedia is not supported in this browser.");
                    statusElement.innerText = "Your browser does not support getUserMedia.";
                    return;
                }

                // Запит доступу до мікрофона
                localStream = await navigator.mediaDevices.getUserMedia({ audio: true });
                console.log("[INFO] Got local stream");

                // Додаємо локального клієнта у грід
                updateClientGrid(userName, localStream, true);

                // Повідомляємо сервер про підключення
                signalingServer.send(JSON.stringify({ type: 'join', name: userName }));
                console.log("[INFO] Sent join request to signaling server");
            };

            signalingServer.onmessage = async (event) => {
                const message = JSON.parse(event.data);
                console.log("[MESSAGE] Received message from signaling server:", message);
            
                if (message.type === 'offer') {
                    console.log("[INFO] Received SDP offer from client", message.clientId);
                    handleOffer(message.offer, message.clientId);
                } else if (message.type === 'answer') {
                    console.log("[INFO] Received SDP answer from client", message.clientId);
                    handleAnswer(message.answer, message.clientId);
                } else if (message.type === 'candidate') {
                    console.log("[INFO] Received ICE candidate from client", message.clientId);
                    handleCandidate(message.candidate, message.clientId);
                } else if (message.type === 'clients') {
                    console.log("[INFO] Updated list of connected clients:", message.clients);
                    updateClientList(message.clients);
                } else if (message.type === 'join') {
                    console.log("[INFO] New client joined with ID", message.clientId);
                    createOfferForNewClient(message.clientId);
                }
            };

            signalingServer.onerror = (error) => {
                console.error("[ERROR] WebSocket error occurred:", error);
                statusElement.innerText = 'WebSocket error occurred.';
            };

            signalingServer.onclose = () => {
                console.log("[INFO] Disconnected from signaling server");
                statusElement.innerText = 'Disconnected from signaling server.';
            };
        })
        .catch(error => {
            console.error("[ERROR] Error loading WebSocket host:", error);
            statusElement.innerText = "Failed to load WebSocket host.";
        });
});

// Обробник кнопки "Mute Self"
muteSelfButton.addEventListener('click', () => {
    if (localStream) {
        localStream.getTracks().forEach(track => {
            track.enabled = !track.enabled;
        });
        console.log(`[INFO] Mute Self: ${localStream.getTracks()[0].enabled ? 'OFF' : 'ON'}`);
        statusElement.innerText = localStream.getTracks()[0].enabled ? 'You are unmuted' : 'You are muted';
    } else {
        console.warn("[WARNING] Local stream not initialized yet!");
    }
});

// Функція для створення RTCPeerConnection
function createPeerConnection(clientId) {
    console.log("[INFO] Creating new RTCPeerConnection for client", clientId);
    const peerConnection = new RTCPeerConnection(rtcConfig);

    peerConnection.onicecandidate = event => {
        if (event.candidate) {
            signalingServer.send(JSON.stringify({ type: 'candidate', candidate: event.candidate, clientId }));
            console.log("[INFO] Sent ICE candidate to signaling server for client", clientId, event.candidate);
        }
    };

    peerConnection.ontrack = event => {
        console.log("[INFO] Received remote stream from client", clientId);
        updateClientGrid(`Client ${clientId}`, event.streams[0]);
    };

    peerConnection.onconnectionstatechange = () => {
        console.log("[INFO] Connection state for client", clientId, ":", peerConnection.connectionState);
        if (peerConnection.connectionState === 'connected') {
            statusElement.innerText = `P2P Connection established with client ${clientId}`;
        }
    };

    localStream.getTracks().forEach(track => {
        peerConnection.addTrack(track, localStream);
    });

    return peerConnection;
}

// Функція для створення SDP-офера для нового клієнта
async function createOfferForNewClient(clientId) {
    console.log("[INFO] Creating SDP offer for new client", clientId);
    const peerConnection = createPeerConnection(clientId);
    peerConnections[clientId] = peerConnection;

    const offer = await peerConnection.createOffer();
    await peerConnection.setLocalDescription(offer);

    signalingServer.send(JSON.stringify({ type: 'offer', offer, clientId }));
    console.log("[INFO] Sent SDP offer to new client", clientId);
}

function handleOffer(offer, clientId) {
    console.log("[INFO] Handling SDP offer for client", clientId);
    const peerConnection = createPeerConnection(clientId);
    peerConnections[clientId] = peerConnection;
    peerConnection.setRemoteDescription(new RTCSessionDescription(offer));
    peerConnection.createAnswer().then(answer => {
        peerConnection.setLocalDescription(answer);
        signalingServer.send(JSON.stringify({ type: 'answer', answer, clientId }));
        console.log("[INFO] Sent SDP answer to client", clientId);
    });
}

function handleAnswer(answer, clientId) {
    console.log("[INFO] Handling SDP answer for client", clientId);
    peerConnections[clientId].setRemoteDescription(new RTCSessionDescription(answer));
}

function handleCandidate(candidate, clientId) {
    console.log("[INFO] Adding ICE candidate for client", clientId);
    peerConnections[clientId].addIceCandidate(new RTCIceCandidate(candidate));
}

function updateClientList(clients) {
    connectedClients = clients;
    console.log("[INFO] Updated client list:", connectedClients);
}

function updateClientGrid(clientName, stream, isCurrentClient = false) {
    let clientElement = document.getElementById(clientName);

    // Якщо клієнта немає у гріді, створюємо новий елемент
    if (!clientElement) {
        clientElement = document.createElement('div');
        clientElement.className = 'client';
        clientElement.id = clientName;
        clientElement.innerHTML = `<h3>${clientName}</h3>`;
        const audioContainer = document.createElement('div');
        audioContainer.className = 'audio-container';
        clientElement.appendChild(audioContainer);
        clientGrid.appendChild(clientElement);
    }

    // Створюємо або оновлюємо аудіо-елемент
    const audio = document.createElement('audio');
    audio.srcObject = stream;
    audio.autoplay = true;
    audio.controls = false;

    // Налаштування повзунка гучності
    const volumeSlider = document.createElement('input');
    volumeSlider.type = 'range';
    volumeSlider.min = '0';
    volumeSlider.max = '1';
    volumeSlider.step = '0.01';

    if (isCurrentClient) {
        audio.muted = true;

        if (!gainNode) {
            const source = audioContext.createMediaStreamSource(stream);
            gainNode = audioContext.createGain();
            const destination = audioContext.createMediaStreamDestination();

            source.connect(gainNode);
            gainNode.connect(destination);

            localStream = destination.stream;

            Object.values(peerConnections).forEach(peerConnection => {
                peerConnection.getSenders().forEach(sender => {
                    if (sender.track && sender.track.kind === "audio") {
                        peerConnection.removeTrack(sender);
                    }
                });
                localStream.getTracks().forEach(track => {
                    peerConnection.addTrack(track, localStream);
                });
            });
        }

        volumeSlider.value = gainNode.gain.value;
        volumeSlider.addEventListener('input', () => {
            gainNode.gain.value = parseFloat(volumeSlider.value);
            console.log(`[INFO] Updated local stream volume to ${gainNode.gain.value}`);
        });
    } else {
        volumeSlider.value = audio.volume;
        volumeSlider.addEventListener('input', () => {
            audio.volume = volumeSlider.value;
        });
    }

    const audioContainer = clientElement.querySelector('.audio-container');
    audioContainer.innerHTML = '';
    audioContainer.appendChild(audio);
    audioContainer.appendChild(volumeSlider);

    console.log("[INFO] Updated grid for client:", clientName);
}
