#!/usr/bin/env python3
"""
Interactive version for Docker - Multi-backend support
"""

import sys
import os

# Detect vector database backend via environment variable
VECTOR_DB_TYPE = os.getenv('VECTOR_DB_TYPE', 'chroma').lower()

# Conditional imports based on backend
if VECTOR_DB_TYPE == 'opensearch':
    try:
        from code_rag_opensearch import OpenSearchCodeRAGSystem as RAGSystem
        BACKEND_NAME = "OpenSearch"
    except ImportError as e:
        print(f"❌ Error importing OpenSearch RAG: {e}")
        print("💡 Install dependencies: pip install opensearch-py")
        sys.exit(1)
elif VECTOR_DB_TYPE == 'chroma':
    try:
        from code_rag_docker import DockerCodeRAGSystem as RAGSystem
        BACKEND_NAME = "ChromaDB"
    except ImportError as e:
        print(f"❌ Error importing ChromaDB RAG: {e}")
        print("💡 Install dependencies: pip install chromadb")
        sys.exit(1)
else:
    print(f"❌ Backend not supported: {VECTOR_DB_TYPE}")
    print("💡 Use VECTOR_DB_TYPE=chroma or VECTOR_DB_TYPE=opensearch")
    sys.exit(1)


def interactive_demo():
    print(f"🐳 CodeRAG Docker - Demo Interativo ({BACKEND_NAME})")
    print("=" * 60)

    # Show current configuration
    print("📋 Current configuration:")
    print(f"   🗄️ Vector Database: {BACKEND_NAME} ({VECTOR_DB_TYPE})")
    print(
        f"   🌐 OLLAMA_HOST: {os.getenv('OLLAMA_HOST', 'http://host.docker.internal:11434')}"
    )
    print(f"   🧠 EMBEDDING_MODEL: {os.getenv('EMBEDDING_MODEL', 'nomic-embed-text')}")
    print(f"   💬 CHAT_MODEL: {os.getenv('CHAT_MODEL', 'qwen2.5-coder')}")
    
    # Show backend-specific configurations
    if VECTOR_DB_TYPE == 'opensearch':
        print(f"   📊 OPENSEARCH_INDEX: {os.getenv('OPENSEARCH_INDEX', 'code-rag-index')}")
        print(f"   🔗 OPENSEARCH_HOST: {os.getenv('OPENSEARCH_HOST', 'localhost')}:{os.getenv('OPENSEARCH_PORT', '9200')}")
    else:  # chroma
        print(f"   📦 COLLECTION_NAME: {os.getenv('COLLECTION_NAME', 'code_project')}")
        print(f"   💾 CHROMA_DB_PATH: {os.getenv('CHROMA_DB_PATH', '/chroma_db')}")
    print()

    # Initialize system
    try:
        print(f"🔄 Initializing {BACKEND_NAME} system...")
        rag = RAGSystem()
        print(f"✅ {BACKEND_NAME} system initialized successfully!")
    except Exception as e:
        print(f"❌ Error initializing {BACKEND_NAME}: {e}")
        if VECTOR_DB_TYPE == 'opensearch':
            print("💡 Check if OpenSearch is running and accessible")
            print("💡 Configure OPENSEARCH_HOST, OPENSEARCH_USER, OPENSEARCH_PASSWORD variables")
        else:
            print("💡 Check if ChromaDB volume is mounted correctly")
        return

    while True:
        print(f"\n📋 Options ({BACKEND_NAME}):")
        print("1. Index project")
        print("2. Ask question")
        print("3. View statistics")
        print("4. List available projects")
        print(f"5. Limpar {BACKEND_NAME.lower()}")
        print("6. Sair")

        try:
            choice = input("\nChoose an option (1-6): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n👋 Saindo...")
            break

        if choice == "1":
            projects = rag.list_projects()
            if not projects:
                print("❌ No projects found in /projects")
                print("💡 Mount a volume with your projects: -v /path/local:/projects")
                continue

            print(f"\n📁 Available projects:")
            for i, project in enumerate(projects, 1):
                print(f"   {i}. {project}")

            try:
                proj_choice = input("\nChoose a project (number or name): ").strip()

                if proj_choice.isdigit():
                    proj_idx = int(proj_choice) - 1
                    if 0 <= proj_idx < len(projects):
                        project_name = projects[proj_idx]
                    else:
                        print("❌ Invalid number")
                        continue
                else:
                    project_name = proj_choice

                print(f"\n🔄 Indexing project '{project_name}'...")
                result = rag.index_project(project_name)

                if "error" in result:
                    print(f"❌ {result['error']}")
                else:
                    print(f"✅ Indexing completed!")
                    print(
                        f"   📁 Files: {result['processed_files']}/{result['total_files']}"
                    )
                    print(f"   📦 Chunks: {result['indexed_chunks']}")
                    if result["errors"]:
                        print(f"   ⚠️ Errors: {len(result['errors'])}")

            except (KeyboardInterrupt, EOFError):
                print("\n⏸️ Operation cancelled")

        elif choice == "2":
            try:
                question = input("❓ Your question: ").strip()
                if not question:
                    print("❌ Empty question")
                    continue

                context_input = input("📦 Context chunks (default 5): ").strip()
                context_size = int(context_input) if context_input.isdigit() else 5

                print("\n🤔 Analyzing...")
                result = rag.ask_question(question, context_size)

                if "error" in result:
                    print(f"❌ {result['error']}")
                else:
                    print("\n💡 Answer:")
                    print("-" * 60)
                    print(result["answer"])
                    print("-" * 60)
                    print(
                        f"📊 Chunks: {result['context_chunks']} | ⏱️ Time: {result['processing_time']:.2f}s"
                    )

            except (KeyboardInterrupt, EOFError):
                print("\n⏸️ Question cancelled")
            except ValueError:
                print("❌ Invalid number of chunks")

        elif choice == "3":
            stats = rag.get_stats()
            if "error" in stats:
                print(f"❌ {stats['error']}")
            else:
                print(f"\n📊 Index statistics:")
                print(f"   📦 Total de chunks: {stats.get('total_chunks', 0)}")
                print(f"   📁 Total files: {stats.get('total_files', 0)}")
                print(f"   🔧 Indexed functions: {stats.get('functions_count', 0)}")
                print(f"   📋 Indexed classes: {stats.get('classes_count', 0)}")
                print(
                    f"   💾 Average chunk size: {stats.get('average_chunk_size', 0):.0f} bytes"
                )

                if stats.get("extensions"):
                    print("   📄 Extensions:")
                    for ext, count in stats["extensions"].items():
                        print(f"      {ext or 'no extension'}: {count} chunks")

        elif choice == "4":
            projects = rag.list_projects()
            print(f"\n📁 Available projects ({len(projects)}):")
            if projects:
                for project in projects:
                    print(f"   📂 {project}")
            else:
                print("   (no projects found)")
                print("💡 Mount a volume: -v /path/your/projects:/projects")

        elif choice == "5":
            try:
                confirm = (
                    input("⚠️ Are you sure you want to clear the index? (yes/no): ")
                    .strip()
                    .lower()
                )
                if confirm in ["yes", "y", "sim", "s"]:
                    # Use appropriate method based on backend
                    if VECTOR_DB_TYPE == 'opensearch':
                        clear_result = rag.clear_index()
                    else:  # chroma
                        clear_result = rag.clear_collection()
                    
                    if clear_result:
                        print(f"✅ {BACKEND_NAME} cleared successfully")
                    else:
                        print(f"❌ Error clearing {BACKEND_NAME}")
                else:
                    print("⏸️ Operation cancelled")
            except (KeyboardInterrupt, EOFError):
                print("\n⏸️ Operation cancelled")

        elif choice == "6":
            print("👋 Goodbye!")
            break

        else:
            print("❌ Invalid option")


if __name__ == "__main__":
    try:
        interactive_demo()
    except KeyboardInterrupt:
        print("\n\n👋 Saindo...")
        sys.exit(0)
