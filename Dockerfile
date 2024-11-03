FROM python:3.13-alpine
WORKDIR /app

ENV PIP_NO_CACHE_DIR=off PYTHONUNBUFFERED=1
RUN pip install --upgrade pip && apk add --no-cache docker-credential-ecr-login
RUN mkdir -p /root/.docker && echo '{ "credsStore": "ecr-login" }' > /root/.docker/config.json

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

ENV HOST=0.0.0.0 PORT=8080
EXPOSE ${PORT}
HEALTHCHECK CMD wget --no-verbose --tries=1 --spider http://127.0.0.1:${PORT}/health || exit 1
CMD uvicorn app:app --host ${HOST} --port ${PORT}
