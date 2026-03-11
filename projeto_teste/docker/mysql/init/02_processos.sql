CREATE TABLE IF NOT EXISTS processos (
    id INT AUTO_INCREMENT PRIMARY KEY,
    empresa_id INT NOT NULL,

    numero_processo VARCHAR(120) NOT NULL,
    status VARCHAR(100),
    assunto_judicial TEXT,
    valor_da_causa DECIMAL(15, 2),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_empresa_processo
        FOREIGN KEY (empresa_id)
        REFERENCES municipal_lots(id)
        ON DELETE CASCADE
);

CREATE INDEX idx_empresa_processo
ON processos(empresa_id);