.PHONY: local-build local-run 

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

# If docker registry is not set, image name should exclude it
ifeq ($(DOCKER_REGISTRY),)
	IMAGE_NAME ?= $(DOCKER_IMAGE):$(DOCKER_TAG)
else
	IMAGE_NAME ?= $(DOCKER_REGISTRY)/$(PROJECT_NAME)/$(DOCKER_IMAGE):$(DOCKER_TAG)
endif

# Makefile commands #############################################################
# This is the default target that will be executed when running `make`
all: local-build

local-build:
	DOCKER_BUILDKIT=1 docker build --platform ${TARGETPLATFORM} -f Dockerfile -t $(DOCKER_IMAGE):$(DOCKER_TAG) --target services ./ \
	&& docker tag $(DOCKER_IMAGE):$(DOCKER_TAG) $(DOCKER_IMAGE):latest
# Run the container locally
local-run: local-build
	docker run --name $(DOCKER_IMAGE) -it --rm \
	$(PORTS) \
	$(IMAGE_NAME)

