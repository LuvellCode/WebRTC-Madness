# My pet (WebRTC Madness)
WebRTC sandbox. 

**Goal**: Make a working solution for P2P Audio Streaming (not only voice chat)

## Comments here
```plain
# For now i'm in love with the generic server implementation, although I've spent some (night) time on it.
# You can check the commit history if needed. Hehe?

# ToDo:
    * Upgrade the client-side solution.
    * Maybe add some testing
    * ???
```
![Cat_Dance.gif?](why_is_the_cat_here.gif)
---
## Most interesting files. Features
 * `signaling_server.py` (websockets)
   * **Core**: Logging, Direct Messaging, Broadcasting.
   * **Unified** support for external handlers (register via `@signaling_server.register_handler`)
   * **Dynamic** execution of handlers with dynamic parameters from local scope. 
     * Whitelisted local scope variables: see `SUPPORTED_HANDLER_ARGS`.
   * **Validation**: 
     * `validate_handler_args`: validate handler arguments (all must exist in `SUPPORTED_HANDLER_ARGS`)
     * `validate_message_structure`: validate incoming messages (must have common structure and one of the `MessageType`[enum] values)
   * Since the handler registrar is a decorator, the `@signaling_server.register_handler` can be used to assign more than one `MessageType` to a handler. You **can** require a `message_type` for current `MessageType` to be passed to the handler.
        ```python
        async def handle_rtc(user:User, payload:dict, message_type:MessageType):
        ```
 * `signaling_main.py`
   * Signaling Server extension. Registers handlers to process messages.

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