#!/usr/bin/env python3
"""
RAG System with OpenSearch - Adapted Version
"""

import os
import json
import requests
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Optional
from opensearchpy import OpenSearch, RequestsHttpConnection
from opensearchpy.helpers import bulk
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

class OpenSearchCodeRAGSystem:
    def __init__(self):
        """Inicializa sistema com OpenSearch"""
        
        # Configuration via environment variables
        self.ollama_host = os.getenv('OLLAMA_HOST', 'http://host.docker.internal:11434')
        self.embedding_model = os.getenv('EMBEDDING_MODEL', 'nomic-embed-text')
        self.chat_model = os.getenv('CHAT_MODEL', 'qwen2.5-coder')
        self.index_name = os.getenv('OPENSEARCH_INDEX', 'code-rag-index')
        self.chunk_size = int(os.getenv('CHUNK_SIZE', '1500'))
        self.max_context_chunks = int(os.getenv('MAX_CONTEXT_CHUNKS', '5'))
        self.temperature = float(os.getenv('TEMPERATURE', '0.1'))
        self.top_p = float(os.getenv('TOP_P', '0.9'))
        self.request_timeout = int(os.getenv('REQUEST_TIMEOUT', '120'))
        
        # OpenSearch configuration
        self.opensearch_host = os.getenv('OPENSEARCH_HOST', 'localhost')
        self.opensearch_port = int(os.getenv('OPENSEARCH_PORT', '9200'))
        self.opensearch_user = os.getenv('OPENSEARCH_USER', 'admin')
        self.opensearch_password = os.getenv('OPENSEARCH_PASSWORD', 'admin')
        self.opensearch_use_ssl = os.getenv('OPENSEARCH_USE_SSL', 'false').lower() == 'true'
        self.opensearch_verify_certs = os.getenv('OPENSEARCH_VERIFY_CERTS', 'false').lower() == 'true'
        
        # Directories
        self.projects_dir = Path('/projects')
        self.data_dir = Path('/data')
        
        logger.info("🔍 Inicializando CodeRAG com OpenSearch")
        logger.info(f"OpenSearch Host: {self.opensearch_host}:{self.opensearch_port}")
        logger.info(f"Ollama Host: {self.ollama_host}")
        logger.info(f"Index: {self.index_name}")
        
        # Inicializar OpenSearch
        self._init_opensearch()
        
        # Check Ollama connection
        self._check_ollama_connection()
        
    def _init_opensearch(self):
        """Initialize OpenSearch connection"""
        try:
            # Connection configuration
            auth = (self.opensearch_user, self.opensearch_password)
            
            self.opensearch_client = OpenSearch(
                hosts=[{
                    'host': self.opensearch_host,
                    'port': self.opensearch_port
                }],
                http_auth=auth,
                use_ssl=self.opensearch_use_ssl,
                verify_certs=self.opensearch_verify_certs,
                ssl_show_warn=False,
                connection_class=RequestsHttpConnection,
                timeout=30,
                max_retries=3,
                retry_on_timeout=True
            )
            
            # Test connection
            info = self.opensearch_client.info()
            logger.info(f"✅ OpenSearch connected: {info['version']['number']}")
            
            # Create/verify index
            self._create_index()
            
        except Exception as e:
            logger.error(f"❌ Error connecting to OpenSearch: {e}")
            sys.exit(1)
    
    def _create_index(self):
        """Create index with optimized mapping for vector search"""
        
        # Detect embedding model dimension
        embedding_dim = self._get_embedding_dimension()
        
        mapping = {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "index": {
                    "knn": True,
                    "knn.algo_param.ef_search": 100
                }
            },
            "mappings": {
                "properties": {
                    "content": {
                        "type": "text",
                        "analyzer": "standard"
                    },
                    "embedding": {
                        "type": "knn_vector",
                        "dimension": embedding_dim,
                        "method": {
                            "name": "hnsw",
                            "space_type": "cosinesimil",
                            "engine": "lucene",
                            "parameters": {
                                "ef_construction": 128,
                                "m": 24
                            }
                        }
                    },
                    "file_path": {"type": "keyword"},
                    "chunk_id": {"type": "integer"},
                    "functions": {"type": "keyword"},
                    "classes": {"type": "keyword"},
                    "extension": {"type": "keyword"},
                    "size": {"type": "integer"},
                    "lines": {"type": "integer"},
                    "hash": {"type": "keyword"},
                    "indexed_at": {"type": "date"},
                    "project_name": {"type": "keyword"}
                }
            }
        }
        
        try:
            if not self.opensearch_client.indices.exists(index=self.index_name):
                self.opensearch_client.indices.create(
                    index=self.index_name,
                    body=mapping
                )
                logger.info(f"✅ Index '{self.index_name}' created with dimension {embedding_dim}")
            else:
                logger.info(f"✅ Index '{self.index_name}' already exists")
                
        except Exception as e:
            logger.error(f"❌ Error creating index: {e}")
            raise
    
    def _get_embedding_dimension(self):
        """Detect embedding model dimension"""
        try:
            test_embedding = self.get_embedding("teste")
            if test_embedding:
                return len(test_embedding)
            else:
                logger.warning("Could not detect dimension, using default 768")
                return 768
        except:
            return 768
    
    def _check_ollama_connection(self):
        """Check Ollama connection"""
        max_retries = int(os.getenv('OLLAMA_RETRY_COUNT', '5'))
        retry_delay = int(os.getenv('OLLAMA_RETRY_DELAY', '10'))
        
        for attempt in range(max_retries):
            try:
                response = requests.get(f"{self.ollama_host}/api/tags", timeout=10)
                if response.status_code == 200:
                    logger.info("✅ Ollama connected successfully")
                    return
                    
            except requests.exceptions.RequestException as e:
                logger.warning(f"Attempt {attempt + 1}/{max_retries} - Connection error: {e}")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(retry_delay)
        
        logger.error("❌ Could not connect to Ollama")
        sys.exit(1)
    
    def get_embedding(self, text: str) -> List[float]:
        """Generate embedding using Ollama"""
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
                logger.error(f"Error generating embedding: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error in embedding request: {e}")
            return []
    
    def chunk_code_file(self, file_path: Path, chunk_size: int = None) -> List[Dict]:
        """Fragment code file"""
        if chunk_size is None:
            chunk_size = self.chunk_size
            
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
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
        
        for line in lines:
            line_size = len(line) + 1
            
            # Detect functions and classes
            stripped_line = line.strip()
            if stripped_line.startswith(('def ', 'function ', 'const ', 'let ', 'var ')):
                func_name = self._extract_function_name(stripped_line)
                if func_name:
                    chunk_metadata['functions'].append(func_name)
            elif stripped_line.startswith(('class ', 'interface ', 'type ')):
                class_name = self._extract_class_name(stripped_line)
                if class_name:
                    chunk_metadata['classes'].append(class_name)
            
            # Verificar se deve criar novo chunk
            if current_size + line_size > chunk_size and current_chunk:
                if not line.strip() or stripped_line.startswith(('def ', 'class ', 'function ')):
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
        """Extract function name"""
        try:
            for keyword in ['def ', 'function ', 'const ', 'let ', 'var ']:
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
        """Extract class name"""
        try:
            for keyword in ['class ', 'interface ', 'type ']:
                if keyword in line:
                    after_keyword = line.split(keyword, 1)[1]
                    name = after_keyword.split('(')[0].split(':')[0].split('{')[0].strip()
                    return name
        except:
            pass
        return None
    
    def _create_chunk(self, lines: List[str], file_path: Path, metadata: Dict, chunk_id: int) -> Dict:
        """Create chunk with metadata"""
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
    
    def index_project(self, project_path: str, file_patterns: List[str] = None, ignore_patterns: List[str] = None) -> Dict:
        """Index project in OpenSearch"""
        
        if file_patterns is None:
            file_patterns = [
                "*.py", "*.js", "*.ts", "*.jsx", "*.tsx", "*.vue",
                "*.java", "*.cpp", "*.c", "*.h", "*.cs", "*.php", 
                "*.rb", "*.go", "*.rs", "*.sql", "*.json", "*.yaml", "*.md"
            ]
        
        if ignore_patterns is None:
            ignore_patterns = [
                "node_modules", ".git", "__pycache__", ".venv", "venv",
                "build", "dist", ".pytest_cache", ".mypy_cache"
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
        logger.info(f"📁 Indexing project: {project_name}")
        
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
        
        # Process files in batches
        total_chunks = 0
        processed_files = 0
        errors = []
        batch_docs = []
        batch_size = 50  # Processar em lotes de 50 documentos
        
        for file_path in all_files:
            try:
                logger.info(f"Processing: {file_path.name}")
                
                chunks = self.chunk_code_file(file_path)
                if not chunks:
                    continue
                
                for chunk in chunks:
                    embedding = self.get_embedding(chunk['content'])
                    if not embedding:
                        continue
                    
                    doc_id = f"{project_name}_{file_path.stem}_{chunk['chunk_id']}_{chunk['hash'][:8]}"
                    
                    doc = {
                        "_index": self.index_name,
                        "_id": doc_id,
                        "_source": {
                            "content": chunk['content'],
                            "embedding": embedding,
                            "file_path": chunk['file'],
                            "chunk_id": chunk['chunk_id'],
                            "functions": chunk['functions'],
                            "classes": chunk['classes'],
                            "extension": chunk['extension'],
                            "size": chunk['size'],
                            "lines": chunk['lines'],
                            "hash": chunk['hash'],
                            "indexed_at": chunk['indexed_at'],
                            "project_name": project_name
                        }
                    }
                    
                    batch_docs.append(doc)
                    
                    # Index in batches
                    if len(batch_docs) >= batch_size:
                        try:
                            bulk(self.opensearch_client, batch_docs)
                            total_chunks += len(batch_docs)
                            logger.info(f"Indexados {len(batch_docs)} chunks")
                            batch_docs = []
                        except Exception as e:
                            logger.error(f"Batch error: {e}")
                            errors.append(str(e))
                            batch_docs = []
                
                processed_files += 1
                
            except Exception as e:
                error_msg = f"Error processing {file_path}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        # Index final batch
        if batch_docs:
            try:
                bulk(self.opensearch_client, batch_docs)
                total_chunks += len(batch_docs)
                logger.info(f"Indexados {len(batch_docs)} chunks finais")
            except Exception as e:
                logger.error(f"Final batch error: {e}")
                errors.append(str(e))
        
        # Refresh index
        self.opensearch_client.indices.refresh(index=self.index_name)
        
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
        logger.info(f"   📁 Files: {processed_files}/{len(all_files)}")
        logger.info(f"   📦 Chunks: {total_chunks}")
        
        return result
    
    def search_code(self, query: str, n_results: int = None, project_filter: str = None) -> Dict:
        """Search code using vector + text search"""
        if n_results is None:
            n_results = self.max_context_chunks
        
        logger.info(f"🔍 Searching: '{query[:50]}...'")
        
        # Generate query embedding
        query_embedding = self.get_embedding(query)
        if not query_embedding:
            return {"hits": []}
        
        # Build hybrid query (vector + text)
        search_body = {
            "size": n_results,
            "query": {
                "bool": {
                    "should": [
                        # Busca vetorial (80% do peso)
                        {
                            "knn": {
                                "embedding": {
                                    "vector": query_embedding,
                                    "k": n_results * 2
                                }
                            }
                        },
                        # Busca textual (20% do peso)
                        {
                            "multi_match": {
                                "query": query,
                                "fields": ["content^1.5", "functions^2", "classes^2"],
                                "fuzziness": "AUTO"
                            }
                        }
                    ],
                    "minimum_should_match": 1
                }
            },
            "_source": {
                "excludes": ["embedding"]  # Don't return embedding in response
            },
            "highlight": {
                "fields": {
                    "content": {"fragment_size": 150, "number_of_fragments": 2}
                }
            }
        }
        
        # Filter by project if specified
        if project_filter:
            search_body["query"]["bool"]["filter"] = [
                {"term": {"project_name": project_filter}}
            ]
        
        try:
            response = self.opensearch_client.search(
                index=self.index_name,
                body=search_body
            )
            
            logger.info(f"Found {len(response['hits']['hits'])} relevant chunks")
            return response['hits']
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            return {"hits": []}
    
    def ask_question(self, question: str, context_size: int = None, project_filter: str = None) -> Dict:
        """Ask question using RAG with OpenSearch"""
        if context_size is None:
            context_size = self.max_context_chunks
        
        start_time = datetime.now()
        
        # Search relevant context
        search_results = self.search_code(question, context_size, project_filter)
        
        if not search_results.get('hits'):
            return {
                "question": question,
                "answer": "❌ No relevant code found.",
                "context_chunks": 0,
                "processing_time": 0,
                "error": "No relevant code found"
            }
        
        # Construir contexto
        context = "# Relevant code found:\n\n"
        context_info = []
        
        for hit in search_results['hits']:
            source = hit['_source']
            
            context += f"## File: {source['file_path']}\n"
            if source.get('functions'):
                context += f"**Functions:** {', '.join(source['functions'])}\n"
            if source.get('classes'):
                context += f"**Classes:** {', '.join(source['classes'])}\n"
            
            # Use highlight if available
            content = source['content']
            if 'highlight' in hit and 'content' in hit['highlight']:
                highlighted = ' ... '.join(hit['highlight']['content'])
                context += f"```{source.get('extension', '').replace('.', '')}\n{highlighted}\n```\n\n"
            else:
                context += f"```{source.get('extension', '').replace('.', '')}\n{content}\n```\n\n"
            
            context_info.append({
                "file": source['file_path'],
                "functions": source.get('functions', []),
                "classes": source.get('classes', []),
                "score": hit['_score'],
                "chunk_size": len(content)
            })
        
        # Generate response using Ollama
        prompt = f"""{context}

# User question:
{question}

# Instructions:
- Analyze the code provided above
- Be precise and cite specific files/functions
- Provide examples when appropriate
- Answer in English

# Response:"""
        
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
                
                return {
                    "question": question,
                    "answer": answer,
                    "context_chunks": len(search_results['hits']),
                    "context_info": context_info,
                    "processing_time": processing_time,
                    "model_used": self.chat_model,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                error_msg = f"Generation error: {response.status_code}"
                return {
                    "question": question,
                    "answer": f"❌ {error_msg}",
                    "error": error_msg
                }
                
        except Exception as e:
            error_msg = f"Request error: {e}"
            return {
                "question": question,
                "answer": f"❌ {error_msg}",
                "error": error_msg
            }
    
    def get_stats(self) -> Dict:
        """OpenSearch index statistics"""
        try:
            # General index stats
            index_stats = self.opensearch_client.indices.stats(index=self.index_name)
            doc_count = index_stats['indices'][self.index_name]['total']['docs']['count']
            
            # Aggregations for detailed statistics
            agg_query = {
                "size": 0,
                "aggs": {
                    "projects": {"terms": {"field": "project_name", "size": 100}},
                    "extensions": {"terms": {"field": "extension", "size": 50}},
                    "unique_files": {"cardinality": {"field": "file_path"}},
                    "functions_count": {"sum": {"script": "params._source.functions.size()"}},
                    "classes_count": {"sum": {"script": "params._source.classes.size()"}},
                    "total_size": {"sum": {"field": "size"}}
                }
            }
            
            agg_response = self.opensearch_client.search(
                index=self.index_name,
                body=agg_query
            )
            
            aggregations = agg_response['aggregations']
            
            # Process results
            projects = {bucket['key']: bucket['doc_count'] 
                       for bucket in aggregations['projects']['buckets']}
            
            extensions = {bucket['key']: bucket['doc_count'] 
                         for bucket in aggregations['extensions']['buckets']}
            
            return {
                "total_chunks": doc_count,
                "indexed_files": int(aggregations['unique_files']['value'] or 0),
                "projects": projects,
                "extensions": extensions,
                "functions_count": int(aggregations['functions_count']['value'] or 0),
                "classes_count": int(aggregations['classes_count']['value'] or 0),
                "total_size_bytes": int(aggregations['total_size']['value'] or 0),
                "index_name": self.index_name,
                "opensearch_version": self.opensearch_client.info()['version']['number']
            }
            
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {"error": str(e)}
    
    def list_projects(self) -> List[str]:
        """List available projects"""
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
            # Get projects aggregation from OpenSearch
            agg_query = {
                "size": 0,
                "aggs": {
                    "projects": {
                        "terms": {"field": "project_name", "size": 100},
                        "aggs": {
                            "unique_files": {"cardinality": {"field": "file_path"}},
                            "functions_count": {"sum": {"script": "params._source.functions.size()"}},
                            "classes_count": {"sum": {"script": "params._source.classes.size()"}}
                        }
                    }
                }
            }
            
            response = self.opensearch_client.search(
                index=self.index_name,
                body=agg_query
            )
            
            projects_stats = {}
            
            for bucket in response['aggregations']['projects']['buckets']:
                project_name = bucket['key']
                projects_stats[project_name] = {
                    "chunks": bucket['doc_count'],
                    "files": int(bucket['unique_files']['value']),
                    "functions": int(bucket['functions_count']['value'] or 0),
                    "classes": int(bucket['classes_count']['value'] or 0)
                }
            
            return {"projects": projects_stats}
            
        except Exception as e:
            logger.error(f"Error getting indexed projects: {e}")
            return {"projects": {}, "error": str(e)}
    
    def clear_index(self) -> bool:
        """Clear OpenSearch index"""
        try:
            self.opensearch_client.indices.delete(index=self.index_name, ignore=[404])
            self._create_index()
            logger.info("✅ Index cleared and recreated")
            return True
        except Exception as e:
            logger.error(f"Error clearing index: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(description="Sistema RAG com OpenSearch")
    parser.add_argument('command', choices=['index', 'ask', 'stats', 'projects', 'clear'])
    parser.add_argument('--project', '-p', help='Project name')
    parser.add_argument('--question', '-q', help='Question to ask')
    parser.add_argument('--context', type=int, help='Number of context chunks')
    parser.add_argument('--filter', help='Filter by project')
    parser.add_argument('--output', '-o', choices=['json', 'text'], default='text')
    
    args = parser.parse_args()
    
    try:
        rag = OpenSearchCodeRAGSystem()
    except Exception as e:
        logger.error(f"Error initializing: {e}")
        sys.exit(1)
    
    if args.command == 'index':
        if not args.project:
            print("❌ Use --project to specify project")
            sys.exit(1)
        result = rag.index_project(args.project)
        if args.output == 'json':
            print(json.dumps(result, indent=2))
        else:
            print(f"✅ Indexados {result['indexed_chunks']} chunks")
    
    elif args.command == 'ask':
        if not args.question:
            print("❌ Use --question to ask a question")
            sys.exit(1)
        result = rag.ask_question(args.question, args.context, args.filter)
        if args.output == 'json':
            print(json.dumps(result, indent=2))
        else:
            print(result['answer'])
    
    elif args.command == 'stats':
        stats = rag.get_stats()
        if args.output == 'json':
            print(json.dumps(stats, indent=2))
        else:
            print(f"📊 Total chunks: {stats.get('total_chunks', 0)}")
            print(f"📁 Projects: {len(stats.get('projects', {}))}")
    
    elif args.command == 'projects':
        projects = rag.list_projects()
        print(f"📁 Projects: {', '.join(projects)}")
    
    elif args.command == 'clear':
        if rag.clear_index():
            print("✅ Index cleared successfully")
        else:
            print("❌ Error clearing index")


# Alias for compatibility with web_api.py
DockerCodeRAGSystem = OpenSearchCodeRAGSystem

if __name__ == "__main__":
    main()