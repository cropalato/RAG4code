#!/bin/bash
set -e

echo "🐳 CodeRAG Docker Container Starting..."
echo "Configuration:"
echo "  OLLAMA_HOST: ${OLLAMA_HOST:-http://host.docker.internal:11434}"
echo "  EMBEDDING_MODEL: ${EMBEDDING_MODEL:-nomic-embed-text}"
echo "  CHAT_MODEL: ${CHAT_MODEL:-qwen2.5-coder}"
echo "  COLLECTION_NAME: ${COLLECTION_NAME:-code_project}"

# Verificar se diretórios essenciais existem
mkdir -p /data /projects /chroma_db

# Aguardar Ollama estar disponível se especificado
if [ "${WAIT_FOR_OLLAMA:-true}" = "true" ]; then
	echo "⏳ Aguardando Ollama estar disponível..."
	timeout=60
	while [ $timeout -gt 0 ]; do
		if curl -s "${OLLAMA_HOST:-http://host.docker.internal:11434}/api/tags" >/dev/null 2>&1; then
			echo "✅ Ollama está disponível"
			break
		fi
		echo "   Tentando conectar ao Ollama... ($timeout segundos restantes)"
		sleep 5
		timeout=$((timeout - 5))
	done

	if [ $timeout -le 0 ]; then
		echo "⚠️ Timeout aguardando Ollama, continuando mesmo assim..."
	fi
fi

# Executar comando baseado no argumento
case "$1" in
"web")
	echo "🌐 Iniciando API Web..."
	exec python web_api.py
	;;
"interactive")
	echo "💬 Iniciando modo interativo..."
	exec python interactive.py
	;;
"cli")
	shift
	echo "⌨️ Executando comando CLI..."
	exec python code_rag.py "$@"
	;;
"index")
	if [ -z "$2" ]; then
		echo "❌ Uso: docker run ... index <nome_do_projeto>"
		exit 1
	fi
	echo "📦 Indexando projeto: $2"
	exec python code_rag.py index --project "$2"
	;;
"ask")
	if [ -z "$2" ]; then
		echo "❌ Uso: docker run ... ask \"<sua_pergunta>\""
		exit 1
	fi
	echo "❓ Fazendo pergunta: $2"
	exec python code_rag.py ask --question "$2"
	;;
"bash")
	echo "🐚 Iniciando shell..."
	exec /bin/bash
	;;
*)
	echo "Comandos disponíveis:"
	echo "  web        - Iniciar API web (padrão)"
	echo "  interactive - Modo interativo"
	echo "  cli        - Linha de comando"
	echo "  index <projeto> - Indexar projeto específico"
	echo "  ask \"<pergunta>\" - Fazer pergunta"
	echo "  bash       - Shell interativo"
	exit 1
	;;
esac
