# Real-Time Voice AI Assistant

This project implements a real-time, voice-to-voice AI assistant accessible via a web interface. Users can speak into their microphone, have their speech transcribed, get an intelligent response generated by an AI agent (potentially using external tools like weather or news), and hear the response spoken back via Text-to-Speech.

The backend is built with Python using FastAPI, handling WebSocket communication, orchestrating AI service calls (Groq for STT, an Agent using Groq/OpenAI LLM, OpenAI for TTS), interacting with tools, and storing conversation history in PostgreSQL. The entire application is containerized using Docker for easy local development and deployment.

## Application Flow Diagram

This diagram shows the sequence of events for a typical voice interaction:
![image](https://github.com/user-attachments/assets/195a0c1e-59e2-4c0f-a973-b8d645f4bbfc)

## Demo

https://github.com/user-attachments/assets/b3ea28ed-21d8-4a55-9ee9-3e873c5d11cc
### With Memory:

https://github.com/user-attachments/assets/d2ec17e0-516f-47fa-bca5-6e9c10397465

## Features

* **Real-time Voice Input:** Captures audio via browser's MediaRecorder API.
* **WebSocket Communication:** Low-latency communication between frontend and backend.
* **Fast AI Inference:** Leverages Groq API for Speech-to-Text (STT).
* **Agent-based LLM Interaction:** Uses an AI agent (`pydantic-ai`) for response generation, enabling tool use.
* **Tool Usage:** Integrated tools for fetching real-time data (e.g., weather, news).
* **Streaming Text-to-Speech (TTS):** Uses OpenAI TTS API to generate and stream audio responses back to the client for immediate playback.
* **Conversation History:** Stores interaction details (transcripts, user/AI timestamps) in a PostgreSQL database.
* **Asynchronous Backend:** Built with `asyncio`, FastAPI, `httpx`, and async database drivers (`psycopg_pool`).
* **Dockerized:** Uses Docker and Docker Compose for a consistent development environment and easy deployment.
* **Modern Tooling:** Uses `uv` for fast dependency management via `pyproject.toml` and `uv.lock`. Includes configuration for `ruff` and `mypy`.

## Project Structure

```text
📁 VoiceAiAssistant/
├── 📁 assets/
│   ├── 📝 image.png 
├── 📁 app/                                   # Main application source code
│   ├── 📁 backend/                           # Backend logic and services
│   │   ├── 📁 agent/                         # AI agent orchestration and tools
│   │   │   ├── 📝 __init__.py                 # Module initializer
│   │   │   ├── 📝 agent.py                    # Core agent logic
│   │   │   ├── 📝 ai_services.py              # AI services integration
│   │   │   ├── 📝 tools.py                    # Helper tools for agents
│   │   │   ├── 📝 utils.py                    # Utility functions for agents
│   │   ├── 📁 api/                            # API handling (WebSocket communication)
│   │   │   ├── 📝 __init__.py                 # Module initializer
│   │   │   ├── 📝 websocket_manager.py        # WebSocket connection management
│   │   ├── 📁 config/                         # Configuration files and settings
│   │   │   ├── 📝 __init__.py                 # Module initializer
│   │   │   ├── 📝 config.py                   # App configurations and environment settings
│   │   ├── 📁 database/                       # Database models and connections
│   │   │   ├── 📝 __init__.py                 # Module initializer
│   │   │   ├── 📝 database.py                 # Database connection and function setup
│   │   ├── 📁 routers/                        # API routing and dependency management
│   │   │   ├── 📝 __init__.py                 # Module initializer
│   │   │   ├── 📝 router.py                   # API router definitions
│   │   ├── 📝 dependencies.py                 # Dependency injection for API and routers
│   │   ├── 📝 factories.py                    # Functions for object creation (client, pool etc)
│   │   ├── 📝 schemas.py                      # Request and response data models
│   │   ├── 📝 services.py                     # Business logic and service layer
├── 📁 frontend/                               # Static frontend assets
│   ├── 📝 index.html                          # Main HTML page
│   ├── 📝 script.js                           # Frontend JavaScript logic
│   ├── 📝 style.css                           # Frontend styling
├── 📝 .dockerignore                           # Docker ignore rules
├── 📝 .env                                    # Environment variable definitions
├── 📝 .gitignore                              # Git ignore rules
├── 📝 .python-version                         # Python version management file
├── 📝 api.py                                  # Application startup and API entrypoint
├── 📝 docker-compose.yml                      # Docker Compose configuration
├── 📝 Dockerfile                              # Dockerfile for building the app image
├── 📝 pyproject.toml                          # Project metadata and dependency management
├── 📝 README.md                               # Project documentation
├── 📝 uv.lock                                 # Project metadata and dependency management
```

## Setup and Running (Local Docker)

1.  **Prerequisites:**
    * Install Docker Desktop or Docker Engine + Compose.
    * Obtain API Keys for: Groq, OpenAI, OpenWeatherMap, NewsAPI.org.
    * (Optional) Install `uv` (`pip install uv`) if you need to. More information on [this website](https://docs.astral.sh/uv/getting-started/installation/)
    
2.  **Configure Environment:**
    * Create or edit the `.env` file in the project root (`voiceaiassistant/.env`).
    * Fill in all your API keys.
    * Ensure database variables (`PG_USER`, `PG_PASSWORD`, `PG_DBNAME`) are set (defaults should match `docker-compose.yml`).


3.  **Build and Start Containers:**
    * Open a terminal in the project root (`voiceaiassistant/`).
    * Run: `docker-compose up --build -d`

4.  **Verify Containers:**
    * Check status: `docker-compose ps`
    * Check logs: `docker-compose logs -f backend db`

5.  **Access Frontend:**
    * Open `frontend/index.html` directly in your web browser.

6.  **Use:** Interact via the "Start/Stop Recording" buttons.

7.  **Stop:**
    * Run: `docker-compose down`
    * To remove database data: `docker-compose down -v`


