FROM ubuntu:20.04

RUN apt-get update && \
    env DEBIAN_FRONTEND=noninteractive TZ="America/Los_Angeles" apt-get install -y texlive-binaries texlive-fonts-extra texlive-formats-extra texlive-latex-base # && \
#    apt-get --purge remove -y .\*-doc$ && \
#    apt-get clean -y && \
#    apt-get autoremove && \
#    rm -rf /var/lib/apt/lists/*

WORKDIR /data
