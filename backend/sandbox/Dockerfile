FROM python:3.11-slim-bookworm

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV MAVEN_OPTS=-Xmx256m
ENV PATH=/usr/lib/jvm/java-17-openjdk-amd64/bin:$PATH

RUN apt-get update \
    && apt-get install -y --no-install-recommends openjdk-17-jdk-headless maven \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir pytest coverage pytest-cov

RUN useradd --create-home --shell /usr/sbin/nologin codeoracle

COPY parse_jacoco.py /opt/parse_jacoco.py

# Pre-populate the Maven local repository (offline at runtime) with everything
# the fixture projects need: JUnit 4, the Surefire/compiler plugins, and the
# JaCoCo agent + report plugin.
COPY offline-java /tmp/offline-java
RUN mvn -q -f /tmp/offline-java/pom.xml \
        verify \
        -Dmaven.repo.local=/home/codeoracle/.m2/repository \
    && rm -rf /tmp/offline-java \
    && chown -R codeoracle:codeoracle /home/codeoracle

USER codeoracle
WORKDIR /sandbox
