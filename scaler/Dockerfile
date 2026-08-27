# Use an official lightweight Python image
FROM python:3.9-slim-buster

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# We need grpcio-tools to compile the proto file during build
RUN pip install grpcio-tools==1.62.1

COPY proto/externalscaler.proto proto/
RUN python -m grpc_tools.protoc -I proto --python_out=proto --grpc_python_out=proto proto/externalscaler.proto

COPY main.py .

EXPOSE 50051

# Switch to non-root
RUN groupadd -r appuser && useradd -r -g appuser appuser
USER appuser

CMD ["python", "main.py"]
