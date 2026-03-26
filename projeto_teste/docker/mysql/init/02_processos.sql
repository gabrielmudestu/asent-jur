CREATE TABLE IF NOT EXISTS processos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,

    numero_processo VARCHAR(120) NOT NULL,
    tipo_processo VARCHAR(100),
    status VARCHAR(100),
    assunto_judicial TEXT,
    valor_da_causa DECIMAL(15, 2),
    recurso_acionado BOOLEAN DEFAULT FALSE,
    tipo_recurso VARCHAR(100),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_empresa_processo
        FOREIGN KEY (empresa_id)
        REFERENCES municipal_lots(id)
        ON DELETE CASCADE
);

CREATE INDEX idx_empresa_processo
ON processos(empresa_id);

ALTER TABLE processos
    ADD COLUMN IF NOT EXISTS tipo_processo VARCHAR(100) AFTER numero_processo,
    ADD COLUMN IF NOT EXISTS recurso_acionado BOOLEAN DEFAULT FALSE AFTER valor_da_causa,
    ADD COLUMN IF NOT EXISTS tipo_recurso VARCHAR(100) AFTER recurso_acionado;
