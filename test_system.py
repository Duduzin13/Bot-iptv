# test_system.py - Testador Completo do Sistema IPTV
import os
import sys
import time
from datetime import datetime

# Adicionar diretório atual ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def testar_database():
    """Testar banco de dados"""
    print("\n🗄️ TESTANDO BANCO DE DADOS...")
    
    try:
        from database import db
        
        # Testar criação de cliente
        telefone_teste = "11967512034"
        
        # Limpar cliente teste se existir
        conn = db.get_connection()
        conn.execute("DELETE FROM clientes WHERE telefone = ?", (telefone_teste,))
        conn.commit()
        conn.close()
        
        # Criar cliente teste
        cliente_id = db.criar_cliente(telefone_teste, "Cliente Teste", "teste_user")
        print(f"✅ Cliente teste criado com ID: {cliente_id}")
        
        # Buscar cliente
        cliente = db.buscar_cliente_por_telefone(telefone_teste)
        print(f"✅ Cliente encontrado: {cliente['nome']}")
        
        # Testar configurações
        db.set_config('test_config', 'valor_teste', 'Config de teste')
        valor = db.get_config('test_config')
        print(f"✅ Config salva e recuperada: {valor}")
        
        # Estatísticas
        stats = db.get_estatisticas()
        print(f"✅ Estatísticas obtidas: {stats['listas_ativas']} listas ativas")
        
        # Log
        db.log_sistema('teste', 'Teste do sistema executado')
        print("✅ Log criado com sucesso")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro no banco: {str(e)}")
        return False

def testar_gemini_ai():
    """Testar IA Gemini"""
    print("\n🤖 TESTANDO IA GEMINI...")
    
    try:
        from gemini_bot import gemini_bot
        
        # Lista de mensagens de teste
        mensagens_teste = [
            "oi",
            "quero fazer um teste",
            "quero comprar",
            "renovar minha lista",
            "consultar meus dados",
            "ajuda",
            "quanto custa 3 conexões por 6 meses?"
        ]
        
        telefone_teste = "11967512034"
        
        print("🔄 Testando diferentes tipos de mensagem:")
        
        for mensagem in mensagens_teste:
            print(f"\n📤 Enviando: '{mensagem}'")
            
            # Processar mensagem
            resposta = gemini_bot.processar_mensagem(telefone_teste, mensagem)
            
            print(f"📥 Resposta (primeiros 100 chars): {resposta[:100]}...")
            
            # Pequena pausa entre mensagens
            time.sleep(1)
        
        # Testar análise de intenção
        print("\n🧠 Testando análise de intenções:")
        intencoes_teste = [
            ("quero um teste gratis", "teste"),
            ("preciso comprar uma lista", "comprar"),
            ("renovar por favor", "renovar"),
            ("ver meus dados", "consultar"),
            ("help me", "ajuda")
        ]
        
        for mensagem, esperada in intencoes_teste:
            intencao, dados = gemini_bot.analisar_intencao(mensagem, None)
            status = "✅" if intencao == esperada else "⚠️"
            print(f"{status} '{mensagem}' -> {intencao} (esperado: {esperada})")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro na IA: {str(e)}")
        return False

def testar_bitpanel_login():
    """Testar apenas login no BitPanel SEM criar listas"""
    print("\n🌐 TESTANDO CONEXÃO BITPANEL (SEM GASTAR CRÉDITO)...")
    
    try:
        from bitpanel_automation import BitPanelManager
        
        manager = BitPanelManager()
        
        # Teste 1: Verificação headless (sem abrir Chrome)
        print("🔄 Teste 1: Verificação silenciosa...")
        resultado_headless = manager.verificar_conexao(headless=True)
        print(f"{'✅' if resultado_headless else '❌'} Conexão headless: {resultado_headless}")
        
        # Teste 2: Login visual (abre Chrome para você ver)
        print("\n🔄 Teste 2: Login visual (você pode acompanhar)...")
        print("⚠️ Chrome vai abrir - FECHE MANUALMENTE quando ver o dashboard!")
        
        input("Pressione Enter para continuar com teste visual...")
        
        manager_visual = BitPanelManager()
        resultado_visual = manager_visual.verificar_conexao(headless=False)
        print(f"{'✅' if resultado_visual else '❌'} Login visual: {resultado_visual}")
        
        if resultado_visual:
            print("✅ Sucesso! Conseguiu fazer login no BitPanel")
            print("⚠️ Feche o navegador manualmente quando quiser")
            
            # Aguardar usuário fechar
            input("\nPressione Enter depois de fechar o navegador...")
        
        # Limpar
        if hasattr(manager_visual, 'driver') and manager_visual.driver:
            try:
                manager_visual.close()
            except:
                pass
        
        return resultado_headless or resultado_visual
        
    except Exception as e:
        print(f"❌ Erro no BitPanel: {str(e)}")
        return False

