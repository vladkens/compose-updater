import logging
import os
from typing import Annotated

import docker
from docker.models.containers import Container
from docker.models.images import Image
from docker.types.networks import EndpointConfig
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


def isid(image: Image):
    return image.short_id.split(":")[1]


def cfg_str(c_cfg: dict, i_cfg: dict, key: str) -> str:
    return "" if c_cfg[key] == i_cfg[key] else c_cfg[key]


def cfg_dict(c_cfg: dict, i_cfg: dict, key: str) -> dict:
    if not i_cfg[key]:
        return c_cfg[key]

    cfg = {}
    for k, v in c_cfg[key].items():
        if k not in i_cfg[key] or v != i_cfg[key][k]:
            cfg[k] = v

    return cfg


def cfg_list(c_cfg: dict, i_cfg: dict, key: str) -> list | None:
    return None if c_cfg[key] == i_cfg[key] else c_cfg[key]


def update_container(project: str, service: str):
    c = get_container(project, service)
    if not c:
        raise HTTPException(status_code=404, detail="Container not found")

    now_image = client.images.get(c.attrs["Config"]["Image"])
    if not now_image.tags:
        raise HTTPException(status_code=404, detail="Tags not found")

    tag = now_image.tags[0]
    new_image = client.images.pull(tag)
    if new_image.id == now_image.id:
        logger.info(f"Image {tag} is already up to date ({isid(now_image)})")
    else:
        logger.info(f"Image updated {tag}: {isid(now_image)} -> {isid(new_image)}")

    if c.attrs["Image"] == new_image.id:
        logger.info(f"Container {c.name} is already up to date ({c.short_id})")
        return

    logger.info(f"Restarting container {c.short_id}")

    c.stop()
    c.remove()

    # network_config: dict[str, EndpointConfig] = c.attrs["NetworkSettings"]["Networks"]
    # for v in network_config.values():
    #     v["Aliases"] = [x for x in v["Aliases"] if x != c.short_id]

    # https://github.com/containrrr/watchtower/blob/v1.7.1/pkg/container/container.go#L283
    # https://github.com/containrrr/watchtower/blob/v1.7.1/pkg/container/client.go#L248
    c_cfg, i_cfg = c.attrs["Config"], c.image.attrs["Config"]
    c = client.containers.run(
        detach=True,
        hostname="",
        name=c.name,
        image=c_cfg["Image"],
        user=cfg_str(c_cfg, i_cfg, "User"),
        working_dir=cfg_str(c_cfg, i_cfg, "WorkingDir"),
        environment=[x for x in c_cfg["Env"] if x not in i_cfg["Env"]],
        labels=cfg_dict(c_cfg, i_cfg, "Labels"),
        volumes=cfg_dict(c_cfg, i_cfg, "Volumes"),
        entrypoint=cfg_list(c_cfg, i_cfg, "Entrypoint"),
        command=cfg_list(c_cfg, i_cfg, "Cmd"),
        network_mode=c.attrs["HostConfig"]["NetworkMode"],
        ports=c.attrs["HostConfig"]["PortBindings"],
        # ports=cfg_dict(c_cfg, i_cfg, "ExposedPorts"),
        # network=list(network_config.keys())[0],
        # networking_config=network_config,
    )

    logger.info(f"Container {c.name} restarted ({c.short_id})")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/update/{project}/{service}")
async def update(project: str, service: str, x_api_key: Annotated[str, Header()]):
    if x_api_key != get_api_key():
        raise HTTPException(status_code=403, detail="Invalid API key")

    try:
        update_container(project, service)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail="Internal server error")

    return {"status": "ok"}
