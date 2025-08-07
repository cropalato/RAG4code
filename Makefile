# Makefile
.PHONY: build run stop clean logs shell index ask stats projects web interactive

# Variáveis
IMAGE_NAME = coderag
CONTAINER_NAME = coderag-container
PROJECTS_DIR = ./projects

# Build da imagem
build:
	@echo "🔨 Construindo imagem Docker..."
	docker build -t $(IMAGE_NAME) .

# Executar com Docker Compose
run:
	@echo "🚀 Iniciando CodeRAG com Docker Compose..."
	docker-compose up -d

# Parar containers
stop:
	@echo "⏹️ Parando containers..."
	docker-compose down

# Limpar tudo (cuidado: remove volumes!)
clean:
	@echo "🧹 Limpando containers e volumes..."
	docker-compose down -v
	docker rmi $(IMAGE_NAME) 2>/dev/null || true

# Ver logs
logs:
	@echo "📋 Mostrando logs..."
	docker-compose logs -f

# Shell no container
shell:
	@echo "🐚 Abrindo shell no container..."
	docker-compose exec coderag bash

# Comandos específicos
index:
	@if [ -z "$(PROJECT)" ]; then \
		echo "❌ Use: make index PROJECT=nome_do_projeto"; \
	else \
		echo "📦 Indexando projeto: $(PROJECT)"; \
		docker-compose exec coderag python code_rag.py index --project $(PROJECT); \
	fi

ask:
	@if [ -z "$(QUESTION)" ]; then \
		echo "❌ Use: make ask QUESTION=\"sua pergunta\""; \
	else \
		echo "❓ Fazendo pergunta..."; \
		docker-compose exec coderag python code_rag.py ask --question "$(QUESTION)"; \
	fi

stats:
	@echo "📊 Mostrando estatísticas..."
	docker-compose exec coderag python code_rag.py stats

projects:
	@echo "📁 Listando projetos..."
	docker-compose exec coderag python code_rag.py projects

# Modos de execução
web:
	@echo "🌐 Iniciando modo web..."
	docker-compose up -d

interactive:
	@echo "💬 Iniciando modo interativo..."
	docker run -it --rm \
		-v $(PROJECTS_DIR):/projects:ro \
		-v coderag_data:/data \
		-v coderag_chroma:/chroma_db \
		--add-host=host.docker.internal:host-gateway \
		$(IMAGE_NAME) interactive

# Comandos de desenvolvimento
dev-build:
	@echo "🔨 Build para desenvolvimento..."
	docker-compose -f docker-compose.dev.yml build

dev-run:
	@echo "🚀 Executando em modo desenvolvimento..."
	docker-compose -f docker-compose.dev.yml up -d

dev-logs:
	@echo "📋 Logs do desenvolvimento..."
	docker-compose -f docker-compose.dev.yml logs -f

# Setup inicial
setup:
	@echo "⚙️ Configuração inicial..."
	@mkdir -p $(PROJECTS_DIR)
	@if [ ! -f .env ]; then cp .env.example .env; echo "📝 Arquivo .env criado"; fi
	@echo "✅ Setup concluído!"
	@echo "💡 Próximos passos:"
	@echo "   1. Ajuste as configurações em .env"
	@echo "   2. Coloque seus projetos em ./projects/"
	@echo "   3. Execute: make run"
