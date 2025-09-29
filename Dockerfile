# 1. Escolha uma imagem base oficial do Python que seja Debian (que tem apt-get)
FROM python:3.11-slim-bookworm

# 2. Defina o diretório de trabalho dentro do contêiner
WORKDIR /app

# 3. Instale as dependências do sistema (incluindo o Google Chrome)
# Usamos apt-get aqui porque a imagem base é Debian e nós temos controle
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    # Instala o Google Chrome
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list' \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    # Limpa o cache para manter a imagem pequena
    && rm -rf /var/lib/apt/lists/*

# 4. Copie o arquivo de requisitos e instale as dependências do Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copie o resto do código do seu projeto para o contêiner
COPY . .

# 6. Exponha a porta que seu Gunicorn/Flask irá usar (Render usa 10000 por padrão)
EXPOSE 5000

# 7. O comando para iniciar sua aplicação (substitua 'app:app' se necessário)
# O bind 0.0.0.0:10000 é importante para o Render
CMD ["gunicorn", "main:app", "--bind", "0.0.0.0:5000"]