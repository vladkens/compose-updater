TAG = compose-updater

dev:
	uvicorn app:app --host 127.0.0.1 --port 8080 --reload

docker-build:
	docker build -t $(TAG) .
	docker images -q $(TAG) | xargs docker inspect -f '{{.Size}}' | xargs numfmt --to=iec
