# main.py - Arquivo Principal Simplificado
import os
import sys

# Adicionar diretório atual ao path para importações corretas
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def main():
    """
    Função principal que inicia o servidor Flask unificado.
    """
    print("🚀 Iniciando Sistema IPTV Unificado (Dashboard + WhatsApp Webhook)")
    print("=" * 60)
    
    try:
        from dashboard import app
        from config import Config
        
        print(f"🖥️  Dashboard e Webhooks rodando em: http://{Config.FLASK_HOST}:{Config.FLASK_PORT}")
        print("   - Dashboard: /")
        print("   - Webhook WhatsApp: /webhook")
        print("   - Webhook Mercado Pago: /webhook/mercadopago")
        print("\n⚠️  Pressione Ctrl+C para parar o servidor.")
        
        # Inicia o servidor Flask que agora contém TUDO
        app.run(
            host=Config.FLASK_HOST,
            port=Config.FLASK_PORT,
            debug=True # Pode ser False em produção
        )
        
    except ImportError as e:
        print(f"❌ Erro de importação: {e}")
        print("   Verifique se todas as dependências estão instaladas com 'pip install -r requirements.txt'")
    except Exception as e:
        print(f"❌ Erro fatal ao iniciar o servidor: {e}")

if __name__ == "__main__":
    main()