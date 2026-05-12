ALTER TABLE processos
    ADD COLUMN IF NOT EXISTS titulo VARCHAR(255) AFTER numero_processo,
    ADD COLUMN IF NOT EXISTS descricao TEXT AFTER titulo,
    ADD COLUMN IF NOT EXISTS tipo_acao VARCHAR(120) AFTER descricao,
    ADD COLUMN IF NOT EXISTS tribunal VARCHAR(120) AFTER tipo_processo,
    ADD COLUMN IF NOT EXISTS vara VARCHAR(120) AFTER tribunal,
    ADD COLUMN IF NOT EXISTS comarca VARCHAR(120) AFTER vara,
    ADD COLUMN IF NOT EXISTS fase VARCHAR(120) AFTER status,
    ADD COLUMN IF NOT EXISTS data_criacao DATE AFTER fase;

CREATE TABLE IF NOT EXISTS processo_partes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    processo_id INT NOT NULL,
    papel VARCHAR(30) NOT NULL,
    nome VARCHAR(255) NOT NULL,
    tipo_parte VARCHAR(120),
    contato VARCHAR(255),
    observacoes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_processo_partes
        FOREIGN KEY (processo_id)
        REFERENCES processos(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS processo_eventos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    processo_id INT NOT NULL,
    categoria VARCHAR(30) NOT NULL,
    titulo VARCHAR(255),
    descricao TEXT NOT NULL,
    data_evento DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_processo_eventos
        FOREIGN KEY (processo_id)
        REFERENCES processos(id)
        ON DELETE CASCADE
);

UPDATE processos
SET titulo = COALESCE(NULLIF(titulo, ''), numero_processo),
    descricao = COALESCE(NULLIF(descricao, ''), assunto_judicial),
    tipo_acao = COALESCE(NULLIF(tipo_acao, ''), NULLIF(tipo_processo, ''), 'civel')
WHERE titulo IS NULL
   OR titulo = ''
   OR tipo_acao IS NULL
   OR tipo_acao = '';
