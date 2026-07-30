FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
# tests live next to the modules (foo_test.py); keep them out of the image
RUN find src -name '*_test.py' -delete && pip install --no-cache-dir .

ENTRYPOINT ["rotato"]
