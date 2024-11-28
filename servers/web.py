from http.server import HTTPServer, SimpleHTTPRequestHandler
from logging import Logger
from socketserver import TCPServer
import json
import os
import ssl
from config import SIGNALING_SERVER, SIGNALING_HOST, WEB_SERVER_PORT, WEB_SERVER


class WebServerHandler(SimpleHTTPRequestHandler):
    """
    Just a dummy server for files loading
    """
    def __init__(self, *args, **kwargs):
        self.base_dir = os.path.join(os.getcwd(), 'web')
        super().__init__(*args, **kwargs)

    def do_GET(self):
        if self.path == '/config':
            return self.handle_config()

        if self.path == '/':
            return self.handle_root()

        return self.handle_static_files()

    def handle_config(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        config_data = {
            "websocket_host": SIGNALING_SERVER
        }
        self.wfile.write(json.dumps(config_data).encode('utf-8'))

    def handle_root(self):
        self.path = '/index.html'
        return self.handle_static_files()

    def handle_static_files(self):
        file_path = os.path.join(self.base_dir, self.path.lstrip('/'))
        print(f"{file_path=}")

        if os.path.isfile(file_path):
            with open(file_path, 'rb') as file:
                self.send_response(200)
                self.send_header('Content-Type', self.guess_type(file_path))
                self.end_headers()
                self.wfile.write(file.read())
            return

        self.send_error(404, "File not found")

def run_web_server():
    httpd = HTTPServer((SIGNALING_HOST, WEB_SERVER_PORT), WebServerHandler)

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile="server.crt", keyfile="server.key")
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)

    print(f"Starting HTTPS server on {WEB_SERVER}")
    httpd.serve_forever()