# gemini_bot.py - Versão Melhorada com processo de renovação completo
import json
import re
import traceback
from typing import Dict, Optional
from datetime import datetime
from bitpanel_automation import BitPanelManager
from config import Config
from database import db

SUPORTE_MSG = "⚠️ Tivemos um problema técnico. Por favor, entre em contato com o suporte no número 11 96751-2034."


class GeminiBot:
    def __init__(self):
        pass

    def processar_mensagem(self, telefone: str, mensagem: str) -> Optional[str]:
        """
        Ponto de entrada principal para processar mensagens de um usuário.
        """
        try:
            print(f"[DEBUG] Processando: {telefone} | \'{mensagem}\'")
            mensagem = mensagem.strip()
            
            # COMANDO UNIVERSAL DE CANCELAMENTO
            if self.is_comando_cancelar(mensagem):
                db.set_conversa(telefone, "inicial", "inicial", json.dumps({}))
                self.limpar_dados_temporarios(telefone)
                return "❌ Atendimento cancelado. Se precisar de algo, é só chamar! 👋"
            
            conversa = db.get_conversa(telefone)
            cliente = db.buscar_cliente_por_telefone(telefone)

            if not cliente:
                db.criar_cliente(telefone=telefone)
                print(f"[INFO] Novo cliente criado no banco: {telefone}")

            # LÓGICA DE CONTEXTO MELHORADA
            if conversa:
                contexto = conversa.get("contexto")
                estado = conversa.get("estado")

                if contexto == "comprar":
                    return self.processar_fluxo_compra(telefone, mensagem, conversa)
                elif contexto == "renovar":
                    return self.processar_fluxo_renovacao(telefone, mensagem, conversa)
                elif contexto == "inicial" and estado == "menu_erro":
                    return self.processar_menu_erro(telefone, mensagem)

            return self.processar_conversa_geral(telefone, mensagem, cliente)

        except Exception as e:
            print(f"[CRITICAL] Erro fatal no processamento da mensagem: {e}")
            traceback.print_exc()
            return self.menu_erro("Ops, tive um problema técnico.", telefone)

    def is_comando_cancelar(self, mensagem: str) -> bool:
        """
        Verifica se a mensagem é um comando de cancelamento
        """
        comandos_cancelar = [
            "cancelar",
            "sair",
            "parar",
            "finalizar",
            "quit",
            "exit",
            "cancel",
            "voltar",
            "tchau",
            "bye",
            "stop",
        ]
        msg_lower = mensagem.lower().strip()
        return any(cmd in msg_lower for cmd in comandos_cancelar)

    def limpar_dados_temporarios(self, telefone: str):
        """
        Limpa dados temporários do cliente se ele não finalizou a compra
        """
        try:
            # Não salvar cliente no banco se não finalizou processo
            conn = db.get_connection()
            try:
                # Verifica se existe um cliente que foi criado mas não tem lista criada
                cliente_temp = conn.execute(
                    """
                    SELECT id FROM clientes 
                    WHERE telefone = ? AND usuario_iptv IS NOT NULL 
                    AND created_at > datetime(\'now\', \'-1 hour\')
                """,
                    (telefone,),
                ).fetchone()

                if cliente_temp:
                    # Remove cliente temporário que não finalizou processo
                    conn.execute(
                        "DELETE FROM clientes WHERE id = ?", (cliente_temp["id"],)
                    )
                    conn.commit()
                    print(f"[INFO] Cliente temporário removido: {telefone}")
            finally:
                conn.close()
        except Exception as e:
            print(f"[ERROR] Erro ao limpar dados temporários: {e}")

    def processar_conversa_geral(
        self, telefone: str, mensagem: str, cliente: Optional[Dict]
    ) -> str:
        """
        Lida com a conversa inicial com sistema numérico.
        """
        msg_lower = mensagem.lower().strip()

        # COMANDOS NUMÉRICOS PRINCIPAIS
        if mensagem.strip() == "1":
            return self.iniciar_compra(telefone)
        elif mensagem.strip() == "2":
            return self.iniciar_renovacao(telefone)
        elif mensagem.strip() == "3":
            return self.consultar_dados(telefone)

        # DETECÇÃO INTELIGENTE DE INTENÇÕES
        intencao = self.detectar_intencao(mensagem)

        if intencao == "comprar":
            return self.iniciar_compra(telefone)
        elif intencao == "renovar":
            return self.iniciar_renovacao(telefone)
        elif intencao == "consultar":
            return self.consultar_dados(telefone)
        elif intencao == "saudacao":
            return self.resposta_saudacao()
        elif intencao == "ajuda":
            return self.menu_principal()
        else:
            # Mensagem não compreendida
            return self.menu_erro("Não entendi sua mensagem.", telefone)

    def detectar_intencao(self, mensagem: str) -> str:
        """
        IA mais robusta para detectar intenções do usuário.
        """
        msg_lower = mensagem.lower().strip()

        # Palavras-chave para cada intenção
        palavras_comprar = [
            "comprar",
            "quero lista",
            "adquirir",
            "assinar",
            "criar lista",
            "nova lista",
            "fazer lista",
            "contratar",
            "pagar",
        ]

        palavras_renovar = [
            "renovar",
            "renovacao",
            "estender",
            "prolongar",
            "continuar",
            "mais tempo",
            "adicionar tempo",
            "prorrogar",
        ]

        palavras_consultar = [
            "consultar",
            "meus dados",
            "minha lista",
            "minhas listas",
            "ver dados",
            "informações",
            "status",
            "verificar",
        ]

        palavras_saudacao = [
            "oi",
            "olá",
            "ola",
            "hey",
            "hello",
            "bom dia",
            "boa tarde",
            "boa noite",
        ]

        palavras_ajuda = [
            "ajuda",
            "help",
            "socorro",
            "não sei",
            "como",
            "menu",
            "opções",
        ]

        # Verificação por palavras-chave
        if any(palavra in msg_lower for palavra in palavras_comprar):
            return "comprar"
        elif any(palavra in msg_lower for palavra in palavras_renovar):
            return "renovar"
        elif any(palavra in msg_lower for palavra in palavras_consultar):
            return "consultar"
        elif any(palavra in msg_lower for palavra in palavras_saudacao):
            return "saudacao"
        elif any(palavra in msg_lower for palavra in palavras_ajuda):
            return "ajuda"
        else:
            return "desconhecido"

    def menu_principal(self) -> str:
        """
        Exibe o menu principal numerado
        """
        return """🤖 **Olá! Sou seu assistente IPTV!**\n\n**O que você gostaria de fazer?**\n\n**1️⃣** - Criar nova lista IPTV\n**2️⃣** - Renovar lista existente  \n**3️⃣** - Consultar meus dados\n\n*Digite apenas o número da opção desejada*\n\n💬 Ou me diga com suas palavras o que precisa!"""

    def resposta_saudacao(self) -> str:
        """
        Resposta personalizada para saudações
        """
        return """👋 **Olá! Tudo bem?** Sou **Alex**, seu assistente de vendas IPTV. \n\n📺 **Oferta Especial:**\n• Canais **Full HD, HD, SD** e **H.265**\n• **VOD**, conteúdos **Adulto** e **LGBT** • **Até 10 conexões simultâneas**\n\n💰 **Apenas R$ 30,00/mês** - Planos de 1 a 12 meses\n\n**Como posso ajudá-lo hoje?**\n\n**1️⃣** - Criar nova lista IPTV\n**2️⃣** - Renovar lista existente  \n**3️⃣** - Consultar meus dados"""

    def menu_erro(self, mensagem_erro: str, telefone: str) -> str:
        """
        Menu de opções quando há erro ou mensagem não compreendida
        """
        db.set_conversa(telefone, "inicial", "menu_erro", json.dumps({}))

        return f"""❓ {mensagem_erro}\n\n**Precisa de ajuda?**\n\n**1️⃣** - Voltar ao menu principal\n**2️⃣** - Falar com suporte humano\n\n*Digite 1 ou 2 para continuar*"""

    def processar_menu_erro(self, telefone: str, mensagem: str) -> str:
        """
        Processa as opções do menu de erro
        """
        if mensagem.strip() == "1":
            db.set_conversa(telefone, "inicial", "inicial", json.dumps({}))
            return self.menu_principal()
        elif mensagem.strip() == "2":
            db.set_conversa(telefone, "inicial", "inicial", json.dumps({}))
            return f"""📞 **Suporte Humano**\n\nEntre em contato com nosso suporte:\n**WhatsApp:** 11 96751-2034\n\nNossa equipe está pronta para ajudá-lo! 😊"""
        else:
            return """❓ Opção inválida.\n\n**1️⃣** - Voltar ao menu principal\n**2️⃣** - Falar com suporte humano"""

    def iniciar_compra(self, telefone: str) -> str:
        """
        Inicia o fluxo de compra
        """
        db.set_conversa(telefone, "comprar", "aguardando_usuario", json.dumps({}))
        return """🛒 **CRIAÇÃO DE NOVA LISTA**\n\nVamos criar sua lista IPTV personalizada!\n\n**Passo 1/4:** Escolha um nome de usuário\n*Use apenas letras e números (4 a 12 caracteres)*\n\nExemplo: `joao123` ou `maria2024`\n\n💡 *Digite "cancelar" a qualquer momento para sair*"""

    def iniciar_renovacao(self, telefone: str) -> str:
        """
        Inicia o fluxo de renovação
        """
        conn = db.get_connection()
        try:
            listas = conn.execute(
                """
                SELECT usuario_iptv, data_expiracao 
                FROM clientes 
                WHERE telefone = ? AND usuario_iptv IS NOT NULL
                ORDER BY created_at DESC
            """,
                (telefone,),
            ).fetchall()
        finally:
            conn.close()

        if not listas:
            return """❌ **Nenhuma lista encontrada**\n\nVocê não possui listas para renovar.\n\n**1️⃣** - Criar nova lista\n**2️⃣** - Voltar ao menu principal"""

        if len(listas) == 1:
            lista = listas[0]
            db.set_conversa(
                telefone,
                "renovar",
                "aguardando_meses",
                json.dumps({"usuario_selecionado": lista["usuario_iptv"]}),
            )
            return f"""🔄 **RENOVAÇÃO DE LISTA**\n\nLista selecionada: **{lista['usuario_iptv']}**\n\n**Passo 1/3:** Por quantos meses deseja renovar?\n*Digite um número de 1 a 12*\n\nExemplo: `3` para 3 meses\n\n💡 *Digite "cancelar" para sair*"""
        else:
            opcoes = []
            listas_nomes = []
            for i, lista in enumerate(listas, 1):
                opcoes.append(f"**{i}️⃣** - {lista['usuario_iptv']}")
                listas_nomes.append(lista["usuario_iptv"])

            db.set_conversa(
                telefone,
                "renovar",
                "escolhendo_lista",
                json.dumps({"listas_disponiveis": listas_nomes}),
            )

            return (
                f"""🔄 **RENOVAÇÃO - ESCOLHA A LISTA**\n\nVocê possui {len(listas)} listas:\n\n"""
                + "\n".join(opcoes)
                + """\n\n*Digite o número da lista que deseja renovar*"""
            )

    def consultar_dados(self, telefone: str) -> str:
        """
        Consulta e exibe dados do cliente, incluindo senha, data de criação e plano.
        """
        conn = db.get_connection()
        try:
            listas = conn.execute(
                """
                SELECT usuario_iptv, senha_iptv, data_criacao, data_expiracao, conexoes, plano, status
                FROM clientes 
                WHERE telefone = ? AND usuario_iptv IS NOT NULL
                ORDER BY created_at DESC
            """,
                (telefone,),
            ).fetchall()
        finally:
            conn.close()

        if not listas:
            return """❌ **Nenhuma lista encontrada**\n\nVocê ainda não possui listas IPTV.\n\n**1️⃣** - Criar nova lista\n**2️⃣** - Voltar ao menu principal"""

        resposta = "📋 **SUAS LISTAS IPTV - INFORMAÇÕES COMPLETAS:**\n\n"

        for i, lista in enumerate(listas, 1):
            try:
                # Formatação de datas
                data_criacao_str = "N/A"
                if lista["data_criacao"]:
                    data_criacao_str = datetime.fromisoformat(lista["data_criacao"]).strftime("%d/%m/%Y")
                
                expira_str = "N/A"
                status_lista = "N/A"
                if lista["data_expiracao"]:
                    expira_dt = datetime.fromisoformat(lista["data_expiracao"])
                    expira_str = expira_dt.strftime("%d/%m/%Y")
                    status_lista = (
                        "✅ ATIVA"
                        if expira_dt > datetime.now()
                        else "❌ EXPIRADA"
                    )
                
                # Senha e Plano
                senha = lista["senha_iptv"] or "Não informada"
                plano = lista["plano"] or "Básico"

                resposta += f"""*\n*{i}. {lista['usuario_iptv']}*\n🔐 *Senha:* {senha}\n📺 *Conexões:* {lista['conexoes'] or 1}\n📅 *Status:* {status_lista}\n📅 *Criada em:* {data_criacao_str}\n⏰ *Expira em:* {expira_str}\n📋 *Plano:* {plano}\n\n"""
            except Exception as e:
                print(f"[ERROR] Erro ao formatar dados da lista {lista.get('usuario_iptv', 'N/A')}: {e}")
                resposta += f"""\n*{i}. {lista['usuario_iptv']}*\n📺 *Conexões:* {lista.get('conexoes', 1)}\n📊 *Status:* Erro ao carregar detalhes\n\n"""

        resposta += """**Precisa de mais alguma coisa?**\n\n**1️⃣** - Renovar uma lista\n**2️⃣** - Criar nova lista\n**3️⃣** - Voltar ao menu"""

        return resposta

    def processar_fluxo_compra(
        self, telefone: str, mensagem: str, conversa: Dict
    ) -> Optional[str]:
        """
        Gerencia a máquina de estados do fluxo de compra melhorada.
        """
        estado = conversa.get("estado", "indefinido")
        dados = json.loads(conversa.get("dados_temporarios", "{}"))

        if estado == "aguardando_usuario":
            usuario = mensagem.strip().replace(" ", "").lower()
            if not re.match(r"^[a-z0-9]{4,12}$", usuario):
                return """❌ **Nome de usuário inválido**\n\nUse apenas letras e números (4 a 12 caracteres)\nExemplo: `joao123` ou `maria2024`\n\nTente novamente:"""

            # Verificar se já existe
            conn = db.get_connection()
            try:
                existe = conn.execute(
                    "SELECT id FROM clientes WHERE usuario_iptv = ?", (usuario,)
                ).fetchone()
            finally:
                conn.close()

            if existe:
                return f"""❌ **Usuário já existe**\n\nO usuário `{usuario}` já está em uso.\nEscolha outro nome:"""

            dados["usuario"] = usuario
            db.set_conversa(
                telefone, "comprar", "aguardando_conexoes", json.dumps(dados)
            )

            return f"""✅ **Usuário definido:** `{usuario}`\n\n**Passo 2/4:** Quantas conexões (telas) simultâneas?\n*Digite um número de 1 a 10*\n\n💡 **Dica:** • 1 conexão = 1 TV/celular\n• 2 conexões = 2 dispositivos simultâneos\n• E assim por diante...\n\nExemplo: `2` para 2 conexões"""

        elif estado == "aguardando_conexoes":
            try:
                conexoes = int(mensagem.strip())
                if not 1 <= conexoes <= 10:
                    return """❌ **Número inválido**\n\nDigite um número de 1 a 10 conexões:"""

                dados["conexoes"] = conexoes
                db.set_conversa(
                    telefone, "comprar", "aguardando_duracao", json.dumps(dados)
                )

                return f"""✅ **Conexões definidas:** {conexoes}\n\n**Passo 3/4:** Por quantos meses deseja assinar?\n*Digite um número de 1 a 12*\n\n💰 **Valores:**\n• 1 mês = R$ 30,00\n• 3 meses = R$ 90,00\n• 6 meses = R$ 180,00\n• 12 meses = R$ 360,00\n\nExemplo: `3` para 3 meses"""
            except ValueError:
                return """❌ **Digite apenas números**\n\nQuantas conexões você precisa? (1 a 10)"""

        elif estado == "aguardando_duracao":
            try:
                from mercpag import mercado_pago

                meses = int(mensagem.strip())
                if not 1 <= meses <= 12:
                    return """❌ **Número inválido**\n\nDigite um número de 1 a 12 meses:"""

                dados["meses"] = meses
                preco = mercado_pago.calcular_preco(dados["conexoes"], meses)
                dados["preco"] = preco

                db.set_conversa(
                    telefone, "comprar", "confirmando_dados", json.dumps(dados)
                )

                return f"""📋 **RESUMO DO PEDIDO**\n\n👤 **Usuário:** `{dados['usuario']}`\n📺 **Conexões:** {dados['conexoes']}\n📅 **Duração:** {meses} mês{'es' if meses > 1 else ''}\n💰 **Valor Total:** R$ {preco:.2f}\n\n**Confirma os dados?**\n**1️⃣** - Sim, gerar PIX\n**2️⃣** - Não, cancelar pedido"""
            except ValueError:
                return """❌ **Digite apenas números**\n\nPor quantos meses? (1 a 12)"""

        elif estado == "confirmando_dados":
            if mensagem.strip() == "1" or mensagem.lower().strip() in [
                "sim",
                "confirmar",
                "ok",
            ]:
                return self.gerar_pix_compra(telefone, dados)
            elif mensagem.strip() == "2" or mensagem.lower().strip() in [
                "não",
                "nao",
                "cancelar",
            ]:
                db.set_conversa(telefone, "inicial", "inicial", json.dumps({}))
                self.limpar_dados_temporarios(telefone)
                return (
                    """❌ **Pedido cancelado**\n\nSe mudar de ideia, é só chamar! \n\n"""
                    + self.menu_principal()
                )
            else:
                return """❓ **Resposta inválida**\n\n**1️⃣** - Sim, gerar PIX\n**2️⃣** - Não, cancelar pedido"""

        return "Erro no fluxo de compra."

    def gerar_pix_compra(self, telefone: str, dados_compra: Dict) -> Optional[str]:
        """
        Gera PIX para compra
        """
        try:
            from mercpag import mercado_pago
            from whatsapp_bot import whatsapp_bot

            cliente = db.buscar_cliente_por_telefone(telefone)
            if not cliente:
                cliente_id = db.criar_cliente(telefone)
                cliente = {"id": cliente_id}

            # MODO DE TESTE - Simular pagamento aprovado
            if Config.TEST_MODE:
                print(
                    "\n--- MODO DE TESTE ATIVADO: Simulando pagamento de COMPRA aprovado ---\n"
                )
                # Em modo de teste, processa o pagamento diretamente sem gerar PIX
                self.processar_pagamento_aprovado(telefone, dados_compra)
                return None  # Retorna None porque a resposta é enviada diretamente pela função de processamento

            # --- MODO REAL ---
            pix_info = mercado_pago.criar_cobranca_pix(
                telefone,
                dados_compra["usuario"],
                dados_compra["conexoes"],
                dados_compra["meses"],
            )

            if not pix_info:
                db.set_conversa(telefone, "inicial", "inicial", json.dumps({}))
                return self.menu_erro(
                    "Não consegui gerar o PIX. Tente novamente.", telefone
                )

            dados_compra["payment_id"] = pix_info["payment_id"]
            db.set_conversa(
                telefone, "comprar", "aguardando_pagamento", json.dumps(dados_compra)
            )

            db.criar_pagamento(
                cliente["id"],
                pix_info["valor"],
                str(pix_info["payment_id"]),
                pix_info["copia_cola"],
            )

            # Enviar PIX via WhatsApp
            whatsapp_bot.enviar_mensagem(
                telefone,
                f"""✅ **PIX GERADO!** 💰 **Valor:** R$ {pix_info['valor']:.2f}\n\n📱 Use o QR Code ou copie o código abaixo:""",
            )

            if pix_info.get("qr_code_base64"):
                whatsapp_bot.enviar_imagem_base64(telefone, pix_info["qr_code_base64"])

            whatsapp_bot.enviar_mensagem(telefone, f"`{pix_info['copia_cola']}`")

            whatsapp_bot.enviar_mensagem(
                telefone,
                """⏳ **Aguardando pagamento...**\n\nAssim que o PIX for aprovado, sua lista será criada automaticamente! ✅\n\n⚡ O processo é instantâneo após a confirmação.""",
            )

            return None

        except Exception as e:
            print(f"[ERROR] Erro ao gerar PIX: {e}")
            db.set_conversa(telefone, "inicial", "inicial", json.dumps({}))
            return self.menu_erro("Erro ao gerar PIX. Tente novamente.", telefone)

    def processar_fluxo_renovacao(
        self, telefone: str, mensagem: str, conversa: Dict
    ) -> Optional[str]:
        """
        Processa renovação com suporte a múltiplas listas e TEST_MODE
        """
        estado = conversa.get("estado", "inicio")
        dados = json.loads(conversa.get("dados_temporarios", "{}"))

        if estado == "escolhendo_lista":
            try:
                escolha = int(mensagem.strip()) - 1
                listas_disponiveis = dados.get("listas_disponiveis", [])

                if 0 <= escolha < len(listas_disponiveis):
                    usuario_selecionado = listas_disponiveis[escolha]
                    dados["usuario_selecionado"] = usuario_selecionado
                    db.set_conversa(
                        telefone, "renovar", "aguardando_meses", json.dumps(dados)
                    )

                    return f"""✅ **Lista selecionada:** `{usuario_selecionado}`\n\n**Por quantos meses deseja renovar?**\n*Digite um número de 1 a 12*\n\n💰 **Valores:**\n• 1 mês = R$ 30,00\n• 3 meses = R$ 90,00  \n• 6 meses = R$ 180,00\n• 12 meses = R$ 360,00"""
                else:
                    return """❌ **Número inválido**\n\nDigite o número da lista que deseja renovar:"""
            except ValueError:
                return """❌ **Digite apenas números**\n\nQual lista deseja renovar?"""

        elif estado == "aguardando_meses":
            try:
                meses = int(mensagem.strip())
                if not 1 <= meses <= 12:
                    return """❌ **Número inválido**\n\nDigite um número de 1 a 12 meses:"""

                from mercpag import mercado_pago

                # Buscar dados da lista
                conn = db.get_connection()
                try:
                    lista = conn.execute(
                        """
                        SELECT conexoes FROM clientes 
                        WHERE telefone = ? AND usuario_iptv = ?
                    """,
                        (telefone, dados["usuario_selecionado"]),
                    ).fetchone()
                finally:
                    conn.close()

                conexoes = lista["conexoes"] if lista else 1
                preco_total = mercado_pago.calcular_preco(conexoes, meses)

                # Adicionar dados ao dicionário para uso posterior
                dados["meses"] = meses
                dados["preco"] = preco_total
                dados["conexoes"] = conexoes

                db.set_conversa(
                    telefone, "renovar", "confirmando_renovacao", json.dumps(dados)
                )

                return f"""📋 **RESUMO DA RENOVAÇÃO**\n\n👤 **Lista:** `{dados['usuario_selecionado']}`\n📺 **Conexões:** {conexoes}\n📅 **Adicionar:** {meses} mês{'es' if meses > 1 else ''}\n💰 **Valor Total:** R$ {preco_total:.2f}\n\n**Confirma a renovação?**\n**1️⃣** - Sim, gerar PIX\n**2️⃣** - Não, cancelar"""

            except ValueError:
                return """❌ **Digite apenas números**\n\nPor quantos meses? (1 a 12)"""

        elif estado == "confirmando_renovacao":
            if mensagem.strip() == "1" or mensagem.lower().strip() in [
                "sim",
                "confirmar",
                "ok",
            ]:
                return self.gerar_pix_renovacao(telefone, dados)
            elif mensagem.strip() == "2" or mensagem.lower().strip() in [
                "não",
                "nao",
                "cancelar",
            ]:
                db.set_conversa(telefone, "inicial", "inicial", json.dumps({}))
                return (
                    """❌ **Renovação cancelada**\n\nSe mudar de ideia, é só chamar! \n\n"""
                    + self.menu_principal()
                )
            else:
                return """❓ **Resposta inválida**\n\n**1️⃣** - Sim, gerar PIX\n**2️⃣** - Não, cancelar"""

        return "Erro no fluxo de renovação."

    def gerar_pix_renovacao(self, telefone: str, dados_renovacao: Dict) -> Optional[str]:
        """
        Gera PIX para renovação
        """
        try:
            from mercpag import mercado_pago
            from whatsapp_bot import whatsapp_bot

            cliente = db.buscar_cliente_por_telefone(telefone)
            if not cliente:
                return self.menu_erro("Cliente não encontrado.", telefone)

            # MODO DE TESTE - Simular pagamento aprovado
            if Config.TEST_MODE:
                print(
                    "\n--- MODO DE TESTE ATIVADO: Simulando pagamento de RENOVAÇÃO aprovado ---\n"
                )
                # Em modo de teste, processa o pagamento diretamente sem gerar PIX
                self.processar_pagamento_renovacao(telefone, dados_renovacao)
                return None  # Retorna None porque a resposta é enviada diretamente pela função de processamento

            # --- MODO REAL ---
            pix_info = mercado_pago.criar_cobranca_pix(
                telefone,
                dados_renovacao["usuario_selecionado"],
                dados_renovacao["conexoes"],
                dados_renovacao["meses"],
            )

            if not pix_info:
                db.set_conversa(telefone, "inicial", "inicial", json.dumps({}))
                return self.menu_erro(
                    "Não consegui gerar o PIX. Tente novamente.", telefone
                )

            dados_renovacao["payment_id"] = pix_info["payment_id"]
            db.set_conversa(
                telefone, "renovar", "aguardando_pagamento", json.dumps(dados_renovacao)
            )

            # Salvar pagamento no banco com contexto de renovação
            db.criar_pagamento(
                cliente["id"],
                pix_info["valor"],
                str(pix_info["payment_id"]),
                pix_info["copia_cola"],
                contexto="renovar",
                dados_temporarios=json.dumps(dados_renovacao)
            )

            # Enviar PIX via WhatsApp
            whatsapp_bot.enviar_mensagem(
                telefone,
                f"""✅ **RENOVAÇÃO - PIX GERADO!**\n\n📺 **Lista:** `{dados_renovacao['usuario_selecionado']}`\n📅 **Adicionar:** {dados_renovacao['meses']} mês{'es' if dados_renovacao['meses'] > 1 else ''}\n💰 **Valor:** R$ {pix_info['valor']:.2f}\n\n📱 Use o QR Code ou copie o código abaixo:""",
            )

            if pix_info.get("qr_code_base64"):
                whatsapp_bot.enviar_imagem_base64(telefone, pix_info["qr_code_base64"])

            whatsapp_bot.enviar_mensagem(telefone, f"`{pix_info['copia_cola']}`")

            whatsapp_bot.enviar_mensagem(
                telefone,
                """⏳ **Aguardando pagamento...**\n\nAssim que o PIX for aprovado, sua lista será renovada automaticamente! ✅\n\n⚡ O processo é instantâneo após a confirmação.""",
            )

            return None

        except Exception as e:
            print(f"[ERROR] Erro ao gerar PIX de renovação: {e}")
            db.set_conversa(telefone, "inicial", "inicial", json.dumps({}))
            return self.menu_erro("Erro ao gerar PIX. Tente novamente.", telefone)

    def processar_pagamento_aprovado(self, telefone: str, dados_compra: Dict):
        """
        Executa a automação de CRIAÇÃO no BitPanel.\n        Esta função é chamada tanto em modo de teste quanto em modo real.\n        """
        from whatsapp_bot import whatsapp_bot
        manager = None
        try:
            whatsapp_bot.enviar_mensagem(
                telefone,
                "✅ **Pagamento confirmado!** Estou criando sua lista agora, isso pode levar um ou dois minutos..."
            )

            # --- AÇÃO REAL NO BITPANEL ---
            manager = BitPanelManager()
            dados_lista = manager.criar_lista(
                username=dados_compra["usuario"],
                conexoes=dados_compra["conexoes"],
                duracao_meses=dados_compra["meses"],
                headless=True
            )
            # -----------------------------

            if dados_lista and "senha" in dados_lista:
                from datetime import datetime, timedelta
                data_criacao_final = datetime.now()
                data_expiracao_final = data_criacao_final + timedelta(days=30 * dados_compra["meses"])

                db.atualizar_cliente_pos_compra(
                    telefone=telefone,
                    usuario_iptv=dados_compra["usuario"],
                    senha_iptv=dados_lista["senha"],
                    conexoes=dados_compra["conexoes"],
                    data_criacao=data_criacao_final,
                    data_expiracao=data_expiracao_final,
                    plano=dados_lista.get("plano", Config.PLANO_DEFAULT)
                )

                link = db.get_config("link_acesso", Config.LINK_ACESSO_DEFAULT)
                data_expiracao_br = data_expiracao_final.strftime("%d/%m/%Y")

                resposta = f"""🎉 **LISTA CRIADA COM SUCESSO!**\n\n**📺 SEUS DADOS DE ACESSO:**\n\n🔗 **Link:** `{link}`\n👤 **Usuário:** `{dados_compra['usuario']}`\n🔐 **Senha:** `{dados_lista['senha']}`\n📱 **Conexões:** {dados_compra['conexoes']}\n⏰ **Expira em:** {data_expiracao_br}\n\n💾 **Guarde esses dados com segurança!**"""
                whatsapp_bot.enviar_mensagem(telefone, resposta)
            else:
                whatsapp_bot.enviar_mensagem(telefone, SUPORTE_MSG)
                db.log_sistema("erro", f"Falha ao criar lista para '{dados_compra['usuario']}' no BitPanel.")

        except Exception as e:
            print(f"[CRITICAL] Erro na automação de criação: {e}")
            traceback.print_exc()
            whatsapp_bot.enviar_mensagem(telefone, SUPORTE_MSG)
        finally:
            if manager:
                manager.close()

    def processar_pagamento_renovacao(self, telefone: str, dados_renovacao: Dict):
        """
        Executa a automação de RENOVAÇÃO no BitPanel e captura as informações atualizadas.\n        CORRIGIDO: Agora funciona como o processo de criação.\n        """
        from whatsapp_bot import whatsapp_bot
        manager = None
        try:
            usuario = dados_renovacao['usuario_selecionado']
            meses = dados_renovacao['meses']

            whatsapp_bot.enviar_mensagem(
                telefone,
                f"✅ **Pagamento confirmado!** Estou renovando sua lista `{usuario}` no painel. Isso pode levar um minuto..."
            )

            # --- AÇÃO REAL NO BITPANEL ---
            manager = BitPanelManager()
            dados_lista_renovada = manager.renovar_lista(
                username=usuario, 
                duracao_meses=meses, 
                headless=True
            )
            # -----------------------------

            if dados_lista_renovada and not dados_lista_renovada.get("erro"):
                print(f"[INFO] Renovação de \'{usuario}\' no BitPanel bem-sucedida. Dados capturados: {dados_lista_renovada}")

                # Atualizar banco de dados com as informações capturadas
                from datetime import datetime
                
                # Extrair informações dos dados capturados
                nova_data_expiracao = None
                if dados_lista_renovada.get("expira_em"):
                    try:
                        # Converter data de expiração do formato do BitPanel
                        nova_data_expiracao = self._converter_data_bitpanel(dados_lista_renovada["expira_em"])
                    except Exception as e:
                        print(f"[WARNING] Erro ao converter data de expiração: {e}")

                # Atualizar dados no banco
                dados_atualizacao = {}
                if nova_data_expiracao:
                    dados_atualizacao["data_expiracao"] = nova_data_expiracao
                if dados_lista_renovada.get("plano"):
                    dados_atualizacao["plano"] = dados_lista_renovada["plano"]
                if dados_lista_renovada.get("conexoes"):
                    dados_atualizacao["conexoes"] = dados_lista_renovada["conexoes"]
                if dados_lista_renovada.get("senha"):
                    dados_atualizacao["senha_iptv"] = dados_lista_renovada["senha"]
                
                # Atualizar a data da última sincronização
                dados_atualizacao["ultima_sincronizacao"] = datetime.now()

                if dados_atualizacao:
                    db.atualizar_cliente_manual(usuario, dados_atualizacao)
                    print(f"[INFO] Banco de dados atualizado para \'{usuario}\' com dados da renovação.")

                link = db.get_config("link_acesso", Config.LINK_ACESSO_DEFAULT)
                data_expiracao_br = nova_data_expiracao.strftime("%d/%m/%Y") if nova_data_expiracao else "N/A"
                
                # Buscar data de criação do banco de dados
                cliente_db = db.buscar_cliente_por_usuario_iptv(usuario)
                data_criacao_br = "N/A"
                if cliente_db and cliente_db.get("data_criacao"):
                    try:
                        data_criacao_br = datetime.fromisoformat(cliente_db["data_criacao"]).strftime("%d/%m/%Y")
                    except Exception as e:
                        print(f"[WARNING] Erro ao formatar data_criacao do DB: {e}")

                senha_br = dados_lista_renovada.get("senha", "Não informada")
                plano_br = dados_lista_renovada.get("plano", "Básico")
                conexoes_br = dados_lista_renovada.get("conexoes", 1)

                resposta = f"""🎉 **LISTA RENOVADA COM SUCESSO!**\n\n**📺 SEUS DADOS DE ACESSO:**\n\n🔗 **Link:** `{link}`\n👤 **Usuário:** `{usuario}`\n🔐 **Senha:** `{senha_br}`\n📱 **Conexões:** {conexoes_br}\n📅 **Criada em:** {data_criacao_br}\n⏰ **Expira em:** {data_expiracao_br}\n📋 **Plano:** {plano_br}\n\n💾 **Guarde esses dados com segurança!**"""
                whatsapp_bot.enviar_mensagem(telefone, resposta)
            else:
                whatsapp_bot.enviar_mensagem(telefone, SUPORTE_MSG)
                db.log_sistema("erro", f"Falha ao renovar lista para \'{usuario}\' no BitPanel.")

        except Exception as e:
            print(f"[CRITICAL] Erro na automação de renovação: {e}")
            traceback.print_exc()
            whatsapp_bot.enviar_mensagem(telefone, SUPORTE_MSG)
        finally:
            if manager:
                manager.close()

    def _converter_data_bitpanel(self, data_str: str) -> datetime:
        """
        Converte string de data do BitPanel (DD/MM/YYYY HH:MM) para objeto datetime.
        """
        return datetime.strptime(data_str, "%d/%m/%Y %H:%M")


# Instância global do bot
gemini_bot = GeminiBot()


