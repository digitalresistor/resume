FROM ubuntu:24.04

RUN apt-get update && \
    env DEBIAN_FRONTEND=noninteractive TZ="America/Los_Angeles" apt-get install -y texlive-binaries texlive-fonts-extra texlive-formats-extra texlive-latex-base

WORKDIR /data
