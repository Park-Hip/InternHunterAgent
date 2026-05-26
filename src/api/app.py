from fastapi import FastAPI

from src.api.routes import query, health

app = FastAPI()

app.include_router(query.router, prefix="/api/v1")
app.include_router(health.router, prefix="/api/v1")