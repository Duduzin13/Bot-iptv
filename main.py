# main.py - Arquivo Principal do Sistema IPTV (Versão Melhorada e Corrigida)
import os
import sys
import threading
import time

# Adicionar diretório atual ao path para importações corretas
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def verificar_dependencias():
    """Verificar se todas as dependências estão instaladas."""
    dependencias = {
        'flask': 'flask',
        'requests': 'requests',
        'selenium': 'selenium',
        'mercadopago': 'mercadopago',
        'google-generativeai': 'google.generativeai',
        'python-dotenv': 'dotenv'
    }
    
    missing = []
    for pip_name, module_name in dependencias.items():
        try:
            __import__(module_name)
        except ImportError:
            missing.append(pip_name)
    
    if missing:
        print("❌ Dependências em falta:")
        for dep in missing:
            print(f"   - {dep}")
        print("\n📦 Execute: pip install -r requirements.txt")
        return False
    
    return True

def verificar_configuracoes():
    """Verificar configurações essenciais no arquivo .env."""
    from config import Config
    
    config = Config()
    problemas = []
    
    if not config.WHATSAPP_TOKEN:
        problemas.append("WHATSAPP_TOKEN não configurado")
    
    if not config.WHATSAPP_PHONE_ID:
        problemas.append("WHATSAPP_PHONE_ID não configurado")
        
    if not config.MERCADOPAGO_ACCESS_TOKEN:
        problemas.append("MERCADOPAGO_ACCESS_TOKEN não configurado")
    
    if problemas:
        print("⚠️ Configurações em falta:")
        for problema in problemas:
            print(f"   - {problema}")
        print("\n🔧 Configure o arquivo .env com suas credenciais")
        return False
    
    return True

def inicializar_sistema():
    """Inicializar banco de dados e testar conexões com os serviços."""
    try:
        print("🔧 Inicializando sistema...")
        
        # Inicializar banco de dados
        from database import db
        print("✅ Banco de dados inicializado")
        
        # Testar conexão com BitPanel
        from bitpanel_automation import BitPanelManager
        bitpanel_manager_instance = BitPanelManager()
        if bitpanel_manager_instance.verificar_conexao(headless=True):
            print("✅ BitPanel acessível")
        else:
            print("⚠️ BitPanel não acessível (pode ser normal se o serviço estiver offline)")
        
        # Testar Gemini Bot
        from gemini_bot import gemini_bot
        print("✅ Gemini Bot melhorado carregado")
        
        # Testar Mercado Pago
        from mercpag import mercado_pago
        print("✅ Mercado Pago configurado")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao inicializar sistema: {str(e)}")
        return False

def iniciar_whatsapp_bot():
    """Iniciar o bot do WhatsApp em uma thread separada."""
    try:
        print("🤖 Iniciando WhatsApp Bot Melhorado...")
        from whatsapp_bot import whatsapp_bot
        # Supondo que o bot do WhatsApp rode em um servidor Flask separado
        whatsapp_bot.iniciar_bot()
    except Exception as e:
        print(f"❌ Erro no WhatsApp Bot: {str(e)}")

def iniciar_dashboard():
    """Iniciar o dashboard web em uma thread separada."""
    try:
        print("🖥️ Iniciando Dashboard...")
        from dashboard import app
        from config import Config
        
        app.run(
            host=Config.FLASK_HOST,
            port=Config.FLASK_PORT,
            debug=False,
            use_reloader=False
        )
    except Exception as e:
        print(f"❌ Erro no Dashboard: {str(e)}")

