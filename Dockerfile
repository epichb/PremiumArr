FROM python:3-slim

# Install essential packages for creating users and supervisor
RUN apt-get update && apt-get install -y --no-install-recommends \
    passwd procps supervisor && \
    rm -rf /var/lib/apt/lists/*

# Create a non-root user with UID/GID 1000
RUN groupadd -g 1000 appgroup && \
    useradd -m -u 1000 -g appgroup -s /bin/bash appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY supervisord.conf .
COPY templates/ ./templates
COPY src/ ./src
COPY webserver.py .
COPY main.py .
COPY start_supervisord.sh .

RUN chown -R appuser:appgroup /app
USER appuser

CMD ["./start_supervisord.sh"]
