#!/bin/bash
# Script de inicialização automática do ProxyTester
# Configura o ambiente virtual Python e inicia o backend FastAPI

set -e

# Cores para o terminal
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Iniciando ProxyTester ===${NC}"

# Navega para o diretório do backend
cd "$(dirname "$0")/backend"

# Verifica se o ambiente virtual existe
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Criando ambiente virtual Python (.venv)...${NC}"
    python3 -m venv .venv
fi

# Ativa o ambiente virtual
echo -e "${GREEN}Ativando ambiente virtual...${NC}"
source .venv/bin/activate

# Instala/atualiza dependências
echo -e "${GREEN}Instalando/atualizando dependências...${NC}"
pip install --upgrade pip
pip install -r requirements.txt

# Inicia o servidor uvicorn
echo -e "${BLUE}Iniciando servidor na porta 8000...${NC}"
echo -e "${YELLOW}Abra seu navegador em: http://localhost:8000${NC}"
uvicorn main:app --host 0.0.0.0 --port 8000
