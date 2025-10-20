FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Ollama
RUN curl -fsSL https://ollama.ai/install.sh | sh

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY week5_assignment.py .
COPY .env.example .env

# Create necessary directories
RUN mkdir -p /app/rag_storage /app/download_folder

# Expose port for Gradio
EXPOSE 7860

# Create start script
RUN echo '#!/bin/bash\n\
# Start Ollama in background\n\
ollama serve &\n\
\n\
# Wait for Ollama to be ready\n\
echo "Waiting for Ollama to start..."\n\
while ! curl -s http://localhost:11434/api/tags > /dev/null; do\n\
    sleep 1\n\
done\n\
\n\
# Pull required models\n\
echo "Pulling Ollama models..."\n\
ollama pull nomic-embed-text:latest\n\
ollama pull llama3.2:3b\n\
\n\
# Start the application\n\
echo "Starting Google Drive RAG System..."\n\
python week5_assignment.py\n\
' > /app/start.sh && chmod +x /app/start.sh

# Set environment variables
ENV PYTHONPATH=/app
ENV SERVER_HOST=0.0.0.0
ENV SERVER_PORT=7860

CMD ["/app/start.sh"]