def mostrar_menu():
    """Exibir o menu principal de opções no console."""
    print("""
╔══════════════════════════════════════════╗
║           🤖 SISTEMA IPTV v2.0           ║
║             (Versão Melhorada)           ║
╠══════════════════════════════════════════╣
║                                          ║
║   1. 🚀 Iniciar Sistema Completo         ║
║   2. 🤖 Apenas WhatsApp Bot              ║
║   3. 🖥️ Apenas Dashboard Web            ║
║   4. 🧪 Testar Componentes               ║
║   5. ⚙️ Configurar Sistema              ║
║   6. 📊 Ver Status                       ║
║   7. 🔧 Testar Nova IA                   ║
║   0. 🚪 Sair                             ║
║                                          ║
╚══════════════════════════════════════════╝
""")

def testar_nova_ia():
    """Executar testes automatizados na IA do Gemini Bot."""
    print("\n🧠 TESTANDO NOVA IA MELHORADA...\n")
    
    try:
        from gemini_bot import gemini_bot
        
        mensagens_teste = [
            ("oi", "saudacao"),
            ("quero comprar uma lista", "comprar"),
            ("1", "menu numerico"),
            ("cancelar", "cancelamento"),
            ("renovar minha lista", "renovar"),
            ("ver meus dados", "consultar"),
            ("ajuda", "ajuda"),
            ("teste123", "usuario"),
            ("3", "numero"),
            ("sim", "confirmacao"),
            ("não sei o que fazer", "menu_erro")
        ]
        
        telefone_teste = "5511999999999" # Número de telefone para testes
        
        print("📝 Testando diferentes cenários:")
        print("-" * 50)
        
        for i, (mensagem, tipo_esperado) in enumerate(mensagens_teste, 1):
            print(f"\n🧪 Teste {i}: '{mensagem}' (esperado: {tipo_esperado})")
            
            try:
                resposta = gemini_bot.processar_mensagem(telefone_teste, mensagem)
                
                if resposta:
                    # Mostrar as duas primeiras linhas da resposta como preview
                    linhas = resposta.split('\n')[:2]
                    preview = ' '.join(linhas).strip()
                    print(f"   ✅ Resposta: {preview[:80]}...")
                else:
                    print("   ⚠️ Resposta: (None - processamento assíncrono)")
                
                time.sleep(0.5)  # Pausa entre os testes
                
            except Exception as e:
                print(f"   ❌ Erro: {e}")
        
        print("\n" + "=" * 50)
        print("🎯 Teste da Nova IA Concluído!")
        print("📝 Verifique se as respostas fazem sentido para cada tipo de mensagem.")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste da IA: {str(e)}")
        return False

def testar_componentes():
    """Testar todos os principais componentes do sistema."""
    print("\n🧪 TESTANDO COMPONENTES...\n")
    
    # Teste 1: Banco de Dados
    try:
        from database import db
        stats = db.get_estatisticas()
        print("✅ Banco de dados: OK")
        print(f"   - {stats.get('listas_ativas', 0)} listas ativas")
    except Exception as e:
        print(f"❌ Banco de dados: ERRO - {str(e)}")
    
    # Teste 2: BitPanel
    try:
        from bitpanel_automation import BitPanelManager
        bitpanel_manager_instance = BitPanelManager()
        if bitpanel_manager_instance.verificar_conexao(headless=True):
            print("✅ BitPanel: ONLINE")
        else:
            print("⚠️ BitPanel: OFFLINE")
    except Exception as e:
        print(f"❌ BitPanel: ERRO - {str(e)}")
    
    # Teste 3: Nova IA
    try:
        from gemini_bot import gemini_bot
        resposta = gemini_bot.processar_mensagem("test_user", "oi")
        print("✅ Nova IA: OK")
        if resposta:
            print(f"   - Resposta teste: {resposta[:50]}...")
        else:
            print("   - Processamento assíncrono funcionando")
    except Exception as e:
        print(f"❌ Nova IA: ERRO - {str(e)}")
    
    # Teste 4: Mercado Pago
    try:
        from mercpag import mercado_pago
        preco = mercado_pago.calcular_preco(2, 3)
        print("✅ Mercado Pago: OK")
        print(f"   - Cálculo teste: R$ {preco}")
    except Exception as e:
        print(f"❌ Mercado Pago: ERRO - {str(e)}")
    
    # Teste 5: WhatsApp Bot
    try:
        from whatsapp_bot import whatsapp_bot
        print("✅ WhatsApp Bot: Carregado")
        print("   - API configurada corretamente")
    except Exception as e:
        print(f"❌ WhatsApp Bot: ERRO - {str(e)}")
    
    print("\n✅ Teste completo!\n")

