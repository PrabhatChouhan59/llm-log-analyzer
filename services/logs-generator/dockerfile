# -----------------------------------------------------------
# Dockerfile for log-generator service
# -----------------------------------------------------------
# A Dockerfile is like a recipe to build a container image.
# Each instruction (FROM, RUN, COPY, etc.) adds a "layer".

# Step 1: Start from an official Python image (slim = smaller size)
FROM python:3.11-slim

# Step 2: Set the working directory inside the container
#         All subsequent commands will run from /app
WORKDIR /app

# Step 3: Copy requirements file first (Docker caches this layer)
#         If requirements haven't changed, Docker skips reinstalling
COPY requirements.txt .

# Step 4: Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Step 5: Copy all source code into the container
COPY . .

# Step 6: Tell Docker which ports this container listens on
#   Port 5000 = Flask web server (log API)
#   Port 8000 = Prometheus metrics endpoint
EXPOSE 5000 8000

# Step 7: The command to run when the container starts
CMD ["python", "app.py"]
