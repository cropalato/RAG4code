#!/bin/bash

# Verificar se o processo principal está rodando
if ! pgrep -f "python" >/dev/null; then
	echo "❌ Processo Python não está rodando"
	exit 1
fi

# Se for API web, verificar endpoint de health
if [ "${1:-web}" = "web" ]; then
	if ! curl -f -s http://localhost:8080/health >/dev/null; then
		echo "❌ API web não está respondendo"
		exit 1
	fi
fi

# Verificar se diretórios essenciais existem e são acessíveis
for dir in /data /projects /chroma_db; do
	if [ ! -d "$dir" ] || [ ! -w "$dir" ]; then
		echo "❌ Diretório $dir não está acessível"
		exit 1
	fi
done

echo "✅ Container saudável"
exit 0
