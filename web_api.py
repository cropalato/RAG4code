#!/usr/bin/env python3
"""
Web API for RAG System - REST Interface
"""

import os
import json
import logging
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from code_rag import DockerCodeRAGSystem
import threading
import time
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask
app = Flask(__name__)
CORS(app)

# Configuration
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max file size

# Initialize RAG system
rag_system = None
initialization_error = None


def initialize_rag():
    """Initialize RAG system in separate thread"""
    global rag_system, initialization_error
    try:
        rag_system = DockerCodeRAGSystem()
        logger.info("✅ RAG system initialized successfully")
    except Exception as e:
        initialization_error = str(e)
        logger.error(f"❌ Error initializing RAG system: {e}")


# Initialize in background
init_thread = threading.Thread(target=initialize_rag)
init_thread.start()

# Simple HTML template for web interface
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>CodeRAG - Code Analysis System</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { 
            font-family: Arial, sans-serif; 
            max-width: 1200px; 
            margin: 0 auto; 
            padding: 20px;
            background-color: #f5f5f5;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        .container { 
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        .form-group { 
            margin-bottom: 15px; 
        }
        label { 
            display: block; 
            margin-bottom: 5px; 
            font-weight: bold;
        }
        input, select, textarea { 
            width: 100%; 
            padding: 10px; 
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 14px;
        }
        button { 
            background: #667eea;
            color: white;
            padding: 12px 24px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
        }
        button:hover { 
            background: #5a6fd8;
        }
        button:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
        .result { 
            background: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            border-left: 4px solid #667eea;
            margin-top: 15px;
            white-space: pre-wrap;
        }
        .error { 
            background: #fee;
            border-left-color: #e74c3c;
            color: #c0392b;
        }
        .success {
            background: #d4edda;
            border-left-color: #28a745;
            color: #155724;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }
        .stat-card {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            text-align: center;
        }
        .stat-number {
            font-size: 24px;
            font-weight: bold;
            color: #667eea;
        }
        .loading {
            display: none;
            text-align: center;
            padding: 20px;
        }
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 2s linear infinite;
            margin: 0 auto;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .tabs {
            display: flex;
            margin-bottom: 20px;
        }
        .tab {
            background: #e9ecef;
            border: none;
            padding: 10px 20px;
            cursor: pointer;
            border-radius: 5px 5px 0 0;
            margin-right: 5px;
        }
        .tab.active {
            background: white;
            border-bottom: 2px solid #667eea;
        }
        .tab-content {
            display: none;
        }
        .tab-content.active {
            display: block;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🤖 CodeRAG - Code Analysis System</h1>
        <p>Web interface for intelligent project analysis using RAG</p>
    </div>

    <div class="tabs">
        <button class="tab active" onclick="showTab('query')">💬 Questions</button>
        <button class="tab" onclick="showTab('index')">📁 Index</button>
        <button class="tab" onclick="showTab('update')">🔄 Update</button>
        <button class="tab" onclick="showTab('stats')">📊 Statistics</button>
        <button class="tab" onclick="showTab('projects')">📂 Projects</button>
    </div>

    <!-- Tab: Ask Questions -->
    <div id="query-tab" class="tab-content active">
        <div class="container">
            <h2>💬 Ask Question about the Code</h2>
            <div class="form-group">
                <label for="question">Your question:</label>
                <textarea id="question" rows="3" placeholder="Ex: How does authentication work in the system?"></textarea>
            </div>
            <div class="form-group">
                <label for="project-filter">Search in project:</label>
                <select id="project-filter">
                    <option value="">All projects</option>
                </select>
            </div>
            <div class="form-group">
                <label for="context-size">Context chunks:</label>
                <select id="context-size">
                    <option value="3">3 chunks</option>
                    <option value="5" selected>5 chunks</option>
                    <option value="7">7 chunks</option>
                    <option value="10">10 chunks</option>
                </select>
            </div>
            <button onclick="askQuestion()">🔍 Ask</button>
            
            <div class="loading" id="query-loading">
                <div class="spinner"></div>
                <p>Analyzing code and generating response...</p>
            </div>
            
            <div id="query-result"></div>
        </div>
    </div>

    <!-- Tab: Index Project -->
    <div id="index-tab" class="tab-content">
        <div class="container">
            <h2>📁 Index Project</h2>
            <div class="form-group">
                <label for="project-name">Project name:</label>
                <select id="project-name">
                    <option value="">Loading projects...</option>
                </select>
            </div>
            <button onclick="indexProject()">📦 Index</button>
            
            <div class="loading" id="index-loading">
                <div class="spinner"></div>
                <p>Indexing project... This may take a few minutes.</p>
            </div>
            
            <div id="index-result"></div>
        </div>
    </div>

    <!-- Tab: Update Project -->
    <div id="update-tab" class="tab-content">
        <div class="container">
            <h2>🔄 Update Project (Incremental)</h2>
            <p style="color: #666; margin-bottom: 20px;">
                <strong>💡 Incremental Update:</strong> Only processes changed files (new, modified, or removed). 
                Much faster than full re-indexing for large projects.
            </p>
            <div class="form-group">
                <label for="update-project-name">Project name:</label>
                <select id="update-project-name">
                    <option value="">Loading projects...</option>
                </select>
            </div>
            <div class="form-group">
                <label>
                    <input type="checkbox" id="force-update" style="width: auto; margin-right: 10px;">
                    Force update all files (ignore modification time)
                </label>
            </div>
            <div style="margin-bottom: 15px;">
                <button onclick="updateProject()">🔄 Update</button>
                <button onclick="checkUpdateStatus()" style="background: #28a745; margin-left: 10px;">📊 Check Status</button>
            </div>
            
            <div class="loading" id="update-loading">
                <div class="spinner"></div>
                <p>Updating project... Analyzing changes...</p>
            </div>
            
            <div id="update-result"></div>
        </div>
    </div>

    <!-- Tab: Statistics -->
    <div id="stats-tab" class="tab-content">
        <div class="container">
            <h2>📊 Index Statistics</h2>
            <button onclick="loadStats()">🔄 Refresh</button>
            <div id="stats-content">
                <p>Click "Refresh" to see statistics</p>
            </div>
        </div>
    </div>

    <!-- Tab: Projects -->
    <div id="projects-tab" class="tab-content">
        <div class="container">
            <h2>📂 Available Projects</h2>
            <button onclick="loadProjects()">🔄 Refresh List</button>
            <div id="projects-content">
                <p>Click "Refresh List" to see projects</p>
            </div>
        </div>
    </div>

    <script>
        // Interface functions
        function showTab(tabName) {
            // Hide all tabs
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            document.querySelectorAll('.tab').forEach(tab => {
                tab.classList.remove('active');
            });
            
            // Show selected tab
            document.getElementById(tabName + '-tab').classList.add('active');
            event.target.classList.add('active');
        }

        // Ask question
        async function askQuestion() {
            const question = document.getElementById('question').value.trim();
            const contextSize = document.getElementById('context-size').value;
            const projectFilter = document.getElementById('project-filter').value;
            
            if (!question) {
                alert('Please enter a question');
                return;
            }
            
            document.getElementById('query-loading').style.display = 'block';
            document.getElementById('query-result').innerHTML = '';
            
            try {
                const requestBody = { 
                    question: question,
                    context_size: parseInt(contextSize)
                };
                
                // Add project filter if selected
                if (projectFilter) {
                    requestBody.project_filter = projectFilter;
                }
                
                const response = await fetch('/api/ask', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(requestBody)
                });
                
                const data = await response.json();
                
                if (data.error) {
                    document.getElementById('query-result').innerHTML = 
                        `<div class="result error">❌ ${data.error}</div>`;
                } else {
                    const projectInfo = projectFilter ? ` | 📁 Project: ${projectFilter}` : ' | 📁 All projects';
                    document.getElementById('query-result').innerHTML = 
                        `<div class="result success">
                            <strong>Answer:</strong><br>
                            ${data.answer}
                            <br><br>
                            <small>
                                📊 Chunks used: ${data.context_chunks} | 
                                ⏱️ Time: ${data.processing_time.toFixed(2)}s |
                                🤖 Model: ${data.model_used}${projectInfo}
                            </small>
                        </div>`;
                }
            } catch (error) {
                document.getElementById('query-result').innerHTML = 
                    `<div class="result error">❌ Error: ${error.message}</div>`;
            } finally {
                document.getElementById('query-loading').style.display = 'none';
            }
        }

        // Index project
        async function indexProject() {
            const projectName = document.getElementById('project-name').value;
            
            if (!projectName) {
                alert('Please select a project');
                return;
            }
            
            document.getElementById('index-loading').style.display = 'block';
            document.getElementById('index-result').innerHTML = '';
            
            try {
                const response = await fetch('/api/index', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ project: projectName })
                });
                
                const data = await response.json();
                
                if (data.error) {
                    document.getElementById('index-result').innerHTML = 
                        `<div class="result error">❌ ${data.error}</div>`;
                } else {
                    document.getElementById('index-result').innerHTML = 
                        `<div class="result success">
                            ✅ Indexing completed!<br>
                            📁 Files processed: ${data.processed_files}/${data.total_files}<br>
                            📦 Chunks indexed: ${data.indexed_chunks}<br>
                            ${data.errors.length > 0 ? `❌ Errors: ${data.errors.length}` : ''}
                        </div>`;
                    
                    // Refresh indexed projects dropdown
                    loadIndexedProjects();
                }
            } catch (error) {
                document.getElementById('index-result').innerHTML = 
                    `<div class="result error">❌ Error: ${error.message}</div>`;
            } finally {
                document.getElementById('index-loading').style.display = 'none';
            }
        }

        // Update project incrementally
        async function updateProject() {
            const projectName = document.getElementById('update-project-name').value;
            const forceUpdate = document.getElementById('force-update').checked;
            
            if (!projectName) {
                alert('Please select a project');
                return;
            }
            
            document.getElementById('update-loading').style.display = 'block';
            document.getElementById('update-result').innerHTML = '';
            
            try {
                const response = await fetch('/api/update', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        project: projectName,
                        force_update: forceUpdate
                    })
                });
                
                const data = await response.json();
                
                if (data.error) {
                    document.getElementById('update-result').innerHTML = 
                        `<div class="result error">❌ ${data.error}</div>`;
                } else if (data.status === 'up_to_date') {
                    document.getElementById('update-result').innerHTML = 
                        `<div class="result success">
                            ✅ Project is already up to date!<br>
                            📁 No changes detected - no files need updating<br>
                            📊 Unchanged files: ${data.unchanged_files}
                        </div>`;
                } else {
                    const errorsInfo = data.errors && data.errors.length > 0 ? 
                        `<br>⚠️ Errors: ${data.errors.length}` : '';
                    
                    document.getElementById('update-result').innerHTML = 
                        `<div class="result success">
                            ✅ Incremental update completed!<br>
                            📝 Files processed: ${data.processed_files}<br>
                            🆕 New files: ${data.new_files}<br>
                            🔄 Modified files: ${data.modified_files}<br>
                            🗑️ Removed files: ${data.removed_files}<br>
                            📊 Updated chunks: ${data.updated_chunks}<br>
                            🗑️ Removed chunks: ${data.removed_chunks}<br>
                            ⏸️ Unchanged files: ${data.unchanged_files}${errorsInfo}
                        </div>`;
                    
                    // Refresh indexed projects dropdown
                    loadIndexedProjects();
                }
            } catch (error) {
                document.getElementById('update-result').innerHTML = 
                    `<div class="result error">❌ Error: ${error.message}</div>`;
            } finally {
                document.getElementById('update-loading').style.display = 'none';
            }
        }

        // Check what would be updated without actually updating
        async function checkUpdateStatus() {
            const projectName = document.getElementById('update-project-name').value;
            
            if (!projectName) {
                alert('Please select a project');
                return;
            }
            
            document.getElementById('update-result').innerHTML = 
                `<div class="result">
                    📊 <strong>Checking project status...</strong><br>
                    This would show what files need updating, but the API doesn't support dry-run yet.<br>
                    Use the update button to see actual changes.
                </div>`;
        }

        // Load statistics
        async function loadStats() {
            try {
                const response = await fetch('/api/stats');
                const data = await response.json();
                
                if (data.error) {
                    document.getElementById('stats-content').innerHTML = 
                        `<div class="result error">❌ ${data.error}</div>`;
                    return;
                }
                
                let extensionsHtml = '';
                for (const [ext, count] of Object.entries(data.extensions || {})) {
                    extensionsHtml += `<div class="stat-card">
                        <div class="stat-number">${count}</div>
                        <div>${ext || 'no extension'}</div>
                    </div>`;
                }
                
                document.getElementById('stats-content').innerHTML = `
                    <div class="stats">
                        <div class="stat-card">
                            <div class="stat-number">${data.total_chunks || 0}</div>
                            <div>Total Chunks</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">${data.total_files || 0}</div>
                            <div>Indexed Files</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">${data.functions_count || 0}</div>
                            <div>Functions</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">${data.classes_count || 0}</div>
                            <div>Classes</div>
                        </div>
                    </div>
                    
                    <h3>📄 Distribution by Extension</h3>
                    <div class="stats">
                        ${extensionsHtml}
                    </div>
                `;
            } catch (error) {
                document.getElementById('stats-content').innerHTML = 
                    `<div class="result error">❌ Error: ${error.message}</div>`;
            }
        }

        // Load indexed projects for filter dropdown
        async function loadIndexedProjects() {
            try {
                const response = await fetch('/api/projects/indexed');
                const data = await response.json();
                
                if (!data.error && data.projects) {
                    const projectFilter = document.getElementById('project-filter');
                    projectFilter.innerHTML = '<option value="">All projects</option>';
                    
                    Object.keys(data.projects).forEach(project => {
                        const stats = data.projects[project];
                        projectFilter.innerHTML += `<option value="${project}">${project} (${stats.chunks} chunks)</option>`;
                    });
                }
            } catch (error) {
                console.error('Error loading indexed projects:', error);
            }
        }

        // Carregar projetos
        async function loadProjects() {
            try {
                const response = await fetch('/api/projects');
                const data = await response.json();
                
                if (data.error) {
                    document.getElementById('projects-content').innerHTML = 
                        `<div class="result error">❌ ${data.error}</div>`;
                    return;
                }
                
                const projectsList = data.projects || [];
                
                // Update project select in indexing tab
                const select = document.getElementById('project-name');
                select.innerHTML = '<option value="">Select a project</option>';
                projectsList.forEach(project => {
                    select.innerHTML += `<option value="${project}">${project}</option>`;
                });
                
                // Update project select in update tab
                const updateSelect = document.getElementById('update-project-name');
                updateSelect.innerHTML = '<option value="">Select a project</option>';
                projectsList.forEach(project => {
                    updateSelect.innerHTML += `<option value="${project}">${project}</option>`;
                });
                
                // Show project list
                let projectsHtml = `<p>📁 Found ${projectsList.length} projects:</p><ul>`;
                projectsList.forEach(project => {
                    projectsHtml += `<li><strong>${project}</strong></li>`;
                });
                projectsHtml += '</ul>';
                
                document.getElementById('projects-content').innerHTML = projectsHtml;
                
                // Also load indexed projects for the filter dropdown
                loadIndexedProjects();
            } catch (error) {
                document.getElementById('projects-content').innerHTML = 
                    `<div class="result error">❌ Error: ${error.message}</div>`;
            }
        }

        // Load projects on initialization
        document.addEventListener('DOMContentLoaded', function() {
            loadProjects();
            loadIndexedProjects();
        });

        // Enter to ask
        document.getElementById('question').addEventListener('keypress', function(e) {
            if (e.key === 'Enter' && e.ctrlKey) {
                askQuestion();
            }
        });
    </script>
