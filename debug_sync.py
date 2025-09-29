# debug_sync.py - Script para debugar problemas de sincronização

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import db
from bitpanel_automation import BitPanelManager
from datetime import datetime
import json

def debug_cliente(usuario_iptv):
    """Debug completo de um cliente específico"""
    print("="*60)
    print(f"🔍 DEBUG COMPLETO DO CLIENTE: {usuario_iptv}")
    print("="*60)
    
    # 1. VERIFICAR NO BANCO ANTES
    print("\n1️⃣ DADOS NO BANCO ANTES DA SYNC:")
    cliente_antes = db.buscar_cliente_por_usuario_iptv(usuario_iptv)
    if cliente_antes:
        for key, value in cliente_antes.items():
            print(f"   {key}: {value}")
    else:
        print("   ❌ Cliente não encontrado no banco!")
        return
    
    # 2. CONECTAR COM BITPANEL
    print("\n2️⃣ CONECTANDO COM BITPANEL:")
    manager = BitPanelManager()
    
    if not manager.login(headless=True):
        print("   ❌ Falha no login do BitPanel")
        return
    
    print("   ✅ Login no BitPanel realizado")
    
    # 3. OBTER DADOS DO BITPANEL
    print("\n3️⃣ OBTENDO DADOS DO BITPANEL:")
    dados_bitpanel = manager.sincronizar_dados_usuario(usuario_iptv, headless=True)
    
    print("   Dados retornados pelo BitPanel:")
    for key, value in dados_bitpanel.items():
        print(f"   {key}: {value}")
    
    # 4. PROCESSAR DADOS MANUALMENTE
    print("\n4️⃣ PROCESSANDO DADOS PARA SINCRONIZAÇÃO:")
    
    # Vamos fazer o mapeamento manual para ver o que está acontecendo
    updates = []
    params = []
    
    # Senha
    if dados_bitpanel.get('senha'):
        updates.append("senha_iptv = ?")
        params.append(dados_bitpanel['senha'])
        print(f"   ✅ Senha para atualizar: {dados_bitpanel['senha']}")
    
    # Conexões (com acento)
    if dados_bitpanel.get('conexões'):
        try:
            conexoes = int(dados_bitpanel['conexões'])
            updates.append("conexoes = ?")
            params.append(conexoes)
            print(f"   ✅ Conexões para atualizar: {conexoes}")
        except Exception as e:
            print(f"   ❌ Erro ao converter conexões '{dados_bitpanel['conexões']}': {e}")
    
    # Data de expiração - testar múltiplos campos
    data_exp_campo = None
    campos_data = ['expira_em', 'expira', 'data_expiracao', 'validade', 'vencimento']
    
    for campo in campos_data:
        if dados_bitpanel.get(campo):
            data_exp_campo = dados_bitpanel[campo]
            print(f"   ✅ Data encontrada no campo '{campo}': {data_exp_campo}")
            break
    
    if data_exp_campo:
        try:
            from datetime import datetime
            # Tentar converter com diferentes formatos
            formatos = [
                "%d/%m/%Y %H:%M",      # 28/10/2025 23:59
                "%d/%m/%Y",            # 28/10/2025
                "%Y-%m-%d %H:%M:%S",   # 2025-10-28 23:59:59
                "%Y-%m-%d",            # 2025-10-28
            ]
            
            data_convertida = None
            for formato in formatos:
                try:
                    data_convertida = datetime.strptime(data_exp_campo.strip(), formato)
                    print(f"   ✅ Data convertida com formato '{formato}': {data_convertida}")
                    break
                except:
                    continue
            
            if data_convertida:
                updates.append("data_expiracao = ?")
                params.append(data_convertida.isoformat())
                print(f"   ✅ Data para banco (ISO): {data_convertida.isoformat()}")
            else:
                print(f"   ❌ Não foi possível converter data: {data_exp_campo}")
                
        except Exception as e:
            print(f"   ❌ Erro ao processar data '{data_exp_campo}': {e}")
    
    # Plano
    if dados_bitpanel.get('plano'):
        updates.append("plano = ?")
        params.append(dados_bitpanel['plano'])
        print(f"   ✅ Plano para atualizar: {dados_bitpanel['plano']}")
    
    # Última sincronização
    updates.append("ultima_sincronizacao = ?")
    params.append(datetime.now().isoformat())
    print(f"   ✅ Última sincronização: {datetime.now().isoformat()}")
    
    # 5. EXECUTAR UPDATE NO BANCO
    print("\n5️⃣ EXECUTANDO UPDATE NO BANCO:")
    if updates:
        params.append(usuario_iptv)
        query = f"UPDATE clientes SET {', '.join(updates)} WHERE usuario_iptv = ?"
        
        print(f"   Query: {query}")
        print(f"   Parâmetros: {params}")
        
        try:
            conn = db.get_connection()
            cursor = conn.execute(query, params)
            conn.commit()
            
            print(f"   ✅ Linhas afetadas: {cursor.rowcount}")
            
            conn.close()
        except Exception as e:
            print(f"   ❌ Erro ao executar update: {e}")
            return
    else:
        print("   ❌ Nenhum campo para atualizar!")
        return
    
    # 6. VERIFICAR NO BANCO DEPOIS
    print("\n6️⃣ DADOS NO BANCO DEPOIS DA SYNC:")
    cliente_depois = db.buscar_cliente_por_usuario_iptv(usuario_iptv)
    if cliente_depois:
        for key, value in cliente_depois.items():
            print(f"   {key}: {value}")
    else:
        print("   ❌ Cliente não encontrado após sync!")
    
    # 7. COMPARAR ANTES E DEPOIS
    print("\n7️⃣ COMPARAÇÃO ANTES vs DEPOIS:")
    mudancas = []
    
    for campo in ['senha_iptv', 'conexoes', 'data_expiracao', 'plano', 'ultima_sincronizacao']:
        valor_antes = cliente_antes.get(campo)
        valor_depois = cliente_depois.get(campo) if cliente_depois else None
        
        if valor_antes != valor_depois:
            mudancas.append(campo)
            print(f"   📊 {campo}: {valor_antes} → {valor_depois}")
    
    if mudancas:
        print(f"   ✅ {len(mudancas)} campo(s) alterado(s): {', '.join(mudancas)}")
    else:
        print("   ❌ Nenhuma mudança detectada!")
    
    # Fechar manager
    manager.close()
    
    print("\n" + "="*60)
    print("🏁 DEBUG CONCLUÍDO")
    print("="*60)

