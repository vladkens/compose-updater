import logging
import os
from typing import Annotated

import docker
from docker.models.containers import Container
from fastapi import FastAPI, Header, HTTPException
from loguru import logger


def get_api_key():
    key = os.environ.get("API_KEY", "").strip()
    if not key:
        raise HTTPException(status_code=500, detail="API_KEY is not set")
    return key


class EndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return msg.find("GET /health") == -1


# https://github.com/encode/starlette/issues/864#issuecomment-653076434
logging.getLogger("uvicorn.access").addFilter(EndpointFilter())


app = FastAPI(docs_url=None, redoc_url=None)
client = docker.from_env()


def get_container(project: str, service: str) -> Container | None:
    for c in client.containers.list():
        c_project = c.labels.get("com.docker.compose.project")
        c_service = c.labels.get("com.docker.compose.service")
        if c_project == project and c_service == service:
            return c

    return None


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/update/{project}/{service}")
async def update_image(project: str, service: str, x_api_key: Annotated[str, Header()]):
    if x_api_key != get_api_key():
        raise HTTPException(status_code=403, detail="Invalid API key")

    c = get_container(project, service)
    if not c:
        raise HTTPException(status_code=404, detail="Container not found")

    if not c.image:
        raise HTTPException(status_code=404, detail="Image not found")

    tags = c.image.tags
    if not tags:
        raise HTTPException(status_code=404, detail="Tags not found")

    di = client.images.pull(tags[0])
    if c.image.id == di.id:
        logger.info(f"Image {di.id} is already up to date")
        return {"status": "ok"}

    logger.info(f"Image updated from {c.image.id} to {di.id}")
    c.restart()

    return {"status": "ok"}
