import os
import glob
import json
import gradio as gr
from dotenv import load_dotenv
import pickle
import io
import mammoth
import PyPDF2
from typing import List, Dict
import requests

import ollama
import chromadb
from chromadb.config import Settings
from pathlib import Path

import colorlog
import logging
from googleapiclient.http import MediaIoBaseDownload
import docx
import shutil
import math
from collections import Counter
from tqdm import tqdm
import argparse
# Configuration Constants
G_DOWNLOAD_FOLDER = os.getenv('DOWNLOAD_FOLDER', './download_folder')
# Supported MIME types
MIME_TYPES = [
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # .docx
    'application/msword',  # .doc
    'application/pdf'  # .pdf
]


# Create a colored logger
handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(
    '%(log_color)s%(levelname)-8s%(reset)s %(blue)s%(message)s',
    datefmt=None,
    reset=True,
    log_colors={
        'DEBUG':    'cyan',
        'INFO':     'green',
        'WARNING':  'yellow',
        'ERROR':    'red',
        'CRITICAL': 'red,bg_white',
    }
))

logger = colorlog.getLogger()
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Configuration from environment variables
CREDENTIALS_PATH = os.getenv('GOOGLE_CREDENTIALS_PATH', 'credentials.json')
PERSIST_DIRECTORY = os.getenv('PERSIST_DIRECTORY', './rag_storage')
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'nomic-embed-text:latest')
LLM_MODEL = os.getenv('LLM_MODEL', 'llama3.2:3b')
SERVER_PORT = int(os.getenv('SERVER_PORT', '7860'))
SERVER_HOST = os.getenv('SERVER_HOST', '127.0.0.1')

# Additional imports
from langchain_community.embeddings import OllamaEmbeddings

import matplotlib.pyplot as plt
from sklearn.manifold import TSNE
import numpy as np
import plotly.graph_objects as go
from langchain.chains import ConversationalRetrievalChain
from langchain_huggingface import HuggingFaceEmbeddings

## Google Auth
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import PyPDF2




# Load environment variables in a file called .env

#load_dotenv(override=True)
#os.environ['OPENAI_API_KEY'] = os.getenv('OPENAI_API_KEY', 'your-key-if-not-using-env')


# Load environment variables
load_dotenv()

# Get current working directory
cwd = os.getcwd()
print(f"Current working directory: {cwd}")

class FileTracker:
    def __init__(self, tracker_file='processed_files.json'):
        self.tracker_file = tracker_file
        self.processed_files = self.load_tracker()
    
    def load_tracker(self):
        """Load previously processed files"""
        if os.path.exists(self.tracker_file):
            try:
                # Check if file is empty first
                if os.path.getsize(self.tracker_file) == 0:
                    return {}
                
                with open(self.tracker_file, 'r') as f:
                    content = f.read().strip()
                    if not content:
                        return {}
                    return json.loads(content)
            except (json.JSONDecodeError, ValueError) as e:
                logger.info(f"⚠️  Tracker file corrupted: {e}")
                logger.info("   Starting fresh...")
                # Backup corrupted file
                os.rename(self.tracker_file, f"{self.tracker_file}.backup")
                return {}
        return {}
    
    def save_tracker(self):
        """Save processed files to disk"""
        with open(self.tracker_file, 'w') as f:
            json.dump(self.processed_files, f, indent=2)
    
    def is_processed(self, file_id):
        """Check if file already processed"""
        return file_id in self.processed_files
    
    def mark_processed(self, file_id, filename, num_chunks):
        """Mark file as processed"""
        self.processed_files[file_id] = {
            'filename': filename,
            'num_chunks': num_chunks,
            'status': 'completed'
        }
        self.save_tracker()
    
    def mark_failed(self, file_id, filename, error):
        """Mark file as failed"""
        self.processed_files[file_id] = {
            'filename': filename,
            'status': 'failed',
            'error': str(error)
        }
        self.save_tracker()
    
    def get_stats(self):
        """Get processing statistics"""
        total = len(self.processed_files)
        completed = sum(1 for f in self.processed_files.values() if f['status'] == 'completed')
        failed = sum(1 for f in self.processed_files.values() if f['status'] == 'failed')
        return {'total': total, 'completed': completed, 'failed': failed}
    
    def reset(self):
        """Clear all tracking (start fresh)"""
        self.processed_files = {}
        self.save_tracker()


