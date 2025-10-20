# Google Drive RAG System 🚀

A complete Retrieval-Augmented Generation (RAG) system that processes documents from Google Drive and enables intelligent question-answering using local LLMs via Ollama.

## Features

- 📁 **Google Drive Integration**: Automatically download and process PDF and DOCX files
- 🔍 **Intelligent Search**: Semantic search using vector embeddings
- 🤖 **Local LLM**: Uses Ollama for embeddings and text generation (privacy-focused)
- 💾 **Persistent Storage**: ChromaDB for vector storage with resume capability
- 🖥️ **Web Interface**: User-friendly Gradio interface
- 📊 **Visualization**: t-SNE embeddings visualization
- 🔐 **Security**: Encryption detection and secure file handling

## Prerequisites

- Python 3.8+
- [Ollama](https://ollama.ai) installed and running
- Google Cloud Console project with Drive API enabled
- Google Drive credentials.json file

## Installation

1. **Clone the repository**
```bash
git clone https://github.com/milo/google-drive-rag.git
cd google-drive-rag
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Install Ollama models**
```bash
ollama pull llama3.2:3b
ollama pull nomic-embed-text:latest
```

4. **Set up Google Drive API**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing
   - Enable Google Drive API
   - Create credentials (OAuth 2.0 Client ID)
   - Download credentials.json and place in project directory

## Configuration

Create a `.env` file in the project directory:

```env
# Google Drive
GOOGLE_CREDENTIALS_PATH=credentials.json

# Models
EMBEDDING_MODEL=nomic-embed-text:latest
LLM_MODEL=llama3.2:3b

# Storage
PERSIST_DIRECTORY=./rag_storage
DOWNLOAD_FOLDER=./download_folder

# Server
SERVER_HOST=127.0.0.1
SERVER_PORT=7860
```

## Usage

### Command Line Interface

**Basic usage:**
```bash
python week5_assignment.py
```

**Reset database and process files:**
```bash
python week5_assignment.py --reset
```

**Process limited number of files:**
```bash
python week5_assignment.py --reset --max_files 10
```

**Set logging level:**
```bash
python week5_assignment.py --loglevel DEBUG
```

### Web Interface

1. **Start the application**
2. **Navigate to Authentication tab**
   - Upload your credentials.json file
   - Complete OAuth authentication
3. **Process files in File Processing tab**
   - Click "List & Process Files"
   - Monitor progress
4. **Ask questions in Ask Questions tab**
   - Enter your question
   - Get AI-powered answers from your documents
5. **Visualize embeddings in Visualization tab**

## Architecture

### Components

- **FileTracker**: Tracks processed files to enable resume functionality
- **GoogleDriveRAG**: Main class handling the complete pipeline
- **Document Processing**: PDF and DOCX text extraction
- **Embedding Generation**: Using Ollama's nomic-embed-text model
- **Vector Storage**: ChromaDB for efficient similarity search
- **RAG Query**: Context-aware question answering

### Pipeline Flow

1. **Authentication**: OAuth with Google Drive
2. **File Discovery**: List supported files from Drive
3. **Download**: Retrieve files to memory
4. **Text Extraction**: Extract text from PDF/DOCX
5. **Chunking**: Split text into manageable chunks
6. **Embedding**: Generate vector embeddings
7. **Storage**: Store in ChromaDB
8. **Query**: RAG-based question answering

## File Structure

```
week5/
├── week5_assignment.py     # Main application
├── requirements.txt        # Python dependencies
├── README.md              # This file
├── .env                   # Environment variables (create this)
├── credentials.json       # Google Drive credentials (create this)
├── rag_storage/          # ChromaDB storage (auto-created)
├── processed_files.json  # File tracking (auto-created)
└── .gitignore            # Git ignore file
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| GOOGLE_CREDENTIALS_PATH | credentials.json | Path to Google Drive credentials |
| EMBEDDING_MODEL | nomic-embed-text:latest | Ollama embedding model |
| LLM_MODEL | llama3.2:3b | Ollama LLM for answers |
| PERSIST_DIRECTORY | ./rag_storage | ChromaDB storage directory |
| DOWNLOAD_FOLDER | ./download_folder | Temporary download folder |
| SERVER_HOST | 127.0.0.1 | Gradio server host |
| SERVER_PORT | 7860 | Gradio server port |

## Troubleshooting

### Common Issues

**Dimension mismatch error:**
- Delete `./rag_storage` folder and restart with `--reset`

**OAuth errors:**
- Ensure credentials.json is valid
- Check Google Cloud Console API enablement

**Ollama connection errors:**
- Verify Ollama is running: `ollama list`
- Ensure models are pulled: `ollama pull nomic-embed-text:latest`

**Memory issues:**
- Reduce `--max_files` parameter
- Process files in smaller batches

### Logs

Enable debug logging for troubleshooting:
```bash
python week5_assignment.py --loglevel DEBUG
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

[Add your license here]

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review logs with DEBUG level
3. Open an issue on GitHub