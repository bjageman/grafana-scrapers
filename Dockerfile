# syntax=docker/dockerfile:1
FROM python:3.12-slim

# Install git (required for pip installing git repos) and curl (to fetch supercronic)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install supercronic v0.2.44
ENV SUPERCRONIC_URL=https://github.com/aptible/supercronic/releases/download/v0.2.44/supercronic-linux-amd64 \
    SUPERCRONIC_SHA1SUM=6eb0a8e1e6673675dc67668c1a9b6409f79c37bc \
    SUPERCRONIC=supercronic-linux-amd64

RUN curl -fsSLO "$SUPERCRONIC_URL" && \
    echo "${SUPERCRONIC_SHA1SUM}  ${SUPERCRONIC}" | sha1sum -c - && \
    chmod +x "$SUPERCRONIC" && \
    mv "$SUPERCRONIC" /usr/local/bin/supercronic

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy all scripts
COPY scripts/ /app/scripts/

# Copy crontab
COPY crontab /etc/crontab
RUN chmod 0644 /etc/crontab

# Run supercronic pointing to our crontab
CMD ["supercronic", "/etc/crontab"]