</body>
</html>
"""


@app.route("/")
def index():
    """Main web interface"""
    return render_template_string(HTML_TEMPLATE)


@app.route("/health")
def health():
    """Health check endpoint"""
    if initialization_error:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": initialization_error,
                    "timestamp": datetime.now().isoformat(),
                }
            ),
            500,
        )

    if not rag_system:
        return (
            jsonify(
                {
                    "status": "initializing",
                    "message": "System still initializing...",
                    "timestamp": datetime.now().isoformat(),
                }
            ),
            503,
        )

    return jsonify(
        {
            "status": "healthy",
            "message": "System operational",
            "ollama_host": rag_system.ollama_host,
            "models": {
                "embedding": rag_system.embedding_model,
                "chat": rag_system.chat_model,
            },
            "timestamp": datetime.now().isoformat(),
        }
    )


@app.route("/api/ask", methods=["POST"])
def api_ask():
    """Endpoint for asking questions"""
    if not rag_system:
        return jsonify({"error": "System not initialized"}), 503

    try:
        data = request.get_json()
        question = data.get("question", "").strip()
        context_size = data.get("context_size", 5)
        project_filter = data.get("project_filter", "").strip() or None

        if not question:
            return jsonify({"error": "Question cannot be empty"}), 400

        result = rag_system.ask_question(question, context_size, project_filter)
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in ask endpoint: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/index", methods=["POST"])
def api_index():
    """Endpoint for indexing projects"""
    if not rag_system:
        return jsonify({"error": "System not initialized"}), 503

    try:
        data = request.get_json()
        project = data.get("project", "").strip()

        if not project:
            return jsonify({"error": "Project name is required"}), 400

        result = rag_system.index_project(project)
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in index endpoint: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/update", methods=["POST"])
def api_update():
    """Endpoint for incremental project updates"""
    if not rag_system:
        return jsonify({"error": "System not initialized"}), 503

    try:
        data = request.get_json()
        project = data.get("project", "").strip()
        force_update = data.get("force_update", False)

        if not project:
            return jsonify({"error": "Project name is required"}), 400

        result = rag_system.update_project_incremental(project, force_update=force_update)
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in update endpoint: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/stats")
def api_stats():
    """Statistics endpoint"""
    if not rag_system:
        return jsonify({"error": "System not initialized"}), 503

    try:
        stats = rag_system.get_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error in stats endpoint: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/projects")
def api_projects():
    """Endpoint for listing projects"""
    if not rag_system:
        return jsonify({"error": "System not initialized"}), 503

    try:
        projects = rag_system.list_projects()
        return jsonify({"projects": projects})
    except Exception as e:
        logger.error(f"Error in projects endpoint: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/projects/indexed")
def api_projects_indexed():
    """Endpoint for listing indexed projects with statistics"""
    if not rag_system:
        return jsonify({"error": "System not initialized"}), 503

    try:
        indexed_projects = rag_system.get_indexed_projects()
        return jsonify(indexed_projects)
    except Exception as e:
        logger.error(f"Error in indexed projects endpoint: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/clear", methods=["POST"])
def api_clear():
    """Endpoint for clearing collection"""
    if not rag_system:
        return jsonify({"error": "System not initialized"}), 503

    try:
        success = rag_system.clear_collection()
        if success:
            return jsonify({"message": "Collection cleared successfully"})
        else:
            return jsonify({"error": "Error clearing collection"}), 500
    except Exception as e:
        logger.error(f"Error in clear endpoint: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.getenv("API_PORT", 8080))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"

    logger.info(f"🚀 Starting web API on port {port}")

    app.run(host="0.0.0.0", port=port, debug=debug, threaded=True)
