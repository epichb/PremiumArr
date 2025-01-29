FROM python:3.9-slim

# Install essential packages for creating users
RUN apt-get update && apt-get install -y --no-install-recommends \
    passwd procps && \
    rm -rf /var/lib/apt/lists/*

# Create a non-root user with UID/GID 1000
RUN groupadd -g 1000 appgroup && \
    useradd -m -u 1000 -g appgroup -s /bin/bash appuser

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src
COPY main.py .

RUN chown -R appuser:appgroup /app
USER appuser

CMD ["python", "-u", "main.py"]
