# API Docker File
FROM kalilinux/kali-rolling

RUN apt-get update && \
    apt-get install -y kali-linux-headless

# Setup environment
RUN mkdir "api"
WORKDIR /api

COPY . src
COPY . requirements.txt
COPY . tool_settings

# move tool settings to user home/.aiops/tools
# ...
# or soem way to add when running docker (...)
COPY . .env

RUN pip install -r requirements.txt

# run api





