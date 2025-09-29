# database.py - Sistema de Banco de Dados SQLite - VERSÃO CORRIGIDA
import sqlite3
import os
import traceback
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from config import Config


class DatabaseManager:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or Config.DATABASE_PATH
        self.init_database()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def init_database(self):
        conn = self.get_connection()
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
            "CREATE TABLE IF NOT EXISTS conversas (telefone TEXT PRIMARY KEY, contexto TEXT, estado TEXT DEFAULT 'inicial', dados_temporarios TEXT DEFAULT '{}', ultima_interacao DATETIME DEFAULT CURRENT_TIMESTAMP)"
        )
        conn.commit()
        self.inserir_configs_padrao(conn)
        conn.close()

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

    # === MÉTODOS PARA CLIENTES ===

    def criar_cliente(self, telefone: str, nome: str = None) -> int:
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                "INSERT INTO clientes (telefone, nome) VALUES (?, ?)", (telefone, nome)
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def buscar_cliente_por_telefone(self, telefone: str) -> Optional[Dict]:
        conn = self.get_connection()
        try:
            result = conn.execute(
                "SELECT * FROM clientes WHERE telefone = ? ORDER BY id DESC LIMIT 1",
                (telefone,),
            ).fetchone()
            return dict(result) if result else None
        finally:
            conn.close()

    def buscar_cliente_por_usuario_iptv(self, usuario_iptv: str) -> Optional[Dict]:
        conn = self.get_connection()
        try:
            result = conn.execute(
                "SELECT * FROM clientes WHERE usuario_iptv = ?", (usuario_iptv,)
            ).fetchone()
            return dict(result) if result else None
        finally:
            conn.close()

    def criar_ou_atualizar_cliente(
        self, telefone: str, usuario_iptv: str, nome: str = ""
    ):
        """Cria um novo cliente ou atualiza um existente com base no telefone."""
        conn = self.get_connection()
        try:
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
        finally:
            conn.close()

    def buscar_lista_por_usuario_e_telefone(
        self, usuario_iptv: str, telefone: str
    ) -> Optional[Dict]:
        """Busca uma lista específica que pertence a um número de telefone."""
        conn = self.get_connection()
        try:
            query = "SELECT * FROM clientes WHERE usuario_iptv = ? AND telefone = ?"
            result = conn.execute(query, (usuario_iptv, telefone)).fetchone()
            return dict(result) if result else None
        finally:
            conn.close()

    def atualizar_lista_cliente(
        self,
        telefone: str,
        usuario_iptv: str,
        senha_iptv: str,
        conexoes: int,
        meses: int,
    ):
        conn = self.get_connection()
        try:
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
        finally:
            conn.close()

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
        conn = self.get_connection()
        try:
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
        finally:
            conn.close()

    def renovar_lista_cliente(self, usuario_iptv: str, meses: int):
        """Esta função ATUALIZA a data de expiração no banco, após a renovação no BitPanel."""
        conn = self.get_connection()
        try:
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
        finally:
            conn.close()

    def atualizar_cliente_manual(self, usuario_iptv: str, dados: Dict) -> bool:
        """Atualiza dados de um cliente manualmente"""
        conn = self.get_connection()
        try:
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
        except Exception as e:
            print(f"Erro ao atualizar cliente: {e}")
            return False
        finally:
            conn.close()

    def marcar_teste_cliente(self, telefone: str, usuario_teste: str, senha_teste: str):
        """Marcar que cliente fez teste"""
        conn = self.get_connection()
        try:
            conn.execute(
                """
                UPDATE clientes 
                SET ultimo_teste = ?, usuario_iptv = ?, senha_iptv = ?
                WHERE telefone = ?
            """,
                (datetime.now(), usuario_teste, senha_teste, telefone),
            )
            conn.commit()
        finally:
            conn.close()

    def pode_fazer_teste(self, telefone: str) -> bool:
        """Verificar se cliente pode fazer teste"""
        conn = self.get_connection()
        try:
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
        finally:
            conn.close()

    def excluir_cliente_por_telefone(self, telefone: str) -> bool:
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                "DELETE FROM clientes WHERE telefone = ? AND usuario_iptv IS NULL",
                (telefone,),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def excluir_cliente(self, usuario_iptv: str) -> bool:
        """Exclui um cliente do banco de dados"""
        conn = self.get_connection()
        try:
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

        except Exception as e:
            print(f"Erro ao excluir cliente: {e}")
            return False
        finally:
            conn.close()

    def obter_todos_usuarios_iptv(self) -> List[str]:
        """Retorna lista de todos os usuários IPTV cadastrados"""
        conn = self.get_connection()
        try:
            results = conn.execute(
                """
                SELECT usuario_iptv FROM clientes 
                WHERE usuario_iptv IS NOT NULL AND usuario_iptv != ''
                ORDER BY created_at DESC
            """
            ).fetchall()

            return [row["usuario_iptv"] for row in results]
        finally:
            conn.close()

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
        conn = self.get_connection()
        try:
            conn.execute(
                """
                INSERT INTO pagamentos (cliente_id, valor, payment_id, contexto, dados_temporarios)
                VALUES (?, ?, ?, ?, ?)
            """,
                (cliente_id, valor, payment_id, contexto, dados_temporarios),
            )
            conn.commit()
        finally:
            conn.close()

    def buscar_pagamento(self, payment_id: str) -> Optional[Dict]:
        """Buscar pagamento por ID"""
        conn = self.get_connection()
        try:
            result = conn.execute(
                """
                SELECT p.*, c.telefone FROM pagamentos p
                JOIN clientes c ON p.cliente_id = c.id
                WHERE p.payment_id = ?
            """,
                (payment_id,),
            ).fetchone()
            return dict(result) if result else None
        finally:
            conn.close()

    def atualizar_pagamento(self, payment_id: str, status: str):
        """Atualizar status do pagamento"""
        conn = self.get_connection()
        try:
            conn.execute(
                """
                UPDATE pagamentos 
                SET status = ?, data_pagamento = ?
                WHERE payment_id = ?
            """,
                (status, datetime.now(), payment_id),
            )
            conn.commit()
        finally:
            conn.close()

    # === MÉTODOS PARA CONFIGURAÇÕES ===

    def get_config(self, chave: str, default: str = None) -> str:
        """Obter configuração"""
        conn = self.get_connection()
        try:
            result = conn.execute(
                "SELECT valor FROM configuracoes WHERE chave = ?", (chave,)
            ).fetchone()
            return result["valor"] if result else default
        finally:
            conn.close()

    def set_config(self, chave: str, valor: str, descricao: str = None):
        """Definir configuração"""
        conn = self.get_connection()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO configuracoes (chave, valor, descricao)
                VALUES (?, ?, ?)
            """,
                (chave, valor, descricao),
            )
            conn.commit()
        finally:
            conn.close()

    # === MÉTODOS PARA CONVERSAS ===

    def salvar_conversa(self, telefone: str, contexto: str, estado: str, dados: str):
        """Salvar estado da conversa - VERSÃO CORRIGIDA"""
        conn = self.get_connection()
        try:
            print(f"[DB DEBUG] Salvando conversa:")
            print(f"[DB DEBUG]   Telefone: {telefone}")
            print(f"[DB DEBUG]   Contexto: {contexto}")
            print(f"[DB DEBUG]   Estado: {estado}")
            print(f"[DB DEBUG]   Dados: {dados}")

            # CORREÇÃO: Usar REPLACE direto com telefone como PRIMARY KEY
            cursor = conn.execute(
                """
                REPLACE INTO conversas 
                (telefone, contexto, estado, dados_temporarios, ultima_interacao)
                VALUES (?, ?, ?, ?, ?)
            """,
                (telefone, contexto, estado, dados or "{}", datetime.now()),
            )

            conn.commit()
            print(
                f"[DB DEBUG] Conversa salva com sucesso - linhas afetadas: {cursor.rowcount}"
            )

        except Exception as e:
            print(f"[DB DEBUG] ERRO na operação: {e}")
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_conversa(self, telefone: str) -> Optional[Dict]:
        """Obter estado da conversa - VERSÃO CORRIGIDA"""
        conn = self.get_connection()
        try:
            result = conn.execute(
                """
                SELECT telefone, contexto, estado, dados_temporarios, ultima_interacao
                FROM conversas WHERE telefone = ?
            """,
                (telefone,),
            ).fetchone()

            if result:
                conversa_dict = dict(result)
                print(f"[DB DEBUG] Conversa recuperada: {conversa_dict}")
                return conversa_dict
            else:
                print(f"[DB DEBUG] Nenhuma conversa encontrada para {telefone}")
                return None
        finally:
            conn.close()

    # === MÉTODOS PARA SINCRONIZAÇÃO ===

    def obter_dados_sincronizacao_para_template(self):
        """
        Retorna dados de sincronização convertidos para dicionários (JSON-serializáveis)
        """
        conn = self.get_connection()
        try:
            # Clientes que nunca foram sincronizados
            nunca_sincronizados_raw = conn.execute(
                """
                SELECT usuario_iptv, created_at, telefone, nome FROM clientes
                WHERE ultima_sincronizacao IS NULL AND usuario_iptv IS NOT NULL
                ORDER BY created_at DESC
            """
            ).fetchall()

            # Últimas 20 sincronizações
            ultimas_sync_raw = conn.execute(
                """
                SELECT usuario_iptv, ultima_sincronizacao, telefone, nome FROM clientes
                WHERE ultima_sincronizacao IS NOT NULL
                ORDER BY ultima_sincronizacao DESC
                LIMIT 20
            """
            ).fetchall()

            # Converter Row objects para dicionários
            nunca_sincronizados = []
            for row in nunca_sincronizados_raw:
                nunca_sincronizados.append(
                    {
                        "usuario_iptv": row["usuario_iptv"],
                        "created_at": row["created_at"],
                        "telefone": row["telefone"],
                        "nome": row["nome"],
                    }
                )

            ultimas_sync = []
            for row in ultimas_sync_raw:
                ultimas_sync.append(
                    {
                        "usuario_iptv": row["usuario_iptv"],
                        "ultima_sincronizacao": row["ultima_sincronizacao"],
                        "telefone": row["telefone"],
                        "nome": row["nome"],
                    }
                )

            stats = {
                "nunca_sincronizados": len(nunca_sincronizados),
                "total_com_sync": len(ultimas_sync),
            }

            return {
                "nunca_sincronizados": nunca_sincronizados,
                "ultimas_sync": ultimas_sync,
                "stats": stats,
            }

        finally:
            conn.close()

    def atualizar_dados_sincronizados(
        self, usuario_iptv: str, dados_bitpanel: Dict
    ) -> bool:
        """
        Atualiza dados do cliente com informações obtidas do BitPanel.
        CORREÇÃO FINAL: Usa EXATAMENTE as datas que vêm do BitPanel, sem criar nada.
        """
        conn = self.get_connection()
        try:
            print(f"\n{'='*60}")
            print(f"[DB SYNC] Sincronizando: {usuario_iptv}")
            print(f"{'='*60}")
            print(f"[DB SYNC] Dados recebidos do BitPanel:")
            for key, value in dados_bitpanel.items():
                print(f"  {key}: {value}")
            print(f"{'='*60}\n")

            updates = []
            params = []

            # ============================================================
            # 1. SENHA
            # ============================================================
            if dados_bitpanel.get("senha"):
                updates.append("senha_iptv = ?")
                params.append(dados_bitpanel["senha"])
                print(f"[DB SYNC] ✓ Senha: {dados_bitpanel['senha']}")

            # ============================================================
            # 2. CONEXÕES (campo vem com acento do BitPanel)
            # ============================================================
            conexoes_valor = dados_bitpanel.get("conexões") or dados_bitpanel.get(
                "conexoes"
            )
            if conexoes_valor:
                try:
                    # Limpar o valor (pode vir como "2 conexões" ou apenas "2")
                    conexoes_limpo = (
                        conexoes_valor.split()[0]
                        if isinstance(conexoes_valor, str)
                        else conexoes_valor
                    )
                    conexoes = int(conexoes_limpo)
                    updates.append("conexoes = ?")
                    params.append(conexoes)
                    print(f"[DB SYNC] ✓ Conexões: {conexoes}")
                except Exception as e:
                    print(
                        f"[DB SYNC] ✗ Erro ao converter conexões '{conexoes_valor}': {e}"
                    )

            # ============================================================
            # 3. DATA DE CRIAÇÃO (vem do BitPanel como "criado_em" ou similar)
            # ============================================================
            # Procurar por variações do campo de criação
            data_criacao_valor = None
            campos_criacao = [
                "data_de_criacao",
                "criado",
                "created",
                "data_criacao",
                "data_de_criacao",
                "Data de criação",
            ]

            for campo in campos_criacao:
                if dados_bitpanel.get(campo):
                    data_criacao_valor = dados_bitpanel[campo]
                    print(
                        f"[DB SYNC] → Data criação encontrada no campo '{campo}': {data_criacao_valor}"
                    )
                    break

            if data_criacao_valor:
                try:
                    data_criacao_convertida = (
                        self._converter_data_bitpanel_melhorada(
                            data_criacao_valor
                        )
                    )
                    updates.append("data_criacao = ?")
                    params.append(data_criacao_convertida.isoformat())
                    print(
                        f"[DB SYNC] ✓ Data Criação: {data_criacao_convertida.strftime('%d/%m/%Y %H:%M')}"
                    )
                except Exception as e:
                    print(
                        f"[DB SYNC] ✗ Erro ao converter data de criação '{data_criacao_valor}': {e}"
                    )

            # ============================================================
            # 4. DATA DE EXPIRAÇÃO (campo CRÍTICO - vem do BitPanel)
            # ============================================================
            # Procurar por TODAS as variações possíveis do campo de expiração
            data_expiracao_valor = None
            campos_expiracao = [
                "data_de_validade",
                "expira",
                "data_expiracao",
                "data_de_expiração",
                "validade",
                "vencimento",
                "expires",
                "expiration_date",
                "Data de validade",
                "data_de_validade",
            ]

            for campo in campos_expiracao:
                if dados_bitpanel.get(campo):
                    data_expiracao_valor = dados_bitpanel[campo]
                    print(
                        f"[DB SYNC] → Data expiração encontrada no campo '{campo}': {data_expiracao_valor}"
                    )
                    break

            if data_expiracao_valor:
                try:
                    data_expiracao_convertida = (
                        self._converter_data_bitpanel_melhorada(
                            data_expiracao_valor
                        )
                    )
                    updates.append("data_expiracao = ?")
                    params.append(data_expiracao_convertida.isoformat())
                    print(
                        f"[DB SYNC] ✓ Data Expiração: {data_expiracao_convertida.strftime('%d/%m/%Y %H:%M')}"
                    )

                    # Atualizar status baseado na data de expiração
                    status_calculado = (
                        "ativo"
                        if data_expiracao_convertida > datetime.now()
                        else "expirado"
                    )
                    updates.append("status = ?")
                    params.append(status_calculado)
                    print(f"[DB SYNC] ✓ Status calculado: {status_calculado}")

                except Exception as e:
                    print(
                        f"[DB SYNC] ✗ Erro ao converter data de expiração '{data_expiracao_valor}': {e}"
                    )
            else:
                print(
                    f"[DB SYNC] ⚠ AVISO: Data de expiração NÃO encontrada nos dados do BitPanel!"
                )
                print(f"[DB SYNC]   Campos disponíveis: {list(dados_bitpanel.keys())}")

            # ============================================================
            # 5. PLANO
            # ============================================================
            if dados_bitpanel.get("plano"):
                updates.append("plano = ?")
                params.append(dados_bitpanel["plano"])
                print(f"[DB SYNC] ✓ Plano: {dados_bitpanel['plano']}")

            # ============================================================
            # 6. STATUS DO BITPANEL (se vier explicitamente)
            # ============================================================
            if dados_bitpanel.get("status_bitpanel"):
                status_bp = dados_bitpanel["status_bitpanel"].lower()
                if status_bp in ["ativo", "active", "enabled"]:
                    updates.append("status = ?")
                    params.append("ativo")
                    print(f"[DB SYNC] ✓ Status BitPanel: ativo")

            # ============================================================
            # 7. ÚLTIMA SINCRONIZAÇÃO (sempre atualizar)
            # ============================================================
            agora = datetime.now()
            updates.append("ultima_sincronizacao = ?")
            params.append(agora.isoformat())
            print(
                f"[DB SYNC] ✓ Última sincronização: {agora.strftime('%d/%m/%Y %H:%M:%S')}"
            )

            # ============================================================
            # EXECUTAR A ATUALIZAÇÃO NO BANCO
            # ============================================================
            if updates:
                params.append(usuario_iptv)
                query = (
                    f"UPDATE clientes SET {', '.join(updates)} WHERE usuario_iptv = ?"
                )

                print(f"\n[DB SYNC] Executando UPDATE:")
                print(f"  Query: {query}")
                print(f"  Params: {params[:len(params)-1]} + ['{usuario_iptv}']")

                cursor = conn.execute(query, params)
                conn.commit()

                linhas_afetadas = cursor.rowcount
                print(f"\n[DB SYNC] {'='*60}")

                if linhas_afetadas > 0:
                    print(
                        f"[DB SYNC] ✅ SUCESSO: {linhas_afetadas} linha(s) atualizada(s)"
                    )

                    # VERIFICAÇÃO CRÍTICA: Conferir se os dados foram realmente salvos
                    cliente_atualizado = conn.execute(
                        "SELECT data_criacao, data_expiracao, conexoes, senha_iptv, plano, ultima_sincronizacao, status FROM clientes WHERE usuario_iptv = ?",
                        (usuario_iptv,),
                    ).fetchone()

                    if cliente_atualizado:
                        print(f"[DB SYNC] Verificação pós-update:")
                        print(f"  - Data Criação: {cliente_atualizado['data_criacao']}")
                        print(
                            f"  - Data Expiração: {cliente_atualizado['data_expiracao']}"
                        )
                        print(f"  - Conexões: {cliente_atualizado['conexoes']}")
                        print(f"  - Senha: {cliente_atualizado['senha_iptv']}")
                        print(f"  - Plano: {cliente_atualizado['plano']}")
                        print(f"  - Status: {cliente_atualizado['status']}")
                        print(
                            f"  - Última Sync: {cliente_atualizado['ultima_sincronizacao']}"
                        )

                    print(f"{'='*60}\n")
                    return True
                else:
                    print(f"[DB SYNC] ❌ ERRO: Nenhuma linha foi atualizada")
                    print(
                        f"  Possível causa: usuário '{usuario_iptv}' não existe no banco"
                    )
                    print(f"{'='*60}\n")
                    return False
            else:
                print(f"[DB SYNC] ⚠ Nenhum campo para atualizar")
                # Mesmo assim, marca como sincronizado
                conn.execute(
                    "UPDATE clientes SET ultima_sincronizacao = ? WHERE usuario_iptv = ?",
                    (datetime.now().isoformat(), usuario_iptv),
                )
                conn.commit()
                return True

        except Exception as e:
            print(f"\n[DB SYNC] ❌ ERRO CRÍTICO ao sincronizar:")
            print(f"  {type(e).__name__}: {str(e)}")
            import traceback

            traceback.print_exc()
            return False
        finally:
            conn.close()

    def _converter_data_bitpanel_melhorada(self, data_str: str) -> datetime:
        """
        Converte string de data do BitPanel para datetime - VERSÃO ROBUSTA
        Suporta múltiplos formatos de data
        """
        if not data_str:
            raise ValueError("Data vazia")

        # Lista de formatos possíveis do BitPanel
        formatos = [
            "%d/%m/%Y %H:%M",  # 28/10/2025 23:59
            "%d/%m/%Y",  # 28/10/2025
            "%Y-%m-%d %H:%M:%S",  # 2025-10-28 23:59:59
            "%Y-%m-%d",  # 2025-10-28
            "%d-%m-%Y",  # 28-10-2025
            "%d-%m-%Y %H:%M",  # 28-10-2025 23:59
        ]

        # Limpar a string
        data_limpa = data_str.strip()

        # Tentar cada formato
        for formato in formatos:
            try:
                return datetime.strptime(data_limpa, formato)
            except ValueError:
                continue

        # Se nenhum formato funcionou
        raise ValueError(
            f"Não foi possível converter data '{data_str}' com nenhum formato conhecido"
        )

    def _converter_data_string(self, data_str: str) -> datetime:
        """Converte string de data para datetime"""
        try:
            # Formato "2024-12-31"
            if "-" in data_str and len(data_str.split("-")[0]) == 4:
                return datetime.strptime(data_str.split(" ")[0], "%d-%m-%Y")
            # Formato "31/12/2024"
            elif "/" in data_str:
                return datetime.strptime(data_str.split(" ")[0], "%d/%m/%Y")
            # Outros formatos...
            else:
                return datetime.fromisoformat(data_str.split("T")[0])
        except Exception as e:
            raise ValueError(f"Não foi possível converter data '{data_str}': {e}")

    def listar_clientes_ativos(self) -> List[Dict]:
        """
        Lista clientes com listas ativas (para broadcast)
        """
        conn = self.get_connection()
        try:
            results = conn.execute(
                """
                SELECT DISTINCT telefone, nome FROM clientes 
                WHERE status = 'ativo' 
                AND data_expiracao > datetime('now')
                AND usuario_iptv IS NOT NULL
            """
            ).fetchall()

            return [dict(row) for row in results]
        finally:
            conn.close()

    def listar_clientes_expirando(self, dias: int = 7) -> List[Dict]:
        """
        Lista clientes com listas expirando em X dias
        """
        conn = self.get_connection()
        try:
            data_limite = datetime.now() + timedelta(days=dias)
            results = conn.execute(
                """
                SELECT telefone, nome, usuario_iptv, data_expiracao FROM clientes 
                WHERE status = 'ativo' 
                AND data_expiracao > datetime('now')
                AND data_expiracao <= ?
                AND usuario_iptv IS NOT NULL
            """,
                (data_limite.isoformat(),),
            ).fetchall()

            return [dict(row) for row in results]
        finally:
            conn.close()

    # === MÉTODOS PARA LOGS ===

    def log_sistema(self, tipo: str, mensagem: str, detalhes: str = None):
        """Adicionar log do sistema"""
        conn = self.get_connection()
        try:
            conn.execute(
                """
                INSERT INTO logs_sistema (tipo, mensagem, detalhes)
                VALUES (?, ?, ?)
            """,
                (tipo, mensagem, detalhes),
            )
            conn.commit()
        finally:
            conn.close()

    # === MÉTODOS PARA ESTATÍSTICAS ===

    def get_estatisticas(self) -> Dict:
        """Obter estatísticas do sistema"""
        conn = self.get_connection()
        try:
            stats = {}

            # Listas ativas
            result = conn.execute(
                """
                SELECT COUNT(*) as count FROM clientes 
                WHERE status = 'ativo' AND data_expiracao > datetime('now')
            """
            ).fetchone()
            stats["listas_ativas"] = result["count"]

            # Vendas do mês
            result = conn.execute(
                """
                SELECT COALESCE(SUM(valor), 0) as total FROM pagamentos 
                WHERE status = 'approved' 
                AND data_pagamento >= date('now', 'start of month')
            """
            ).fetchone()
            stats["vendas_mes"] = float(result["total"])

            # Expirando em 7 dias
            data_limite = datetime.now() + timedelta(days=7)
            result = conn.execute(
                """
                SELECT COUNT(*) as count FROM clientes 
                WHERE status = 'ativo' 
                AND data_expiracao > datetime('now')
                AND data_expiracao <= ?
            """,
                (data_limite,),
            ).fetchone()
            stats["expirando_7_dias"] = result["count"]

            return stats
        finally:
            conn.close()


# Instância global do banco
db = DatabaseManager()

if __name__ == "__main__":
    # Teste do banco
    db = DatabaseManager()
    print("✅ Banco de dados testado com sucesso!")

    # Mostrar estatísticas
    stats = db.get_estatisticas()
    print(f"📊 Estatísticas: {stats}")
