// DOM
const statusElement = document.getElementById('status');
const serverConnectButton = document.getElementById('serverConnect');
const startCallButton = document.getElementById('startCall');
const muteSelfButton = document.getElementById('muteSelf');
const clientGrid = document.getElementById('clientGrid');
const namePopup = document.getElementById('namePopup');
const userNameInput = document.getElementById('userNameInput');
const submitNameButton = document.getElementById('submitNameButton');

const chatInput = document.getElementById("chatInput");
const sendButton = document.getElementById("sendButton");

///////////////////////

/**
 * CONSTANTS
 */

const MessageType = Object.freeze({
    OFFER: "OFFER",
    ANSWER: "ANSWER",
    CANDIDATE: "CANDIDATE",
    JOIN: "JOIN",
    CONFIRM_ID: "CONFIRM_ID"
});


// STUN
const RTC_CONFIG = {
    iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
};

////////////////////////
// Current User Settings

let current_user = new User(id=null, name=null); // User Obj

////////////////////////
// Application-level (AppManager)
let app;
////////////////////////

// Web Audio Context
let audioContext = null;
let gainNode = null; // Node to configure the local stream

// Name entering popup
submitNameButton.addEventListener('click', () => {
    const inputName = userNameInput.value.trim();
    if (inputName.length > 0) {

        current_user = new User(id=null, name=inputName)
        console.log(`[INFO] Current user was updated:`, current_user);
        namePopup.style.display = 'none';
        startCallButton.disabled = false;
        muteSelfButton.disabled = false;
    } else {
        alert("Please enter a valid name!");
    }
});

serverConnectButton.addEventListener('click', async () => {
    console.debug('[DEBUG] Loading WebSocket host...');

    fetch('/config')
        .then(response => {
            if (!response.ok) {
                throw new Error("Failed to load config");
            }
            response = response.json();
            console.debug(`[DEBUG] Loaded config:`, response);
            return response;
        })
        .then(async config => {
            const websocketHost = config.websocket_host;
            console.info(`[INFO] WebSocket Host: `, websocketHost);
            
            app = new AppManager(websocketHost);
            await app.start();

            sendButton.addEventListener("click", () => {
                const message = chatInput.value.trim();
                if (message) {
                    for (const remoteUserId of app.remoteUsers.keys()) {
                        app.sendMessage(remoteUserId, message);
                    }
                    chatInput.value = "";
                    app.displayMessage(current_user, message); // Відобразити власне повідомлення
                }
            });
        })

})