def listar_clientes_para_debug():
    """Lista clientes disponíveis para debug"""
    print("\n📋 CLIENTES DISPONÍVEIS PARA DEBUG:")
    
    conn = db.get_connection()
    try:
        clientes = conn.execute("""
            SELECT usuario_iptv, telefone, nome, ultima_sincronizacao, data_expiracao
            FROM clientes 
            WHERE usuario_iptv IS NOT NULL 
            ORDER BY created_at DESC
        """).fetchall()
        
        for i, cliente in enumerate(clientes, 1):
            print(f"   {i}. {cliente['usuario_iptv']} | {cliente['telefone']} | {cliente['nome'] or 'Sem nome'}")
            print(f"      Última sync: {cliente['ultima_sincronizacao'] or 'Nunca'}")
            print(f"      Expira: {cliente['data_expiracao'] or 'Sem data'}")
            print()
        
        return [cliente['usuario_iptv'] for cliente in clientes]
    finally:
        conn.close()

def test_database_connection():
    """Testa conexão com banco de dados"""
    print("\n🔌 TESTANDO CONEXÃO COM BANCO DE DADOS:")
    
    try:
        stats = db.get_estatisticas()
        print(f"   ✅ Banco conectado - {stats.get('listas_ativas', 0)} listas ativas")
        return True
    except Exception as e:
        print(f"   ❌ Erro na conexão: {e}")
        return False

def test_bitpanel_connection():
    """Testa conexão com BitPanel"""
    print("\n🌐 TESTANDO CONEXÃO COM BITPANEL:")
    
    try:
        manager = BitPanelManager()
        if manager.login(headless=True):
            print("   ✅ BitPanel conectado")
            manager.close()
            return True
        else:
            print("   ❌ Falha no login do BitPanel")
            return False
    except Exception as e:
        print(f"   ❌ Erro na conexão: {e}")
        return False

def debug_sync_function():
    """Testa especificamente a função de sincronização do database.py"""
    print("\n🔧 TESTANDO FUNÇÃO DE SINCRONIZAÇÃO:")
    
    # Dados simulados como se viessem do BitPanel
    dados_teste = {
        'senha': 'teste123',
        'conexões': '2',  # com acento como vem do BitPanel
        'expira_em': '28/10/2025 23:59',
        'plano': 'Básico'
    }
    
    print(f"   Dados de teste: {dados_teste}")
    
    # Escolher um cliente para teste
    usuarios = listar_clientes_para_debug()
    if not usuarios:
        print("   ❌ Nenhum cliente disponível para teste")
        return
    
    usuario_teste = usuarios[0]
    print(f"   Testando com usuário: {usuario_teste}")
    
    # Cliente antes
    cliente_antes = db.buscar_cliente_por_usuario_iptv(usuario_teste)
    print(f"   Cliente antes: {cliente_antes}")
    
    # Executar sincronização
    sucesso = db.atualizar_dados_sincronizados(usuario_teste, dados_teste)
    print(f"   Resultado da sincronização: {sucesso}")
    
    # Cliente depois
    cliente_depois = db.buscar_cliente_por_usuario_iptv(usuario_teste)
    print(f"   Cliente depois: {cliente_depois}")
    
    return sucesso

if __name__ == "__main__":
    print("🚀 INICIANDO DEBUG DE SINCRONIZAÇÃO")
    print("="*60)
    
    # Menu interativo
    while True:
        print("\n📋 OPÇÕES DE DEBUG:")
        print("1. Listar clientes disponíveis")
        print("2. Debug completo de um cliente específico")
        print("3. Testar conexão banco de dados")
        print("4. Testar conexão BitPanel")
        print("5. Testar função de sincronização")
        print("0. Sair")
        
        escolha = input("\n👉 Escolha uma opção: ").strip()
        
        if escolha == '0':
            break
        elif escolha == '1':
            listar_clientes_para_debug()
        elif escolha == '2':
            usuarios = listar_clientes_para_debug()
            if usuarios:
                print("\n📝 Digite o nome do usuário IPTV para debug:")
                usuario = input("Usuario: ").strip()
                if usuario in usuarios:
                    debug_cliente(usuario)
                else:
                    print("❌ Usuário não encontrado!")
            else:
                print("❌ Nenhum cliente disponível!")
        elif escolha == '3':
            test_database_connection()
        elif escolha == '4':
            test_bitpanel_connection()
        elif escolha == '5':
            debug_sync_function()
        else:
            print("❌ Opção inválida!")
    
    print("\n👋 Debug finalizado!")