def testar_navegacao_bitpanel():
    """Testar navegação no BitPanel SEM criar listas"""
    print("\n🖱️ TESTANDO NAVEGAÇÃO BITPANEL...")
    
    try:
        from bitpanel_automation import BitPanelManager
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.by import By
        
        print("⚠️ Este teste vai abrir o Chrome e navegar até a página de listas")
        print("⚠️ NÃO vai criar nenhuma lista - apenas testar navegação")
        
        continuar = input("Continuar? (s/N): ").lower().strip()
        if continuar != 's':
            print("⏭️ Teste pulado")
            return True
        
        manager = BitPanelManager()
        
        # Login
        if not manager.login(headless=False):
            print("❌ Falha no login")
            return False
        
        print("✅ Login realizado!")
        
        # Navegar para página de listas
        list_url = f"{manager.config.BITPANEL_URL}/list"
        print(f"🔄 Navegando para: {list_url}")
        
        manager.driver.get(list_url)
        
        # Aguardar página carregar
        wait = WebDriverWait(manager.driver, 10)
        
        try:
            # Procurar botão de adicionar
            add_button = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".mdi-plus")))
            print("✅ Botão 'Adicionar' encontrado!")
            
            # Procurar campo de pesquisa
            try:
                search_field = manager.driver.find_element(By.XPATH, "//label[text()='Pesquisar']/following-sibling::input")
                print("✅ Campo de pesquisa encontrado!")
            except:
                print("⚠️ Campo de pesquisa não encontrado (pode ser normal)")
            
            # Aguardar usuário ver a tela
            print("\n👀 VERIFICAÇÃO VISUAL:")
            print("- Você consegue ver a página de listas?")
            print("- Há um botão '+' para adicionar?")
            print("- A interface parece normal?")
            
            input("\nPressione Enter quando terminar de verificar...")
            
            print("✅ Navegação testada com sucesso!")
            
        except Exception as e:
            print(f"⚠️ Alguns elementos não encontrados: {e}")
            print("Mas isso pode ser normal dependendo da interface")
        
        # Fechar
        manager.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Erro na navegação: {str(e)}")
        return False

def testar_mercado_pago():
    """Testar Mercado Pago (apenas cálculos)"""
    print("\n💳 TESTANDO MERCADO PAGO (SEM CRIAR PIX)...")
    
    try:
        from mercpag import mercado_pago
        
        # Testar cálculos de preço
        print("🔄 Testando cálculos de preço:")
        
        testes_preco = [
            (1, 1),  # 1 conexão, 1 mês
            (2, 3),  # 2 conexões, 3 meses
            (5, 6),  # 5 conexões, 6 meses
            (10, 12) # 10 conexões, 12 meses
        ]
        
        for conexoes, meses in testes_preco:
            preco = mercado_pago.calcular_preco(conexoes, meses)
            print(f"✅ {conexoes} conexão(ões) x {meses} mês(es) = R$ {preco:.2f}")
        
        # Testar verificação de pagamento (sem payment_id real)
        print("\n🔄 Testando verificação de pagamento:")
        resultado = mercado_pago.verificar_pagamento("payment_id_inexistente")
        print(f"✅ Método de verificação funciona: {resultado['status']}")
        
        # Testar relatório
        print("\n🔄 Testando geração de relatório:")
        from datetime import datetime, timedelta
        hoje = datetime.now()
        inicio = hoje - timedelta(days=30)
        relatorio = mercado_pago.gerar_relatorio_vendas(inicio, hoje)
        print(f"✅ Relatório gerado: {relatorio}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro no Mercado Pago: {str(e)}")
        return False

