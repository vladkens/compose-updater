# compose-updater

Simple webhook based updater for Docker Compose images inspired by [containrrr/watchtower](https://github.com/containrrr/watchtower) and [umputun/updater](https://github.com/umputun/updater). Has preshiped setup to work with Amazon ECR.

## Usage

Add `compose-updater` to Docker Compose file:

```
name: my-project

services:
  web:
    image: nginx
    ports:
    - 80:80

  compose-updater:
    image: ghcr.io/vladkens/compose-updater:latest
    container_name: compose-updater
    restart: always
    environment:
      - API_KEY=1234
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    ports:
      - 8080:8080
```

Run update of given service from CI environment:

```sh
curl -H "x-api-key: 1234" https://example.com:8080/update/my-project/web
```