class GoogleDriveRAG:
    """
    Complete pipeline: Google Drive → Download → Extract → Chunk → Embed → VectorDB
    """
    def __init__(self, reset_db=False): 
        self.service = None
        self.collection = None
        self.llm_model = LLM_MODEL
        self.embedding_model = EMBEDDING_MODEL
        self.persist_directory = PERSIST_DIRECTORY
        self.is_authenticated = False
        self.filelist = []
        
        #self.embeddings = OllamaEmbeddings(model=self.embedding_model)
        #self.llm = Ollama(model=self.llm_model)
        
        logger.info("🚀 Initializing Google Drive RAG Pipeline")
        if reset_db:
            logger.info("🚀 Resetting Chroma/Vector DB")
            
            if os.path.exists(self.persist_directory):
                shutil.rmtree(self.persist_directory)
                logger.info("🚀 Chroma/Vector deleted")
            
        self._init_chromadb()
        
    
    def _init_chromadb(self):
        """Initialize ChromaDB"""
        logger.info("Init ChromaDB")

        self.client = chromadb.PersistentClient(path=self.persist_directory)
        self.collection = self.client.get_or_create_collection(
            name="gdrive_documents",
            metadata={"description": "Documents from Google Drive", "hnsw:space": "cosine"},
        )

   
    def is_file_encrypted(self, file_handle):
        """
        Check if a PDF file is encrypted.
        Returns True if encrypted, False otherwise.
        """
        logger.info("Checking if PDF is encrypted")
        try:
            pdf = PyPDF2.PdfReader(file_handle)
            if pdf.is_encrypted:
                logger.warn("Result: ENCRYPTED ✓")
                return True
            else:
                logger.info("Result: NOT ENCRYPTED ✗")
                return False
        except Exception as e:
            logger.warning(f"Error checking encryption: {e}")
            return False
        
    def is_file_encrypted2(self, file_path):
        """
        Simple check if a file is encrypted based on entropy.
        Returns True if likely encrypted, False otherwise.
        """
        logger.info(f"Checking encryption for file: {file_path}")
        try:
            # Read first 10KB of file
            with open(file_path, 'rb') as f:
                data = f.read(10000)
        
            if not data:
                print("File is empty")
                return False
        
        # Calculate entropy (randomness)
            counter = Counter(data)
            length = len(data)
            
            entropy = 0
            for count in counter.values():
                p = count / length
                entropy -= p * math.log2(p)
            
            logger.info(f"File: {file_path}")
            print(f"Entropy: {entropy:.2f}/8.0")
            
            # Encrypted files have entropy > 7.5
            if entropy > 7.5:
                logger.info("Result: LIKELY ENCRYPTED ✓")
                return True
            else:
                logger.info("Result: NOT ENCRYPTED ✗")
                return False
                
        except Exception as e:
            logger.error(f"Error: {e}")
        return False
    
    def authenticate_gdrive(self, credentials_path=None):
        """Authenticate with Google Drive"""
        if credentials_path is None:
            credentials_path = CREDENTIALS_PATH
            
        logger.info("Google Drive Auth in progress")
        try:
            if not os.path.exists(credentials_path):
                error_msg = f"❌ Error: {credentials_path} not found. Please upload it first."
                logger.error(error_msg)
                return error_msg
            
            SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
            creds = None
            
            if os.path.exists('token.pickle'):
                with open('token.pickle', 'rb') as token:
                    creds = pickle.load(token)
            
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        credentials_path, SCOPES)
                    creds = flow.run_local_server(port=0)
                
                with open('token.pickle', 'wb') as token:
                    pickle.dump(creds, token)
            
            self.service = build('drive', 'v3', credentials=creds)
            self.is_authenticated = True
            logger.info("Google Drive Auth successful")

            return "✅ Successfully authenticated with Google Drive!"
        except Exception as e:
            error_msg = f"❌ Authentication failed: {str(e)}"
            logger.error(error_msg)
            return error_msg
        
    
    def get_file_id_from_url(self, url):
        """
        Extract file ID from Google Drive URL
        
        Args:
            url: Google Drive URL or file ID
        
        Returns:
            File ID string
        
        Examples:
            https://drive.google.com/file/d/1ABC123/view → 1ABC123
            1ABC123 → 1ABC123 (returns as-is if already an ID)
        """
        if '/d/' in url:
            return url.split('/d/')[1].split('/')[0]
        elif 'id=' in url:
            return url.split('id=')[1].split('&')[0]
        else:
            return url  # Assume it's already a file ID
        


    def is_authenticated(self):
        """ Check if authenticated with Google Drive"""
        return self.is_authenticated
        
        
    def process_file2(self, file_id_or_url, chunk_size=1000, overlap=100):
        """
        Complete pipeline: Download → Extract → Chunk → Embed → Store
        
        Args:
            file_id_or_url: Google Drive file ID or URL
            chunk_size: Characters per chunk
            overlap: Overlap between chunks
        """
        if not self.is_authenticated:
            print("❌ Not authenticated. Call authenticate() first.")
            return None
    def return_llm(self):
        """ Return LLM """
        return self.llm_model
    
    def Get_list_files(self, page_size=10, mtype=None, max_files=None):
        """List files in Google Drive"""
        file_types=['.pdf','.docx','.doc','.txt']
        file_mime_types = {
        '.pdf': "mimeType='application/pdf'",
        '.docx': "mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document'",
        '.doc': "mimeType='application/msword'",
        '.txt': "mimeType='text/plain'"
    }
        logger.info("Listing Google Drive files")
        type_file = []
        queries = [file_mime_types.get(ext) for ext in file_types if ext in file_mime_types]
        query = f"({' or '.join(queries)}) and trashed=false"
        page_token = None
        all_files = []
        while True:
                results = self.service.files().list(
                pageSize=page_size,
                pageToken=page_token,
                q=query,
                fields="nextPageToken, files(id, name, mimeType, modifiedTime, size)"
                ).execute()

                items = results.get('files', [])
                all_files.extend(items)
                for filename in items:
                    if filename['mimeType'] in mtype and Path(filename['name']).suffix not in ['.tmp'] \
                            and not filename['mimeType'] == 'NoneType':
                        all_files.append(filename)
                if max_files and len(all_files) >= max_files:
                    all_files = all_files[:max_files]
                    break
        
                page_token = results.get('nextPageToken', None) 
                if page_token is None:
                 logger.info("No more pages to fetch")
                break
        self.filelist = all_files
        logger.info(f"Found {len(all_files)} files to process")
        return all_files
        
        
    def tsns(self):
        """Visualize document embeddings using t-SNE"""
        result = self.collection.get(include=['embeddings', 'documents', 'metadatas'])
        
        if len(result['embeddings']) == 0:
            logger.warning("No embeddings found - collection is empty")
            return
            
        vectors = np.array(result['embeddings'])
        documents = result['documents']
        metadatas = result['metadatas']
        
        logger.info(f"Visualizing {len(vectors)} embeddings with t-SNE")
        
        # Extract document types from metadata (use filename if doc_type not available)
        doc_types = []
        for metadata in metadatas:
            if 'filename' in metadata:
                # Use file extension as type
                filename = metadata['filename']
                doc_type = filename.split('.')[-1] if '.' in filename else 'unknown'
                doc_types.append(doc_type)
            else:
                doc_types.append('unknown')
        
        # Create color mapping
        unique_types = list(set(doc_types))
        color_palette = ['blue', 'green', 'red', 'orange', 'purple', 'brown', 'pink', 'gray', 'cyan', 'magenta']
        color_map = {doc_type: color_palette[i % len(color_palette)] for i, doc_type in enumerate(unique_types)}
        colors = [color_map[doc_type] for doc_type in doc_types]
        
        # Configure t-SNE parameters based on data size
        n_samples = len(vectors)
        perplexity = min(30, max(5, n_samples // 3))  # Adjust perplexity for dataset size
        
        logger.info(f"Running t-SNE with perplexity={perplexity}")
        tsne = TSNE(
            n_components=2, 
            random_state=42, 
            perplexity=perplexity,
            max_iter=1000,
            learning_rate='auto'
        )
        
        reduced_vectors = tsne.fit_transform(vectors)
        
        # Create interactive scatter plot
        fig = go.Figure(data=[go.Scatter(
            x=reduced_vectors[:, 0],
            y=reduced_vectors[:, 1],
            mode='markers',
            marker=dict(size=8, color=colors, opacity=0.7),
            text=[f"File: {metadatas[i].get('filename', 'unknown')}<br>Chunk: {metadatas[i].get('chunk', 'N/A')}<br>Text: {d[:100]}..." 
                  for i, d in enumerate(documents)],
            hovertemplate='%{text}<extra></extra>',
            name='Documents'
        )])
        
        # Add legend for document types
        for doc_type in unique_types:
            fig.add_scatter(
                x=[None], y=[None],
                mode='markers',
                marker=dict(size=10, color=color_map[doc_type]),
                name=doc_type,
                showlegend=True
            )

        fig.update_layout(
            title=f't-SNE Visualization of {n_samples} Document Embeddings',
            xaxis_title='t-SNE Dimension 1',
            yaxis_title='t-SNE Dimension 2',
            width=1000,
            height=700,
            margin=dict(r=20, b=10, l=10, t=40),
            hovermode='closest'
        )   

        fig.show()
        logger.info("t-SNE visualization complete")


    def chunk_and_embed_pdf(self, pdf_path: str, 
                        chunk_size: int = 1000,
                        ) -> List[Dict]:
        
        logger.info("🚀 Commend Chunking")

        # Extract text from PDF
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            full_text = ""
        
            for page_num, page in enumerate(pdf_reader.pages):
                full_text += page.extract_text() + "\n"
    
        # Split into chunks
        chunks = []
        start = 0
    
        while start < len(full_text):
            end = start + chunk_size
        
        # Try to break at sentence boundary
            if end < len(full_text):
                chunk_text = full_text[start:end]
                last_period = chunk_text.rfind('.')
                if last_period > chunk_size * 0.5:
                    end = start + last_period + 1
        
            chunk_text = full_text[start:end].strip()

    def download_file(self, file_id,filename):
        logger.info(f"Downloading file {filename} from Google Drive")
        """
        Download file from Google Drive to memory
        
        Args:
            file_id: Google Drive file ID
        
        Returns:
            BytesIO object with file content
        """
        request = self.service.files().get_media(fileId=file_id)
        file_handle = io.BytesIO()
        downloader = MediaIoBaseDownload(file_handle, request)
        
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                logger.info(f"      Download {filename} {progress}%")
       
        
        print()  # New line after progress
        file_handle.seek(0)
        logger.info(f"Downloaded file {filename} successfully")
        logger.debug(f"Checking if file {filename} is encrypted")
        if self.is_file_encrypted(file_handle):
                logger.debug(f"⚠️  PDF file {filename} appears to be encrypted. Skipping.")
                return None
        return file_handle
    
    def chunk_text(self, text, file_id, document, chunk_size=1000):
        """Split text into chunks"""
        logger.info(f"Chunking Text from PDF: {file_id}")

        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size        
             # Try to break at sentence
            if end < len(text):
                piece = text[start:end]
                last_period = piece.rfind('.')
                if last_period > chunk_size * 0.5:
                     end = start + last_period + 1
                
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
                
            start = end - 100  # 100 char overlap
        logger.info(f"Chunking complete for {file_id}")
            
        return chunks
    def extract_pdf_text(self, file_bytes):
        """Extract text from PDF"""
        logger.info("Extracting text from PDF")
        try:  
            pdf = PyPDF2.PdfReader(file_bytes)
        except Exception as e:
            logger.warning(f"Error reading PDF: {str(e)}")
            return None
        text = ""
        for page in pdf.pages:
            try:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            except Exception as e:
                logger.warning(f"Error extracting text from page: {str(e)}")
                return None
        return text
    def extract_docx_text(self, file_bytes):
        """Extract text from DOCX"""
        logger.info("Extracting text from DOCX")
        if isinstance(file_bytes, io.BytesIO):
            file_bytes = file_bytes.getvalue()
        result = mammoth.extract_raw_text(file_bytes)
        text = result.value
        return text

    def extract_text(self, file_bytes,file_id,mime_type,filename):
        """Extract text from PDF"""
        #logger.info(f"Extracting text {filename} ")
        if mime_type == 'application/pdf':
            logger.info(f"Extracting Text from PDF: {file_id}:: {filename}")

            text = self.extract_pdf_text(file_bytes)
            return text
        elif mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
            logger.info(f"Extracting Text from docx: {file_id}")
            """
                Extract text from .docx file
            """
            text = self.extract_docx_text(file_bytes)
            return text
            
        elif mime_type == 'application/msword':
            logger.warning("⚠️  .doc files not supported. Please convert to .docx")
            return None
    
    def embed(self, text):
        #logger.info(f"Generating Embedding using Ollama:{self.embedding_model}") 

        response = ollama.embeddings(model=self.embedding_model, prompt=text)
        #logger.info(f"Generated Embedding len(embedding) {len(response['embedding'])}...") 

        return response['embedding']
    
    def process_files(self):
        """ 
        Pipeline Download -> Extract -> Chunk -> Embed -> Store
        """
        if not self.is_authenticated:
            print("❌ Not authenticated. Call authenticate() first.")
            return
        if not self.filelist:   
            print("❌ No files to process. Call Get_list_files() first.")
            return
        logger.info("Processing files from Google Drive")
        
        tracker = FileTracker()
        # If you want to ensure it's working
        logger.info(f"Loaded {len(tracker.processed_files)} previously processed files")
        # Show resume info
        stats = tracker.get_stats()
        if stats['total'] > 0:
            logger.info(f"📊 Resume mode: {stats['completed']} completed, {stats['failed']} failed")
            logger.info(f"   Processing remaining {len(self.filelist) - stats['completed']} files\n")

        #for file in self.filelist:
        for file in tqdm(self.filelist, desc="📁 Processing files", unit="file",position=0, colour="green"):
            file_info = self.service.files().get(fileId=file['id'], fields='name').execute()
            file_id = file['id']
            filename = file['name']
            mime_type = file['mimeType']           
            filename = file_info['name']

            if tracker.is_processed(file_id):
                logger.info(f"⏭️  Skipping {filename} (already processed)")
                continue

            if Path(filename).suffix not in ['.tmp']:
                try:
                    #Download
                    logger.info(f"Downloading  {file_id} == {filename}")
                    file_bytes = self.download_file(file_id,filename)
                    if file_bytes is None:
                        logger.warning(f"Skipping {filename} due to download/extraction error")
                        tracker.mark_failed(file_id, filename, "Download failed")
                        continue

                    #Extract
                    logger.info(f"Extract text  {file_id} == {filename}")
                    text = self.extract_text(file_bytes,file_id,mime_type,filename)
                    
                    
                    #Check if text extraction was successful
                    logger.info(f"Chunking text  {file_id} == {filename}")
                    chunks = self.chunk_text(text,file_id,filename, chunk_size=500)
                    #Embed and store with progress bar

                    logger.info(f"Embedding  {file_id} with Ollama: {filename} using model {self.embedding_model} with {len(chunks)} chunks")
                    embeddings = []
                    for chunk in tqdm(chunks, desc=f"  🔢 Embedding {filename[:30]}", 
                                    unit="chunk", 
                                    leave=False, 
                                    colour='blue'):
                        embedding = self.embed(chunk)
                        embeddings.append(embedding)
                    for i, (chunk, embedding) in enumerate(tqdm(zip(chunks, embeddings), 
                                                                total=len(chunks), 
                                                                desc=f"  💾 Storing {filename[:30]}", 
                                                                unit="chunk", 
                                                                leave=False,
                                                                colour="YELLOW")):
                    
                        self.collection.add(
                            embeddings=[embedding],
                            documents=[chunk],
                            metadatas=[{'filename': filename, 'chunk': i}],
                            ids=[f"{file_id}_{i}"]
                        )   
                    tracker.mark_processed(file_id, filename, len(chunks))
                        
                    logger.info(f"Finished processing {filename}")
                    logger.info(f"Stored {len(chunks)} chunks from {filename} in the database") 
                    logger.info(f"Database now has {self.collection.count()} documents")
                    logger.info("--------------------------------------------------")
                except Exception as e:
                    logger.error(f"Skipping {filename}:{e}")
                    tracker.mark_failed(file_id, filename, str(e))
                    continue
                
    def get_database_info(self):
        """Get current database statistics"""
        return self.collection.count()
    
    def query_with_rag(self, question, n_results=3):
        """Query the RAG system with a question"""
        logger.info(f"Querying RAG system with question: {question}")
        try:
            # Search for relevant documents
            query_embedding = self.embed(question)
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results
            )
            
            if not results['documents'] or not results['documents'][0]:
                return "No relevant documents found in the database."
            
            # Combine the retrieved documents
            context = "\n\n".join(results['documents'][0])
            logger.info(f"Retrieved {len(results['documents'][0])} relevant documents for context")
            logger.info(f"Context: {context}")
            logger.info(f"results: {results['documents'][0]}")
            logger.info("Generating answer using Ollama LLM")
            # Create prompt for Ollama
            prompt = f"""Based on the following context, answer the question. 
            If the context doesn't contain enough information to answer the question, say so clearly. 
            Provide all detail available from the context and use more than 500 words if needed. All sources *must* be cited at bottom of the response.

Context:
{context}

Question: {question}

Answer:"""

            # Call Ollama API
            response = ollama.generate(
                model=self.llm_model,
                prompt=prompt
            )
            
            return response['response']
            
        except Exception as e:
            return f"Error querying RAG system: {str(e)}"

    def chunk_and_embed(self,filelist,
                        chunk_size: int=1000):
        logger.info("Chunking and embed")                      
        ##Must call different method based on filetype
        #for file in filelist:
        #    if file['mimeType'] in 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
        #            self.process_file_doc(file['id'])
        #    elif file['mimeType'] in 'application/pdf':
        #        self.process_file(file['id'],file['mimeType'])
        for file in filelist:
            if file['mimeType'] in MIME_TYPES:
                self.process_file(file['id'],file['mimeType'])


    
def chat_with_ollama(drive,message, history):
    """
    Simple chat function that talks to Ollama
    """
    url = "http://localhost:11434/api/chat"
    
    # Build messages from history
    messages = []
    for human, assistant in history:
        messages.append({"role": "user", "content": human})
        messages.append({"role": "assistant", "content": assistant})
    
    # Add current message
    messages.append({"role": "user", "content": message})
    
    # Call Ollama
    llm = drive.return_llm()
    payload = {
            "model": llm,  # Change to your model
            "messages": messages,
            "stream": False
    }
    
    try:
        response = requests.post(url, json=payload)
        return response.json()['message']['content']
    except Exception as e:
        return f"Error: {str(e)}"


def create_gradio_interface(drive_instance):
    """Create and return a Gradio interface for the RAG system"""
    
    def authenticate_drive(credentials_file):
        """Handle Google Drive authentication"""
        if drive_instance.is_authenticated:
            return "✅ Already authenticated with Google Drive."
        else:
            if credentials_file is not None:
                with open("temp_credentials.json", "wb") as f:
                    f.write(credentials_file.read())
                    result = drive_instance.authenticate_gdrive("temp_credentials.json")
                    # Clean up temp file
                    if os.path.exists("temp_credentials.json"):
                        os.remove("temp_credentials.json")
                if result:
                    return "✅ Authentication successful!"
                else:
                    return "❌ Authentication failed."
            else:
                return "❌ Please upload credentials.json first."

        
    
    def list_and_process_files():
        """List and process files from Google Drive"""
        logger.info("Listing and processing files from Google Drive")
        if not drive_instance.is_authenticated:
            return "❌ Please authenticate first.", "0"
        
        try:
            files = drive_instance.Get_list_files(1000, MIME_TYPES)
            if not files:
                return "No supported files found in Google Drive.", "0"
            
            # Process files
            drive_instance.chunk_and_embed(files)
            count = drive_instance.get_database_info()
            
            file_list = "\n".join([f"✅ {f['name']} ({f['mimeType'].split('/')[-1]})" for f in files])
            return f"Processed {len(files)} files:\n{file_list}", str(count)
        except Exception as e:
            return f"❌ Error processing files: {str(e)}", "0"
    
    def get_db_count():
        """Get current database count"""
        logger.info("Getting DB count")
        try:
            logger.info(f"DB info {drive_instance.get_database_info()}")
            return str(drive_instance.get_database_info())
        except:
            return "0"
    
    def query_documents(question):
        """Query the RAG system"""
        if not question.strip():
            return "Please enter a question."
        
        if drive_instance.get_database_info() == 0:
            return "❌ No documents in database. Please process some files first."
        
        return drive_instance.query_with_rag(question)
    
    def show_visualization():
        """Generate and show t-SNE visualization"""
        try:
            if drive_instance.get_database_info() == 0:
                return "❌ No documents to visualize. Please process some files first."
            
            drive_instance.tsns()
            return "✅ Visualization generated! Check your browser/output window."
        except Exception as e:
            return f"❌ Error generating visualization: {str(e)}"
    
    # Create Gradio interface
    with gr.Blocks(title="Google Drive RAG System", theme=gr.themes.Soft()) as demo:
        gr.Markdown("""
        # 🚀 Google Drive RAG System
        ## Upload documents from Google Drive, process them with AI, and ask questions!
        """)
        
        with gr.Tab("🔐 Authentication"):
            gr.Markdown("### Step 1: Authenticate with Google Drive")
            gr.Markdown("""
            1. Download credentials.json from Google Cloud Console
            2. Upload it here to authenticate
            3. Complete OAuth flow in popup window
            """)
            
            credentials_file = gr.File(
                label="Upload credentials.json",
                file_types=[".json"],
                type="binary"
            )
            auth_btn = gr.Button("🔐 Authenticate", variant="primary")
            auth_status = gr.Textbox(label="Authentication Status", lines=3)
            
            auth_btn.click(
                authenticate_drive,
                inputs=[credentials_file],
                outputs=[auth_status]
            )
        
        with gr.Tab("📁 File Processing"):
            gr.Markdown("### Step 2: Process Documents")
            gr.Markdown("List and process PDF and DOCX files from your Google Drive")
            
            with gr.Row():
                process_btn = gr.Button("📥 List & Process Files", variant="primary")
                refresh_btn = gr.Button("🔄 Refresh Count")
            
            processing_status = gr.Textbox(label="Processing Status", lines=8)
            
            with gr.Row():
                db_count = gr.Textbox(label="Documents in Database", value=get_db_count())
                
            process_btn.click(
                list_and_process_files,
                outputs=[processing_status, db_count]
            )
            
            refresh_btn.click(
                get_db_count,
                outputs=[db_count]
            )
        
        with gr.Tab("❓ Ask Questions"):
            gr.Markdown("### Step 3: Query Your Documents")
            gr.Markdown("Ask questions about your processed documents using RAG")
            
            question_input = gr.Textbox(
                label="Your Question",
                placeholder="What is the main topic discussed in the documents?",
                lines=2
            )
            
            ask_btn = gr.Button("🤔 Ask Question", variant="primary")
            answer_output = gr.Textbox(label="Answer", lines=10)
            
            ask_btn.click(
                query_documents,
                inputs=[question_input],
                outputs=[answer_output]
            )
            
            gr.Examples(
                examples=[
                    "What are the main topics covered in the documents?",
                    "Can you summarize the key points?",
                    "What specific information is provided about [topic]?",
                    "Who are the main people or entities mentioned?",
                    "What are the conclusions or recommendations?"
                ],
                inputs=[question_input]
            )
        
        with gr.Tab("📊 Visualization"):
            gr.Markdown("### Step 4: Visualize Document Embeddings")
            gr.Markdown("Generate t-SNE visualization of your document embeddings")
            
            viz_btn = gr.Button("📊 Generate Visualization", variant="primary")
            viz_status = gr.Textbox(label="Visualization Status", lines=3)
            
            viz_btn.click(
                show_visualization,
                outputs=[viz_status]
            )
        
        with gr.Tab("ℹ️ System Info"):
            gr.Markdown("### System Information")
            gr.Markdown(f"""
            - **Embedding Model**: {drive_instance.embedding_model}
            - **LLM Model**: {drive_instance.llm_model}
            - **Storage**: {drive_instance.persist_directory}
            - **Supported Formats**: PDF, DOCX
            - **Chunk Size**: 1000 characters
            - **Overlap**: 100 characters
            """)
    
    return demo
def Raginit(reset=False, page_size=1000, max_files=None):
    """Initialize the RAG system with error handling"""
    try:
        drive = GoogleDriveRAG(reset_db=reset)
        auth_result = drive.authenticate_gdrive(CREDENTIALS_PATH)
        
        if "❌" in auth_result:
            logger.error(f"Authentication failed: {auth_result}")
            return None
            
        if reset:
            files = drive.Get_list_files(page_size=page_size, mtype=MIME_TYPES, max_files=max_files)
            if not files:
                logger.warning("No files found to process")
                return drive
            drive.process_files()
        return drive
    except Exception as e:
        logger.error(f"Failed to initialize RAG system: {str(e)}")
        return None
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process Google Drive files')
    parser.add_argument('--reset', action='store_true', help='Reset the database')
    parser.add_argument('--page_size', type=int, default=1000, help='Number of files to process per page')
    parser.add_argument('--max_files', type=int, default=None, help='Maximum number of files to process')
    parser.add_argument('--loglevel', type=str, default=None, help='Logging level (DEBUG, INFO, WARNING, ERROR)')
    args = parser.parse_args()
    if args.loglevel:
        logger.setLevel(args.loglevel)

    logger.info(f"{args.reset}")
    # Initialize the RAG system
    logger.info("🚀 Initializing Google Drive RAG Pipeline System")
    drive = Raginit(args.reset, args.page_size, args.max_files)
    
    if drive is None:
        logger.error("Failed to initialize RAG system. Exiting.")
        exit(1)
    
    # Create and launch the Gradio interface
    aboutme = create_gradio_interface(drive)
    
    # Launch with sharing enabled for remote access
    #logger.info("🌐 Launching Gradio interface...")
    if aboutme:
        aboutme.launch(
            share=False,
            server_name=SERVER_HOST,
            server_port=SERVER_PORT,
            show_error=True
        )
    else:
        logger.error("Failed to create Gradio interface")
        server_port=7860,
        show_error=True
    )