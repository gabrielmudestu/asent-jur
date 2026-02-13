FROM python:3.11-slim

WORKDIR /app

# evita gerar cache desnecessário
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# dependências do sistema
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

# instala dependências python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install gunicorn

# copia projeto
COPY . .

# expõe porta
EXPOSE 8000

# comando produção
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "run:app"]
