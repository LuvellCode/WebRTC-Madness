from cert import load_or_create
SIGNALING_HOST = "192.168.0.176" 
SIGNALING_PORT = 8765

WEB_SERVER_PORT = 8080

SIGNALING_SERVER = f"wss://{SIGNALING_HOST}:{SIGNALING_PORT}"
WEB_SERVER = f"https://{SIGNALING_HOST}:{WEB_SERVER_PORT}"


SSL_CONTEXT = load_or_create(certfile="server.crt", keyfile="server.key")