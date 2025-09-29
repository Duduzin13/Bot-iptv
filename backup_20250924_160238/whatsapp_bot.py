# whatsapp_bot.py - VERSÃO FINAL CORRIGIDA SEM EMOJIS

import requests
import json
from flask import Flask, request, jsonify
from typing import Dict, List
import time
import traceback

# Importa as classes e instâncias necessárias de outros arquivos
from config import Config
from database import db

class WhatsAppBot:
    def __init__(self):
        self.config = Config()
        self.app = Flask(__name__)
        
        # Define as rotas do webhook
        self.app.add_url_rule('/webhook', 'webhook', self.webhook_handler, methods=['GET', 'POST'])
        self.app.add_url_rule('/webhook/mercadopago', 'webhook_mp', self.webhook_mercadopago, methods=['POST'])

    def webhook_handler(self):
        """Lida com as requisições que chegam no webhook."""
        if request.method == 'GET':
            return self.verify_webhook()
        else:
            return self.process_new_message()

    def verify_webhook(self):
        """Verifica o token do webhook da Meta."""
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        if mode == 'subscribe' and token == self.config.WEBHOOK_VERIFY_TOKEN:
            print("Webhook verificado com sucesso!")
            return challenge
        else:
            print("Falha na verificação do Webhook.")
            return "Forbidden", 403

    def process_new_message(self):
        """Extrai a mensagem do corpo da requisição e a processa."""
        try:
            data = request.get_json()
            
            if not data or data.get('object') != 'whatsapp_business_account':
                return "OK", 200
                
            for entry in data.get('entry', []):
                for change in entry.get('changes', []):
                    if change.get('field') == 'messages':
                        value = change.get('value', {})
                        
                        # Processar mensagens
                        for message_data in value.get('messages', []):
                            if message_data.get('type') == 'text':
                                telefone = message_data.get('from')
                                mensagem_texto = message_data.get('text', {}).get('body', '').strip()
                                
                                if telefone and mensagem_texto:
                                    print(f"Mensagem de {telefone}: {mensagem_texto}")
                                    
                                    # Processar mensagem com IA
                                    try:
                                        # Import aqui para evitar import circular
                                        from gemini_bot import gemini_bot
                                        resposta = gemini_bot.processar_mensagem(telefone, mensagem_texto)
                                        
                                        if resposta:
                                            self.enviar_mensagem(telefone, resposta)
                                        else:
                                            print("Resposta vazia da IA")
                                            
                                    except Exception as e:
                                        print(f"Erro ao processar com IA: {str(e)}")
                                        print(traceback.format_exc())
                                        
                                        # Resposta de fallback sem emoji
                                        resposta_erro = "Desculpe, tive um problema técnico. Nossa equipe foi notificada. Pode tentar novamente?"
                                        self.enviar_mensagem(telefone, resposta_erro)
                                        
                                        # Log do erro
                                        db.log_sistema('erro', f'Erro processar mensagem: {str(e)}')
            
            return "OK", 200
            
        except Exception as e:
            print(f"Erro crítico no webhook: {str(e)}")
            print(traceback.format_exc())
            db.log_sistema('erro', f'Erro crítico webhook: {str(e)}')
            return "Error", 500

    def webhook_mercadopago(self):
        """Webhook para processar notificações do Mercado Pago"""
        try:
            data = request.get_json()
            print(f"Webhook Mercado Pago recebido")
            
            # Processar webhook
            from mercpag import mercado_pago
            resultado = mercado_pago.processar_webhook(data)
            
            if resultado:
                print("Webhook Mercado Pago processado com sucesso")
                return "OK", 200
            else:
                print("Webhook Mercado Pago não processado")
                return "Not Processed", 200
                
        except Exception as e:
            print(f"Erro no webhook Mercado Pago: {str(e)}")
            db.log_sistema('erro', f'Erro webhook MP: {str(e)}')
            return "Error", 500

    def enviar_mensagem(self, telefone: str, mensagem: str) -> bool:
        """Envia uma mensagem de texto para um número de telefone."""
        try:
            # Limitar tamanho da mensagem (WhatsApp tem limite)
            if len(mensagem) > 4000:
                mensagem = mensagem[:3900] + "\n\n(mensagem cortada por limite de tamanho)"
            
            url = f"https://graph.facebook.com/v18.0/{self.config.WHATSAPP_PHONE_ID}/messages"
            headers = {
                'Authorization': f'Bearer {self.config.WHATSAPP_TOKEN}', 
                'Content-Type': 'application/json'
            }
            
            payload = {
                "messaging_product": "whatsapp", 
                "to": telefone, 
                "type": "text", 
                "text": {"body": mensagem}
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                print(f"Mensagem enviada para {telefone}")
                return True
            else:
                print(f"Erro ao enviar para {telefone}: {response.status_code}")
                print(f"Resposta: {response.text}")
                
                # Log detalhado do erro
                db.log_sistema('erro', f'Erro enviar WhatsApp {telefone}: {response.status_code} - {response.text}')
                return False
                
        except requests.exceptions.Timeout:
            print(f"Timeout ao enviar mensagem para {telefone}")
            return False
        except Exception as e:
            print(f"Exceção ao enviar mensagem para {telefone}: {str(e)}")
            db.log_sistema('erro', f'Exceção enviar WhatsApp: {str(e)}')
            return False

    def broadcast_mensagem(self, telefones: List[str], mensagem: str) -> tuple:
        """Envia a mesma mensagem para uma lista de telefones."""
        if not telefones:
            return 0, 0
            
        sucesso, erro = 0, 0
        
        print(f"Iniciando broadcast para {len(telefones)} números...")
        
        for i, telefone in enumerate(telefones):
            try:
                if self.enviar_mensagem(telefone, mensagem):
                    sucesso += 1
                    print(f"   {i+1}/{len(telefones)} - {telefone} - OK")
                else:
                    erro += 1
                    print(f"   {i+1}/{len(telefones)} - {telefone} - ERRO")
                    
                # Pausa entre mensagens para evitar rate limit
                time.sleep(1.5)
                
            except Exception as e:
                erro += 1
                print(f"   {i+1}/{len(telefones)} - {telefone} - Erro: {str(e)}")
        
        print(f"Broadcast finalizado: {sucesso} enviados, {erro} falhas")
        db.log_sistema('info', f'Broadcast: {sucesso} sucessos, {erro} erros para {len(telefones)} destinatários')
        
        return sucesso, erro

    def iniciar_bot(self):
        """Inicia o servidor Flask para o bot."""
        print("Iniciando servidor do WhatsApp Bot...")
        print(f"Webhook URL: http://localhost:5001/webhook")
        print(f"Webhook Mercado Pago: http://localhost:5001/webhook/mercadopago")
        print("IMPORTANTE: Configure seu webhook no WhatsApp Business API")
        
        try:
            self.app.run(
                host=self.config.FLASK_HOST, 
                port=5001, 
                debug=False, 
                use_reloader=False,
                threaded=True
            )
        except Exception as e:
            print(f"Erro ao iniciar bot: {str(e)}")
            db.log_sistema('erro', f'Erro iniciar bot: {str(e)}')

# --- Instâncias e Funções Auxiliares ---

# Cria a instância ÚNICA do bot do WhatsApp
whatsapp_bot = WhatsAppBot()

# Funções de atalho que outros arquivos podem importar
def enviar_mensagem(telefone: str, mensagem: str) -> bool:
    """Função de atalho para enviar mensagem"""
    return whatsapp_bot.enviar_mensagem(telefone, mensagem)

def broadcast_para_clientes_ativos(mensagem: str) -> tuple:
    """Envia mensagem para todos os clientes com listas ativas"""
    try:
        clientes = db.listar_clientes_ativos()
        if not clientes:
            print("Nenhum cliente ativo encontrado")
            return 0, 0
            
        telefones = [cliente['telefone'] for cliente in clientes if cliente.get('telefone')]
        print(f"Broadcast para {len(telefones)} clientes ativos")
        
        return whatsapp_bot.broadcast_mensagem(telefones, mensagem)
        
    except Exception as e:
        print(f"Erro no broadcast para ativos: {str(e)}")
        return 0, 1

def broadcast_para_todos_clientes(mensagem: str) -> tuple:
    """Envia mensagem para todos os clientes cadastrados"""
    try:
        conn = db.get_connection()
        try:
            clientes = conn.execute('''
                SELECT DISTINCT telefone 
                FROM clientes 
                WHERE telefone IS NOT NULL AND telefone != ''
            ''').fetchall()
        finally:
            conn.close()
            
        if not clientes:
            print("Nenhum cliente encontrado")
            return 0, 0
            
        telefones = [cliente['telefone'] for cliente in clientes]
        print(f"Broadcast para {len(telefones)} clientes totais")
        
        return whatsapp_bot.broadcast_mensagem(telefones, mensagem)
        
    except Exception as e:
        print(f"Erro no broadcast geral: {str(e)}")
        return 0, 1

def broadcast_para_clientes_expirando(mensagem: str, dias: int = 7) -> tuple:
    """Envia mensagem para clientes com listas expirando"""
    try:
        clientes = db.listar_clientes_expirando(dias)
        if not clientes:
            print(f"Nenhum cliente expirando em {dias} dias")
            return 0, 0
            
        telefones = [cliente['telefone'] for cliente in clientes if cliente.get('telefone')]
        print(f"Broadcast para {len(telefones)} clientes expirando")
        
        return whatsapp_bot.broadcast_mensagem(telefones, mensagem)
        
    except Exception as e:
        print(f"Erro no broadcast expirando: {str(e)}")
        return 0, 1

# Teste do sistema
if __name__ == "__main__":
    print("TESTE DO WHATSAPP BOT")
    print("=" * 50)
    
    try:
        # Teste básico de configuração
        bot = WhatsAppBot()
        print("Bot inicializado com sucesso")
        print(f"Phone ID: {bot.config.WHATSAPP_PHONE_ID}")
        print(f"Token configurado: {'Sim' if bot.config.WHATSAPP_TOKEN else 'Não'}")
        
        # Opção de teste de envio
        teste_envio = input("\nTestar envio de mensagem? (s/N): ").lower().strip()
        if teste_envio == 's':
            numero = input("Digite o número (com código do país): ")
            if numero:
                sucesso = bot.enviar_mensagem(numero, "Teste do sistema IPTV Bot - Funcionando!")
                print(f"Resultado: {'Sucesso' if sucesso else 'Falha'}")
        
        # Opção de iniciar servidor
        iniciar = input("\nIniciar servidor do bot? (s/N): ").lower().strip()
        if iniciar == 's':
            bot.iniciar_bot()
            
    except Exception as e:
        print(f"Erro no teste: {str(e)}")
        print(traceback.format_exc())