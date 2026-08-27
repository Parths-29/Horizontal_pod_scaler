# Use an official lightweight Python image
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

# We use gunicorn with threads for production-like load handling
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "8", "app:app"]
