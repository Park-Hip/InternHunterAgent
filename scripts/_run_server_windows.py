import asyncio; asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["OTEL_SDK_DISABLED"] = "true"
from src.core.config import settings
settings.config_yaml.setdefault("agent", {}).setdefault("groq", {})["timeout"] = 120
from src.agents.tracing import langfuse
langfuse._langfuse_handler = None
import uvicorn
config = uvicorn.Config("src.api.app:app", host="127.0.0.1", port=8000, loop="none")
asyncio.run(uvicorn.Server(config).serve())
