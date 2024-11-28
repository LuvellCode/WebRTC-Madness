class User {
    /**
     * 
     * @param {string} id - Websocket ID
     * @param {string} name - Name
     * @param {MediaStream|null} stream - Local or remote stream (null by default).
     */
    constructor(id, name, stream = null) {
        this.id = id;
        this.name = name;
        this.stream = stream;
        this.peerConnection = null;
        this.dataChannel = null;
    }

    /**
     * Set new stream
     * @param {MediaStream} stream - New Stream
     */
    setStream(stream) {
        this.stream = stream;
    }

    /**
     * Check if user has active stream
     * @returns {boolean} - Result
     */
    hasStream() {
        return this.stream !== null;
    }

    /**
     * Get API-like user object (stream excluded)
     * @returns {{id: string, name: string}} - Basic info
     */
    getInfo() {
        return {
            id: this.id,
            name: this.name
        };
    }

    /**
     * Convert User -> string
     * @returns {string} - String with user info
     */
    toString() {
        return `User { id: ${this.id}, name: ${this.name}, hasStream: ${this.hasStream()} }`;
    }

    static fromPayload(payload) {
        return new User(payload.id, payload.name);
    }

    setPeerConnection(peerConnection) {
        this.peerConnection = peerConnection;
    }

    getPeerConnection() {
        return this.peerConnection;
    }

    setDataChannel(dataChannel) {
        this.dataChannel = dataChannel;
    }

    getDataChannel() {
        return this.dataChannel;
    }
}