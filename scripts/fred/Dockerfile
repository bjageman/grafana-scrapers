# syntax=docker/dockerfile:1
FROM python:3.12-slim

# Install supercronic v0.2.44
ENV SUPERCRONIC_URL=https://github.com/aptible/supercronic/releases/download/v0.2.44/supercronic-linux-amd64 \
    SUPERCRONIC_SHA1SUM=6eb0a8e1e6673675dc67668c1a9b6409f79c37bc \
    SUPERCRONIC=supercronic-linux-amd64

RUN apt-get update && apt-get install -y curl && \
    curl -fsSLO "$SUPERCRONIC_URL" && \
    echo "${SUPERCRONIC_SHA1SUM}  ${SUPERCRONIC}" | sha1sum -c - && \
    chmod +x "$SUPERCRONIC" && \
    mv "$SUPERCRONIC" /usr/local/bin/supercronic && \
    apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app/.

RUN pip install --no-cache-dir -r /app/requirements.txt

# Create runtime dirs + full crontab
RUN mkdir -p /var/log

# ARG for cron schedule - set in docker-compose.yml build args
ARG CRON_SCHEDULE
RUN echo "SHELL=/bin/sh" > /etc/crontab && \
    touch "/var/log/cron.log" && \
    echo "PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin" >> /etc/crontab && \
    echo "${CRON_SCHEDULE} python3 -u /app/main.py >> /var/log/cron.log 2>&1" >> /etc/crontab && \
    chmod 0644 /etc/crontab /var/log/cron.log

CMD ["sh", "-c", "supercronic /etc/crontab & tail -f /var/log/cron.log"]