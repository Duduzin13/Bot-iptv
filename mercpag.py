import mercadopago
import json
import traceback
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from config import Config
from database import db

class MercadoPagoManager:
    def __init__(self):
        self.config = Config()
        if not self.config.MERCADOPAGO_ACCESS_TOKEN:
            raise ValueError("MERCADOPAGO_ACCESS_TOKEN não foi configurado no arquivo .env")
        self.mp = mercadopago.SDK(self.config.MERCADOPAGO_ACCESS_TOKEN)
        
    def calcular_preco(self, conexoes: int, meses: int) -> float:
        preco_mes = float(db.get_config('preco_mes', '30.00'))
        preco_conexao = float(db.get_config('preco_conexao', '30.00'))
        conexoes_adicionais = max(0, conexoes - 1)
        total = (preco_mes * meses) + (preco_conexao * conexoes_adicionais * meses)
        return round(total, 2)
    
    def criar_cobranca_pix(self, cliente_telefone: str, usuario_iptv: str, conexoes: int, meses: int) -> Optional[Dict]:
        try:
            valor = self.calcular_preco(conexoes, meses)
            descricao = f"Lista IPTV {usuario_iptv} - {conexoes}x{meses}m"
            
            # CORREÇÃO: Simplificar dados do pagamento PIX
            payment_data = {
                "transaction_amount": float(valor),
                "description": descricao,
                "payment_method_id": "pix",
                "payer": {
                    "email": f"cliente{cliente_telefone.replace('+', '').replace('-', '')}@gmail.com",
                    "first_name": "Cliente",
                    "last_name": "IPTV"
                },
                "external_reference": f"iptv_{cliente_telefone}_{int(datetime.now().timestamp())}",
                "date_of_expiration": (datetime.now(timezone.utc) + timedelta(minutes=6)).isoformat(timespec='milliseconds')
            }
            
            print(f"[DEBUG] Criando PIX com dados: {json.dumps(payment_data, indent=2)}")
            
            payment_response = self.mp.payment().create(payment_data)
            
            print(f"[DEBUG] Resposta do MP: {json.dumps(payment_response, indent=2)}")
            
            if payment_response["status"] == 201:
                payment = payment_response["response"]
                pix_data = payment.get("point_of_interaction", {}).get("transaction_data", {})
                
                # CORREÇÃO: Verificar se o PIX foi criado corretamente
                if not pix_data.get("qr_code"):
                    print("❌ ERRO: QR Code não foi gerado pelo Mercado Pago")
                    return None
                
                print(f"✅ PIX criado com sucesso para {usuario_iptv} no valor de R$ {valor}")
                return {
                    "payment_id": payment["id"],
                    "status": payment["status"],
                    "valor": valor,
                    "copia_cola": pix_data.get("qr_code", ""),
                    "qr_code_base64": pix_data.get("qr_code_base64", "")
                }
            else:
                print(f"❌ Erro ao criar PIX no Mercado Pago:")
                print(f"Status: {payment_response.get('status')}")
                print(f"Response: {json.dumps(payment_response.get('response', {}), indent=2)}")
                return None
                
        except Exception as e:
            print(f"❌ Exceção ao criar cobrança PIX: {e}")
            traceback.print_exc()
            return None
    
    def verificar_pagamento(self, payment_id: str) -> Optional[Dict]:
        try:
            payment_response = self.mp.payment().get(payment_id)
            if payment_response["status"] == 200:
                return payment_response["response"]
            return None
        except Exception as e:
            print(f"❌ Erro ao verificar pagamento '{payment_id}': {e}")
            traceback.print_exc()
            return None

    def processar_webhook(self, webhook_data: Dict) -> bool:
        """Processa notificações de pagamento, diferenciando compra de renovação."""
        try:
            if webhook_data.get("action") in ["payment.updated", "payment.created"]:
                payment_id = webhook_data.get("data", {}).get("id")
                if not payment_id: return False

                payment_info = self.verificar_pagamento(str(payment_id))
                if not payment_info or payment_info.get("status") != "approved":
                    return False

                pagamento_db = db.buscar_pagamento(str(payment_id))
                if pagamento_db and pagamento_db.get('status') != 'approved':
                    print(f"[WEBHOOK MP] Pagamento {payment_id} APROVADO.")
                    db.atualizar_pagamento(str(payment_id), "approved")
                    
                    telefone = pagamento_db['telefone']
                    contexto = pagamento_db['contexto']
                    dados = json.loads(pagamento_db.get('dados_temporarios', '{}'))

                    from gemini_bot import gemini_bot

                    # --- LÓGICA CORRIGIDA ---
                    if contexto == 'comprar':
                        print(f"[WEBHOOK MP] Iniciando fluxo de CRIAÇÃO para {telefone}")
                        gemini_bot.processar_pagamento_aprovado(telefone, dados)
                    elif contexto == 'renovar':
                        print(f"[WEBHOOK MP] Iniciando fluxo de RENOVAÇÃO para {telefone}")
                        gemini_bot.processar_pagamento_renovacao(telefone, dados)
                    
                    db.salvar_conversa(telefone, 'inicial', 'menu', '{}') # Reseta a conversa
                    return True
            return False
        except Exception as e:
            print(f"❌ Erro crítico ao processar webhook do Mercado Pago: {e}")
            traceback.print_exc()
            return False

mercado_pago = MercadoPagoManager()