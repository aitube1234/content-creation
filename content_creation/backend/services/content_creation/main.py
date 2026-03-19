""" service entry point."""

from fastapi import FastAPI

app = FastAPI(title="")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "content_creation"}
