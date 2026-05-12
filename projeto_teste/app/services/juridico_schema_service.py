def garantir_schema_juridico(db):
    with db.cursor(dictionary=True) as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processos (
                id INT AUTO_INCREMENT PRIMARY KEY,
                empresa_id INT NULL,
                numero_processo VARCHAR(120) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            SELECT CONSTRAINT_NAME
            FROM information_schema.REFERENTIAL_CONSTRAINTS
            WHERE CONSTRAINT_SCHEMA = DATABASE()
              AND TABLE_NAME = 'processos'
              AND REFERENCED_TABLE_NAME = 'municipal_lots'
        """)
        for constraint in cursor.fetchall():
            cursor.execute(f"ALTER TABLE processos DROP FOREIGN KEY `{constraint['CONSTRAINT_NAME']}`")

        cursor.execute("SHOW COLUMNS FROM processos LIKE 'empresa_id'")
        if cursor.fetchone():
            cursor.execute("ALTER TABLE processos MODIFY COLUMN empresa_id INT NULL")
        else:
            cursor.execute("ALTER TABLE processos ADD COLUMN empresa_id INT NULL AFTER id")

        colunas = {
            'titulo': "ALTER TABLE processos ADD COLUMN titulo VARCHAR(255) AFTER numero_processo",
            'descricao': "ALTER TABLE processos ADD COLUMN descricao TEXT AFTER titulo",
            'tipo_acao': "ALTER TABLE processos ADD COLUMN tipo_acao VARCHAR(120) AFTER descricao",
            'tipo_processo': "ALTER TABLE processos ADD COLUMN tipo_processo VARCHAR(100) AFTER tipo_acao",
            'tribunal': "ALTER TABLE processos ADD COLUMN tribunal VARCHAR(120) AFTER tipo_processo",
            'vara': "ALTER TABLE processos ADD COLUMN vara VARCHAR(120) AFTER tribunal",
            'comarca': "ALTER TABLE processos ADD COLUMN comarca VARCHAR(120) AFTER vara",
            'valor_da_causa': "ALTER TABLE processos ADD COLUMN valor_da_causa DECIMAL(15, 2) AFTER comarca",
            'status': "ALTER TABLE processos ADD COLUMN status VARCHAR(100) AFTER valor_da_causa",
            'fase': "ALTER TABLE processos ADD COLUMN fase VARCHAR(120) AFTER status",
            'data_criacao': "ALTER TABLE processos ADD COLUMN data_criacao DATE AFTER fase",
            'assunto_judicial': "ALTER TABLE processos ADD COLUMN assunto_judicial TEXT AFTER data_criacao",
            'recurso_acionado': "ALTER TABLE processos ADD COLUMN recurso_acionado BOOLEAN DEFAULT FALSE AFTER assunto_judicial",
            'tipo_recurso': "ALTER TABLE processos ADD COLUMN tipo_recurso VARCHAR(100) AFTER recurso_acionado",
        }

        cursor.execute("""
            SELECT COLUMN_NAME
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'processos'
        """)
        colunas_existentes = {row['COLUMN_NAME'] for row in cursor.fetchall()}

        for nome_coluna, alter_sql in colunas.items():
            if nome_coluna not in colunas_existentes:
                cursor.execute(alter_sql)

        cursor.execute("""
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
            )
        """)

        cursor.execute("""
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
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processo_documentos (
                id INT AUTO_INCREMENT PRIMARY KEY,
                processo_id INT NOT NULL,
                nome VARCHAR(255) NOT NULL,
                tipo VARCHAR(80),
                data_documento DATE,
                observacao TEXT,
                nome_arquivo_original VARCHAR(255) NOT NULL,
                nome_arquivo_salvo VARCHAR(255) NOT NULL,
                caminho_arquivo VARCHAR(500) NOT NULL,
                content_type VARCHAR(120),
                tamanho_bytes BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT fk_processo_documentos
                    FOREIGN KEY (processo_id)
                    REFERENCES processos(id)
                    ON DELETE CASCADE
            )
        """)

    db.commit()
