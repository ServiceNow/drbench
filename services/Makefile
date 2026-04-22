.PHONY: local-build local-run amd64-build amd64-push multiarch-build multiarch-push

PROJECT_NAME ?= drbench-services

DOCKER_IMAGE ?= ${PROJECT_NAME}
# get docker tag from pyproject.toml if it exists
ifeq ($(wildcard pyproject.toml),)
	DOCKER_TAG ?= latest
else
	DOCKER_TAG := $(shell grep -E '^version\s*=' pyproject.toml | sed -E 's|^version = "([^"]*)"|\1|')
endif

## Ports configuration #####################################################
ROOT_HOST_PORT ?= 8080
NC_HOST_PORT ?= 8081
MM_HOST_PORT ?= 8082
VNC_HOST_PORT ?= 5901
NOVNC_HOST_PORT ?= 6080
FILEBROWSER_HOST_PORT ?= 8090
HEALTH_CHECK_PORT ?= 8099
ROUNDCUBE_PORT ?= 8085
MCP_NC_PORT ?= 9090

# Mapping of container ports to host ports for different services
PORTS ?= -p $(ROOT_HOST_PORT):8080 \
	-p $(NC_HOST_PORT):8081 \
	-p $(MM_HOST_PORT):8082 \
	-p $(VNC_HOST_PORT):5901 \
	-p $(NOVNC_HOST_PORT):6080 \
	-p $(FILEBROWSER_HOST_PORT):8090 \
	-p $(HEALTH_CHECK_PORT):8099 \
	-p $(ROUNDCUBE_PORT):8085 \
	-p $(MCP_NC_PORT):9090


# Docker basic configuration #################################################
TARGETPLATFORM ?= linux/arm64
TARGETARCH ?= $(shell basename $(TARGETPLATFORM))

# Registry prefix for remote image pushes (e.g. ghcr.io/servicenow)
DOCKER_REGISTRY ?=

# If docker registry is not set, image name should exclude it
ifeq ($(DOCKER_REGISTRY),)
	IMAGE_NAME ?= $(DOCKER_IMAGE):$(DOCKER_TAG)
else
	IMAGE_NAME ?= $(DOCKER_REGISTRY)/$(DOCKER_IMAGE):$(DOCKER_TAG)
endif

# Makefile commands #############################################################
all: local-build

# Build the services image for the local platform (default: arm64)
local-build:
	DOCKER_BUILDKIT=1 docker build --platform ${TARGETPLATFORM} -f Dockerfile -t $(DOCKER_IMAGE):$(DOCKER_TAG) --target services ./ \
	&& docker tag $(DOCKER_IMAGE):$(DOCKER_TAG) $(DOCKER_IMAGE):latest

# Run the container locally
local-run: local-build
	docker run --name $(DOCKER_IMAGE) -it --rm \
	$(PORTS) \
	$(IMAGE_NAME)

# Build the services image for amd64 (for remote deployment)
# Override DOCKER_REGISTRY to tag for a remote registry:
#   make amd64-build DOCKER_REGISTRY=ghcr.io/servicenow
amd64-build:
	DOCKER_BUILDKIT=1 docker build --platform linux/amd64 --target services \
		-t $(IMAGE_NAME) -f Dockerfile ./ && \
	docker tag $(IMAGE_NAME) $(DOCKER_IMAGE):latest-amd64

# Push the amd64 image to the configured registry
# Requires DOCKER_REGISTRY to be set:
#   make amd64-push DOCKER_REGISTRY=ghcr.io/servicenow
amd64-push: amd64-build
	docker push $(IMAGE_NAME)

# Buildx builder name (create with: docker buildx create --name my_builder --use)
BUILDX_BUILDER ?= my_builder

# Build multi-arch image (amd64 + arm64) and load to local Docker (one platform at a time)
# For local testing only — use multiarch-push to build+push both platforms at once.
multiarch-build:
	docker buildx build --builder $(BUILDX_BUILDER) --platform linux/arm64 \
		--target services -t $(DOCKER_IMAGE):$(DOCKER_TAG) -f Dockerfile --load ./
	docker buildx build --builder $(BUILDX_BUILDER) --platform linux/amd64 \
		--target services -t $(DOCKER_IMAGE):$(DOCKER_TAG)-amd64 -f Dockerfile --load ./

# Build and push multi-arch manifest (amd64 + arm64) to remote registry.
# Requires DOCKER_REGISTRY to be set:
#   make multiarch-push DOCKER_REGISTRY=ghcr.io/servicenow
multiarch-push:
ifeq ($(DOCKER_REGISTRY),)
	$(error DOCKER_REGISTRY is required for multiarch-push. Example: make multiarch-push DOCKER_REGISTRY=ghcr.io/servicenow)
endif
	docker buildx build --builder $(BUILDX_BUILDER) \
		--platform linux/amd64,linux/arm64 \
		--target services \
		-t $(DOCKER_REGISTRY)/$(DOCKER_IMAGE):$(DOCKER_TAG) \
		-t $(DOCKER_REGISTRY)/$(DOCKER_IMAGE):latest \
		-f Dockerfile --push ./
