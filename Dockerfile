FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    BROWSER_HEADLESS=true \
    HOST=0.0.0.0 \
    PORT=8000

WORKDIR /app

# Install system utilities needed for Playwright dependency management
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    wget \
    gnupg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium and required OS shared libraries
RUN playwright install --with-deps chromium

# Copy application source code
COPY . .

# Ensure data and runs directories exist
RUN mkdir -p data runs

# Expose port (Render overrides with $PORT dynamically)
EXPOSE 8000

# Run entrypoint
CMD ["python", "run.py"]
