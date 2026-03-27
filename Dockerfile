FROM python:3.11-slim

# Install system dependencies for lxml / python-docx if needed
RUN apt-get update && apt-get install -y \
    build-essential \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app
COPY . .

# Cloud Run uses the PORT environment variable
ENV PORT=8080
EXPOSE 8080

# Run streamlit
CMD streamlit run app.py --server.port=${PORT} --server.address=0.0.0.0
