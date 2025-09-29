# gemini_bot.py - VERSÃO CORRIGIDA SEM EMOJIS E RESPOSTAS CURTAS

import google.generativeai as genai
import json
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
from config import Config
from database import db
import re
import random

class GeminiBot:
    def __init__(self):
        self.config = Config()
        genai.configure(api_key=self.config.GEMINI_API_KEY)
        self.model = genai.GenerativeModel("gemini-1.5-flash")
        
        # Contexto do sistema sem emojis
        self.system_context = """
        Você é Alex, assistente de vendas IPTV. Seja profissional e direto.
        
        REGRAS IMPORTANTES:
        - NUNCA use emojis
        - Respostas curtas (máximo 50 palavras)
        - Tom profissional mas amigável
        - Seja direto ao ponto
        - Varie as respostas para não ser robotizado
        
        PRODUTOS:
        - Lista IPTV com canais Full HD + H265 + HD + SD + VOD + Adulto + LGBT
        - Preço: R$ 30,00 por mês
        - Suporte até 10 conexões simultâneas
        - Planos de 1 a 12 meses
        """

    def processar_mensagem(self, telefone: str, mensagem: str) -> str:
        """Processa mensagem usando IA contextual"""
        try:
            # Buscar conversa existente
            conversa = db.get_conversa(telefone)
            
            # Se está em fluxo de compra
            if conversa and conversa.get('contexto') == 'comprar':
                return self.processar_fluxo_compra(telefone, mensagem, conversa)
            
            # Se está em fluxo de renovação
            if conversa and conversa.get('contexto') == 'renovar':
                return self.processar_fluxo_renovacao(telefone, mensagem, conversa)
            
            # Primeira mensagem ou conversa geral
            return self.processar_conversa_geral(telefone, mensagem)
                
        except Exception as e:
            print(f"Erro no processamento da IA: {str(e)}")
            db.log_sistema('erro', f'Erro IA: {str(e)}')
            return "Ops, tive um problema técnico. Pode tentar novamente?"

    def processar_conversa_geral(self, telefone: str, mensagem: str) -> str:
        """Processa conversa geral detectando intenções"""
        try:
            cliente = db.buscar_cliente_por_telefone(telefone)
            mensagem_lower = mensagem.lower().strip()
            
            # Detectar intenções diretamente sem IA para ser mais rápido
            if any(palavra in mensagem_lower for palavra in ['comprar', 'quero lista', 'quero iptv', 'adquirir']):
                db.salvar_conversa(telefone, 'comprar', 'aguardando_usuario', json.dumps({}))
                return "Vou te ajudar a criar sua lista IPTV. Qual nome de usuário você gostaria?"
            
            elif any(palavra in mensagem_lower for palavra in ['renovar', 'estender', 'continuar']):
                if cliente and cliente.get('usuario_iptv'):
                    db.salvar_conversa(telefone, 'renovar', 'aguardando_meses', json.dumps({}))
                    return f"Vou renovar a lista do usuário {cliente['usuario_iptv']}. Por quantos meses?"
                else:
                    return "Você não possui uma lista para renovar. Digite 'comprar' para criar uma nova."
            
            elif any(palavra in mensagem_lower for palavra in ['teste', 'gratis', 'gratuito']):
                return "Não oferecemos teste gratuito, mas você tem 7 dias de garantia. Digite 'comprar' para adquirir sua lista."
            
            elif any(palavra in mensagem_lower for palavra in ['consultar', 'meus dados', 'minha lista']):
                if cliente and cliente.get('usuario_iptv'):
                    data_exp = cliente.get('data_expiracao', 'Indefinido')
                    if data_exp and data_exp != 'Indefinido':
                        try:
                            exp_date = datetime.fromisoformat(data_exp)
                            if exp_date > datetime.now():
                                return f"Sua lista: {cliente['usuario_iptv']} - Expira em: {exp_date.strftime('%d/%m/%Y')}"
                            else:
                                return f"Sua lista {cliente['usuario_iptv']} está expirada. Digite 'renovar' para reativar."
                        except:
                            return f"Usuário: {cliente['usuario_iptv']} - Status: Verificar no painel"
                    else:
                        return f"Usuário: {cliente['usuario_iptv']} - Status: Sem data de expiração"
                else:
                    return "Você não possui lista cadastrada. Digite 'comprar' para adquirir."
            
            elif any(palavra in mensagem_lower for palavra in ['preço', 'valor', 'quanto custa']):
                return "Lista IPTV: R$ 30,00 por mês por conexão. Planos de 1 a 12 meses. Digite 'comprar' para adquirir."
            
            elif any(palavra in mensagem_lower for palavra in ['oi', 'olá', 'ola', 'bom dia', 'boa tarde', 'boa noite']):
                frases_saudacao = [
                    "Olá! Sou Alex, especialista em IPTV. Como posso ajudar?",
                    "Oi! Precisa de lista IPTV? Posso te ajudar.",
                    "Olá! Trabalho com listas IPTV premium. Em que posso ajudar?"
                ]
                return random.choice(frases_saudacao)
            
            else:
                # Resposta geral para outras mensagens
                return "Olá! Trabalho com listas IPTV. Digite 'comprar' para nova lista, 'renovar' para estender ou 'consultar' para ver seus dados."
                
        except Exception as e:
            print(f"Erro na conversa geral: {str(e)}")
            return "Desculpe, houve um erro. Pode tentar novamente?"

    def processar_fluxo_compra(self, telefone: str, mensagem: str, conversa: Dict) -> str:
        """Processa o fluxo de compra passo a passo"""
        estado_atual = conversa.get('estado', 'inicio')
        dados_temp = json.loads(conversa.get('dados_temporarios', '{}'))

        if estado_atual == 'inicio':
            db.salvar_conversa(telefone, 'comprar', 'aguardando_usuario', json.dumps({}))
            return "Qual nome de usuário você gostaria? Use apenas letras e números, sem espaços."

        elif estado_atual == 'aguardando_usuario':
            return self.processar_usuario(telefone, mensagem, dados_temp)

        elif estado_atual == 'aguardando_conexoes':
            return self.processar_conexoes(telefone, mensagem, dados_temp)

        elif estado_atual == 'aguardando_duracao':
            return self.processar_duracao(telefone, mensagem, dados_temp)

        elif estado_atual == 'confirmando_dados':
            return self.processar_confirmacao(telefone, mensagem, dados_temp)

        else:
            # Estado desconhecido - reiniciar
            db.salvar_conversa(telefone, 'inicial', 'inicial', json.dumps({}))
            return "Algo deu errado. Vamos começar de novo. Digite 'comprar' para nova lista."

    def processar_usuario(self, telefone: str, mensagem: str, dados_temp: Dict) -> str:
        """Processa o nome de usuário"""
        usuario = mensagem.strip().replace(' ', '').lower()
        
        # Validações
        if not usuario or len(usuario) < 3:
            return "Nome muito curto. Use pelo menos 3 caracteres."
        
        if not re.match(r'^[a-zA-Z0-9_]+$', usuario):
            return "Use apenas letras, números e underscore. Tente outro nome."

        # Salvar usuário
        dados_temp['usuario'] = usuario
        db.salvar_conversa(telefone, 'comprar', 'aguardando_conexoes', json.dumps(dados_temp))
        
        return f"Usuário '{usuario}' confirmado. Quantas conexões você precisa? (1 a 10)"

    def processar_conexoes(self, telefone: str, mensagem: str, dados_temp: Dict) -> str:
        """Processa número de conexões"""
        try:
            conexoes = int(mensagem.strip())
            
            if not (1 <= conexoes <= 10):
                return "Digite um número entre 1 e 10."
            
            dados_temp['conexoes'] = conexoes
            db.salvar_conversa(telefone, 'comprar', 'aguardando_duracao', json.dumps(dados_temp))
            
            # Calcular preço mensal
            preco_mes = float(db.get_config('preco_mes', '30.00'))
            preco_conexao = float(db.get_config('preco_conexao', '30.00'))
            conexoes_extras = max(0, conexoes - 1)
            preco_mensal = preco_mes + (preco_conexao * conexoes_extras)
            
            return f"{conexoes} conexões confirmadas. Por quantos meses? (1 a 12) - Preço mensal: R$ {preco_mensal:.2f}"
            
        except ValueError:
            return "Digite apenas o número de conexões (exemplo: 2)"

    def processar_duracao(self, telefone: str, mensagem: str, dados_temp: Dict) -> str:
        """Processa duração em meses"""
        try:
            meses = int(mensagem.strip())
            
            if not (1 <= meses <= 12):
                return "Digite um número entre 1 e 12 meses."
            
            dados_temp['meses'] = meses
            
            # Calcular preço total
            from mercpag import mercado_pago
            preco_total = mercado_pago.calcular_preco(dados_temp['conexoes'], meses)
            dados_temp['preco_total'] = preco_total
            
            # Salvar estado de confirmação
            db.salvar_conversa(telefone, 'comprar', 'confirmando_dados', json.dumps(dados_temp))
            
            # Criar resumo conciso
            usuario = dados_temp['usuario']
            conexoes = dados_temp['conexoes']
            
            resumo = f"""RESUMO:
Usuário: {usuario}
Conexões: {conexoes}
Duração: {meses} mês{'es' if meses > 1 else ''}
Total: R$ {preco_total:.2f}

Digite 'sim' para confirmar ou 'não' para cancelar."""

            return resumo
            
        except ValueError:
            return "Digite apenas o número de meses (exemplo: 3)"

    def processar_confirmacao(self, telefone: str, mensagem: str, dados_temp: Dict) -> str:
        """Processa confirmação e gera PIX"""
        resposta = mensagem.strip().lower()
        
        if resposta in ['sim', 's', 'confirmar', 'ok']:
            return self.gerar_pix_pagamento(telefone, dados_temp)
        
        elif resposta in ['não', 'nao', 'n', 'cancelar']:
            db.salvar_conversa(telefone, 'inicial', 'inicial', json.dumps({}))
            return "Compra cancelada. Se precisar de ajuda, é só chamar."
        
        else:
            return "Digite 'sim' para confirmar ou 'não' para cancelar."

    def gerar_pix_pagamento(self, telefone: str, dados_temp: Dict) -> str:
        """Gera PIX para pagamento"""
        try:
            from mercpag import mercado_pago
            
            # Buscar ou criar cliente
            cliente = db.buscar_cliente_por_telefone(telefone)
            if not cliente:
                cliente_id = db.criar_cliente(telefone, None, dados_temp['usuario'])
            else:
                cliente_id = cliente['id']
            
            # Gerar PIX
            pix_data = mercado_pago.criar_cobranca_pix(
                telefone, 
                dados_temp['usuario'],
                dados_temp['conexoes'],
                dados_temp['meses'],
                "lista"
            )
            
            if not pix_data:
                return "Erro ao gerar PIX. Tente novamente em alguns minutos."
            
            # Salvar pagamento no banco
            db.criar_pagamento(cliente_id, dados_temp['preco_total'], pix_data['payment_id'], pix_data['qr_code'])
            
            # Salvar ID do pagamento na conversa
            dados_temp['payment_id'] = pix_data['payment_id']
            db.salvar_conversa(telefone, 'comprar', 'aguardando_pagamento', json.dumps(dados_temp))
            
            # Resposta com PIX concisa
            resposta_pix = f"""PIX GERADO!

Valor: R$ {pix_data['valor']:.2f}
Válido por: 30 minutos

COPIE E COLE:
{pix_data['copia_cola']}

Após o pagamento sua lista será criada automaticamente em até 2 minutos."""

            return resposta_pix
            
        except Exception as e:
            print(f"Erro ao gerar PIX: {str(e)}")
            db.log_sistema('erro', f'Erro gerar PIX: {str(e)}')
            return "Erro interno. Nossa equipe foi notificada. Tente novamente."

    def processar_pagamento_aprovado(self, telefone: str, dados_conversa: Dict):
        """Processa pagamento aprovado e cria lista no BitPanel"""
        try:
            from bitpanel_automation import BitPanelManager
            
            usuario = dados_conversa.get('usuario')
            conexoes = dados_conversa.get('conexoes')
            meses = dados_conversa.get('meses')
            
            print(f"Processando pagamento aprovado para {usuario}")
            
            # Criar lista no BitPanel
            bitpanel = BitPanelManager()
            resultado = bitpanel.criar_lista(usuario, conexoes, meses, headless=True)
            bitpanel.close()
            
            if resultado:
                # Atualizar dados no banco
                senha = resultado.get('senha', 'senha_padrao')
                db.atualizar_lista_cliente(telefone, usuario, senha, conexoes, meses)
                
                # Enviar confirmação de sucesso
                link_acesso = db.get_config('link_acesso', Config.LINK_ACESSO_DEFAULT)
                
                mensagem_sucesso = f"""LISTA CRIADA COM SUCESSO!

Pagamento confirmado e lista ativa.

DADOS DE ACESSO:
Link: {link_acesso}
Usuário: {usuario}
Senha: {senha}
Conexões: {conexoes}
Válido até: {(datetime.now() + timedelta(days=30*meses)).strftime('%d/%m/%Y')}

COMO USAR:
1. Baixe app IPTV (Smart IPTV, IPTV Smarters)
2. Configure com os dados acima
3. Aproveite milhares de canais

Suporte: Se precisar de ajuda, é só chamar."""

                from whatsapp_bot import enviar_mensagem
                enviar_mensagem(telefone, mensagem_sucesso)
                
                db.log_sistema('sucesso', f'Lista criada: {usuario} - {conexoes} conexões - {meses} meses')
                
            else:
                # Erro na criação - notificar
                mensagem_erro = f"""PAGAMENTO CONFIRMADO!

PIX aprovado, mas problema técnico na criação automática.

Nossa equipe foi notificada e criará sua lista manualmente em até 30 minutos.

Você receberá os dados assim que estiver pronto."""

                from whatsapp_bot import enviar_mensagem  
                enviar_mensagem(telefone, mensagem_erro)
                
                db.log_sistema('erro', f'Pagamento aprovado mas falha na criação: {usuario}')
                
        except Exception as e:
            print(f"Erro ao processar pagamento aprovado: {str(e)}")
            db.log_sistema('erro', f'Erro processar pagamento: {str(e)}')

    def processar_fluxo_renovacao(self, telefone: str, mensagem: str, conversa: Dict) -> str:
        """Processa renovação de lista existente"""
        estado_atual = conversa.get('estado', 'inicio')
        dados_temp = json.loads(conversa.get('dados_temporarios', '{}'))
        
        cliente = db.buscar_cliente_por_telefone(telefone)
        if not cliente or not cliente.get('usuario_iptv'):
            db.salvar_conversa(telefone, 'inicial', 'inicial', json.dumps({}))
            return "Você não possui lista para renovar. Digite 'comprar' para criar nova."

        if estado_atual == 'inicio':
            db.salvar_conversa(telefone, 'renovar', 'aguardando_meses', json.dumps({}))
            return f"Renovar lista '{cliente['usuario_iptv']}' por quantos meses? (1 a 12)"

        elif estado_atual == 'aguardando_meses':
            return self.processar_meses_renovacao(telefone, mensagem, dados_temp, cliente)
        
        return "Erro no fluxo de renovação. Digite 'renovar' para tentar novamente."

    def processar_meses_renovacao(self, telefone: str, mensagem: str, dados_temp: Dict, cliente: Dict) -> str:
        """Processa meses para renovação"""
        try:
            meses = int(mensagem.strip())
            
            if not (1 <= meses <= 12):
                return "Digite um número entre 1 e 12 meses."
            
            # Calcular preço
            from mercpag import mercado_pago
            conexoes = cliente.get('conexoes', 1)
            preco_total = mercado_pago.calcular_preco(conexoes, meses)
            
            # Gerar PIX para renovação
            pix_data = mercado_pago.criar_cobranca_pix(
                telefone,
                cliente['usuario_iptv'],
                conexoes,
                meses,
                "renovacao"
            )
            
            if pix_data:
                # Salvar pagamento
                db.criar_pagamento(cliente['id'], preco_total, pix_data['payment_id'], pix_data['qr_code'])
                
                # Limpar conversa
                db.salvar_conversa(telefone, 'inicial', 'inicial', json.dumps({}))
                
                resposta = f"""RENOVAÇÃO - PIX GERADO!

Lista: {cliente['usuario_iptv']}
Adicionar: {meses} mês{'es' if meses > 1 else ''}
Valor: R$ {preco_total:.2f}

COPIE E COLE:
{pix_data['copia_cola']}

Após pagamento sua lista será renovada automaticamente."""

                return resposta
            else:
                return "Erro ao gerar PIX. Tente novamente."
                
        except ValueError:
            return "Digite apenas o número de meses (1 a 12)."

    def resposta_geral(self, mensagem: str, contexto: Optional[str] = None) -> str:
        """Método para compatibilidade"""
        return "Olá! Sou especialista em IPTV. Como posso ajudar?"

# Instância única do bot
gemini_bot = GeminiBot()