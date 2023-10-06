# Change these for your environment
ENV ?= "-dev0"
IMG ?= ui${ENV}
.PHONY: docker-build
docker-build:
	docker buildx build --platform linux/amd64 --load -t  ${IMG} .

.PHONY: docker-push
docker-push:
	docker push ${IMG}
