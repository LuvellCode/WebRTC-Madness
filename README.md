# My pet (WebRTC Madness)
WebRTC sandbox. 

**Goal**: Make a working solution for P2P Audio Streaming (not only voice chat)

## Project structure 
(probably outdated but at least something)

```plaintext
📂 WEBRTC-MADNESS
├── 📂 servers                     # Backend server logic
│   ├── 📂 includes                # Shared modules and utilities
│   │   ├── enums.py               # Enums for various constants
│   │   ├── messages.py            # Message classes for WebRTC signaling
│   │   ├── models.py              # Models, such as User representation
│   │   ├── logging_config.py      # Logging setup for the server
│   │   ├── server_config.py       # Centralized configuration for the server
│   │   └── signaling.py           # Main signaling logic
│   └── web.py                     # Webserver logic
├── 📂 web                         # Frontend web application
│   ├── client.js                  # WebRTC client-side logic
│   └── index.html                 # Main HTML file
├── .gitignore                     # Git ignore rules
├── cert.py                        # SSL certificate configuration
├── config.py                      # General configuration (host, ports, etc.)
├── LICENSE                        # Project license
├── main.py                        # Entry point for the server
├── README.md                      # Documentation for the project
├── server.crt                     # SSL certificate
├── server.key                     # SSL private key
└── tests.py                       # Various tests
```