# ==========================================
# ARQUIVO: code_rag.py (Sistema RAG principal)
# ==========================================

#!/usr/bin/env python3
"""
Sistema RAG para código - Versão Docker
Complete support for environment variables and volumes
"""

import os
import json
import requests
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Optional
import chromadb
from chromadb.config import Settings
import argparse
import sys
from datetime import datetime

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/data/coderag.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)

class DockerCodeRAGSystem:
    def __init__(self):
        """Initialize system with environment variable configurations"""
        
        # Configurações via environment variables
        self.ollama_host = os.getenv('OLLAMA_HOST', 'http://host.docker.internal:11434')
        self.embedding_model = os.getenv('EMBEDDING_MODEL', 'nomic-embed-text')
        self.chat_model = os.getenv('CHAT_MODEL', 'qwen2.5-coder')
        self.collection_name = os.getenv('COLLECTION_NAME', 'code_project')
        self.db_path = os.getenv('CHROMA_DB_PATH', '/chroma_db')
        self.chunk_size = int(os.getenv('CHUNK_SIZE', '1500'))
        self.max_context_chunks = int(os.getenv('MAX_CONTEXT_CHUNKS', '5'))
        self.temperature = float(os.getenv('TEMPERATURE', '0.1'))
        self.top_p = float(os.getenv('TOP_P', '0.9'))
        self.request_timeout = int(os.getenv('REQUEST_TIMEOUT', '120'))
        
        # Diretórios
        self.projects_dir = Path('/projects')
        self.data_dir = Path('/data')
        
        logger.info("🐳 Inicializando CodeRAG Docker System")
        logger.info(f"Ollama Host: {self.ollama_host}")
        logger.info(f"Embedding Model: {self.embedding_model}")
        logger.info(f"Chat Model: {self.chat_model}")
        logger.info(f"Collection: {self.collection_name}")
        
        # Inicializar ChromaDB
        self._init_chromadb()
        
        # Verificar conexão com Ollama
        self._check_ollama_connection()
        
    def _init_chromadb(self):
        """Initialize ChromaDB with optimized settings"""
        try:
            os.makedirs(self.db_path, exist_ok=True)
            
            self.client = chromadb.PersistentClient(
                path=self.db_path,
                settings=Settings(
                    anonymized_telemetry=False,
                    is_persistent=True
                )
            )
            
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            
            logger.info("✅ ChromaDB inicializado com sucesso")
            
        except Exception as e:
            logger.error(f"❌ Erro ao inicializar ChromaDB: {e}")
            sys.exit(1)
    
    def _check_ollama_connection(self):
        """Check Ollama connection"""
        max_retries = int(os.getenv('OLLAMA_RETRY_COUNT', '5'))
        retry_delay = int(os.getenv('OLLAMA_RETRY_DELAY', '10'))
        
        for attempt in range(max_retries):
            try:
                response = requests.get(f"{self.ollama_host}/api/tags", timeout=10)
                if response.status_code == 200:
                    logger.info("✅ Ollama conectado com sucesso")
                    
                    # Verificar se modelos estão disponíveis
                    models = response.json().get('models', [])
                    model_names = [m['name'] for m in models]
                    
                    if self.embedding_model not in str(model_names):
                        logger.warning(f"⚠️ Embedding model '{self.embedding_model}' not found")
                    
                    if self.chat_model not in str(model_names):
                        logger.warning(f"⚠️ Chat model '{self.chat_model}' not found")
                    
                    return
                    
            except requests.exceptions.RequestException as e:
                logger.warning(f"Tentativa {attempt + 1}/{max_retries} - Erro ao conectar: {e}")
                if attempt < max_retries - 1:
                    logger.info(f"Waiting {retry_delay}s before next attempt...")
                    import time
                    time.sleep(retry_delay)
        
        logger.error("❌ Could not connect to Ollama after multiple attempts")
        logger.info("💡 Dicas:")
        logger.info("   - Check if Ollama is running on host")  
        logger.info("   - Use --add-host=host.docker.internal:host-gateway no docker run")
        logger.info(f"   - Ou configure OLLAMA_HOST para: {self.ollama_host}")
        sys.exit(1)
    
    def get_embedding(self, text: str) -> List[float]:
        """Gera embedding usando Ollama"""
        try:
            response = requests.post(
                f"{self.ollama_host}/api/embeddings", 
                json={
                    "model": self.embedding_model,
                    "prompt": text
                }, 
                timeout=self.request_timeout
            )
            
            if response.status_code == 200:
                return response.json()["embedding"]
            else:
                logger.error(f"Erro ao gerar embedding: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Error in embedding request: {e}")
            return []
    
    def chunk_code_file(self, file_path: Path, chunk_size: int = None) -> List[Dict]:
        """Fragment code file intelligently"""
        if chunk_size is None:
            chunk_size = self.chunk_size
            
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Erro ao ler {file_path}: {e}")
            return []
        
        if not content.strip():
            return []
        
        extension = file_path.suffix.lower()
        chunks = []
        lines = content.split('\n')
        current_chunk = []
        current_size = 0
        chunk_metadata = {
            'file': str(file_path),
            'extension': extension,
            'functions': [],
            'classes': []
        }
        
        for i, line in enumerate(lines):
            line_size = len(line) + 1
            
            # Detectar funções e classes
            stripped_line = line.strip()
            if stripped_line.startswith(('def ', 'function ', 'const ', 'let ', 'var ', 'async function')):
                func_name = self._extract_function_name(stripped_line)
                if func_name:
                    chunk_metadata['functions'].append(func_name)
            elif stripped_line.startswith(('class ', 'interface ', 'type ')):
                class_name = self._extract_class_name(stripped_line)
                if class_name:
                    chunk_metadata['classes'].append(class_name)
            
            # Verificar se deve criar novo chunk
            if current_size + line_size > chunk_size and current_chunk:
                if not line.strip() or stripped_line.startswith(('def ', 'class ', 'function ', '}', 'export')):
                    chunks.append(self._create_chunk(current_chunk, file_path, chunk_metadata, len(chunks)))
                    current_chunk = [line] if line.strip() else []
                    current_size = line_size if line.strip() else 0
                    chunk_metadata = {
                        'file': str(file_path),
                        'extension': extension,
                        'functions': [],
                        'classes': []
                    }
                    continue
            
            current_chunk.append(line)
            current_size += line_size
        
        if current_chunk:
            chunks.append(self._create_chunk(current_chunk, file_path, chunk_metadata, len(chunks)))
        
        return chunks
    
    def _extract_function_name(self, line: str) -> Optional[str]:
        """Extract function name from line"""
        try:
            for keyword in ['def ', 'function ', 'const ', 'let ', 'var ', 'async function ']:
                if keyword in line:
                    after_keyword = line.split(keyword, 1)[1]
                    if '(' in after_keyword:
                        return after_keyword.split('(')[0].strip()
                    elif '=' in after_keyword:
                        return after_keyword.split('=')[0].strip()
        except:
            pass
        return None
    
    def _extract_class_name(self, line: str) -> Optional[str]:
        """Extract class name from line"""
        try:
            for keyword in ['class ', 'interface ', 'type ']:
                if keyword in line:
                    after_keyword = line.split(keyword, 1)[1]
                    name = after_keyword.split('(')[0].split(':')[0].split('{')[0].split('=')[0].strip()
                    return name
        except:
            pass
        return None
    
    def _create_chunk(self, lines: List[str], file_path: Path, metadata: Dict, chunk_id: int) -> Dict:
        """Create a chunk with metadata"""
        content = '\n'.join(lines)
        
        return {
            'content': content,
            'file': str(file_path),
            'chunk_id': chunk_id,
            'size': len(content),
            'lines': len(lines),
            'functions': metadata.get('functions', []),
            'classes': metadata.get('classes', []),
            'extension': metadata.get('extension', ''),
            'hash': hashlib.md5(content.encode()).hexdigest(),
            'indexed_at': datetime.now().isoformat()
        }
    
    def index_project(self, 
                     project_path: str, 
                     file_patterns: List[str] = None,
                     ignore_patterns: List[str] = None) -> Dict:
        """Index complete project"""
        
        # Patterns via environment variables
        if file_patterns is None:
            env_patterns = os.getenv('FILE_PATTERNS', '')
            if env_patterns:
                file_patterns = [p.strip() for p in env_patterns.split(',')]
            else:
                file_patterns = [
                    "*.py", "*.js", "*.ts", "*.jsx", "*.tsx", "*.vue",
                    "*.java", "*.cpp", "*.c", "*.h", "*.hpp", "*.cs",
                    "*.php", "*.rb", "*.go", "*.rs", "*.kt", "*.swift",
                    "*.sql", "*.json", "*.yaml", "*.yml", "*.toml",
                    "*.md", "*.txt", "*.dockerfile", "Dockerfile",
                    "requirements.txt", "package.json", "pom.xml",
                    "*.sh", "*.bash", "*.zsh"
                ]
        
        if ignore_patterns is None:
            env_ignore = os.getenv('IGNORE_PATTERNS', '')
            if env_ignore:
                ignore_patterns = [p.strip() for p in env_ignore.split(',')]
            else:
                ignore_patterns = [
                    "node_modules", ".git", "__pycache__", ".venv", "venv",
                    "build", "dist", ".pytest_cache", ".mypy_cache",
                    ".next", ".nuxt", "target", "bin", "obj", ".gradle",
                    "vendor", "composer.lock", "package-lock.json", "yarn.lock"
                ]
        
        # Resolve project path
        if not os.path.isabs(project_path):
            project_path = self.projects_dir / project_path
        else:
            project_path = Path(project_path)
        
        if not project_path.exists():
            error_msg = f"❌ Path not found: {project_path}"
            logger.error(error_msg)
            return {"error": error_msg, "indexed_chunks": 0}
        
        project_name = project_path.name
        logger.info(f"📁 Indexing project: {project_name} ({project_path})")
        
        # Collect files
        all_files = []
        for pattern in file_patterns:
            files = list(project_path.rglob(pattern))
            filtered_files = []
            for file_path in files:
                if any(ignore_dir in str(file_path) for ignore_dir in ignore_patterns):
                    continue
                if file_path.is_file() and file_path.stat().st_size > 0:
                    filtered_files.append(file_path)
            all_files.extend(filtered_files)
        
        logger.info(f"📄 Found {len(all_files)} files")
        
        # Process files
        total_chunks = 0
        processed_files = 0
        errors = []
        
        for file_path in all_files:
            try:
                logger.info(f"Processando: {file_path.name}")
                
                chunks = self.chunk_code_file(file_path)
                if not chunks:
                    logger.warning(f"No chunks generated for {file_path}")
                    continue
                
                # Gerar embeddings e adicionar ao banco
                for chunk in chunks:
                    embedding = self.get_embedding(chunk['content'])
                    if not embedding:
                        logger.warning(f"Failed to generate embedding for chunk from {file_path}")
                        continue
                    
                    chunk_id = f"{project_name}_{file_path.stem}_{chunk['chunk_id']}_{chunk['hash'][:8]}"
                    
                    try:
                        # Check if chunk already exists
                        existing = self.collection.get(ids=[chunk_id])
                        if existing['ids']:
                            logger.debug(f"Chunk {chunk_id} already exists, skipping...")
                            total_chunks += 1
                            continue
                        
                        self.collection.add(
                            embeddings=[embedding],
                            documents=[chunk['content']],
                            metadatas=[{
                                'file': chunk['file'],
                                'chunk_id': chunk['chunk_id'],
                                'size': chunk['size'],
                                'lines': chunk['lines'],
                                'functions': json.dumps(chunk['functions']),
                                'classes': json.dumps(chunk['classes']),
                                'extension': chunk['extension'],
                                'indexed_at': chunk['indexed_at'],
                                'project_name': project_name
                            }],
                            ids=[chunk_id]
                        )
                        total_chunks += 1
                        
                    except Exception as e:
                        error_msg = f"Error adding chunk from {file_path}: {e}"
                        logger.error(error_msg)
                        errors.append(error_msg)
                        continue
                
                processed_files += 1
                
            except Exception as e:
                error_msg = f"Error processing {file_path}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
                continue
        
        result = {
            "project_path": str(project_path),
            "project_name": project_name,
            "processed_files": processed_files,
            "total_files": len(all_files),
            "indexed_chunks": total_chunks,
            "errors": errors,
            "indexed_at": datetime.now().isoformat()
        }
        
        logger.info(f"🎉 Indexing completed!")
        logger.info(f"   📁 Files processed: {processed_files}/{len(all_files)}")
        logger.info(f"   📦 Total chunks: {total_chunks}")
        logger.info(f"   ❌ Erros: {len(errors)}")
        
        # Save indexing log
        log_file = self.data_dir / f"index_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(log_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        return result
    
    def search_code(self, query: str, n_results: int = None, project_filter: str = None) -> Dict:
        """Search relevant code for the query"""
        if n_results is None:
            n_results = self.max_context_chunks
            
        filter_info = f" (project: {project_filter})" if project_filter else ""
        logger.info(f"🔍 Buscando: '{query[:50]}...'{filter_info}")
        
        query_embedding = self.get_embedding(query)
        if not query_embedding:
            return {"documents": [[]], "metadatas": [[]]}
        
        try:
            # Build query parameters
            query_params = {
                "query_embeddings": [query_embedding],
                "n_results": n_results
            }
            
            # Add project filter if specified
            if project_filter:
                query_params["where"] = {"project_name": project_filter}
            
            results = self.collection.query(**query_params)
            
            logger.info(f"Found {len(results['documents'][0])} relevant chunks")
            return results
            
        except Exception as e:
            logger.error(f"Erro na busca: {e}")
            return {"documents": [[]], "metadatas": [[]]}
    
    def ask_question(self, question: str, context_size: int = None, project_filter: str = None) -> Dict:
        """Faz pergunta usando RAG"""
        if context_size is None:
            context_size = self.max_context_chunks
            
        start_time = datetime.now()
        
        # Buscar contexto relevante
        search_results = self.search_code(question, context_size, project_filter)
        
        if not search_results['documents'][0]:
            return {
                "question": question,
                "answer": "❌ No relevant code found. Make sure the project has been indexed.",
                "context_chunks": 0,
                "processing_time": 0,
                "error": "No relevant code found"
            }
        
        # Construir contexto
        context = "# Relevant code found:\n\n"
        context_info = []
        
        for i, (doc, metadata) in enumerate(zip(
            search_results['documents'][0], 
            search_results['metadatas'][0]
        )):
            file_path = metadata['file']
            functions = json.loads(metadata.get('functions', '[]'))
            classes = json.loads(metadata.get('classes', '[]'))
            
            context += f"## Arquivo: {file_path}\n"
            if functions:
                context += f"**Functions:** {', '.join(functions)}\n"
            if classes:
                context += f"**Classes:** {', '.join(classes)}\n"
            context += f"```{metadata.get('extension', '').replace('.', '')}\n{doc}\n```\n\n"
            
            context_info.append({
                "file": file_path,
                "functions": functions,
                "classes": classes,
                "chunk_size": len(doc)
            })
        
        # Gerar resposta
        prompt = f"""{context}

# Pergunta do usuário:
{question}

# Instruções:
- Analise APENAS o código fornecido acima
- Be precise and cite specific files/functions when relevant
- Se a informação não estiver no código fornecido, diga que precisa de mais contexto
- Forneça exemplos de código quando apropriado
- Responda em português quando possível

# Resposta:"""
        
        try:
            response = requests.post(
                f"{self.ollama_host}/api/generate", 
                json={
                    "model": self.chat_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": self.temperature,
                        "top_p": self.top_p
                    }
                }, 
                timeout=self.request_timeout
            )
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            if response.status_code == 200:
                answer = response.json()['response']
                
                result = {
                    "question": question,
                    "answer": answer,
                    "context_chunks": len(search_results['documents'][0]),
                    "context_info": context_info,
                    "processing_time": processing_time,
                    "model_used": self.chat_model,
                    "timestamp": datetime.now().isoformat()
                }
                
                logger.info(f"✅ Pergunta respondida em {processing_time:.2f}s")
                return result
            else:
                error_msg = f"Generation error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return {
                    "question": question,
                    "answer": f"❌ {error_msg}",
                    "context_chunks": len(search_results['documents'][0]),
                    "processing_time": processing_time,
                    "error": error_msg
                }
                
        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            error_msg = f"Request error: {e}"
            logger.error(error_msg)
            return {
                "question": question,
                "answer": f"❌ {error_msg}",
                "context_chunks": 0,
                "processing_time": processing_time,
                "error": error_msg
            }
    
    def get_stats(self) -> Dict:
        """Index statistics"""
        try:
            all_results = self.collection.get()
            total_chunks = len(all_results['ids'])
            
            if total_chunks == 0:
                return {
                    "total_chunks": 0,
                    "total_files": 0,
                    "extensions": {},
                    "collection_name": self.collection_name
                }
            
            files = set()
            extensions = {}
            functions_count = 0
            classes_count = 0
            total_size = 0
            
            for metadata in all_results['metadatas']:
                files.add(metadata['file'])
                ext = metadata.get('extension', 'unknown')
                extensions[ext] = extensions.get(ext, 0) + 1
                
                functions = json.loads(metadata.get('functions', '[]'))
                classes = json.loads(metadata.get('classes', '[]'))
                functions_count += len(functions)
                classes_count += len(classes)
                total_size += metadata.get('size', 0)
            
            return {
                "total_chunks": total_chunks,
                "total_files": len(files),
                "extensions": extensions,
                "functions_count": functions_count,
                "classes_count": classes_count,
                "total_size_bytes": total_size,
                "collection_name": self.collection_name,
                "average_chunk_size": total_size / total_chunks if total_chunks > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {"error": str(e)}
    
    def list_projects(self) -> List[str]:
        """List available projects in volume"""
        try:
            projects = []
            for item in self.projects_dir.iterdir():
                if item.is_dir() and not item.name.startswith('.'):
                    projects.append(item.name)
            return sorted(projects)
        except Exception as e:
            logger.error(f"Error listing projects: {e}")
            return []
    
    def get_indexed_projects(self) -> Dict:
        """Get list of indexed projects with statistics"""
        try:
            all_results = self.collection.get()
            
            if not all_results['metadatas']:
                return {"projects": {}}
            
            projects_stats = {}
            
            for metadata in all_results['metadatas']:
                project_name = metadata.get('project_name', 'unknown')
                
                if project_name not in projects_stats:
                    projects_stats[project_name] = {
                        "chunks": 0,
                        "files": set(),
                        "functions": 0,
                        "classes": 0
                    }
                
                projects_stats[project_name]["chunks"] += 1
                projects_stats[project_name]["files"].add(metadata.get('file', ''))
                
                functions = json.loads(metadata.get('functions', '[]'))
                classes = json.loads(metadata.get('classes', '[]'))
                projects_stats[project_name]["functions"] += len(functions)
                projects_stats[project_name]["classes"] += len(classes)
            
            # Convert sets to counts
            for project in projects_stats:
                projects_stats[project]["files"] = len(projects_stats[project]["files"])
            
            return {"projects": projects_stats}
            
        except Exception as e:
            logger.error(f"Error getting indexed projects: {e}")
            return {"projects": {}, "error": str(e)}
    
    def update_project_incremental(self, 
                                  project_path: str,
                                  file_patterns: List[str] = None,
                                  ignore_patterns: List[str] = None,
                                  force_update: bool = False) -> Dict:
        """
        Update project index incrementally - only process changed files.
        
        Args:
            project_path: Path to the project
            file_patterns: File patterns to include
            ignore_patterns: Patterns to ignore
            force_update: If True, reprocess all files regardless of modification time
            
        Returns:
            Dictionary with update statistics
        """
        
        # Use same default patterns as full indexing
        if file_patterns is None:
            env_patterns = os.getenv('FILE_PATTERNS', '')
            if env_patterns:
                file_patterns = [p.strip() for p in env_patterns.split(',')]
            else:
                file_patterns = [
                    "*.py", "*.js", "*.ts", "*.jsx", "*.tsx", "*.vue",
                    "*.java", "*.cpp", "*.c", "*.h", "*.hpp", "*.cs",
                    "*.php", "*.rb", "*.go", "*.rs", "*.kt", "*.swift",
                    "*.sql", "*.json", "*.yaml", "*.yml", "*.toml",
                    "*.md", "*.txt", "*.dockerfile", "Dockerfile",
                    "requirements.txt", "package.json", "pom.xml",
                    "*.sh", "*.bash", "*.zsh"
                ]
        
        if ignore_patterns is None:
            env_ignore = os.getenv('IGNORE_PATTERNS', '')
            if env_ignore:
                ignore_patterns = [p.strip() for p in env_ignore.split(',')]
            else:
                ignore_patterns = [
                    "node_modules", ".git", "__pycache__", ".venv", "venv",
                    "build", "dist", ".pytest_cache", ".mypy_cache",
                    ".next", ".nuxt", "target", "bin", "obj", ".gradle",
                    "vendor", "composer.lock", "package-lock.json", "yarn.lock"
                ]
        
        # Resolve project path
        if not os.path.isabs(project_path):
            project_path = self.projects_dir / project_path
        else:
            project_path = Path(project_path)
        
        if not project_path.exists():
            error_msg = f"❌ Path not found: {project_path}"
            logger.error(error_msg)
            return {"error": error_msg, "updated_chunks": 0}
        
        project_name = project_path.name
        logger.info(f"🔄 Incremental update for project: {project_name} ({project_path})")
        
        # Get current indexed files and their timestamps
        indexed_files_info = self._get_indexed_files_info(project_name)
        logger.info(f"📊 Found {len(indexed_files_info)} previously indexed files")
        
        # Collect current files
        current_files = []
        for pattern in file_patterns:
            files = list(project_path.rglob(pattern))
            filtered_files = []
            for file_path in files:
                if any(ignore_dir in str(file_path) for ignore_dir in ignore_patterns):
                    continue
                if file_path.is_file() and file_path.stat().st_size > 0:
                    filtered_files.append(file_path)
            current_files.extend(filtered_files)
        
        logger.info(f"📄 Found {len(current_files)} current files")
        
        # Determine files to update
        files_to_update = []
        files_to_remove = []
        new_files = []
        unchanged_files = []
        
        current_file_paths = {str(f.relative_to(project_path)): f for f in current_files}
        
        # Check for removed files
        for indexed_file in indexed_files_info.keys():
            if indexed_file not in current_file_paths:
                files_to_remove.append(indexed_file)
                logger.info(f"🗑️  File removed: {indexed_file}")
        
        # Check for new and modified files
        for rel_path, file_path in current_file_paths.items():
            file_mtime = file_path.stat().st_mtime
            
            if rel_path in indexed_files_info:
                indexed_mtime = indexed_files_info[rel_path]['mtime']
                if force_update or file_mtime > indexed_mtime:
                    files_to_update.append(file_path)
                    logger.info(f"🔄 File modified: {rel_path}")
                else:
                    unchanged_files.append(file_path)
            else:
                new_files.append(file_path)
                logger.info(f"🆕 New file: {rel_path}")
        
        # Remove chunks for deleted files
        removed_chunks = 0
        for file_to_remove in files_to_remove:
            removed_chunks += self._remove_file_chunks(project_name, file_to_remove)
        
        # Process new and modified files
        updated_chunks = 0
        processed_files = 0
        errors = []
        
        files_to_process = new_files + files_to_update
        
        if not files_to_process and not files_to_remove:
            logger.info("✅ No files need updating")
            return {
                "project_name": project_name,
                "status": "up_to_date",
                "processed_files": 0,
                "updated_chunks": 0,
                "removed_chunks": 0,
                "new_files": 0,
                "modified_files": 0,
                "removed_files": 0,
                "unchanged_files": len(unchanged_files)
            }
        
        logger.info(f"📝 Processing {len(files_to_process)} files...")
        
        for file_path in files_to_process:
            try:
                rel_path = str(file_path.relative_to(project_path))
                logger.info(f"Processing: {rel_path}")
                
                # Remove existing chunks for this file (if it's an update)
                if file_path in files_to_update:
                    removed_count = self._remove_file_chunks(project_name, rel_path)
                    logger.debug(f"Removed {removed_count} old chunks for {rel_path}")
                
                # Process file and add new chunks
                chunks = self.chunk_code_file(file_path)
                if not chunks:
                    logger.warning(f"No chunks generated for {file_path}")
                    continue
                
                file_mtime = file_path.stat().st_mtime
                
                # Generate embeddings and add to database
                for chunk in chunks:
                    embedding = self.get_embedding(chunk['content'])
                    if not embedding:
                        logger.warning(f"Failed to generate embedding for chunk from {file_path}")
                        continue
                    
                    chunk_id = f"{project_name}_{file_path.stem}_{chunk['chunk_id']}_{chunk['hash'][:8]}"
                    
                    try:
                        self.collection.add(
                            embeddings=[embedding],
                            documents=[chunk['content']],
                            metadatas=[{
                                'file': chunk['file'],
                                'chunk_id': chunk['chunk_id'],
                                'size': chunk['size'],
                                'lines': chunk['lines'],
                                'functions': json.dumps(chunk['functions']),
                                'classes': json.dumps(chunk['classes']),
                                'extension': chunk['extension'],
                                'indexed_at': chunk['indexed_at'],
                                'project_name': project_name,
                                'relative_path': rel_path,
                                'mtime': file_mtime
                            }],
                            ids=[chunk_id]
                        )
                        updated_chunks += 1
                        
                    except Exception as e:
                        error_msg = f"Error adding chunk {chunk_id}: {e}"
                        logger.error(error_msg)
                        errors.append(error_msg)
                
                processed_files += 1
                
            except Exception as e:
                error_msg = f"Error processing file {file_path}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        # Generate summary
        result = {
            "project_name": project_name,
            "status": "updated",
            "processed_files": processed_files,
            "updated_chunks": updated_chunks,
            "removed_chunks": removed_chunks,
            "new_files": len(new_files),
            "modified_files": len(files_to_update),
            "removed_files": len(files_to_remove),
            "unchanged_files": len(unchanged_files),
            "errors": errors
        }
        
        logger.info(f"✅ Incremental update complete:")
        logger.info(f"   📁 Project: {project_name}")
        logger.info(f"   📝 Processed files: {processed_files}")
        logger.info(f"   🆕 New files: {len(new_files)}")
        logger.info(f"   🔄 Modified files: {len(files_to_update)}")
        logger.info(f"   🗑️  Removed files: {len(files_to_remove)}")
        logger.info(f"   📊 Updated chunks: {updated_chunks}")
        logger.info(f"   🗑️  Removed chunks: {removed_chunks}")
        
        return result
    
    def _get_indexed_files_info(self, project_name: str) -> Dict[str, Dict]:
        """Get information about currently indexed files for a project."""
        try:
            # Query all chunks for this project
            results = self.collection.get(
                where={"project_name": project_name}
            )
            
            files_info = {}
            
            if results['metadatas']:
                for metadata in results['metadatas']:
                    rel_path = metadata.get('relative_path', metadata.get('file', ''))
                    mtime = metadata.get('mtime', 0)
                    
                    if rel_path not in files_info:
                        files_info[rel_path] = {
                            'mtime': mtime,
                            'chunks': 0
                        }
                    
                    files_info[rel_path]['chunks'] += 1
                    
                    # Keep the most recent mtime if there are multiple chunks
                    if mtime > files_info[rel_path]['mtime']:
                        files_info[rel_path]['mtime'] = mtime
            
            return files_info
            
        except Exception as e:
            logger.error(f"Error getting indexed files info: {e}")
            return {}
    
    def _remove_file_chunks(self, project_name: str, relative_path: str) -> int:
        """Remove all chunks for a specific file in a project."""
        try:
            # Find all chunks for this file
            results = self.collection.get(
                where={
                    "$and": [
                        {"project_name": project_name},
                        {"relative_path": relative_path}
                    ]
                }
            )
            
            if results['ids']:
                chunk_count = len(results['ids'])
                self.collection.delete(ids=results['ids'])
                logger.debug(f"Removed {chunk_count} chunks for {relative_path}")
                return chunk_count
            
            return 0
            
        except Exception as e:
            logger.error(f"Error removing chunks for {relative_path}: {e}")
            return 0
    
    def clear_collection(self):
        """Clear current collection"""
        try:
            self.client.delete_collection(self.collection_name)
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info("✅ Collection cleared successfully")
            return True
        except Exception as e:
            logger.error(f"Error clearing collection: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(description="RAG System for Code - Docker Version")
    parser.add_argument('command', choices=['index', 'update', 'ask', 'stats', 'list', 'projects', 'clear'], 
                       help='Comando a executar')
    parser.add_argument('--project', '-p', help='Project name (relative to /projects)')
    parser.add_argument('--question', '-q', help='Pergunta a fazer')
    parser.add_argument('--context', type=int, help='Number of context chunks')
    parser.add_argument('--output', '-o', choices=['json', 'text'], default='text',
                       help='Output format')
    parser.add_argument('--force', action='store_true', 
                       help='Force update all files (for update command)')
    
    args = parser.parse_args()
    
    # Inicializar sistema RAG
    try:
        rag = DockerCodeRAGSystem()
    except Exception as e:
        logger.error(f"Erro ao inicializar sistema: {e}")
        sys.exit(1)
    
    if args.command == 'index':
        if not args.project:
            print("❌ Use --project to specify project name")
            sys.exit(1)
        
        result = rag.index_project(args.project)
        
        if args.output == 'json':
            print(json.dumps(result, indent=2))
        else:
            if 'error' in result:
                print(result['error'])
            else:
                print(f"✅ Indexing completed: {result['indexed_chunks']} chunks")
    
    elif args.command == 'update':
        if not args.project:
            print("❌ Use --project to specify project name")
            sys.exit(1)
        
        result = rag.update_project_incremental(args.project, force_update=args.force)
        
        if args.output == 'json':
            print(json.dumps(result, indent=2))
        else:
            if 'error' in result:
                print(result['error'])
            elif result['status'] == 'up_to_date':
                print("✅ Project is already up to date - no changes needed")
            else:
                print(f"✅ Incremental update completed:")
                print(f"   📝 Processed files: {result['processed_files']}")
                print(f"   🆕 New files: {result['new_files']}")
                print(f"   🔄 Modified files: {result['modified_files']}")
                print(f"   🗑️  Removed files: {result['removed_files']}")
                print(f"   📊 Updated chunks: {result['updated_chunks']}")
                print(f"   🗑️  Removed chunks: {result['removed_chunks']}")
                if result.get('errors'):
                    print(f"   ⚠️  Errors: {len(result['errors'])}")
    
    elif args.command == 'ask':
        if not args.question:
            print("❌ Use --question para fazer uma pergunta")
            sys.exit(1)
        
        context_size = args.context if args.context else None
        result = rag.ask_question(args.question, context_size)
        
        if args.output == 'json':
            print(json.dumps(result, indent=2))
        else:
            print("\n" + "="*60)
            print("RESPOSTA:")
            print("="*60)
            print(result['answer'])
            print(f"\n📊 Chunks used: {result['context_chunks']}")
            print(f"⏱️ Tempo: {result['processing_time']:.2f}s")
    
    elif args.command == 'stats':
        stats = rag.get_stats()
        
        if args.output == 'json':
            print(json.dumps(stats, indent=2))
        else:
            print("\n📊 Index statistics:")
            print(f"   📦 Total chunks: {stats.get('total_chunks', 0)}")
            print(f"   📁 Total files: {stats.get('total_files', 0)}")
            print(f"   🔧 Indexed functions: {stats.get('functions_count', 0)}")
            print(f"   📋 Indexed classes: {stats.get('classes_count', 0)}")
            print("   📄 Extensions:")
            for ext, count in stats.get('extensions', {}).items():
                print(f"      {ext}: {count} chunks")
    
    elif args.command == 'projects':
        projects = rag.list_projects()
        
        if args.output == 'json':
            print(json.dumps(projects, indent=2))
        else:
            print(f"\n📁 Available projects ({len(projects)}):")
            for project in projects:
                print(f"   {project}")
    
    elif args.command == 'clear':
        if rag.clear_collection():
            print("✅ Collection cleared successfully")
        else:
            print("❌ Error clearing collection")
    
    elif args.command == 'list':
        # Manter compatibilidade com versão anterior
        stats = rag.get_stats()
        if args.output == 'json':
            print(json.dumps(stats, indent=2))
        else:
            print(f"\n📊 Indexed files: {stats.get('total_files', 0)}")


if __name__ == "__main__":
    main()



