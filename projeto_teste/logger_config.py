import logging
import os

# Define o nome do arquivo de log
LOG_FILE = 'registro_acessos.log'

# Verifica se o arquivo existe e o cria se necessário
if not os.path.exists(LOG_FILE):
    # Cria o arquivo vazio para garantir que o logging possa escrever nele
    open(LOG_FILE, 'a').close()

def setup_logger():
    """
    Configura o logger principal para a aplicação.
    """
    # 1. Cria o objeto logger
    logger = logging.getLogger('sistema_juridico')
    logger.setLevel(logging.INFO) # Define o nível mínimo de registro

    # 2. Cria o formatter (formato da mensagem)
    # Formato: Data e Hora - Nível - IP do Usuário - Mensagem
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 3. Cria o FileHandler (onde o log será salvo - um arquivo)
    file_handler = logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8')
    file_handler.setFormatter(formatter)

    # 4. Adiciona o handler ao logger
    if not logger.handlers: # Evita adicionar handlers múltiplos vezes
        logger.addHandler(file_handler)
        
    return logger

# Inicializa o logger para ser importado em app.py
sistema_logger = setup_logger()