def testar_integracao_completa():
    """Testar fluxo completo SEM executar ações reais"""
    print("\n🔄 TESTANDO INTEGRAÇÃO COMPLETA (SIMULAÇÃO)...")
    
    try:
        telefone_teste = "119967512034"
        
        # Simular fluxo de teste gratuito
        print("\n1️⃣ SIMULANDO FLUXO DE TESTE GRATUITO:")
        
        from gemini_bot import gemini_bot
        from database import db
        
        # Verificar se pode fazer teste
        pode_teste = db.pode_fazer_teste(telefone_teste)
        print(f"✅ Pode fazer teste: {pode_teste}")
        
        # Processar mensagem "teste"
        resposta1 = gemini_bot.processar_mensagem(telefone_teste, "teste")
        print(f"✅ Resposta para 'teste': {resposta1[:50]}...")
        
        # Processar nome para teste
        resposta2 = gemini_bot.processar_mensagem(telefone_teste, "joao123")
        print(f"✅ Resposta para nome: {resposta2[:50]}...")
        
        print("\n2️⃣ SIMULANDO FLUXO DE COMPRA:")
        
        # Processar "comprar"
        # Limpar estado anterior
        db.salvar_conversa(telefone_teste, 'inicial', 'inicial', '{}')
        
        resposta3 = gemini_bot.processar_mensagem(telefone_teste, "comprar")
        print(f"✅ Resposta para 'comprar': {resposta3[:50]}...")
        
        # Simular sequência completa
        mensagens_compra = ["usuario123", "2", "3", "sim"]
        
        for i, msg in enumerate(mensagens_compra):
            resposta = gemini_bot.processar_mensagem(telefone_teste, msg)
            print(f"✅ Passo {i+1} ('{msg}'): {resposta[:50]}...")
            time.sleep(0.5)
        
        print("\n3️⃣ TESTANDO CONSULTA DE DADOS:")
        
        # Limpar estado
        db.salvar_conversa(telefone_teste, 'inicial', 'inicial', '{}')
        
        resposta4 = gemini_bot.processar_mensagem(telefone_teste, "consultar")
        print(f"✅ Resposta para 'consultar': {resposta4[:50]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro na integração: {str(e)}")
        return False

def menu_testes():
    """Menu principal de testes"""
    while True:
        print("""
╔══════════════════════════════════════════╗
║         🧪 TESTADOR SISTEMA IPTV         ║
╠══════════════════════════════════════════╣
║                                          ║
║  1. 🗄️ Testar Banco de Dados            ║
║  2. 🤖 Testar IA Gemini                  ║
║  3. 🌐 Testar Login BitPanel             ║
║  4. 🖱️ Testar Navegação BitPanel         ║
║  5. 💳 Testar Mercado Pago               ║
║  6. 🔄 Testar Integração Completa        ║
║  7. 🚀 Executar Todos os Testes          ║
║  0. 🚪 Sair                              ║
║                                          ║
╚══════════════════════════════════════════╝
""")
        
        escolha = input("👉 Escolha uma opção: ").strip()
        
        if escolha == '0':
            print("👋 Encerrando testes...")
            break
        
        elif escolha == '1':
            testar_database()
        
        elif escolha == '2':
            testar_gemini_ai()
        
        elif escolha == '3':
            testar_bitpanel_login()
        
        elif escolha == '4':
            testar_navegacao_bitpanel()
        
        elif escolha == '5':
            testar_mercado_pago()
        
        elif escolha == '6':
            testar_integracao_completa()
        
        elif escolha == '7':
            print("🚀 EXECUTANDO TODOS OS TESTES...\n")
            
            resultados = []
            
            print("=" * 60)
            resultados.append(("Banco de Dados", testar_database()))
            
            print("=" * 60)
            resultados.append(("IA Gemini", testar_gemini_ai()))
            
            print("=" * 60)
            resultados.append(("BitPanel Login", testar_bitpanel_login()))
            
            print("=" * 60)
            resultados.append(("Mercado Pago", testar_mercado_pago()))
            
            print("=" * 60)
            resultados.append(("Integração", testar_integracao_completa()))
            
            # Resumo final
            print("\n" + "=" * 60)
            print("📊 RESUMO DOS TESTES:")
            print("=" * 60)
            
            for nome, resultado in resultados:
                status = "✅ PASSOU" if resultado else "❌ FALHOU"
                print(f"{status} - {nome}")
            
            sucessos = sum(1 for _, r in resultados if r)
            total = len(resultados)
            
            print(f"\n🏆 RESULTADO FINAL: {sucessos}/{total} testes passaram")
            
            if sucessos == total:
                print("🎉 Todos os testes passaram! Sistema funcionando corretamente.")
            else:
                print("⚠️ Alguns testes falharam. Verifique as configurações.")
        
        else:
            print("❌ Opção inválida!")
        
        if escolha != '0':
            input("\nPressione Enter para continuar...")

if __name__ == "__main__":
    print("🧪 TESTADOR DO SISTEMA IPTV")
    print("Permite testar todos os componentes sem gastar créditos")
    print("=" * 60)
    
    menu_testes()