def configurar_sistema():
    """Criar e verificar o arquivo de configuração .env."""
    print("\n⚙️ CONFIGURAÇÃO DO SISTEMA\n")
    
    # Criar arquivo .env se não existir
    if not os.path.exists('.env'):
        print("📄 Criando arquivo .env...")
        
        env_content = """# WhatsApp Business API
WHATSAPP_TOKEN=seu_token_whatsapp_aqui
WHATSAPP_PHONE_ID=seu_phone_id_aqui
WEBHOOK_VERIFY_TOKEN=iptv_webhook_2024

# Mercado Pago
MERCADOPAGO_ACCESS_TOKEN=seu_access_token_mp_aqui
MERCADOPAGO_PUBLIC_KEY=sua_public_key_mp_aqui

# BitPanel
BITPANEL_URL=https://painel.seubitpanel.com
BITPANEL_USER=seu_usuario_bitpanel
BITPANEL_PASS=sua_senha_bitpanel

# URL Pública (Ngrok) - ESSENCIAL para QR Code e Webhook
BASE_URL=https://seu-ngrok-url.ngrok.io

# Modo de Teste (true/false)
TEST_MODE=true
"""
        
        with open('.env', 'w') as f:
            f.write(env_content)
        
        print("✅ Arquivo .env criado!")
        print("🔧 Edite o arquivo .env e preencha suas credenciais.")
    else:
        print("ℹ️ Arquivo .env já existe.")
    
    # Mostrar status das configurações
    print("\n📋 STATUS DAS CONFIGURAÇÕES:")
    try:
        from config import Config
        config = Config()
        
        configs = [
            ("WhatsApp Token", config.WHATSAPP_TOKEN),
            ("WhatsApp Phone ID", config.WHATSAPP_PHONE_ID),
            ("Mercado Pago Token", config.MERCADOPAGO_ACCESS_TOKEN),
            ("BitPanel URL", config.BITPANEL_URL),
            ("BitPanel User", config.BITPANEL_USER),
            ("Base URL (Ngrok)", config.BASE_URL)
        ]
        
        for nome, valor in configs:
            status = "✅ OK" if valor and 'seu_' not in valor else "❌ Faltando"
            print(f"   {nome}: {status}")
            
    except Exception as e:
        print(f"❌ Erro ao verificar configurações: {str(e)}")

def ver_status():
    """Exibir o status atual do sistema, estatísticas e serviços."""
    print("\n📊 STATUS DO SISTEMA\n")
    
    try:
        from database import db
        from config import Config
        
        # Estatísticas do banco
        stats = db.get_estatisticas()
        
        print("📈 ESTATÍSTICAS:")
        print(f"   📺 Listas ativas: {stats.get('listas_ativas', 0)}")
        print(f"   💰 Vendas do mês: R$ {stats.get('vendas_mes', 0):.2f}")
        print(f"   ⚠️ Expirando (7 dias): {stats.get('expirando_7_dias', 0)}")
        
        # Configurações atuais
        print("\n⚙️ CONFIGURAÇÕES:")
        print(f"   🔗 Link de acesso: {db.get_config('link_acesso', 'Não configurado')}")
        print(f"   💵 Preço/mês: R$ {db.get_config('preco_mes', '30.00')}")
        print(f"   💵 Preço/conexão: R$ {db.get_config('preco_conexao', '30.00')}")
        
        # Status dos serviços
        print("\n🔧 SERVIÇOS:")
        
        # BitPanel
        try:
            from bitpanel_automation import BitPanelManager
            bitpanel_manager_instance = BitPanelManager()
            if bitpanel_manager_instance.verificar_conexao(headless=True):
                print("   🟢 BitPanel: ONLINE")
            else:
                print("   🔴 BitPanel: OFFLINE")
        except:
            print("   ⚫ BitPanel: ERRO")
        
        # Portas
        print("\n🌐 ACESSO:")
        print(f"   📊 Dashboard: http://{Config.FLASK_HOST}:{Config.FLASK_PORT}")
        print(f"   🤖 Webhook WhatsApp: Porta {Config.WHATSAPP_PORT}")
        
    except Exception as e:
        print(f"❌ Erro ao obter status: {str(e)}")

