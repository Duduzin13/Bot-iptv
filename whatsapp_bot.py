# whatsapp_bot.py - WhatsApp Bot Melhorado com IA Aprimorada
import base64
import json
import requests
import time
from flask import Flask, request, jsonify, Blueprint
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import threading

from config import Config
from database import db
whatsapp_blueprint = Blueprint('whatsapp', __name__)
app = Flask(__name__)

class WhatsAppBot:
    def __init__(self):
        self.config = Config()
        if not self.config.WHATSAPP_TOKEN or not self.config.WHATSAPP_PHONE_ID:
            raise ValueError("WHATSAPP_TOKEN e WHATSAPP_PHONE_ID devem estar configurados no .env")
        
        self.api_url = f"https://graph.facebook.com/v17.0/{self.config.WHATSAPP_PHONE_ID}/messages"
        self.headers = {
            "Authorization": f"Bearer {self.config.WHATSAPP_TOKEN}",
            "Content-Type": "application/json"
        }

    def enviar_mensagem(self, telefone: str, mensagem: str) -> bool:
        """
        Envia mensagem de texto via WhatsApp Business API.
        """
        try:
            payload = {
                "messaging_product": "whatsapp",
                "to": telefone,
                "type": "text",
                "text": {"body": mensagem}
            }
            
            response = requests.post(self.api_url, headers=self.headers, json=payload)
            
            if response.status_code == 200:
                print(f"✅ Mensagem enviada para {telefone}")
                return True
            else:
                print(f"❌ Erro ao enviar mensagem para {telefone}: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Exceção ao enviar mensagem: {e}")
            return False

    def enviar_imagem_base64(self, telefone: str, imagem_base64: str) -> bool:
        """
        Envia imagem via WhatsApp Business API usando base64.
        """
        try:
            # Remove o prefixo data:image/png;base64, se existir
            if imagem_base64.startswith('data:image'):
                imagem_base64 = imagem_base64.split(',')[1]
            
            # Primeiro, fazer upload da mídia
            upload_url = f"https://graph.facebook.com/v17.0/{self.config.WHATSAPP_PHONE_ID}/media"
            
            # Decodificar base64 para bytes
            image_data = base64.b64decode(imagem_base64)
            
            files = {
                'file': ('qr_code.png', image_data, 'image/png'),
                'type': (None, 'image/png'),
                'messaging_product': (None, 'whatsapp')
            }
            
            upload_headers = {
                "Authorization": f"Bearer {self.config.WHATSAPP_TOKEN}"
            }
            
            upload_response = requests.post(upload_url, headers=upload_headers, files=files)
            
            if upload_response.status_code == 200:
                upload_data = upload_response.json()
                media_id = upload_data.get('id')
                
                if media_id:
                    # Enviar a imagem usando o media_id
                    payload = {
                        "messaging_product": "whatsapp",
                        "to": telefone,
                        "type": "image",
                        "image": {"id": media_id}
                    }
                    
                    response = requests.post(self.api_url, headers=self.headers, json=payload)
                    
                    if response.status_code == 200:
                        print(f"✅ Imagem enviada para {telefone}")
                        return True
                    else:
                        print(f"❌ Erro ao enviar imagem para {telefone}: {response.text}")
                        return False
            
            print(f"❌ Erro no upload da imagem: {upload_response.text}")
            return False
            
        except Exception as e:
            print(f"❌ Exceção ao enviar imagem: {e}")
            return False

    def processar_webhook(self, data: dict) -> bool:
        """
        Processa webhooks recebidos do WhatsApp.
        """
        try:
            if not data.get('entry'):
                return False

            for entry in data['entry']:
                if not entry.get('changes'):
                    continue
                    
                for change in entry['changes']:
                    if change.get('field') != 'messages':
                        continue
                        
                    messages = change.get('value', {}).get('messages', [])
                    
                    for message in messages:
                        self._processar_mensagem_recebida(message)
            
            return True
        except Exception as e:
            print(f"❌ Erro ao processar webhook: {e}")
            return False

    def _processar_mensagem_recebida(self, message: dict):
        """
        Processa uma mensagem individual recebida.
        """
        try:
            telefone = message.get('from')
            message_type = message.get('type')
            
            if not telefone:
                return
                
            # Processar apenas mensagens de texto
            if message_type == 'text':
                texto = message.get('text', {}).get('body', '').strip()
                
                if texto:
                    print(f"📱 Mensagem recebida de {telefone}: {texto}")
                    
                    # Processar em thread separada para não bloquear o webhook
                    thread = threading.Thread(
                        target=self._processar_mensagem_thread,
                        args=(telefone, texto)
                    )
                    thread.start()
            
            elif message_type in ['image', 'audio', 'video', 'document']:
                # Responder a arquivos de mídia
                self.enviar_mensagem(
                    telefone,
                    """📎 **Arquivo recebido**
                    
Desculpe, no momento só consigo processar mensagens de texto.

Se precisar de ajuda, digite uma das opções:
**1** - Menu principal
**2** - Falar com suporte"""
                )
                
        except Exception as e:
            print(f"❌ Erro ao processar mensagem individual: {e}")

    def _processar_mensagem_thread(self, telefone: str, mensagem: str):
        """
        Processa mensagem em thread separada.
        """
        try:
            # Importar aqui para evitar dependência circular
            from gemini_bot import gemini_bot
            
            # Log da interação
            db.log_sistema('info', f'Mensagem recebida de {telefone}: {mensagem[:50]}...')
            
            # Processar mensagem com o Gemini Bot
            resposta = gemini_bot.processar_mensagem(telefone, mensagem)
            
            if resposta:
                # Adicionar delay pequeno para parecer mais natural
                time.sleep(0.5)
                
                # Dividir mensagens muito longas
                if len(resposta) > 4000:  # WhatsApp tem limite de ~4096 caracteres
                    partes = self._dividir_mensagem(resposta, 3900)
                    for i, parte in enumerate(partes):
                        self.enviar_mensagem(telefone, parte)
                        if i < len(partes) - 1:  # Pausa entre partes
                            time.sleep(1)
                else:
                    self.enviar_mensagem(telefone, resposta)
            
        except Exception as e:
            print(f"❌ Erro ao processar mensagem em thread: {e}")
            # Enviar mensagem de erro genérica
            self.enviar_mensagem(
                telefone,
                """⚠️ **Erro temporário**

Tive um problema técnico. Tente novamente em alguns segundos.

Se o problema persistir:
📞 **Suporte:** 11 96751-2034"""
            )

    def _dividir_mensagem(self, mensagem: str, max_length: int) -> List[str]:
        """
        Divide mensagem longa em partes menores.
        """
        if len(mensagem) <= max_length:
            return [mensagem]
        
        partes = []
        linhas = mensagem.split('\n')
        parte_atual = ""
        
        for linha in linhas:
            if len(parte_atual + linha + "\n") <= max_length:
                parte_atual += linha + "\n"
            else:
                if parte_atual:
                    partes.append(parte_atual.strip())
                    parte_atual = linha + "\n"
                else:
                    # Linha muito longa, dividir por caracteres
                    while len(linha) > max_length:
                        partes.append(linha[:max_length])
                        linha = linha[max_length:]
                    parte_atual = linha + "\n"
        
        if parte_atual:
            partes.append(parte_atual.strip())
        
        return partes

    #def iniciar_bot(self):
        #####app.run(host='0.0.0.0', port=5001, debug=False, use_reloader=False)

