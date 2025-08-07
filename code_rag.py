#!/usr/bin/env python3
"""
CodeRAG - Unified Interface
Imports the appropriate RAG system based on environment
"""

import os

# Determine which RAG system to use based on environment variable
USE_OPENSEARCH = os.getenv('USE_OPENSEARCH', 'false').lower() == 'true'

if USE_OPENSEARCH:
    from code_rag_opensearch import OpenSearchCodeRAGSystem as DockerCodeRAGSystem
else:
    from code_rag_docker import DockerCodeRAGSystem

# Export the main class
__all__ = ['DockerCodeRAGSystem']