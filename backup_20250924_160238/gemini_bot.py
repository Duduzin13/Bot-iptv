# debug_version.py - Versão com debug intensivo para identificar o problema

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

    def processar_mensagem(self, telefone: str, mensagem: str) -> str:
        """Processa mensagem usando IA contextual"""
        try:
            print(f"[DEBUG] ===== INÍCIO PROCESSAMENTO =====")
            print(f"[DEBUG] Telefone: {telefone}")
            print(f"[DEBUG] Mensagem: '{mensagem}'")
            
            # Buscar conversa existente
            conversa = db.get_conversa(telefone)
            
            if conversa:
                print(f"[DEBUG] Conversa encontrada:")
                print(f"[DEBUG]   - Contexto: '{conversa.get('contexto')}'")
                print(f"[DEBUG]   - Estado: '{conversa.get('estado')}'")
                print(f"[DEBUG]   - Dados: '{conversa.get('dados_temporarios')}'")
            else:
                print(f"[DEBUG] Nenhuma conversa encontrada")
            
            # Verificar se está em fluxo de compra
            if conversa and conversa.get('contexto') == 'comprar':
                print(f"[DEBUG] Direcionando para fluxo de COMPRA")
                return self.processar_fluxo_compra(telefone, mensagem, conversa)
            
            # Verificar se está em fluxo de renovação
            if conversa and conversa.get('contexto') == 'renovar':
                print(f"[DEBUG] Direcionando para fluxo de RENOVAÇÃO")
                return self.processar_fluxo_renovacao(telefone, mensagem, conversa)
            
            # Conversa geral
            print(f"[DEBUG] Direcionando para conversa GERAL")
            return self.processar_conversa_geral(telefone, mensagem)
                
        except Exception as e:
            print(f"[DEBUG] ERRO no processamento: {str(e)}")
            import traceback
            traceback.print_exc()
            return "Ops, tive um problema técnico. Pode tentar novamente?"

    def processar_conversa_geral(self, telefone: str, mensagem: str) -> str:
        """Processa conversa geral detectando intenções"""
        try:
            print(f"[DEBUG] === CONVERSA GERAL ===")
            cliente = db.buscar_cliente_por_telefone(telefone)
            mensagem_lower = mensagem.lower().strip()
            
            print(f"[DEBUG] Mensagem processada: '{mensagem_lower}'")
            
            # Detectar intenção de compra
            if any(palavra in mensagem_lower for palavra in ['comprar', 'quero lista', 'quero iptv', 'adquirir']):
                print(f"[DEBUG] INTENÇÃO COMPRAR detectada!")
                print(f"[DEBUG] Salvando estado: contexto='comprar', estado='aguardando_usuario'")
                
                # Salvar estado de compra
                db.salvar_conversa(telefone, 'comprar', 'aguardando_usuario', json.dumps({}))
                
                # Verificar se foi salvo corretamente
                conversa_salva = db.get_conversa(telefone)
                print(f"[DEBUG] Verificação pós-salvamento:")
                print(f"[DEBUG]   - Contexto salvo: '{conversa_salva.get('contexto') if conversa_salva else 'ERRO'}'")
                print(f"[DEBUG]   - Estado salvo: '{conversa_salva.get('estado') if conversa_salva else 'ERRO'}'")
                
                return "Vou te ajudar a criar sua lista IPTV. Qual nome de usuário você gostaria?"
            
            # Outras intenções...
            return "Olá! Trabalho com listas IPTV. Digite 'comprar' para nova lista, 'renovar' para estender ou 'consultar' para ver seus dados."
                
        except Exception as e:
            print(f"[DEBUG] ERRO na conversa geral: {str(e)}")
            import traceback
            traceback.print_exc()
            return "Desculpe, houve um erro. Pode tentar novamente?"

    def processar_fluxo_compra(self, telefone: str, mensagem: str, conversa: Dict) -> str:
        """Processa o fluxo de compra passo a passo"""
        print(f"[DEBUG] === FLUXO DE COMPRA ===")
        
        estado_atual = conversa.get('estado', 'indefinido')
        dados_temp = conversa.get('dados_temporarios', '{}')
        
        print(f"[DEBUG] Estado atual: '{estado_atual}'")
        print(f"[DEBUG] Dados temporários raw: '{dados_temp}'")
        
        try:
            dados_temp = json.loads(dados_temp) if dados_temp else {}
        except json.JSONDecodeError:
            print(f"[DEBUG] ERRO ao decodificar JSON dos dados temporários")
            dados_temp = {}
        
        print(f"[DEBUG] Dados temporários parsed: {dados_temp}")

        # Processar baseado no estado
        if estado_atual == 'aguardando_usuario':
            print(f"[DEBUG] Processando USUÁRIO...")
            return self.processar_usuario(telefone, mensagem, dados_temp)

        elif estado_atual == 'aguardando_conexoes':
            print(f"[DEBUG] Processando CONEXÕES...")
            return self.processar_conexoes(telefone, mensagem, dados_temp)

        elif estado_atual == 'aguardando_duracao':
            print(f"[DEBUG] Processando DURAÇÃO...")
            return self.processar_duracao(telefone, mensagem, dados_temp)

        elif estado_atual == 'confirmando_dados':
            print(f"[DEBUG] Processando CONFIRMAÇÃO...")
            return self.processar_confirmacao(telefone, mensagem, dados_temp)

        else:
            print(f"[DEBUG] Estado desconhecido: '{estado_atual}' - RESETANDO")
            db.salvar_conversa(telefone, 'inicial', 'inicial', json.dumps({}))
            return "Algo deu errado. Vamos começar de novo. Digite 'comprar' para nova lista."

    def processar_usuario(self, telefone: str, mensagem: str, dados_temp: Dict) -> str:
        """Processa o nome de usuário"""
        print(f"[DEBUG] === PROCESSAR USUÁRIO ===")
        print(f"[DEBUG] Mensagem recebida: '{mensagem}'")
        
        usuario = mensagem.strip().replace(' ', '').lower()
        print(f"[DEBUG] Usuário processado: '{usuario}'")
        
        # Validações
        if not usuario or len(usuario) < 3:
            print(f"[DEBUG] Usuário muito curto")
            return "Nome muito curto. Use pelo menos 3 caracteres."
        
        if not re.match(r'^[a-zA-Z0-9_]+$', usuario):
            print(f"[DEBUG] Usuário com caracteres inválidos")
            return "Use apenas letras, números e underscore. Tente outro nome."

        # Salvar usuário e avançar
        dados_temp['usuario'] = usuario
        print(f"[DEBUG] Dados após adicionar usuário: {dados_temp}")
        
        print(f"[DEBUG] Salvando estado: contexto='comprar', estado='aguardando_conexoes'")
        db.salvar_conversa(telefone, 'comprar', 'aguardando_conexoes', json.dumps(dados_temp))
        
        # Verificar se foi salvo
        conversa_nova = db.get_conversa(telefone)
        print(f"[DEBUG] Verificação pós-salvamento usuário:")
        if conversa_nova:
            print(f"[DEBUG]   - Novo contexto: '{conversa_nova.get('contexto')}'")
            print(f"[DEBUG]   - Novo estado: '{conversa_nova.get('estado')}'")
            print(f"[DEBUG]   - Novos dados: '{conversa_nova.get('dados_temporarios')}'")
        else:
            print(f"[DEBUG]   - ERRO: Conversa não encontrada após salvamento!")
        
        return f"Usuário '{usuario}' confirmado. Quantas conexões você precisa? (1 a 10)"

    def processar_conexoes(self, telefone: str, mensagem: str, dados_temp: Dict) -> str:
        """Processa número de conexões"""
        print(f"[DEBUG] === PROCESSAR CONEXÕES ===")
        try:
            conexoes = int(mensagem.strip())
            print(f"[DEBUG] Conexões convertidas: {conexoes}")
            
            if not (1 <= conexoes <= 10):
                return "Digite um número entre 1 e 10."
            
            dados_temp['conexoes'] = conexoes
            db.salvar_conversa(telefone, 'comprar', 'aguardando_duracao', json.dumps(dados_temp))
            
            return f"{conexoes} conexões confirmadas. Por quantos meses? (1 a 12)"
            
        except ValueError:
            print(f"[DEBUG] Erro ao converter '{mensagem}' para número")
            return "Digite apenas o número de conexões (exemplo: 2)"

    def processar_duracao(self, telefone: str, mensagem: str, dados_temp: Dict) -> str:
        """Processa duração"""
        print(f"[DEBUG] === PROCESSAR DURAÇÃO ===")
        try:
            meses = int(mensagem.strip())
            
            if not (1 <= meses <= 12):
                return "Digite um número entre 1 e 12 meses."
            
            dados_temp['meses'] = meses
            db.salvar_conversa(telefone, 'comprar', 'confirmando_dados', json.dumps(dados_temp))
            
            return f"RESUMO:\nUsuário: {dados_temp['usuario']}\nConexões: {dados_temp['conexoes']}\nDuração: {meses} meses\n\nDigite 'sim' para confirmar."
            
        except ValueError:
            return "Digite apenas o número de meses (exemplo: 3)"

    def processar_confirmacao(self, telefone: str, mensagem: str, dados_temp: Dict) -> str:
        """Processa confirmação"""
        resposta = mensagem.strip().lower()
        
        if resposta in ['sim', 's', 'confirmar', 'ok']:
            return "PIX seria gerado aqui! (Teste concluído com sucesso)"
        elif resposta in ['não', 'nao', 'n', 'cancelar']:
            db.salvar_conversa(telefone, 'inicial', 'inicial', json.dumps({}))
            return "Compra cancelada."
        else:
            return "Digite 'sim' para confirmar ou 'não' para cancelar."

    def processar_fluxo_renovacao(self, telefone: str, mensagem: str, conversa: Dict) -> str:
        """Placeholder para renovação"""
        return "Fluxo de renovação em desenvolvimento."

    def resposta_geral(self, mensagem: str, contexto: Optional[str] = None) -> str:
        """Método para compatibilidade"""
        return "Olá! Sou especialista em IPTV. Como posso ajudar?"

# Instância única do bot
gemini_bot = GeminiBot()