# Instância global do bot
whatsapp_bot = WhatsAppBot()

# Função auxiliar para enviar mensagens (para compatibilidade)
def enviar_mensagem(telefone: str, mensagem: str) -> bool:
    """Função auxiliar para enviar mensagem"""
    return whatsapp_bot.enviar_mensagem(telefone, mensagem)

# === ROTAS FLASK PARA WEBHOOKS ===

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    """
    Endpoint para receber webhooks do WhatsApp Business API.
    """
    if request.method == 'GET':
        # Verificação do webhook
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        if mode == 'subscribe' and token == Config().WEBHOOK_VERIFY_TOKEN:
            print("✅ Webhook verificado com sucesso")
            return challenge
        else:
            print("❌ Falha na verificação do webhook")
            return 'Forbidden', 403
    
    elif request.method == 'POST':
        # Processar mensagens recebidas
        try:
            data = request.get_json()
            if data:
                whatsapp_bot.processar_webhook(data)
            return 'OK', 200
        except Exception as e:
            print(f"❌ Erro no webhook POST: {e}")
            return 'Error', 500

@whatsapp_blueprint.route('/webhook', methods=['GET', 'POST'])
def webhook_mercadopago():
    """
    Webhook para receber notificações do Mercado Pago.
    """
    try:
        data = request.get_json()
        if data:
            from mercpag import mercado_pago
            processado = mercado_pago.processar_webhook(data)
            
            if processado:
                print("✅ Webhook Mercado Pago processado com sucesso")
            else:
                print("⚠️ Webhook Mercado Pago ignorado ou não processado")
                
        return 'OK', 200
    except Exception as e:
        print(f"❌ Erro no webhook Mercado Pago: {e}")
        return 'Error', 500

# === FUNÇÕES DE BROADCAST ===

