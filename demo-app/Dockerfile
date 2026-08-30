# Use an official lightweight Python image
# Build arg for CI/CD image tagging (set by Jenkins: --build-arg IMAGE_TAG=$GIT_COMMIT)
ARG IMAGE_TAG=latest
FROM python:3.9-slim-buster AS build

WORKDIR /app

# Install dependencies in a virtualenv for isolation
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.9-slim-buster

# Create a non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app
COPY --from=build /opt/venv /opt/venv

# Make sure we use the virtualenv
ENV PATH="/opt/venv/bin:$PATH"

COPY app.py .

# Switch to non-root
USER appuser

EXPOSE 5000

# Label for CI/CD build traceability
ARG IMAGE_TAG
LABEL version="${IMAGE_TAG}" project="horizontal-pod-scaler" service="demo-app"

# We use gunicorn with threads for production-like load handling
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "8", "app:app"]
