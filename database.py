import sqlite3
import os
import traceback
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from config import Config


class DatabaseManager:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or Config.DATABASE_PATH

    def get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def __enter__(self):
        self._conn = self.get_connection()
        return self._conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._conn:
            self._conn.close()

    def init_database(self):
        with self as conn:
            # Criação das tabelas
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS clientes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    telefone TEXT NOT NULL, 
                    nome TEXT,
                    usuario_iptv TEXT UNIQUE, 
                    senha_iptv TEXT, 
                    data_criacao DATETIME, 
                    data_expiracao DATETIME,
                    conexoes INTEGER DEFAULT 1, 
                    plano TEXT, 
                    status TEXT, 
                    ultimo_teste DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP, 
                    ultima_sincronizacao DATETIME
                )
            """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pagamentos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    cliente_id INTEGER, 
                    telefone TEXT, 
                    valor REAL,
                    payment_id TEXT UNIQUE, 
                    status TEXT DEFAULT 'pendente', 
                    data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
                    data_pagamento DATETIME, 
                    contexto TEXT DEFAULT 'comprar', 
                    dados_temporarios TEXT,
                    FOREIGN KEY (cliente_id) REFERENCES clientes (id)
                )
            """
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS configuracoes (chave TEXT PRIMARY KEY, valor TEXT, descricao TEXT)"
            )
            conn.execute(
                "CREATE TABLE IF NOT EXISTS logs_sistema (id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT NOT NULL, mensagem TEXT NOT NULL, detalhes TEXT, data_log DATETIME DEFAULT CURRENT_TIMESTAMP)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversas (telefone TEXT PRIMARY KEY, contexto TEXT, estado TEXT DEFAULT '{}', dados_temporarios TEXT DEFAULT '{}', ultima_interacao DATETIME DEFAULT CURRENT_TIMESTAMP)"""
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS templates_avisos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT UNIQUE NOT NULL,
                    assunto TEXT,
                    corpo TEXT NOT NULL,
                    tipo TEXT DEFAULT 'whatsapp', -- 'whatsapp', 'email', etc.
                    data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
                    data_atualizacao DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()
            self.inserir_configs_padrao(conn)
            self.inserir_templates_padrao(conn)

    def inserir_configs_padrao(self, conn):
        configs = [
            (
                "link_acesso",
                Config.LINK_ACESSO_DEFAULT,
                "Link de acesso principal dos clientes",
            ),
            ("preco_mes", str(Config.PRECO_MES_DEFAULT), "Preço por mês em R$"),
            (
                "preco_conexao",
                str(Config.PRECO_CONEXAO_DEFAULT),
                "Preço por conexão adicional em R$",
            ),
        ]
        for chave, valor, desc in configs:
            conn.execute(
                "INSERT OR IGNORE INTO configuracoes (chave, valor, descricao) VALUES (?, ?, ?)",
                (chave, valor, desc),
            )
        conn.commit()

    def inserir_templates_padrao(self, conn):
        templates = [
            (
                "aviso_vencimento_whatsapp",
                "Sua lista está para vencer!",
                "Olá {{nome_cliente}}! Sua lista {{nome_lista}} (ID: {{id_lista}}) irá vencer em {{data_vencimento}} (faltam {{dias_restantes}} dias). Renove já para não perder o acesso!",
                "whatsapp",
            )
        ]
        for nome, assunto, corpo, tipo in templates:
            conn.execute(
                "INSERT OR IGNORE INTO templates_avisos (nome, assunto, corpo, tipo) VALUES (?, ?, ?, ?)",
                (nome, assunto, corpo, tipo),
            )
        conn.commit()

    # === MÉTODOS PARA TEMPLATES DE AVISOS ===

    def get_template(self, nome: str) -> Optional[Dict]:
        with self as conn:
            result = conn.execute(
                "SELECT * FROM templates_avisos WHERE nome = ?", (nome,)
            ).fetchone()
            return dict(result) if result else None

    def update_template(self, nome: str, assunto: str, corpo: str) -> bool:
        with self as conn:
            cursor = conn.execute(
                "UPDATE templates_avisos SET assunto = ?, corpo = ?, data_atualizacao = CURRENT_TIMESTAMP WHERE nome = ?",
                (assunto, corpo, nome),
            )
            conn.commit()
            return cursor.rowcount > 0

    # === MÉTODOS PARA CLIENTES ===

    def criar_cliente(self, telefone: str, nome: str = None) -> int:
        with self as conn:
            cursor = conn.execute(
                "INSERT INTO clientes (telefone, nome) VALUES (?, ?)", (telefone, nome)
            )
            conn.commit()
            return cursor.lastrowid

    def buscar_cliente_por_telefone(self, telefone: str) -> Optional[Dict]:
        with self as conn:
            result = conn.execute(
                "SELECT * FROM clientes WHERE telefone = ? ORDER BY id DESC LIMIT 1",
                (telefone,),
            ).fetchone()
            return dict(result) if result else None

    def buscar_cliente_por_usuario_iptv(self, usuario_iptv: str) -> Optional[Dict]:
        with self as conn:
            result = conn.execute(
                "SELECT * FROM clientes WHERE usuario_iptv = ?", (usuario_iptv,)
            ).fetchone()
            return dict(result) if result else None

    def criar_ou_atualizar_cliente(
        self, telefone: str, usuario_iptv: str, nome: str = ""
    ):
        """Cria um novo cliente ou atualiza um existente com base no telefone."""
        with self as conn:
            # Verifica se já existe um cliente com este telefone
            existente = conn.execute(
                "SELECT id FROM clientes WHERE telefone = ?", (telefone,)
            ).fetchone()

            if existente:
                # Atualiza
                query = """
                    UPDATE clientes 
                    SET nome = ?, usuario_iptv = ? 
                    WHERE telefone = ?
                """
                conn.execute(query, (nome, usuario_iptv, telefone))
            else:
                # Insere
                query = """
                    INSERT INTO clientes (nome, telefone, usuario_iptv, status) 
                    VALUES (?, ?, ?, 'manual')
                """
                conn.execute(query, (nome, telefone, usuario_iptv))

            conn.commit()

    def buscar_lista_por_usuario_e_telefone(
        self, usuario_iptv: str, telefone: str
    ) -> Optional[Dict]:
        """Busca uma lista específica que pertence a um número de telefone."""
        with self as conn:
            query = "SELECT * FROM clientes WHERE usuario_iptv = ? AND telefone = ?"
            result = conn.execute(query, (usuario_iptv, telefone)).fetchone()
            return dict(result) if result else None

    def atualizar_lista_cliente(
        self,
        telefone: str,
        usuario_iptv: str,
        senha_iptv: str,
        conexoes: int,
        meses: int,
    ):
        with self as conn:
            data_criacao = datetime.now()
            data_expiracao = data_criacao + timedelta(days=30 * meses)
            conn.execute(
                "UPDATE clientes SET usuario_iptv = ?, senha_iptv = ?, conexoes = ?, data_criacao = ?, data_expiracao = ?, status = 'ativo' WHERE telefone = ? AND usuario_iptv IS NULL ORDER BY id DESC LIMIT 1",
                (
                    usuario_iptv,
                    senha_iptv,
                    conexoes,
                    data_criacao,
                    data_expiracao,
                    telefone,
                ),
            )
            conn.commit()

    def atualizar_cliente_pos_compra(
        self,
        telefone: str,
        usuario_iptv: str,
        senha_iptv: str,
        conexoes: int,
        data_criacao: datetime,
        data_expiracao: datetime,
        plano: str = None,
    ):
        """Atualiza cliente após compra bem-sucedida"""
        with self as conn:
            conn.execute(
                """
                UPDATE clientes 
                SET usuario_iptv = ?, senha_iptv = ?, conexoes = ?, data_criacao = ?, data_expiracao = ?, plano = ?, status = 'ativo'
                WHERE telefone = ? AND usuario_iptv IS NULL
                ORDER BY id DESC LIMIT 1
            """,
                (
                    usuario_iptv,
                    senha_iptv,
                    conexoes,
                    data_criacao,
                    data_expiracao,
                    plano,
                    telefone,
                ),
            )
            conn.commit()

    def renovar_lista_cliente(self, usuario_iptv: str, meses: int):
        """Esta função ATUALIZA a data de expiração no banco, após a renovação no BitPanel."""
        with self as conn:
            cliente = self.buscar_cliente_por_usuario_iptv(usuario_iptv)
            if not cliente or not cliente["data_expiracao"]:
                return

            data_base = max(
                datetime.now(), datetime.fromisoformat(cliente["data_expiracao"])
            )
            nova_expiracao = data_base + timedelta(days=30 * meses)

            conn.execute(
                "UPDATE clientes SET data_expiracao = ?, status = 'ativo' WHERE usuario_iptv = ?",
                (nova_expiracao, usuario_iptv),
            )
            conn.commit()
            print(
                f"[DB] Data de expiração de {usuario_iptv} atualizada para {nova_expiracao.strftime('%d/%m/%Y')}"
            )

    def atualizar_cliente_manual(self, usuario_iptv: str, dados: Dict) -> bool:
        """Atualiza dados de um cliente manualmente"""
        with self as conn:
            updates = []
            params = []

            for campo, valor in dados.items():
                if campo in [
                    "nome",
                    "conexoes",
                    "data_expiracao",
                    "status",
                    "senha_iptv",
                    "plano",
                ]:
                    updates.append(f"{campo} = ?")
                    params.append(valor)

            if updates:
                params.append(usuario_iptv)
                query = (
                    f"UPDATE clientes SET {', '.join(updates)} WHERE usuario_iptv = ?"
                )
                conn.execute(query, params)
                conn.commit()
                return True

            return False

    def marcar_teste_cliente(self, telefone: str, usuario_teste: str, senha_teste: str):
        """Marcar que cliente fez teste"""
        with self as conn:
            conn.execute(
                """
                UPDATE clientes 
                SET ultimo_teste = ?, usuario_iptv = ?, senha_iptv = ?
                WHERE telefone = ?
            """,
                (datetime.now(), usuario_teste, senha_teste, telefone),
            )
            conn.commit()

    def pode_fazer_teste(self, telefone: str) -> bool:
        """Verificar se cliente pode fazer teste"""
        with self as conn:
            result = conn.execute(
                """
                SELECT ultimo_teste FROM clientes WHERE telefone = ?
            """,
                (telefone,),
            ).fetchone()

            if not result or not result["ultimo_teste"]:
                return True

            ultimo_teste = datetime.fromisoformat(result["ultimo_teste"])
            intervalo_horas = int(self.get_config("teste_intervalo", "24"))

            return (datetime.now() - ultimo_teste).total_seconds() > (
                intervalo_horas * 3600
            )

    def excluir_cliente_por_telefone(self, telefone: str) -> bool:
        with self as conn:
            cursor = conn.execute(
                "DELETE FROM clientes WHERE telefone = ? AND usuario_iptv IS NULL",
                (telefone,),
            )
            conn.commit()
            return cursor.rowcount > 0

    def excluir_cliente(self, usuario_iptv: str) -> bool:
        """Exclui um cliente do banco de dados"""
        with self as conn:
            # Verificar se existe
            cliente = conn.execute(
                "SELECT id FROM clientes WHERE usuario_iptv = ?", (usuario_iptv,)
            ).fetchone()
            if not cliente:
                return False

            # Excluir registros relacionados primeiro
            conn.execute(
                "DELETE FROM pagamentos WHERE cliente_id = ?", (cliente["id"],)
            )

            # Excluir cliente
            conn.execute("DELETE FROM clientes WHERE usuario_iptv = ?", (usuario_iptv,))

            conn.commit()
            self.log_sistema("info", f"Cliente {usuario_iptv} excluído do banco")
            return True

    def obter_todos_usuarios_iptv(self) -> List[str]:
        """Retorna lista de todos os usuários IPTV cadastrados"""
        with self as conn:
            results = conn.execute(
                """
                SELECT usuario_iptv FROM clientes 
                WHERE usuario_iptv IS NOT NULL AND usuario_iptv != ''
                ORDER BY created_at DESC
            """
            ).fetchall()

            return [row["usuario_iptv"] for row in results]

    # === MÉTODOS PARA PAGAMENTOS ===

    def criar_pagamento(
        self,
        cliente_id: int,
        valor: float,
        payment_id: str,
        copia_cola: str,
        contexto: str = "comprar",
        dados_temporarios: str = None,
    ):
        """Criar registro de pagamento"""
        with self as conn:
            conn.execute(
                """
                INSERT INTO pagamentos (cliente_id, valor, payment_id, contexto, dados_temporarios)
                VALUES (?, ?, ?, ?, ?)
            """,
                (cliente_id, valor, payment_id, contexto, dados_temporarios),
            )
            conn.commit()

    def buscar_pagamento(self, payment_id: str) -> Optional[Dict]:
        with self as conn:
            result = conn.execute(
                "SELECT * FROM pagamentos WHERE payment_id = ?", (payment_id,)
            ).fetchone()
            return dict(result) if result else None

    def atualizar_status_pagamento(self, payment_id: str, status: str):
        with self as conn:
            conn.execute(
                "UPDATE pagamentos SET status = ?, data_pagamento = CURRENT_TIMESTAMP WHERE payment_id = ?",
                (status, payment_id),
            )
            conn.commit()

    def buscar_pagamentos_por_cliente_id(self, cliente_id: int) -> List[Dict]:
        with self as conn:
            results = conn.execute(
                "SELECT * FROM pagamentos WHERE cliente_id = ?", (cliente_id,)
            ).fetchall()
            return [dict(row) for row in results]

    # === MÉTODOS PARA CONFIGURAÇÕES ===

    def get_config(self, chave: str, default: str = None) -> Optional[str]:
        with self as conn:
            result = conn.execute(
                "SELECT valor FROM configuracoes WHERE chave = ?", (chave,)
            ).fetchone()
            return result["valor"] if result else default

    def set_config(self, chave: str, valor: str):
        with self as conn:
            conn.execute(
                "INSERT OR REPLACE INTO configuracoes (chave, valor) VALUES (?, ?)",
                (chave, valor),
            )
            conn.commit()

    # === MÉTODOS PARA LOGS ===

    def log_sistema(self, tipo: str, mensagem: str, detalhes: str = None):
        with self as conn:
            conn.execute(
                "INSERT INTO logs_sistema (tipo, mensagem, detalhes) VALUES (?, ?, ?)",
                (tipo, mensagem, detalhes),
            )
            conn.commit()

    def get_logs_sistema(self, limit: int = 100) -> List[Dict]:
        with self as conn:
            results = conn.execute(
                "SELECT * FROM logs_sistema ORDER BY data_log DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(row) for row in results]

    # === MÉTODOS PARA CONVERSAS ===

    def get_conversa(self, telefone: str) -> Optional[Dict]:
        with self as conn:
            result = conn.execute(
                "SELECT * FROM conversas WHERE telefone = ?", (telefone,)
            ).fetchone()
            return dict(result) if result else None

    def set_conversa(self, telefone: str, contexto: str, estado: str = "{}", dados_temporarios: str = "{}"):
        with self as conn:
            conn.execute(
                "INSERT OR REPLACE INTO conversas (telefone, contexto, estado, dados_temporarios, ultima_interacao) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
                (telefone, contexto, estado, dados_temporarios),
            )
            conn.commit()

    def atualizar_estado_conversa(self, telefone: str, estado: str):
        with self as conn:
            conn.execute(
                "UPDATE conversas SET estado = ?, ultima_interacao = CURRENT_TIMESTAMP WHERE telefone = ?",
                (estado, telefone),
            )
            conn.commit()

    def atualizar_contexto_conversa(self, telefone: str, contexto: str):
        with self as conn:
            conn.execute(
                "UPDATE conversas SET contexto = ?, ultima_interacao = CURRENT_TIMESTAMP WHERE telefone = ?",
                (contexto, telefone),
            )
            conn.commit()

    def atualizar_dados_temporarios_conversa(self, telefone: str, dados_temporarios: str):
        with self as conn:
            conn.execute(
                "UPDATE conversas SET dados_temporarios = ?, ultima_interacao = CURRENT_TIMESTAMP WHERE telefone = ?",
                (dados_temporarios, telefone),
            )
            conn.commit()

    def deletar_conversa(self, telefone: str):
        with self as conn:
            conn.execute("DELETE FROM conversas WHERE telefone = ?", (telefone,))
            conn.commit()

    def listar_clientes_expirando(self, dias: int = 7) -> List[Dict]:
        with self as conn:
            data_limite = (datetime.now() + timedelta(days=dias)).strftime('%Y-%m-%d')
            query = """
                SELECT 
                    nome, 
                    telefone, 
                    usuario_iptv, 
                    data_expiracao 
                FROM 
                    clientes 
                WHERE 
                    data_expiracao IS NOT NULL AND 
                    data_expiracao <= ? AND
                    status = 'ativo'
                ORDER BY 
                    data_expiracao ASC
            """
            results = conn.execute(query, (data_limite,)).fetchall()
            return [dict(row) for row in results]

    def contar_clientes_por_status(self) -> Dict[str, int]:
        with self as conn:
            query = "SELECT status, COUNT(*) as count FROM clientes GROUP BY status"
            results = conn.execute(query).fetchall()
            return {row['status']: row['count'] for row in results}

    def contar_clientes_por_plano(self) -> Dict[str, int]:
        with self as conn:
            query = "SELECT plano, COUNT(*) as count FROM clientes WHERE plano IS NOT NULL GROUP BY plano"
            results = conn.execute(query).fetchall()
            return {row['plano']: row['count'] for row in results}

    def contar_clientes_expirando_por_periodo(self, dias: int = 7) -> Dict[str, int]:
        with self as conn:
            data_limite = (datetime.now() + timedelta(days=dias)).strftime('%Y-%m-%d')
            query = """
                SELECT 
                    COUNT(*) as count 
                FROM 
                    clientes 
                WHERE 
                    data_expiracao IS NOT NULL AND 
                    data_expiracao <= ? AND
                    status = 'ativo'
            """
            result = conn.execute(query, (data_limite,)).fetchone()
            return {'expirando': result['count'] if result else 0}

    def get_all_templates(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM templates_avisos").fetchall()
            return [dict(row) for row in results]

    def add_template(self, nome: str, assunto: str, corpo: str, tipo: str = 'whatsapp') -> int:
        with self as conn:
            cursor = conn.execute(
                "INSERT INTO templates_avisos (nome, assunto, corpo, tipo) VALUES (?, ?, ?, ?)",
                (nome, assunto, corpo, tipo)
            )
            conn.commit()
            return cursor.lastrowid

    def delete_template(self, nome: str) -> bool:
        with self as conn:
            cursor = conn.execute("DELETE FROM templates_avisos WHERE nome = ?", (nome,))
            conn.commit()
            return cursor.rowcount > 0

    def get_cliente_by_id(self, cliente_id: int) -> Optional[Dict]:
        with self as conn:
            result = conn.execute("SELECT * FROM clientes WHERE id = ?", (cliente_id,)).fetchone()
            return dict(result) if result else None

    def get_cliente_by_usuario_iptv(self, usuario_iptv: str) -> Optional[Dict]:
        with self as conn:
            result = conn.execute("SELECT * FROM clientes WHERE usuario_iptv = ?", (usuario_iptv,)).fetchone()
            return dict(result) if result else None

    def get_cliente_by_telefone(self, telefone: str) -> Optional[Dict]:
        with self as conn:
            result = conn.execute("SELECT * FROM clientes WHERE telefone = ?", (telefone,)).fetchone()
            return dict(result) if result else None

    def get_all_clientes(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM clientes").fetchall()
            return [dict(row) for row in results]

    def update_cliente_status(self, usuario_iptv: str, status: str) -> bool:
        with self as conn:
            cursor = conn.execute("UPDATE clientes SET status = ? WHERE usuario_iptv = ?", (status, usuario_iptv))
            conn.commit()
            return cursor.rowcount > 0

    def update_cliente_plano(self, usuario_iptv: str, plano: str) -> bool:
        with self as conn:
            cursor = conn.execute("UPDATE clientes SET plano = ? WHERE usuario_iptv = ?", (plano, usuario_iptv))
            conn.commit()
            return cursor.rowcount > 0

    def update_cliente_conexoes(self, usuario_iptv: str, conexoes: int) -> bool:
        with self as conn:
            cursor = conn.execute("UPDATE clientes SET conexoes = ? WHERE usuario_iptv = ?", (conexoes, usuario_iptv))
            conn.commit()
            return cursor.rowcount > 0

    def update_cliente_senha_iptv(self, usuario_iptv: str, senha_iptv: str) -> bool:
        with self as conn:
            cursor = conn.execute("UPDATE clientes SET senha_iptv = ? WHERE usuario_iptv = ?", (senha_iptv, usuario_iptv))
            conn.commit()
            return cursor.rowcount > 0

    def update_cliente_nome(self, usuario_iptv: str, nome: str) -> bool:
        with self as conn:
            cursor = conn.execute("UPDATE clientes SET nome = ? WHERE usuario_iptv = ?", (nome, usuario_iptv))
            conn.commit()
            return cursor.rowcount > 0

    def update_cliente_telefone(self, usuario_iptv: str, telefone: str) -> bool:
        with self as conn:
            cursor = conn.execute("UPDATE clientes SET telefone = ? WHERE usuario_iptv = ?", (telefone, usuario_iptv))
            conn.commit()
            return cursor.rowcount > 0

    def update_cliente_data_expiracao(self, usuario_iptv: str, data_expiracao: datetime) -> bool:
        with self as conn:
            cursor = conn.execute("UPDATE clientes SET data_expiracao = ? WHERE usuario_iptv = ?", (data_expiracao, usuario_iptv))
            conn.commit()
            return cursor.rowcount > 0

    def update_cliente_data_criacao(self, usuario_iptv: str, data_criacao: datetime) -> bool:
        with self as conn:
            cursor = conn.execute("UPDATE clientes SET data_criacao = ? WHERE usuario_iptv = ?", (data_criacao, usuario_iptv))
            conn.commit()
            return cursor.rowcount > 0

    def update_cliente_ultimo_teste(self, usuario_iptv: str, ultimo_teste: datetime) -> bool:
        with self as conn:
            cursor = conn.execute("UPDATE clientes SET ultimo_teste = ? WHERE usuario_iptv = ?", (ultimo_teste, usuario_iptv))
            conn.commit()
            return cursor.rowcount > 0

    def update_cliente_ultima_sincronizacao(self, usuario_iptv: str, ultima_sincronizacao: datetime) -> bool:
        with self as conn:
            cursor = conn.execute("UPDATE clientes SET ultima_sincronizacao = ? WHERE usuario_iptv = ?", (ultima_sincronizacao, usuario_iptv))
            conn.commit()
            return cursor.rowcount > 0

    def get_estatisticas(self) -> Dict[str, Any]:
        with self as conn:
            total_clientes = conn.execute("SELECT COUNT(*) FROM clientes").fetchone()[0]
            clientes_ativos = conn.execute("SELECT COUNT(*) FROM clientes WHERE status = 'ativo'").fetchone()[0]
            clientes_inativos = conn.execute("SELECT COUNT(*) FROM clientes WHERE status = 'inativo'").fetchone()[0]
            clientes_teste = conn.execute("SELECT COUNT(*) FROM clientes WHERE status = 'teste'").fetchone()[0]
            clientes_expirando = self.contar_clientes_expirando_por_periodo(7)['expirando']

            return {
                "total_clientes": total_clientes,
                "clientes_ativos": clientes_ativos,
                "clientes_inativos": clientes_inativos,
                "clientes_teste": clientes_teste,
                "clientes_expirando": clientes_expirando,
            }

    def get_all_configs(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM configuracoes").fetchall()
            return [dict(row) for row in results]

    def update_config(self, chave: str, valor: str, descricao: str = None) -> bool:
        with self as conn:
            cursor = conn.execute("UPDATE configuracoes SET valor = ?, descricao = ? WHERE chave = ?", (valor, descricao, chave))
            conn.commit()
            return cursor.rowcount > 0

    def get_pagamentos_pendentes(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM pagamentos WHERE status = 'pendente'").fetchall()
            return [dict(row) for row in results]

    def get_pagamentos_aprovados(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM pagamentos WHERE status = 'aprovado'").fetchall()
            return [dict(row) for row in results]

    def get_pagamentos_rejeitados(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM pagamentos WHERE status = 'rejeitado'").fetchall()
            return [dict(row) for row in results]

    def get_pagamentos_por_status(self, status: str) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM pagamentos WHERE status = ?", (status,)).fetchall()
            return [dict(row) for row in results]

    def get_pagamentos_por_periodo(self, dias: int = 30) -> List[Dict]:
        with self as conn:
            data_limite = (datetime.now() - timedelta(days=dias)).strftime('%Y-%m-%d')
            query = "SELECT * FROM pagamentos WHERE data_pagamento >= ? ORDER BY data_pagamento DESC"
            results = conn.execute(query, (data_limite,)).fetchall()
            return [dict(row) for row in results]

    def get_pagamentos_por_cliente_telefone(self, telefone: str) -> List[Dict]:
        with self as conn:
            query = "SELECT p.* FROM pagamentos p JOIN clientes c ON p.cliente_id = c.id WHERE c.telefone = ? ORDER BY p.data_pagamento DESC"
            results = conn.execute(query, (telefone,)).fetchall()
            return [dict(row) for row in results]

    def get_pagamentos_por_cliente_usuario_iptv(self, usuario_iptv: str) -> List[Dict]:
        with self as conn:
            query = "SELECT p.* FROM pagamentos p JOIN clientes c ON p.cliente_id = c.id WHERE c.usuario_iptv = ? ORDER BY p.data_pagamento DESC"
            results = conn.execute(query, (usuario_iptv,)).fetchall()
            return [dict(row) for row in results]

    def get_logs_por_tipo(self, tipo: str, limit: int = 100) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM logs_sistema WHERE tipo = ? ORDER BY data_log DESC LIMIT ?", (tipo, limit)).fetchall()
            return [dict(row) for row in results]

    def get_logs_por_mensagem(self, mensagem: str, limit: int = 100) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM logs_sistema WHERE mensagem LIKE ? ORDER BY data_log DESC LIMIT ?", (f'%{mensagem}%', limit)).fetchall()
            return [dict(row) for row in results]

    def get_logs_por_detalhes(self, detalhes: str, limit: int = 100) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM logs_sistema WHERE detalhes LIKE ? ORDER BY data_log DESC LIMIT ?", (f'%{detalhes}%', limit)).fetchall()
            return [dict(row) for row in results]

    def get_conversas_por_contexto(self, contexto: str) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM conversas WHERE contexto = ? ORDER BY ultima_interacao DESC").fetchall()
            return [dict(row) for row in results]

    def get_conversas_por_estado(self, estado: str) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM conversas WHERE estado LIKE ? ORDER BY ultima_interacao DESC", (f'%{estado}%',)).fetchall()
            return [dict(row) for row in results]

    def get_conversas_por_dados_temporarios(self, dados_temporarios: str) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM conversas WHERE dados_temporarios LIKE ? ORDER BY ultima_interacao DESC", (f'%{dados_temporarios}%',)).fetchall()
            return [dict(row) for row in results]

    def get_conversas_antigas(self, dias: int = 30) -> List[Dict]:
        with self as conn:
            data_limite = (datetime.now() - timedelta(days=dias)).strftime('%Y-%m-%d %H:%M:%S')
            query = "SELECT * FROM conversas WHERE ultima_interacao <= ? ORDER BY ultima_interacao DESC"
            results = conn.execute(query, (data_limite,)).fetchall()
            return [dict(row) for row in results]

    def delete_conversas_antigas(self, dias: int = 30) -> bool:
        with self as conn:
            data_limite = (datetime.now() - timedelta(days=dias)).strftime('%Y-%m-%d %H:%M:%S')
            cursor = conn.execute("DELETE FROM conversas WHERE ultima_interacao <= ?", (data_limite,))
            conn.commit()
            return cursor.rowcount > 0

    def get_clientes_por_status(self, status: str) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM clientes WHERE status = ?", (status,)).fetchall()
            return [dict(row) for row in results]

    def get_clientes_por_plano(self, plano: str) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM clientes WHERE plano = ?", (plano,)).fetchall()
            return [dict(row) for row in results]

    def get_clientes_por_data_criacao(self, data_inicio: datetime, data_fim: datetime) -> List[Dict]:
        with self as conn:
            query = "SELECT * FROM clientes WHERE data_criacao BETWEEN ? AND ? ORDER BY data_criacao DESC"
            results = conn.execute(query, (data_inicio, data_fim)).fetchall()
            return [dict(row) for row in results]

    def get_clientes_por_data_expiracao(self, data_inicio: datetime, data_fim: datetime) -> List[Dict]:
        with self as conn:
            query = "SELECT * FROM clientes WHERE data_expiracao BETWEEN ? AND ? ORDER BY data_expiracao DESC"
            results = conn.execute(query, (data_inicio, data_fim)).fetchall()
            return [dict(row) for row in results]

    def get_clientes_com_ultimo_teste_recente(self, dias: int = 7) -> List[Dict]:
        with self as conn:
            data_limite = (datetime.now() - timedelta(days=dias)).strftime('%Y-%m-%d %H:%M:%S')
            query = "SELECT * FROM clientes WHERE ultimo_teste >= ? ORDER BY ultimo_teste DESC"
            results = conn.execute(query, (data_limite,)).fetchall()
            return [dict(row) for row in results]

    def get_clientes_sem_usuario_iptv(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM clientes WHERE usuario_iptv IS NULL OR usuario_iptv = ''").fetchall()
            return [dict(row) for row in results]

    def get_clientes_com_usuario_iptv(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM clientes WHERE usuario_iptv IS NOT NULL AND usuario_iptv != ''").fetchall()
            return [dict(row) for row in results]

    def get_clientes_com_senha_iptv(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM clientes WHERE senha_iptv IS NOT NULL AND senha_iptv != ''").fetchall()
            return [dict(row) for row in results]

    def get_clientes_sem_senha_iptv(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM clientes WHERE senha_iptv IS NULL OR senha_iptv = ''").fetchall()
            return [dict(row) for row in results]

    def get_clientes_com_conexoes(self, conexoes: int) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM clientes WHERE conexoes = ?", (conexoes,)).fetchall()
            return [dict(row) for row in results]

    def get_clientes_com_mais_de_x_conexoes(self, conexoes: int) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM clientes WHERE conexoes > ?", (conexoes,)).fetchall()
            return [dict(row) for row in results]

    def get_clientes_com_menos_de_x_conexoes(self, conexoes: int) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM clientes WHERE conexoes < ?", (conexoes,)).fetchall()
            return [dict(row) for row in results]

    def get_clientes_por_nome_parcial(self, nome_parcial: str) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM clientes WHERE nome LIKE ?", (f'%{nome_parcial}%',)).fetchall()
            return [dict(row) for row in results]

    def get_clientes_por_telefone_parcial(self, telefone_parcial: str) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM clientes WHERE telefone LIKE ?", (f'%{telefone_parcial}%',)).fetchall()
            return [dict(row) for row in results]

    def get_clientes_por_usuario_iptv_parcial(self, usuario_iptv_parcial: str) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM clientes WHERE usuario_iptv LIKE ?", (f'%{usuario_iptv_parcial}%',)).fetchall()
            return [dict(row) for row in results]

    def get_clientes_com_plano_e_status(self, plano: str, status: str) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM clientes WHERE plano = ? AND status = ?", (plano, status)).fetchall()
            return [dict(row) for row in results]

    def get_clientes_com_plano_ou_status(self, plano: str, status: str) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM clientes WHERE plano = ? OR status = ?", (plano, status)).fetchall()
            return [dict(row) for row in results]

    def get_clientes_ordenados_por_expiracao(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM clientes ORDER BY data_expiracao ASC").fetchall()
            return [dict(row) for row in results]

    def get_clientes_ordenados_por_criacao(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM clientes ORDER BY data_criacao DESC").fetchall()
            return [dict(row) for row in results]

    def get_clientes_ordenados_por_nome(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM clientes ORDER BY nome ASC").fetchall()
            return [dict(row) for row in results]

    def get_clientes_ordenados_por_telefone(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM clientes ORDER BY telefone ASC").fetchall()
            return [dict(row) for row in results]

    def get_clientes_ordenados_por_usuario_iptv(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM clientes ORDER BY usuario_iptv ASC").fetchall()
            return [dict(row) for row in results]

    def get_clientes_com_data_expiracao_nula(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM clientes WHERE data_expiracao IS NULL").fetchall()
            return [dict(row) for row in results]

    def get_clientes_com_data_criacao_nula(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM clientes WHERE data_criacao IS NULL").fetchall()
            return [dict(row) for row in results]

    def get_clientes_com_ultimo_teste_nulo(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM clientes WHERE ultimo_teste IS NULL").fetchall()
            return [dict(row) for row in results]

    def get_clientes_com_ultima_sincronizacao_nula(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM clientes WHERE ultima_sincronizacao IS NULL").fetchall()
            return [dict(row) for row in results]

    def get_clientes_com_status_e_plano_nulos(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM clientes WHERE status IS NULL AND plano IS NULL").fetchall()
            return [dict(row) for row in results]

    def get_clientes_com_status_nulo(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM clientes WHERE status IS NULL").fetchall()
            return [dict(row) for row in results]

    def get_clientes_com_plano_nulo(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM clientes WHERE plano IS NULL").fetchall()
            return [dict(row) for row in results]

    def get_clientes_com_conexoes_nulas(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM clientes WHERE conexoes IS NULL").fetchall()
            return [dict(row) for row in results]

    def get_clientes_com_senha_iptv_nula(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM clientes WHERE senha_iptv IS NULL").fetchall()
            return [dict(row) for row in results]

    def get_clientes_com_nome_nulo(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM clientes WHERE nome IS NULL").fetchall()
            return [dict(row) for row in results]

    def get_clientes_com_telefone_nulo(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM clientes WHERE telefone IS NULL").fetchall()
            return [dict(row) for row in results]

    def get_clientes_com_usuario_iptv_nulo(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM clientes WHERE usuario_iptv IS NULL").fetchall()
            return [dict(row) for row in results]

    def get_clientes_com_todos_campos_nulos(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM clientes WHERE nome IS NULL AND telefone IS NULL AND usuario_iptv IS NULL AND senha_iptv IS NULL AND data_criacao IS NULL AND data_expiracao IS NULL AND conexoes IS NULL AND plano IS NULL AND status IS NULL AND ultimo_teste IS NULL AND created_at IS NULL AND ultima_sincronizacao IS NULL").fetchall()
            return [dict(row) for row in results]

    def get_clientes_com_qualquer_campo_nulo(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM clientes WHERE nome IS NULL OR telefone IS NULL OR usuario_iptv IS NULL OR senha_iptv IS NULL OR data_criacao IS NULL OR data_expiracao IS NULL OR conexoes IS NULL OR plano IS NULL OR status IS NULL OR ultimo_teste IS NULL OR created_at IS NULL OR ultima_sincronizacao IS NULL").fetchall()
            return [dict(row) for row in results]

    def get_clientes_com_todos_campos_preenchidos(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM clientes WHERE nome IS NOT NULL AND telefone IS NOT NULL AND usuario_iptv IS NOT NULL AND senha_iptv IS NOT NULL AND data_criacao IS NOT NULL AND data_expiracao IS NOT NULL AND conexoes IS NOT NULL AND plano IS NOT NULL AND status IS NOT NULL AND ultimo_teste IS NOT NULL AND created_at IS NOT NULL AND ultima_sincronizacao IS NOT NULL").fetchall()
            return [dict(row) for row in results]

    def get_clientes_com_data_expiracao_futura(self) -> List[Dict]:
        with self as conn:
            data_atual = datetime.now().strftime('%Y-%m-%d')
            results = conn.execute("SELECT * FROM clientes WHERE data_expiracao > ? ORDER BY data_expiracao ASC", (data_atual,)).fetchall()
            return [dict(row) for row in results]

    def get_clientes_com_data_expiracao_passada(self) -> List[Dict]:
        with self as conn:
            data_atual = datetime.now().strftime('%Y-%m-%d')
            results = conn.execute("SELECT * FROM clientes WHERE data_expiracao < ? ORDER BY data_expiracao DESC", (data_atual,)).fetchall()
            return [dict(row) for row in results]

    def get_clientes_com_data_expiracao_hoje(self) -> List[Dict]:
        with self as conn:
            data_hoje = datetime.now().strftime('%Y-%m-%d')
            results = conn.execute("SELECT * FROM clientes WHERE data_expiracao = ?", (data_hoje,)).fetchall()
            return [dict(row) for row in results]

    def get_clientes_com_data_criacao_hoje(self) -> List[Dict]:
        with self as conn:
            data_hoje = datetime.now().strftime('%Y-%m-%d')
            results = conn.execute("SELECT * FROM clientes WHERE DATE(data_criacao) = ?", (data_hoje,)).fetchall()
            return [dict(row) for row in results]

    def get_clientes_com_ultimo_teste_hoje(self) -> List[Dict]:
        with self as conn:
            data_hoje = datetime.now().strftime('%Y-%m-%d')
            results = conn.execute("SELECT * FROM clientes WHERE DATE(ultimo_teste) = ?", (data_hoje,)).fetchall()
            return [dict(row) for row in results]

    def get_clientes_com_ultima_sincronizacao_hoje(self) -> List[Dict]:
        with self as conn:
            data_hoje = datetime.now().strftime('%Y-%m-%d')
            results = conn.execute("SELECT * FROM clientes WHERE DATE(ultima_sincronizacao) = ?", (data_hoje,)).fetchall()
            return [dict(row) for row in results]

    def get_pagamentos_hoje(self) -> List[Dict]:
        with self as conn:
            data_hoje = datetime.now().strftime('%Y-%m-%d')
            results = conn.execute("SELECT * FROM pagamentos WHERE DATE(data_pagamento) = ?", (data_hoje,)).fetchall()
            return [dict(row) for row in results]

    def get_pagamentos_pendentes_hoje(self) -> List[Dict]:
        with self as conn:
            data_hoje = datetime.now().strftime('%Y-%m-%d')
            results = conn.execute("SELECT * FROM pagamentos WHERE status = 'pendente' AND DATE(data_pagamento) = ?", (data_hoje,)).fetchall()
            return [dict(row) for row in results]

    def get_pagamentos_aprovados_hoje(self) -> List[Dict]:
        with self as conn:
            data_hoje = datetime.now().strftime('%Y-%m-%d')
            results = conn.execute("SELECT * FROM pagamentos WHERE status = 'aprovado' AND DATE(data_pagamento) = ?", (data_hoje,)).fetchall()
            return [dict(row) for row in results]

    def get_pagamentos_rejeitados_hoje(self) -> List[Dict]:
        with self as conn:
            data_hoje = datetime.now().strftime('%Y-%m-%d')
            results = conn.execute("SELECT * FROM pagamentos WHERE status = 'rejeitado' AND DATE(data_pagamento) = ?", (data_hoje,)).fetchall()
            return [dict(row) for row in results]

    def get_logs_hoje(self) -> List[Dict]:
        with self as conn:
            data_hoje = datetime.now().strftime('%Y-%m-%d')
            results = conn.execute("SELECT * FROM logs_sistema WHERE DATE(data_log) = ?", (data_hoje,)).fetchall()
            return [dict(row) for row in results]

    def get_logs_de_erro_hoje(self) -> List[Dict]:
        with self as conn:
            data_hoje = datetime.now().strftime('%Y-%m-%d')
            results = conn.execute("SELECT * FROM logs_sistema WHERE tipo = 'erro' AND DATE(data_log) = ?", (data_hoje,)).fetchall()
            return [dict(row) for row in results]

    def get_logs_de_info_hoje(self) -> List[Dict]:
        with self as conn:
            data_hoje = datetime.now().strftime('%Y-%m-%d')
            results = conn.execute("SELECT * FROM logs_sistema WHERE tipo = 'info' AND DATE(data_log) = ?", (data_hoje,)).fetchall()
            return [dict(row) for row in results]

    def get_logs_de_aviso_hoje(self) -> List[Dict]:
        with self as conn:
            data_hoje = datetime.now().strftime('%Y-%m-%d')
            results = conn.execute("SELECT * FROM logs_sistema WHERE tipo = 'aviso' AND DATE(data_log) = ?", (data_hoje,)).fetchall()
            return [dict(row) for row in results]

    def get_conversas_hoje(self) -> List[Dict]:
        with self as conn:
            data_hoje = datetime.now().strftime('%Y-%m-%d')
            results = conn.execute("SELECT * FROM conversas WHERE DATE(ultima_interacao) = ?", (data_hoje,)).fetchall()
            return [dict(row) for row in results]

    def get_conversas_ativas_hoje(self) -> List[Dict]:
        with self as conn:
            data_hoje = datetime.now().strftime('%Y-%m-%d')
            results = conn.execute("SELECT * FROM conversas WHERE DATE(ultima_interacao) = ? AND contexto != 'finalizado'", (data_hoje,)).fetchall()
            return [dict(row) for row in results]

    def get_conversas_finalizadas_hoje(self) -> List[Dict]:
        with self as conn:
            data_hoje = datetime.now().strftime('%Y-%m-%d')
            results = conn.execute("SELECT * FROM conversas WHERE DATE(ultima_interacao) = ? AND contexto = 'finalizado'", (data_hoje,)).fetchall()
            return [dict(row) for row in results]

    def get_conversas_por_telefone_parcial(self, telefone_parcial: str) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM conversas WHERE telefone LIKE ?", (f'%{telefone_parcial}%',)).fetchall()
            return [dict(row) for row in results]

    def get_conversas_por_contexto_e_estado(self, contexto: str, estado: str) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM conversas WHERE contexto = ? AND estado LIKE ?", (contexto, f'%{estado}%')).fetchall()
            return [dict(row) for row in results]

    def get_conversas_por_contexto_e_dados_temporarios(self, contexto: str, dados_temporarios: str) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM conversas WHERE contexto = ? AND dados_temporarios LIKE ?", (contexto, f'%{dados_temporarios}%')).fetchall()
            return [dict(row) for row in results]

    def get_conversas_por_estado_e_dados_temporarios(self, estado: str, dados_temporarios: str) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM conversas WHERE estado LIKE ? AND dados_temporarios LIKE ?", (f'%{estado}%', f'%{dados_temporarios}%')).fetchall()
            return [dict(row) for row in results]

    def get_conversas_por_todos_campos(self, telefone: str, contexto: str, estado: str, dados_temporarios: str) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM conversas WHERE telefone LIKE ? AND contexto LIKE ? AND estado LIKE ? AND dados_temporarios LIKE ?", (f'%{telefone}%', f'%{contexto}%', f'%{estado}%', f'%{dados_temporarios}%')).fetchall()
            return [dict(row) for row in results]

    def get_conversas_com_contexto_nulo(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM conversas WHERE contexto IS NULL").fetchall()
            return [dict(row) for row in results]

    def get_conversas_com_estado_nulo(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM conversas WHERE estado IS NULL").fetchall()
            return [dict(row) for row in results]

    def get_conversas_com_dados_temporarios_nulos(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM conversas WHERE dados_temporarios IS NULL").fetchall()
            return [dict(row) for row in results]

    def get_conversas_com_ultima_interacao_nula(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM conversas WHERE ultima_interacao IS NULL").fetchall()
            return [dict(row) for row in results]

    def get_conversas_com_todos_campos_nulos(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM conversas WHERE telefone IS NULL AND contexto IS NULL AND estado IS NULL AND dados_temporarios IS NULL AND ultima_interacao IS NULL").fetchall()
            return [dict(row) for row in results]

    def get_conversas_com_qualquer_campo_nulo(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM conversas WHERE telefone IS NULL OR contexto IS NULL OR estado IS NULL OR dados_temporarios IS NULL OR ultima_interacao IS NULL").fetchall()
            return [dict(row) for row in results]

    def get_conversas_com_todos_campos_preenchidos(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM conversas WHERE telefone IS NOT NULL AND contexto IS NOT NULL AND estado IS NOT NULL AND dados_temporarios IS NOT NULL AND ultima_interacao IS NOT NULL").fetchall()
            return [dict(row) for row in results]

    def get_templates_por_tipo(self, tipo: str) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM templates_avisos WHERE tipo = ?", (tipo,)).fetchall()
            return [dict(row) for row in results]

    def get_templates_por_nome_parcial(self, nome_parcial: str) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM templates_avisos WHERE nome LIKE ?", (f'%{nome_parcial}%',)).fetchall()
            return [dict(row) for row in results]

    def get_templates_por_assunto_parcial(self, assunto_parcial: str) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM templates_avisos WHERE assunto LIKE ?", (f'%{assunto_parcial}%',)).fetchall()
            return [dict(row) for row in results]

    def get_templates_por_corpo_parcial(self, corpo_parcial: str) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM templates_avisos WHERE corpo LIKE ?", (f'%{corpo_parcial}%',)).fetchall()
            return [dict(row) for row in results]

    def get_templates_ordenados_por_nome(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM templates_avisos ORDER BY nome ASC").fetchall()
            return [dict(row) for row in results]

    def get_templates_ordenados_por_data_criacao(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM templates_avisos ORDER BY data_criacao DESC").fetchall()
            return [dict(row) for row in results]

    def get_templates_ordenados_por_data_atualizacao(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM templates_avisos ORDER BY data_atualizacao DESC").fetchall()
            return [dict(row) for row in results]

    def get_templates_com_assunto_nulo(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM templates_avisos WHERE assunto IS NULL").fetchall()
            return [dict(row) for row in results]

    def get_templates_com_corpo_nulo(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM templates_avisos WHERE corpo IS NULL").fetchall()
            return [dict(row) for row in results]

    def get_templates_com_tipo_nulo(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM templates_avisos WHERE tipo IS NULL").fetchall()
            return [dict(row) for row in results]

    def get_templates_com_data_criacao_nula(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM templates_avisos WHERE data_criacao IS NULL").fetchall()
            return [dict(row) for row in results]

    def get_templates_com_data_atualizacao_nula(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM templates_avisos WHERE data_atualizacao IS NULL").fetchall()
            return [dict(row) for row in results]

    def get_templates_com_todos_campos_nulos(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM templates_avisos WHERE nome IS NULL AND assunto IS NULL AND corpo IS NULL AND tipo IS NULL AND data_criacao IS NULL AND data_atualizacao IS NULL").fetchall()
            return [dict(row) for row in results]

    def get_templates_com_qualquer_campo_nulo(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM templates_avisos WHERE nome IS NULL OR assunto IS NULL OR corpo IS NULL OR tipo IS NULL OR data_criacao IS NULL OR data_atualizacao IS NULL").fetchall()
            return [dict(row) for row in results]

    def get_templates_com_todos_campos_preenchidos(self) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM templates_avisos WHERE nome IS NOT NULL AND assunto IS NOT NULL AND corpo IS NOT NULL AND tipo IS NOT NULL AND data_criacao IS NOT NULL AND data_atualizacao IS NOT NULL").fetchall()
            return [dict(row) for row in results]

    def get_templates_com_nome_exato(self, nome: str) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM templates_avisos WHERE nome = ?", (nome,)).fetchall()
            return [dict(row) for row in results]

    def get_templates_com_assunto_exato(self, assunto: str) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM templates_avisos WHERE assunto = ?", (assunto,)).fetchall()
            return [dict(row) for row in results]

    def get_templates_com_corpo_exato(self, corpo: str) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM templates_avisos WHERE corpo = ?", (corpo,)).fetchall()
            return [dict(row) for row in results]

    def get_templates_com_tipo_exato(self, tipo: str) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM templates_avisos WHERE tipo = ?", (tipo,)).fetchall()
            return [dict(row) for row in results]

    def get_templates_com_data_criacao_exata(self, data_criacao: datetime) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM templates_avisos WHERE data_criacao = ?", (data_criacao,)).fetchall()
            return [dict(row) for row in results]

    def get_templates_com_data_atualizacao_exata(self, data_atualizacao: datetime) -> List[Dict]:
        with self as conn:
            results = conn.execute("SELECT * FROM templates_avisos WHERE data_atualizacao = ?", (data_atualizacao,)).fetchall()
            return [dict(row) for row in results]

    def get_templates_com_data_criacao_entre(self, data_inicio: datetime, data_fim: datetime) -> List[Dict]:
        with self as conn:
            query = "SELECT * FROM templates_avisos WHERE data_criacao BETWEEN ? AND ? ORDER BY data_criacao DESC"
            results = conn.execute(query, (data_inicio, data_fim)).fetchall()
            return [dict(row) for row in results]

    def get_templates_com_data_atualizacao_entre(self, data_inicio: datetime, data_fim: datetime) -> List[Dict]:
        with self as conn:
            query = "SELECT * FROM templates_avisos WHERE data_atualizacao BETWEEN ? AND ? ORDER BY data_atualizacao DESC"
            results = conn.execute(query, (data_inicio, data_fim)).fetchall()
            return [dict(row) for row in results]

    def get_templates_com_data_criacao_antes(self, data: datetime) -> List[Dict]:
        with self as conn:
            query = "SELECT * FROM templates_avisos WHERE data_criacao < ? ORDER BY data_criacao DESC"
            results = conn.execute(query, (data,)).fetchall()
            return [dict(row) for row in results]

    def get_templates_com_data_criacao_depois(self, data: datetime) -> List[Dict]:
        with self as conn:
            query = "SELECT * FROM templates_avisos WHERE data_criacao > ? ORDER BY data_criacao DESC"
            results = conn.execute(query, (data,)).fetchall()
            return [dict(row) for row in results]

    def get_templates_com_data_atualizacao_antes(self, data: datetime) -> List[Dict]:
        with self as conn:
            query = "SELECT * FROM templates_avisos WHERE data_atualizacao < ? ORDER BY data_atualizacao DESC"
            results = conn.execute(query, (data,)).fetchall()
            return [dict(row) for row in results]

    def get_templates_com_data_atualizacao_depois(self, data: datetime) -> List[Dict]:
        with self as conn:
            query = "SELECT * FROM templates_avisos WHERE data_atualizacao > ? ORDER BY data_atualizacao DESC"
            results = conn.execute(query, (data,)).fetchall()
            return [dict(row) for row in results]

    def get_templates_com_data_criacao_hoje(self) -> List[Dict]:
        with self as conn:
            data_hoje = datetime.now().strftime('%Y-%m-%d')
            results = conn.execute("SELECT * FROM templates_avisos WHERE DATE(data_criacao) = ?", (data_hoje,)).fetchall()
            return [dict(row) for row in results]

    def get_templates_com_data_atualizacao_hoje(self) -> List[Dict]:
        with self as conn:
            data_hoje = datetime.now().strftime('%Y-%m-%d')
            results = conn.execute("SELECT * FROM templates_avisos WHERE DATE(data_atualizacao) = ?", (data_hoje,)).fetchall()
            return [dict(row) for row in results]

    def get_templates_com_data_criacao_ontem(self) -> List[Dict]:
        with self as conn:
            data_ontem = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            results = conn.execute("SELECT * FROM templates_avisos WHERE DATE(data_criacao) = ?", (data_ontem,)).fetchall()
            return [dict(row) for row in results]

    def get_templates_com_data_atualizacao_ontem(self) -> List[Dict]:
        with self as conn:
            data_ontem = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            results = conn.execute("SELECT * FROM templates_avisos WHERE DATE(data_atualizacao) = ?", (data_ontem,)).fetchall()
            return [dict(row) for row in results]

    def get_templates_com_data_criacao_esta_semana(self) -> List[Dict]:
        with self as conn:
            hoje = datetime.now()
            inicio_semana = (hoje - timedelta(days=hoje.weekday())).strftime('%Y-%m-%d')
            fim_semana = (hoje + timedelta(days=6 - hoje.weekday())).strftime('%Y-%m-%d')
            query = "SELECT * FROM templates_avisos WHERE DATE(data_criacao) BETWEEN ? AND ? ORDER BY data_criacao DESC"
            results = conn.execute(query, (inicio_semana, fim_semana)).fetchall()
            return [dict(row) for row in results]

    def get_templates_com_data_atualizacao_esta_semana(self) -> List[Dict]:
        with self as conn:
            hoje = datetime.now()
            inicio_semana = (hoje - timedelta(days=hoje.weekday())).strftime('%Y-%m-%d')
            fim_semana = (hoje + timedelta(days=6 - hoje.weekday())).strftime('%Y-%m-%d')
            query = "SELECT * FROM templates_avisos WHERE DATE(data_atualizacao) BETWEEN ? AND ? ORDER BY data_atualizacao DESC"
            results = conn.execute(query, (inicio_semana, fim_semana)).fetchall()
            return [dict(row) for row in results]

    def get_templates_com_data_criacao_este_mes(self) -> List[Dict]:
        with self as conn:
            hoje = datetime.now()
            inicio_mes = hoje.replace(day=1).strftime('%Y-%m-%d')
            fim_mes = (hoje.replace(day=1, month=hoje.month % 12 + 1) - timedelta(days=1)).strftime('%Y-%m-%d')
            query = "SELECT * FROM templates_avisos WHERE DATE(data_criacao) BETWEEN ? AND ? ORDER BY data_criacao DESC"
            results = conn.execute(query, (inicio_mes, fim_mes)).fetchall()
            return [dict(row) for row in results]

    def get_templates_com_data_atualizacao_este_mes(self) -> List[Dict]:
        with self as conn:
            hoje = datetime.now()
            inicio_mes = hoje.replace(day=1).strftime('%Y-%m-%d')
            fim_mes = (hoje.replace(day=1, month=hoje.month % 12 + 1) - timedelta(days=1)).strftime('%Y-%m-%d')
            query = "SELECT * FROM templates_avisos WHERE DATE(data_atualizacao) BETWEEN ? AND ? ORDER BY data_atualizacao DESC"
            results = conn.execute(query, (inicio_mes, fim_mes)).fetchall()
            return [dict(row) for row in results]

    def get_templates_com_data_criacao_este_ano(self) -> List[Dict]:
        with self as conn:
            hoje = datetime.now()
            inicio_ano = hoje.replace(month=1, day=1).strftime('%Y-%m-%d')
            fim_ano = hoje.replace(month=12, day=31).strftime('%Y-%m-%d')
            query = "SELECT * FROM templates_avisos WHERE DATE(data_criacao) BETWEEN ? AND ? ORDER BY data_criacao DESC"
            results = conn.execute(query, (inicio_ano, fim_ano)).fetchall()
            return [dict(row) for row in results]

    def get_templates_com_data_atualizacao_este_ano(self) -> List[Dict]:
        with self as conn:
            hoje = datetime.now()
            inicio_ano = hoje.replace(month=1, day=1).strftime('%Y-%m-%d')
            fim_ano = hoje.replace(month=12, day=31).strftime('%Y-%m-%d')
            query = "SELECT * FROM templates_avisos WHERE DATE(data_atualizacao) BETWEEN ? AND ? ORDER BY data_atualizacao DESC"
            results = conn.execute(query, (inicio_ano, fim_ano)).fetchall()
            return [dict(row) for row in results]

    def get_templates_com_data_criacao_no_ano(self, ano: int) -> List[Dict]:
        with self as conn:
            inicio_ano = datetime(ano, 1, 1).strftime('%Y-%m-%d')
            fim_ano = datetime(ano, 12, 31).strftime('%Y-%m-%d')
            query = "SELECT * FROM templates_avisos WHERE DATE(data_criacao) BETWEEN ? AND ? ORDER BY data_criacao DESC"
            results = conn.execute(query, (inicio_ano, fim_ano)).fetchall()
            return [dict(row) for row in results]

    def get_templates_com_data_atualizacao_no_ano(self, ano: int) -> List[Dict]:
        with self as conn:
            inicio_ano = datetime(ano, 1, 1).strftime('%Y-%m-%d')
            fim_ano = datetime(ano, 12, 31).strftime('%Y-%m-%d')
            query = "SELECT * FROM templates_avisos WHERE DATE(data_atualizacao) BETWEEN ? AND ? ORDER BY data_atualizacao DESC"
            results = conn.execute(query, (inicio_ano, fim_ano)).fetchall()
            return [dict(row) for row in results]

    def get_templates_com_data_criacao_no_mes(self, ano: int, mes: int) -> List[Dict]:
        with self as conn:
            inicio_mes = datetime(ano, mes, 1).strftime('%Y-%m-%d')
            fim_mes = (datetime(ano, mes, 1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            fim_mes = fim_mes.strftime('%Y-%m-%d')
            query = "SELECT * FROM templates_avisos WHERE DATE(data_criacao) BETWEEN ? AND ? ORDER BY data_criacao DESC"
            results = conn.execute(query, (inicio_mes, fim_mes)).fetchall()
            return [dict(row) for row in results]

    def get_templates_com_data_atualizacao_no_mes(self, ano: int, mes: int) -> List[Dict]:
        with self as conn:
            inicio_mes = datetime(ano, mes, 1).strftime('%Y-%m-%d')
            fim_mes = (datetime(ano, mes, 1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            fim_mes = fim_mes.strftime('%Y-%m-%d')
            query = "SELECT * FROM templates_avisos WHERE DATE(data_atualizacao) BETWEEN ? AND ? ORDER BY data_atualizacao DESC"
            results = conn.execute(query, (inicio_mes, fim_mes)).fetchall()
            return [dict(row) for row in results]

    def get_templates_com_data_criacao_na_semana(self, ano: int, semana: int) -> List[Dict]:
        with self as conn:
            # Calcula a data do primeiro dia do ano
            primeiro_dia_ano = datetime(ano, 1, 1)
            # Calcula o dia da semana do primeiro dia do ano (0=segunda, 6=domingo)
            dia_semana_primeiro_dia = primeiro_dia_ano.weekday()
            # Calcula o primeiro dia da primeira semana do ano (pode ser no ano anterior)
            primeiro_dia_primeira_semana = primeiro_dia_ano - timedelta(days=dia_semana_primeiro_dia)
            # Calcula o primeiro dia da semana desejada
            inicio_semana = primeiro_dia_primeira_semana + timedelta(weeks=semana - 1)
            fim_semana = inicio_semana + timedelta(days=6)
            query = "SELECT * FROM templates_avisos WHERE DATE(data_criacao) BETWEEN ? AND ? ORDER BY data_criacao DESC"
            results = conn.execute(query, (inicio_semana.strftime('%Y-%m-%d'), fim_semana.strftime('%Y-%m-%d'))).fetchall()
            return [dict(row) for row in results]

    def get_templates_com_data_atualizacao_na_semana(self, ano: int, semana: int) -> List[Dict]:
        with self as conn:
            # Calcula a data do primeiro dia do ano
            primeiro_dia_ano = datetime(ano, 1, 1)
            # Calcula o dia da semana do primeiro dia do ano (0=segunda, 6=domingo)
            dia_semana_primeiro_dia = primeiro_dia_ano.weekday()
            # Calcula o primeiro dia da primeira semana do ano (pode ser no ano anterior)
            primeiro_dia_primeira_semana = primeiro_dia_ano - timedelta(days=dia_semana_primeiro_dia)
            # Calcula o primeiro dia da semana desejada
            inicio_semana = primeiro_dia_primeira_semana + timedelta(weeks=semana - 1)
            fim_semana = inicio_semana + timedelta(days=6)
            query = "SELECT * FROM templates_avisos WHERE DATE(data_atualizacao) BETWEEN ? AND ? ORDER BY data_atualizacao DESC"
            results = conn.execute(query, (inicio_semana.strftime('%Y-%m-%d'), fim_semana.strftime('%Y-%m-%d'))).fetchall()
            return [dict(row) for row in results]