def broadcast_para_clientes_ativos(mensagem: str) -> Tuple[int, int]:
    """
    Envia mensagem para todos os clientes com listas ativas.
    """
    clientes_ativos = db.listar_clientes_ativos()
    sucesso = 0
    erro = 0
    
    print(f"📡 Iniciando broadcast para {len(clientes_ativos)} clientes ativos...")
    
    for cliente in clientes_ativos:
        try:
            if whatsapp_bot.enviar_mensagem(cliente['telefone'], mensagem):
                sucesso += 1
            else:
                erro += 1
            
            # Pausa entre envios para não sobrecarregar a API
            time.sleep(0.5)
            
        except Exception as e:
            print(f"❌ Erro ao enviar para {cliente['telefone']}: {e}")
            erro += 1
    
    print(f"📊 Broadcast concluído: {sucesso} sucessos, {erro} falhas")
    return sucesso, erro

def broadcast_para_todos_clientes(mensagem: str) -> Tuple[int, int]:
    """
    Envia mensagem para TODOS os clientes cadastrados.
    """
    try:
        conn = db.get_connection()
        clientes = conn.execute("SELECT DISTINCT telefone FROM clientes").fetchall()
        conn.close()
        
        sucesso = 0
        erro = 0
        
        print(f"📡 Iniciando broadcast para {len(clientes)} clientes...")
        
        for cliente in clientes:
            try:
                if whatsapp_bot.enviar_mensagem(cliente['telefone'], mensagem):
                    sucesso += 1
                else:
                    erro += 1
                
                # Pausa entre envios
                time.sleep(0.5)
                
            except Exception as e:
                print(f"❌ Erro ao enviar para {cliente['telefone']}: {e}")
                erro += 1
        
        print(f"📊 Broadcast concluído: {sucesso} sucessos, {erro} falhas")
        return sucesso, erro
        
    except Exception as e:
        print(f"❌ Erro no broadcast geral: {e}")
        return 0, 0

def broadcast_para_clientes_expirando(mensagem: str, dias: int = 7) -> Tuple[int, int]:
    """
    Envia mensagem para clientes com listas expirando em X dias.
    """
    clientes_expirando = db.listar_clientes_expirando(dias)
    sucesso = 0
    erro = 0
    
    print(f"📡 Iniciando broadcast para {len(clientes_expirando)} clientes expirando...")
    
    for cliente in clientes_expirando:
        try:
            # Personalizar mensagem com dados do cliente
            mensagem_personalizada = mensagem.replace(
                "[USUARIO]", cliente.get('usuario_iptv', 'Cliente')
            ).replace(
                "[EXPIRACAO]", cliente.get('data_expiracao', 'em breve')
            )
            
            if whatsapp_bot.enviar_mensagem(cliente['telefone'], mensagem_personalizada):
                sucesso += 1
            else:
                erro += 1
            
            # Pausa entre envios
            time.sleep(0.5)
            
        except Exception as e:
            print(f"❌ Erro ao enviar para {cliente['telefone']}: {e}")
            erro += 1
    
    print(f"📊 Broadcast concluído: {sucesso} sucessos, {erro} falhas")
    return sucesso, erro

# === FUNÇÕES AUXILIARES ===

def testar_whatsapp_api() -> bool:
    """
    Testa se a API do WhatsApp está funcionando.
    """
    try:
        # Testar com o próprio número (se configurado)
        numero_teste = "5511967512034"  # Substitua pelo seu número
        
        resultado = whatsapp_bot.enviar_mensagem(
            numero_teste,
            "🧪 **Teste de API WhatsApp**\n\nSe você recebeu esta mensagem, a API está funcionando corretamente!"
        )
        
        if resultado:
            print("✅ Teste da API WhatsApp: SUCESSO")
            return True
        else:
            print("❌ Teste da API WhatsApp: FALHA")
            return False
            
    except Exception as e:
        print(f"❌ Erro no teste da API WhatsApp: {e}")
        return False

@whatsapp_blueprint.route('/test', methods=['GET'])
def test_endpoint():
    """
    Endpoint para testar se o servidor está funcionando.
    """
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "message": "WhatsApp Bot está funcionando!"
    })

@whatsapp_blueprint.route('/health', methods=['GET'])
def health_check():
    """
    Endpoint de health check.
    """
    try:
        # Verificar banco de dados
        stats = db.get_estatisticas()
        
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "database": "connected",
            "stats": stats
        })
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }), 500

# === INICIALIZAÇÃO ===

if __name__ == '__main__':
    print("🚀 Iniciando WhatsApp Bot...")
    print(f"📱 Phone ID: {Config().WHATSAPP_PHONE_ID}")
    print(f"🌐 Webhook disponível em: http://localhost:5001/webhook")
    print("=" * 60)
    
    # Iniciar o bot
    whatsapp_bot.iniciar_bot()