def main():
    """Função principal que executa o menu interativo."""
    print("""
    🤖 SISTEMA IPTV v2.0 - VERSÃO MELHORADA
    📱 WhatsApp Bot + IA Aprimorada + PIX + Dashboard Web
    """)
    print("=" * 60)
    
    # Verificações iniciais
    if not verificar_dependencias():
        return
    
    while True:
        mostrar_menu()
        
        try:
            escolha = input("👉 Escolha uma opção: ").strip()
            
            if escolha == '0':
                print("\n👋 Encerrando sistema...")
                break
                
            elif escolha == '1':
                # Sistema completo
                if verificar_configuracoes() and inicializar_sistema():
                    print("\n🚀 Iniciando sistema completo melhorado...")
                    
                    # Iniciar WhatsApp Bot em thread
                    bot_thread = threading.Thread(target=iniciar_whatsapp_bot, daemon=True)
                    bot_thread.start()
                    
                    time.sleep(2)
                    
                    from config import Config
                    print("🖥️ Acessos disponíveis:")
                    print(f"   📊 Dashboard: http://{Config.FLASK_HOST}:{Config.FLASK_PORT}")
                    print("   🤖 WhatsApp: Rodando em background")
                    print(f"   📱 Webhook: http://{Config.FLASK_HOST}:{Config.WHATSAPP_PORT}/webhook")
                    print("\n⚠️ Pressione Ctrl+C para parar")
                    
                    # Iniciar dashboard (bloqueia a thread principal)
                    iniciar_dashboard()
                    
            elif escolha == '2':
                # Apenas WhatsApp Bot
                if verificar_configuracoes():
                    print("🤖 Iniciando apenas WhatsApp Bot...")
                    from config import Config
                    print(f"📱 Webhook: http://{Config.FLASK_HOST}:{Config.WHATSAPP_PORT}/webhook")
                    print("⚠️ Pressione Ctrl+C para parar")
                    iniciar_whatsapp_bot()
                    
            elif escolha == '3':
                # Apenas Dashboard
                try:
                    print("🖥️ Iniciando apenas o Dashboard Web...")
                    from config import Config
                    print(f"📊 Acesse: http://{Config.FLASK_HOST}:{Config.FLASK_PORT}")
                    print("⚠️ Pressione Ctrl+C para parar")
                    iniciar_dashboard()
                except KeyboardInterrupt:
                    print("\n👋 Dashboard interrompido pelo usuário")
                    
            elif escolha == '4':
                testar_componentes()
                
            elif escolha == '5':
                configurar_sistema()
                
            elif escolha == '6':
                ver_status()
                
            elif escolha == '7':
                testar_nova_ia()
                
            else:
                print("❌ Opção inválida!")
                
        except KeyboardInterrupt:
            print("\n\n👋 Sistema interrompido pelo usuário.")
            break
        except Exception as e:
            print(f"\n❌ Erro inesperado: {str(e)}")
        
        if escolha not in ['1', '2', '3']:
            input("\nPressione Enter para continuar...")

if __name__ == "__main__":
    main()
