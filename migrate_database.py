#!/usr/bin/env python3
"""
migrate_database.py - Script para migrar/atualizar o banco de dados
Execute este arquivo para adicionar as novas colunas necessárias
"""

import sqlite3
from datetime import datetime
from config import Config

def migrate_database():
    """Executa migrações necessárias no banco de dados"""
    
    db_path = Config.DATABASE_PATH
    
    print(f"🔄 Iniciando migração do banco de dados: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        
        # Lista de migrações a serem executadas
        migrations = [
            {
                'name': 'Adicionar coluna ultima_sincronizacao',
                'sql': '''
                    ALTER TABLE clientes 
                    ADD COLUMN ultima_sincronizacao DATETIME DEFAULT NULL
                ''',
                'check_sql': "SELECT ultima_sincronizacao FROM clientes LIMIT 1"
            },
            {
                'name': 'Adicionar índices para performance',
                'sql': '''
                    CREATE INDEX IF NOT EXISTS idx_clientes_usuario_iptv 
                    ON clientes(usuario_iptv);
                ''',
                'always_run': True
            },
            {
                'name': 'Adicionar índices para telefone',
                'sql': '''
                    CREATE INDEX IF NOT EXISTS idx_clientes_telefone 
                    ON clientes(telefone);
                ''',
                'always_run': True
            },
            {
                'name': 'Adicionar índices para data_expiracao',
                'sql': '''
                    CREATE INDEX IF NOT EXISTS idx_clientes_expiracao 
                    ON clientes(data_expiracao);
                ''',
                'always_run': True
            }
        ]
        
        for migration in migrations:
            print(f"  📋 Executando: {migration['name']}")
            
            try:
                # Se tem check_sql, verificar se já existe
                if 'check_sql' in migration and not migration.get('always_run'):
                    try:
                        conn.execute(migration['check_sql'])
                        print(f"    ✅ {migration['name']} - Já existe, pulando")
                        continue
                    except sqlite3.OperationalError:
                        # Coluna não existe, pode executar a migração
                        pass
                
                # Executar a migração
                conn.execute(migration['sql'])
                conn.commit()
                print(f"    ✅ {migration['name']} - Executada com sucesso")
                
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                    print(f"    ✅ {migration['name']} - Já existe, pulando")
                else:
                    print(f"    ❌ {migration['name']} - Erro: {e}")
            except Exception as e:
                print(f"    ❌ {migration['name']} - Erro inesperado: {e}")
        
        # Verificar integridade do banco
        print("\n  🔍 Verificando integridade do banco...")
        result = conn.execute("PRAGMA integrity_check").fetchone()
        if result[0] == 'ok':
            print("    ✅ Integridade do banco: OK")
        else:
            print(f"    ⚠️ Problemas de integridade: {result[0]}")
        
        # Mostrar estatísticas
        print("\n  📊 Estatísticas pós-migração:")
        
        # Contar registros
        total_clientes = conn.execute("SELECT COUNT(*) FROM clientes").fetchone()[0]
        print(f"    📱 Total de clientes: {total_clientes}")
        
        clientes_com_lista = conn.execute(
            "SELECT COUNT(*) FROM clientes WHERE usuario_iptv IS NOT NULL"
        ).fetchone()[0]
        print(f"    📺 Clientes com lista IPTV: {clientes_com_lista}")
        
        # Clientes com sincronização
        try:
            sincronizados = conn.execute(
                "SELECT COUNT(*) FROM clientes WHERE ultima_sincronizacao IS NOT NULL"
            ).fetchone()[0]
            nunca_sincronizados = conn.execute(
                "SELECT COUNT(*) FROM clientes WHERE usuario_iptv IS NOT NULL AND ultima_sincronizacao IS NULL"
            ).fetchone()[0]
            print(f"    🔄 Já sincronizados: {sincronizados}")
            print(f"    ⏳ Nunca sincronizados: {nunca_sincronizados}")
        except:
            print("    ⏳ Coluna de sincronização não disponível")
        
        conn.close()
        
        print(f"\n✅ Migração concluída com sucesso!")
        print(f"   Database: {db_path}")
        print(f"   Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Erro durante a migração: {e}")
        return False

def backup_database():
    """Cria backup do banco antes da migração"""
    import shutil
    
    db_path = Config.DATABASE_PATH
    backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    try:
        shutil.copy2(db_path, backup_path)
        print(f"📋 Backup criado: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"⚠️ Erro ao criar backup: {e}")
        return None

def main():
    """Função principal"""
    print("=" * 60)
    print("🔧 MIGRAÇÃO DO BANCO DE DADOS - SISTEMA IPTV")
    print("=" * 60)
    
    # Verificar se o banco existe
    db_path = Config.DATABASE_PATH
    import os
    if not os.path.exists(db_path):
        print(f"❌ Banco de dados não encontrado: {db_path}")
        print("   Execute primeiro o sistema para criar o banco")
        return False
    
    # Criar backup
    print("🛡️ Criando backup de segurança...")
    backup_path = backup_database()
    
    if backup_path:
        print("✅ Backup criado com sucesso")
    else:
        print("⚠️ Falha ao criar backup, mas continuando...")
    
    # Executar migrações
    print("\n🔄 Iniciando migrações...")
    sucesso = migrate_database()
    
    if sucesso:
        print("\n🎉 MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
        print("\nPróximos passos:")
        print("1. Execute o sistema normalmente")
        print("2. Teste as novas funcionalidades de sincronização")
        print("3. Use o relatório de sincronização para verificar status")
        
        if backup_path:
            print(f"\n💾 Backup disponível em: {backup_path}")
            print("   (pode ser removido após confirmar que tudo funciona)")
    else:
        print("\n❌ FALHA NA MIGRAÇÃO!")
        if backup_path:
            print(f"   Restaure o backup se necessário: {backup_path}")
    
    return sucesso

if __name__ == "__main__":
    main()
    input("\nPressione Enter para finalizar...")