import os
import io
import sys
import time
import argparse
import subprocess
from pathlib import Path

import docker
from docker.models.containers import Container
from docker.models.images import Image
from docker.errors import DockerException

try:
    CLIENT = docker.from_env()
except DockerException:
    print('[!] Docker daemon not running.')
    sys.exit(-1)

DK_FILE_PATH = Path(Path(__file__).parent / 'TestDockerfile')
BUILD_ARGS = {
    'ollama_model': 'gemma:7b',
    'ollama_endpoint': 'http://localhost:11434'
}


def run_docker_api(container: Container | None = None,
                   build_image: Image | None = None):
    print('### create')
    img = None
    if container:
        print('Container is provided')
        if not container.status == 'running':
            container.start()
    elif not container and build_image:
        print('Image is provided')
        img = build_image
    elif not container and not build_image:
        print('Building Image')
        with open(str(DK_FILE_PATH), 'r') as fp:
            dockerfile = fp.read()

        img, logs = CLIENT.images.build(
            fileobj=io.BytesIO(dockerfile.encode('utf-8')),
            tag='ai-ops:api-dev',
            rm=True,
            buildargs=BUILD_ARGS,
            pull=True,
        )

        for log in logs:
            if 'stream' in log:
                print(log['stream'], end='')

    if img:
        print('Run Container')
        _ = CLIENT.containers.run(
            img,
            name='ai-ops-api',
            tty=True,
            stdin_open=True,
            detach=True,
            ports={"8000/tcp": 8000}
        )

    print('Done')


# image gets built if we don't want to update it
# (`update` is False ) and it is not found
_update = False
_container = None
image = None
available_images = {image.tags[0]: image for image in CLIENT.images.list()}
if not _update and 'ai-ops:api-dev' in available_images.keys():
    print('Found Image for AI-OPS')
    image = available_images['ai-ops:api-dev']


# container is restarted if we don't want to update it
# (`update` is False ) and it is found, if not found run from image
available_containers = {ctr.attrs.get('Name'): ctr for ctr in CLIENT.containers.list(all=True)}
if not _update and '/ai-ops-api' in available_containers.keys():
    print('Found Container for AI-OPS')
    _container = available_containers['/ai-ops-api']

# delete existing container if it already exists
if _update and '/ai-ops-api' in available_containers.keys():
    ctr: Container = available_containers['/ai-ops-api']
    if ctr.status == 'running':
        ctr.stop()
    ctr.remove()

run_docker_api(container=_container, build_image=image)
