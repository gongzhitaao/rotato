FROM debian:bookworm-slim

# Pin to a known bws release. Check for newer:
# https://github.com/bitwarden/sdk-sm/releases
ARG BWS_VERSION=1.0.0
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl jq unzip \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL -o /tmp/bws.zip \
       "https://github.com/bitwarden/sdk-sm/releases/download/bws-v${BWS_VERSION}/bws-x86_64-unknown-linux-gnu-${BWS_VERSION}.zip" \
    && unzip /tmp/bws.zip -d /usr/local/bin \
    && chmod +x /usr/local/bin/bws \
    && rm /tmp/bws.zip

WORKDIR /app
COPY . /app
RUN chmod +x /app/rotato.sh
ENTRYPOINT ["/app/rotato.sh"]
