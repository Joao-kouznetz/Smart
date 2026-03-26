FROM python:3.10-slim 

# Definindo o diretório de trabalho
WORKDIR /usr/local/app

# Copiando o conteúdo da pasta local 'app' para dentro do container
COPY ./ ./

# Instalando as dependências
# Caso você tenha um requirements.txt, utilize:
COPY requirements.txt ./ 
# Instalando as dependências
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install mysql-connector-python
RUN pip install mkdocs


# Garantir que a pasta do app tenha permissões corretas para o SQLite
RUN chmod -R 777 /usr/local/app

# Expondo a porta para acesso externo
EXPOSE 8000


# Comando padrão para rodar a aplicação
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]