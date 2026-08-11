FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends openjdk-17-jdk-headless maven \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir pytest coverage

RUN useradd --create-home --shell /usr/sbin/nologin codeoracle \
    && mkdir -p /sandbox \
    && chown -R codeoracle:codeoracle /sandbox

USER codeoracle
WORKDIR /sandbox
