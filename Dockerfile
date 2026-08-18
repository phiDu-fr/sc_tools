FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 1. Installation des utilitaires (incluant gcc pour Radio France)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    netcat-openbsd \
    xmlstarlet \
    avahi-utils \
    openssh-client \
    procps \
    hostname \
    iputils-ping \
    dnsutils \
    util-linux \
    dosfstools \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 2. Copie de l'exécutable Docker officiel
COPY --from=docker:cli /usr/local/bin/docker /usr/local/bin/

# 3. Installation manuelle de ttyd (Dashboard Tools)
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then TTYD_ARCH="x86_64"; \
    elif [ "$ARCH" = "aarch64" ]; then TTYD_ARCH="aarch64"; \
    elif [ "$ARCH" = "armv7l" ] || [ "$ARCH" = "armv6l" ]; then TTYD_ARCH="armhf"; \
    else TTYD_ARCH="i686"; fi && \
    curl -sSL -o /usr/local/bin/ttyd https://github.com/tsl0922/ttyd/releases/download/1.7.4/ttyd.${TTYD_ARCH} && \
    chmod +x /usr/local/bin/ttyd

EXPOSE 80 8080 8081
CMD ["python", "app.py"]