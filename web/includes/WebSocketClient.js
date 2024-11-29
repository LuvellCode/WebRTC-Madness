/**
 * Responsible for communication with Signaling Server
 */
class WebSocketClient {
    constructor(url, logger = console) {
        this.url = url;
        this.logger = logger;
        this.socket = null;
        this.handlers = new Map();
    }

    connect() {
        this.socket = new WebSocket(this.url);

        this.socket.onopen = () => {
            this.logger.info(`[WebSocket] Connected to `, this.url);
            this.onOpen();
        };

        this.socket.onmessage = (event) => {
            const message = JSON.parse(event.data);
            this.onMessage(message);
        };

        this.socket.onclose = () => {
            this.logger.warn("[WebSocket] Connection closed");
            this.onClose();
        };

        this.socket.onerror = (error) => {
            this.logger.error("[WebSocket] Error:", error);
        };
    }

    onOpen() {
        // To be updated
    }

    onMessage(message) {
        const handler = this.handlers.get(message.type);
        if (handler) {
            this.logger.info(`[WebSocket] Handling message from server. ${message.type}: `, message.payload)
            handler(message.payload);
        } else {
            this.logger.warn(`[WebSocket] No handler for message type: ${message.type}`);
        }
    }

    onClose() {
        // To be updated
    }

    send(type, payload) {
        let msg = { type, payload };
        const message = JSON.stringify(msg);
        this.logger.info(`[WebSocket] Sending message to server with type ${type}: `, msg)
        this.socket.send(message);
    }

    send_to(type, target, payload) {
        let msg = { type, target: target.getInfo(), payload };
        const message = JSON.stringify(msg);
        this.logger.info(`[WebSocket] Sending message to ${target.name} with type ${type}: `, msg)
        this.socket.send(message);
    }

    registerHandler(type, handler) {
        this.handlers.set(type, handler);
        this.logger.info(`[WebSocket] Registered handler for type: ${type}`);
    }
}