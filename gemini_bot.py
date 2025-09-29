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
        Ponto de entrada principal que lida com novos clientes e clientes existentes.
        """
        try:
            print(f"[DEBUG] Processando: {telefone} | '{mensagem}'")
            mensagem = mensagem.strip()

            # --- 1. COMANDO UNIVERSAL DE CANCELAMENTO ---
            if self.is_comando_cancelar(mensagem):
                self.resetar_conversa(telefone)
                return "❌ Atendimento cancelado. Se precisar de algo, é só chamar! 👋"

            conversa = db.get_conversa(telefone)
            cliente = db.buscar_cliente_por_telefone(telefone)

            # --- 2. LÓGICA PARA NOVOS CLIENTES (CÓDIGO MESCLADO) ---
            # Se não há registro do cliente, inicia o fluxo de cadastro.
            if not cliente:
                # Se a conversa ainda não foi iniciada ou não está no contexto de 'novo_cliente'
                if not conversa or conversa.get("contexto") != "novo_cliente":
                    db.set_conversa(telefone, "novo_cliente", "aguardando_nome", "{}")
                    return "👋 Olá! Sou o assistente virtual. Para começarmos, qual é o seu nome?"
                else:
                    # Se o bot já perguntou o nome e está aguardando a resposta
                    nome = mensagem.strip().title()
                    if len(nome) < 2:
                        return "Por favor, digite um nome válido."

                    # Cria o cliente no banco de dados
                    db.criar_cliente(telefone=telefone, nome=nome)
                    # Limpa o estado da conversa para que o usuário vá para o menu principal
                    self.resetar_conversa(telefone)
                    
                    # Confirma a criação e mostra o menu principal
                    return f"✅ Prazer, {nome}! Seu contato foi guardado.\n\n" + self.resposta_saudacao()

            # --- 3. LÓGICA PARA CLIENTES EXISTENTES ---
            # Se chegamos aqui, o cliente já existe no banco de dados.

            # Se há um fluxo de conversa ativo (compra, renovação, etc.)
            if conversa:
                contexto = conversa.get("contexto")
                estado = conversa.get("estado")

                if contexto == "comprar":
                    return self.processar_fluxo_compra(telefone, mensagem, conversa)
                elif contexto == "renovar":
                    return self.processar_fluxo_renovacao(telefone, mensagem, conversa)
                elif contexto == "inicial" and estado == "menu_erro":
                    return self.processar_menu_erro(telefone, mensagem)

            # Se não há nenhum fluxo ativo para um cliente existente, processa como geral
            return self.processar_conversa_geral(telefone, mensagem, cliente)

        except Exception as e:
            print(f"[CRITICAL] Erro fatal: {e}")
            traceback.print_exc()
            return self.menu_erro("Ops, tive um problema técnico.", telefone)
    def resetar_conversa(self, telefone: str):
        """Reseta conversa para o menu principal"""
        db.set_conversa(telefone, "inicial", "menu", json.dumps({}))
    
    def is_comando_cancelar(self, mensagem: str) -> bool:
        """Verifica se é comando de cancelamento"""
        comandos = ["cancelar", "sair", "parar", "finalizar", "voltar"]
        return any(cmd in mensagem.lower().strip() for cmd in comandos)

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
                    AND created_at > datetime('now', '-1 hour')
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

    def processar_conversa_geral(self, telefone: str, mensagem: str, cliente: Optional[Dict]) -> str:
        """Conversa inicial com sistema numérico"""
        
        # COMANDOS NUMÉRICOS
        if mensagem.strip() == "1":
            return self.iniciar_compra(telefone)
        elif mensagem.strip() == "2":
            # Só permite renovar se TEM cliente e TEM lista
            if not cliente:
                return "❌ Você não possui listas para renovar.\n\n**1️⃣** - Criar nova lista\n**2️⃣** - Voltar ao menu principal"
            
            conn = db.get_connection()
            try:
                tem_lista = conn.execute(
                    "SELECT id FROM clientes WHERE telefone = ? AND usuario_iptv IS NOT NULL", 
                    (telefone,)
                ).fetchone()
            finally:
                conn.close()
                
            if not tem_lista:
                return "❌ Você não possui listas para renovar.\n\n**1️⃣** - Criar nova lista\n**2️⃣** - Voltar ao menu principal"
            
            return self.iniciar_renovacao(telefone)
        elif mensagem.strip() == "3":
            if not cliente:
                return "❌ Você ainda não possui cadastro.\n\n**1️⃣** - Criar nova lista"
            return self.consultar_dados(telefone)

        # DETECÇÃO INTELIGENTE
        intencao = self.detectar_intencao(mensagem)

        if intencao == "comprar":
            return self.iniciar_compra(telefone)
        elif intencao == "renovar":
            if not cliente:
                return "❌ Você não possui listas para renovar.\n\n**1️⃣** - Criar nova lista"
            return self.iniciar_renovacao(telefone)
        elif intencao == "consultar":
            if not cliente:
                return "❌ Você ainda não possui cadastro.\n\n**1️⃣** - Criar nova lista"
            return self.consultar_dados(telefone)
        elif intencao == "saudacao":
            return self.resposta_saudacao()
        elif intencao == "ajuda":
            return self.menu_principal()
        elif intencao == "preco":
            return self.informacao_preco()
        elif intencao == "dispositivo":
            return self.informacao_dispositivos()
        else:
            return self.menu_erro("Não entendi sua mensagem.", telefone)

    def detectar_intencao(self, mensagem: str) -> str:
        """IA para detectar intenções"""
        msg_lower = mensagem.lower().strip()

        palavras_comprar = ["comprar", "quero lista", "adquirir", "assinar", "criar lista", "nova lista", "contratar"]
        palavras_renovar = ["renovar", "renovacao", "estender", "prolongar", "continuar", "mais tempo"]
        palavras_consultar = ["consultar", "meus dados", "minha lista", "minhas listas", "ver dados", "status"]
        palavras_saudacao = ["oi", "olá", "ola", "hey", "hello", "bom dia", "boa tarde", "boa noite"]
        palavras_ajuda = ["ajuda", "help", "socorro", "não sei", "como", "menu", "opções"]
        palavras_preco = ["preço", "preco", "valor", "quanto custa", "quanto é", "quanto fica", "custo"]
        palavras_dispositivo = ["dispositivo", "aparelho", "celular", "tv", "smart tv", "android", "ios", "windows", "funciona"]

        if any(p in msg_lower for p in palavras_comprar):
            return "comprar"
        elif any(p in msg_lower for p in palavras_renovar):
            return "renovar"
        elif any(p in msg_lower for p in palavras_consultar):
            return "consultar"
        elif any(p in msg_lower for p in palavras_saudacao):
            return "saudacao"
        elif any(p in msg_lower for p in palavras_ajuda):
            return "ajuda"
        elif any(p in msg_lower for p in palavras_preco):
            return "preco"
        elif any(p in msg_lower for p in palavras_dispositivo):
            return "dispositivo"
        return "desconhecido"

    def informacao_preco(self) -> str:
        """Informações sobre preços"""
        return """💰 **TABELA DE PREÇOS**

📺 **Plano IPTV Premium:**
• **R$ 30,00 por mês**
• Planos disponíveis de 1 a 12 meses

📊 **Exemplos:**
• 1 mês = R$ 30,00
• 3 meses = R$ 90,00
• 6 meses = R$ 180,00
• 12 meses = R$ 360,00

✨ **Inclui:**
• Canais Full HD, HD, SD e H.265
• VOD (Filmes e Séries)
• Conteúdo Adulto e LGBT
• Até 10 conexões simultâneas

**Gostaria de criar sua lista?**

**1️⃣** - Criar nova lista IPTV
**2️⃣** - Voltar ao menu principal"""

    def informacao_dispositivos(self) -> str:
        """Informações sobre dispositivos compatíveis"""
        return """📱 **DISPOSITIVOS COMPATÍVEIS**

Nosso serviço funciona em diversos dispositivos!

**Qual dispositivo você usa?**

**1️⃣** - Android (Celular/TV Box)
**2️⃣** - Smart TV
**3️⃣** - iOS (iPhone/iPad)
**4️⃣** - Windows/Mac
**5️⃣** - Outros dispositivos

*Digite o número do seu dispositivo para mais informações*"""

    def processar_info_dispositivo_especifico(self, telefone: str, opcao: str) -> str:
        """Processa informação específica de dispositivo"""
        if opcao == "1":
            return """📱 **ANDROID (Celular/TV Box)**

**Aplicativo Recomendado:** BIT PLAYER

📥 **Como baixar:**
1. Acesse: https://bitplatform.vip/
2. Baixe o aplicativo BIT PLAYER para Android
3. Instale e configure com seus dados de acesso

✅ **Período de teste:** 7 dias grátis
💳 **Após teste:** Plano anual ou vitalício disponível

📞 **Renovação:** WhatsApp 11 96751-2034
👤 **Contato:** Eduardo Gabriel

**Gostaria de criar sua lista?**

**1️⃣** - Criar nova lista IPTV
**2️⃣** - Voltar ao menu principal"""
        
        elif opcao == "2":
            return """📺 **SMART TV**

**Aplicativo Recomendado:** IBO PLAYER

📥 **Como baixar:**
1. Acesse: https://bitplatform.vip/
2. Baixe o IBO Player para Smart TV
3. Instale e configure com seus dados de acesso

⚠️ **IMPORTANTE:**
• O IBO Player é **PAGO**
• ✅ Período de teste: 7 dias grátis
• 💳 Após teste: Plano anual ou vitalício

📞 **Para renovar o aplicativo:**
WhatsApp: 11 96751-2034
👤 Falar com: Eduardo Gabriel

**Gostaria de criar sua lista IPTV?**

**1️⃣** - Criar nova lista IPTV
**2️⃣** - Voltar ao menu principal"""
        
        elif opcao == "3":
            return """🍎 **iOS (iPhone/iPad)**

📥 **Como baixar:**
1. Acesse: https://bitplatform.vip/
2. Escolha um aplicativo compatível com iOS
3. Instale e configure com seus dados

**Opções disponíveis no site**

**Gostaria de criar sua lista?**

**1️⃣** - Criar nova lista IPTV
**2️⃣** - Voltar ao menu principal"""
        
        elif opcao == "4":
            return """💻 **WINDOWS/MAC**

📥 **Como baixar:**
1. Acesse: https://bitplatform.vip/
2. Escolha o aplicativo para seu sistema
3. Instale e configure com seus dados

**Opções disponíveis no site**

**Gostaria de criar sua lista?**

**1️⃣** - Criar nova lista IPTV
**2️⃣** - Voltar ao menu principal"""
        
        else:
            return """📱 **OUTROS DISPOSITIVOS**

Para outros dispositivos:

1. Acesse: https://bitplatform.vip/
2. Escolha o aplicativo compatível
3. Instale e configure com seus dados

📞 **Dúvidas?** WhatsApp: 11 96751-2034

**Gostaria de criar sua lista?**

**1️⃣** - Criar nova lista IPTV
**2️⃣** - Voltar ao menu principal"""

    def menu_principal(self) -> str:
        return """🤖 **Olá! Sou seu assistente IPTV!**

**O que você gostaria de fazer?**

**1️⃣** - Criar nova lista IPTV
**2️⃣** - Renovar lista existente  
**3️⃣** - Consultar meus dados

*Digite apenas o número da opção desejada*

💬 Ou me diga com suas palavras o que precisa!"""

    def resposta_saudacao(self) -> str:
        return """👋 **Olá! Tudo bem?** Sou **Ozzy**, seu assistente de vendas IPTV. 

📺 **Oferta Especial:**
• Canais **Full HD, HD, SD** e **H.265**
• **VOD**, conteúdos **Adulto** e **LGBT**
• **Até 10 conexões simultâneas**

💰 **Apenas R$ 30,00/mês** - Planos de 1 a 12 meses

**Como posso ajudá-lo hoje?**

**1️⃣** - Criar nova lista IPTV
**2️⃣** - Renovar lista existente  
**3️⃣** - Consultar meus dados"""

    def menu_erro(self, mensagem_erro: str, telefone: str) -> str:
        db.set_conversa(telefone, "inicial", "menu_erro", json.dumps({}))
        return f"""❓ {mensagem_erro}

**Precisa de ajuda?**

**1️⃣** - Voltar ao menu principal
**2️⃣** - Falar com suporte humano

*Digite 1 ou 2 para continuar*"""

    def processar_menu_erro(self, telefone: str, mensagem: str) -> str:
        if mensagem.strip() == "1":
            self.resetar_conversa(telefone)
            return self.menu_principal()
        elif mensagem.strip() == "2":
            self.resetar_conversa(telefone)
            return f"""📞 **Suporte Humano**

Entre em contato com nosso suporte:
**WhatsApp:** 11 96751-2034

Nossa equipe está pronta para ajudá-lo! 😊"""
        return """❌ Opção inválida.\n\n**1️⃣** - Voltar ao menu principal\n**2️⃣** - Falar com suporte humano"""

    def iniciar_compra(self, telefone: str) -> str:
        db.set_conversa(telefone, "comprar", "aguardando_usuario", json.dumps({}))
        return """🛒 **CRIAÇÃO DE NOVA LISTA**

Vamos criar sua lista IPTV personalizada!

**Passo 1/4:** Escolha um nome de usuário
*Use apenas letras e números (4 a 12 caracteres)*

Exemplo: `joao123` ou `maria2024`

💡 *Digite "cancelar" a qualquer momento para sair*"""

    def iniciar_renovacao(self, telefone: str) -> str:
        conn = db.get_connection()
        try:
            listas = conn.execute("""
                SELECT usuario_iptv, data_expiracao 
                FROM clientes 
                WHERE telefone = ? AND usuario_iptv IS NOT NULL
                ORDER BY created_at DESC
            """, (telefone,)).fetchall()
        finally:
            conn.close()

        if not listas:
            return """❌ **Nenhuma lista encontrada**

Você não possui listas para renovar.

**1️⃣** - Criar nova lista
**2️⃣** - Voltar ao menu"""

        if len(listas) == 1:
            lista = listas[0]
            db.set_conversa(
                telefone,
                "renovar",
                "aguardando_meses",
                json.dumps({"usuario_selecionado": lista["usuario_iptv"]}),
            )
            return f"""🔄 **RENOVAÇÃO DE LISTA**

Lista selecionada: **{lista['usuario_iptv']}**

**Passo 1/3:** Por quantos meses deseja renovar?
*Digite um número de 1 a 12*

Exemplo: `3` para 3 meses

💡 *Digite "cancelar" para sair*"""
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
                f"""🔄 **RENOVAÇÃO - ESCOLHA A LISTA**

Você possui {len(listas)} listas:

"""
                + "\n".join(opcoes)
                + """\n\n*Digite o número da lista que deseja renovar*"""
            )

    def consultar_dados(self, telefone: str) -> str:
        """Consulta dados do cliente"""
        conn = db.get_connection()
        try:
            listas = conn.execute("""
                SELECT usuario_iptv, senha_iptv, data_criacao, data_expiracao, conexoes, plano, status
                FROM clientes 
                WHERE telefone = ? AND usuario_iptv IS NOT NULL
                ORDER BY created_at DESC
            """, (telefone,)).fetchall()
        finally:
            conn.close()

        if not listas:
            return """❌ **Nenhuma lista encontrada**

Você ainda não possui listas IPTV.

**1️⃣** - Criar nova lista
**2️⃣** - Voltar ao menu principal"""

        resposta = "📋 **SUAS LISTAS IPTV - INFORMAÇÕES COMPLETAS:**\n\n"

        for i, lista in enumerate(listas, 1):
            try:
                data_criacao_str = "N/A"
                if lista["data_criacao"]:
                    data_criacao_str = datetime.fromisoformat(lista["data_criacao"]).strftime("%d/%m/%Y")
                
                expira_str = "N/A"
                status_lista = "N/A"
                if lista["data_expiracao"]:
                    expira_dt = datetime.fromisoformat(lista["data_expiracao"])
                    expira_str = expira_dt.strftime("%d/%m/%Y")
                    status_lista = "✅ ATIVA" if expira_dt > datetime.now() else "❌ EXPIRADA"
                
                senha = lista["senha_iptv"] or "Não informada"
                plano = lista["plano"] or "Básico"

                resposta += f"""
**{i}. {lista['usuario_iptv']}**
🔐 **Senha:** {senha}
📺 **Conexões:** {lista['conexoes'] or 1}
📊 **Status:** {status_lista}
📅 **Criada em:** {data_criacao_str}
⏰ **Expira em:** {expira_str}
📋 **Plano:** {plano}

"""
            except Exception as e:
                print(f"[ERROR] Erro ao formatar lista: {e}")
                resposta += f"""
**{i}. {lista['usuario_iptv']}**
📺 **Conexões:** {lista.get('conexoes', 1)}
📊 **Status:** Erro ao carregar detalhes

"""

        resposta += """**Precisa de mais alguma coisa?**

**1️⃣** - Renovar uma lista
**2️⃣** - Criar nova lista
**3️⃣** - Voltar ao menu"""

        return resposta

    def processar_fluxo_compra(self, telefone: str, mensagem: str, conversa: Dict) -> Optional[str]:
        """Gerencia fluxo de compra"""
        estado = conversa.get("estado", "indefinido")
        dados = json.loads(conversa.get("dados_temporarios", "{}"))

        if estado == "aguardando_usuario":
            usuario = mensagem.strip().replace(" ", "").lower()
            if not re.match(r"^[a-z0-9]{4,12}$", usuario):
                return """❌ **Nome de usuário inválido**

Use apenas letras e números (4 a 12 caracteres)
Exemplo: `joao123` ou `maria2024`

Tente novamente:"""

            conn = db.get_connection()
            try:
                existe = conn.execute("SELECT id FROM clientes WHERE usuario_iptv = ?", (usuario,)).fetchone()
            finally:
                conn.close()

            if existe:
                return f"""❌ **Usuário já existe**

O usuário `{usuario}` já está em uso.
Escolha outro nome:"""

            dados["usuario"] = usuario
            db.set_conversa(telefone, "comprar", "aguardando_conexoes", json.dumps(dados))

            return f"""✅ **Usuário definido:** `{usuario}`

**Passo 2/4:** Quantas conexões (telas) simultâneas?
*Digite um número de 1 a 10*

💡 **Dica:**
• 1 conexão = 1 TV/celular
• 2 conexões = 2 dispositivos simultâneos
• E assim por diante...

Exemplo: `2` para 2 conexões"""

        elif estado == "aguardando_conexoes":
            try:
                conexoes = int(mensagem.strip())
                if not 1 <= conexoes <= 10:
                    return """❌ **Número inválido**

Digite um número de 1 a 10 conexões:"""

                dados["conexoes"] = conexoes
                db.set_conversa(telefone, "comprar", "aguardando_duracao", json.dumps(dados))

                return f"""✅ **Conexões definidas:** {conexoes}

**Passo 3/4:** Por quantos meses deseja assinar?
*Digite um número de 1 a 12*

💰 **Valores:**
• 1 mês = R$ 30,00
• 3 meses = R$ 90,00
• 6 meses = R$ 180,00
• 12 meses = R$ 360,00

Exemplo: `3` para 3 meses"""
            except ValueError:
                return """❌ **Digite apenas números**

Quantas conexões você precisa? (1 a 10)"""

        elif estado == "aguardando_duracao":
            try:
                from mercpag import mercado_pago

                meses = int(mensagem.strip())
                if not 1 <= meses <= 12:
                    return """❌ **Número inválido**

Digite um número de 1 a 12 meses:"""

                dados["meses"] = meses
                preco = mercado_pago.calcular_preco(dados["conexoes"], meses)
                dados["preco"] = preco

                db.set_conversa(telefone, "comprar", "confirmando_dados", json.dumps(dados))

                return f"""📋 **RESUMO DO PEDIDO**

👤 **Usuário:** `{dados['usuario']}`
📺 **Conexões:** {dados['conexoes']}
📅 **Duração:** {meses} mês{'es' if meses > 1 else ''}
💰 **Valor Total:** R$ {preco:.2f}

**Confirma os dados?**
**1️⃣** - Sim, gerar PIX
**2️⃣** - Não, cancelar pedido"""
            except ValueError:
                return """❌ **Digite apenas números**

Por quantos meses? (1 a 12)"""

        elif estado == "confirmando_dados":
            if mensagem.strip() == "1" or mensagem.lower().strip() in ["sim", "confirmar", "ok"]:
                return self.gerar_pix_compra(telefone, dados)
            elif mensagem.strip() == "2" or mensagem.lower().strip() in ["não", "nao", "cancelar"]:
                self.resetar_conversa(telefone)
                return "❌ **Pedido cancelado**\n\nSe mudar de ideia, é só chamar! \n\n" + self.menu_principal()
            else:
                return """❓ **Resposta inválida**

**1️⃣** - Sim, gerar PIX
**2️⃣** - Não, cancelar pedido"""

        return self.menu_erro("Erro no fluxo de compra.", telefone)

    def gerar_pix_compra(self, telefone: str, dados_compra: Dict) -> Optional[str]:
        """Gera PIX para compra - SÓ CRIA CLIENTE AQUI"""
        try:
            from mercpag import mercado_pago
            from whatsapp_bot import whatsapp_bot

            # AGORA SIM: Criar cliente no banco (vai finalizar compra)
            cliente = db.buscar_cliente_por_telefone(telefone)
            if not cliente:
                cliente_id = db.criar_cliente(telefone)
                cliente = {"id": cliente_id}

            # MODO DE TESTE
            if Config.TEST_MODE:
                print("\n--- MODO DE TESTE: Simulando pagamento de COMPRA aprovado ---\n")
                self.processar_pagamento_aprovado(telefone, dados_compra)
                return None

            # MODO REAL
            pix_info = mercado_pago.criar_cobranca_pix(
                telefone,
                dados_compra["usuario"],
                dados_compra["conexoes"],
                dados_compra["meses"],
            )

            if not pix_info:
                self.resetar_conversa(telefone)
                return self.menu_erro("Não consegui gerar o PIX. Tente novamente.", telefone)

            dados_compra["payment_id"] = pix_info["payment_id"]
            db.set_conversa(telefone, "comprar", "aguardando_pagamento", json.dumps(dados_compra))

            db.criar_pagamento(
                cliente_id=cliente["id"],
                telefone=telefone,
                valor=pix_info["valor"],
                payment_id=str(pix_info["payment_id"]),
                copia_cola=pix_info["copia_cola"],
                contexto="comprar",
                dados_temporarios=json.dumps(dados_compra)
            )

            whatsapp_bot.enviar_mensagem(
                telefone,
                f"""✅ **PIX GERADO!**

💰 **Valor:** R$ {pix_info['valor']:.2f}

📱 Use o QR Code ou copie o código abaixo:"""
            )

            if pix_info.get("qr_code_base64"):
                whatsapp_bot.enviar_imagem_base64(telefone, pix_info["qr_code_base64"])

            whatsapp_bot.enviar_mensagem(telefone, f"`{pix_info['copia_cola']}`")

            whatsapp_bot.enviar_mensagem(
                telefone,
                """⏳ **Aguardando pagamento...**

Assim que o PIX for aprovado, sua lista será criada automaticamente! ✅

⚡ O processo é instantâneo após a confirmação."""
            )

            return None

        except Exception as e:
            print(f"[ERROR] Erro ao gerar PIX: {e}")
            self.resetar_conversa(telefone)
            return self.menu_erro("Erro ao gerar PIX. Tente novamente.", telefone)

    def processar_fluxo_renovacao(self, telefone: str, mensagem: str, conversa: Dict) -> Optional[str]:
        """Processa renovação"""
        estado = conversa.get("estado", "inicio")
        dados = json.loads(conversa.get("dados_temporarios", "{}"))

        if estado == "escolhendo_lista":
            try:
                escolha = int(mensagem.strip()) - 1
                listas_disponiveis = dados.get("listas_disponiveis", [])

                if 0 <= escolha < len(listas_disponiveis):
                    usuario_selecionado = listas_disponiveis[escolha]
                    dados["usuario_selecionado"] = usuario_selecionado
                    db.set_conversa(telefone, "renovar", "aguardando_meses", json.dumps(dados))

                    return f"""✅ **Lista selecionada:** `{usuario_selecionado}`

**Por quantos meses deseja renovar?**
*Digite um número de 1 a 12*

💰 **Valores:**
• 1 mês = R$ 30,00
• 3 meses = R$ 90,00  
• 6 meses = R$ 180,00
• 12 meses = R$ 360,00"""

                else:
                    return """❌ **Número inválido**

Digite o número da lista que deseja renovar:"""
            except ValueError:
                return """❌ **Digite apenas números**

Qual lista deseja renovar?"""

        elif estado == "aguardando_meses":
            try:
                meses = int(mensagem.strip())
                if not 1 <= meses <= 12:
                    return """❌ **Número inválido**

Digite um número de 1 a 12 meses:"""

                from mercpag import mercado_pago

                conn = db.get_connection()
                try:
                    lista = conn.execute("""
                        SELECT conexoes FROM clientes 
                        WHERE telefone = ? AND usuario_iptv = ?
                    """, (telefone, dados["usuario_selecionado"])).fetchone()
                finally:
                    conn.close()

                conexoes = lista["conexoes"] if lista else 1
                preco_total = mercado_pago.calcular_preco(conexoes, meses)

                dados["meses"] = meses
                dados["preco"] = preco_total
                dados["conexoes"] = conexoes

                db.set_conversa(telefone, "renovar", "confirmando_renovacao", json.dumps(dados))

                return f"""📋 **RESUMO DA RENOVAÇÃO**

👤 **Lista:** `{dados['usuario_selecionado']}`
📺 **Conexões:** {conexoes}
📅 **Adicionar:** {meses} mês{'es' if meses > 1 else ''}
💰 **Valor Total:** R$ {preco_total:.2f}

**Confirma a renovação?**
**1️⃣** - Sim, gerar PIX
**2️⃣** - Não, cancelar"""

            except ValueError:
                return """❌ **Digite apenas números**

Por quantos meses? (1 a 12)"""

        elif estado == "confirmando_renovacao":
            if mensagem.strip() == "1" or mensagem.lower().strip() in ["sim", "confirmar", "ok"]:
                return self.gerar_pix_renovacao(telefone, dados)
            elif mensagem.strip() == "2" or mensagem.lower().strip() in ["não", "nao", "cancelar"]:
                self.resetar_conversa(telefone)
                return "❌ **Renovação cancelada**\n\nSe mudar de ideia, é só chamar! \n\n" + self.menu_principal()
            else:
                return """❓ **Resposta inválida**

**1️⃣** - Sim, gerar PIX
**2️⃣** - Não, cancelar"""

        return self.menu_erro("Erro no fluxo de renovação.", telefone)

    def gerar_pix_renovacao(self, telefone: str, dados_renovacao: Dict) -> Optional[str]:
        """Gera PIX para renovação"""
        try:
            from mercpag import mercado_pago
            from whatsapp_bot import whatsapp_bot

            cliente = db.buscar_cliente_por_telefone(telefone)
            if not cliente:
                return self.menu_erro("Cliente não encontrado.", telefone)

            if Config.TEST_MODE:
                print("\n--- MODO DE TESTE: Simulando pagamento de RENOVAÇÃO aprovado ---\n")
                self.processar_pagamento_renovacao(telefone, dados_renovacao)
                return None

            pix_info = mercado_pago.criar_cobranca_pix(
                telefone,
                dados_renovacao["usuario_selecionado"],
                dados_renovacao["conexoes"],
                dados_renovacao["meses"],
            )

            if not pix_info:
                self.resetar_conversa(telefone)
                return self.menu_erro("Não consegui gerar o PIX. Tente novamente.", telefone)

            dados_renovacao["payment_id"] = pix_info["payment_id"]
            db.set_conversa(telefone, "renovar", "aguardando_pagamento", json.dumps(dados_renovacao))

            db.criar_pagamento(
                cliente["id"],
                telefone,
                pix_info["valor"],
                str(pix_info["payment_id"]),
                pix_info["copia_cola"],
                contexto="renovar",
                dados_temporarios=json.dumps(dados_renovacao)
            )

            whatsapp_bot.enviar_mensagem(
                telefone,
                f"""✅ **RENOVAÇÃO - PIX GERADO!**

📺 **Lista:** `{dados_renovacao['usuario_selecionado']}`
📅 **Adicionar:** {dados_renovacao['meses']} mês{'es' if dados_renovacao['meses'] > 1 else ''}
💰 **Valor:** R$ {pix_info['valor']:.2f}

📱 Use o QR Code ou copie o código abaixo:"""
            )

            if pix_info.get("qr_code_base64"):
                whatsapp_bot.enviar_imagem_base64(telefone, pix_info["qr_code_base64"])

            whatsapp_bot.enviar_mensagem(telefone, f"`{pix_info['copia_cola']}`")

            whatsapp_bot.enviar_mensagem(
                telefone,
                """⏳ **Aguardando pagamento...**

Assim que o PIX for aprovado, sua lista será renovada automaticamente! ✅

⚡ O processo é instantâneo após a confirmação."""
            )

            return None

        except Exception as e:
            print(f"[ERROR] Erro ao gerar PIX de renovação: {e}")
            self.resetar_conversa(telefone)
            return self.menu_erro("Erro ao gerar PIX. Tente novamente.", telefone)

    def processar_pagamento_aprovado(self, telefone: str, dados_compra: Dict):
        """Executa automação de CRIAÇÃO no BitPanel"""
        from whatsapp_bot import whatsapp_bot
        manager = None
        try:
            whatsapp_bot.enviar_mensagem(
                telefone,
                "✅ **Pagamento confirmado!** Estou criando sua lista agora, isso pode levar um ou dois minutos..."
            )

            manager = BitPanelManager()
            dados_lista = manager.criar_lista(
                username=dados_compra["usuario"],
                conexoes=dados_compra["conexoes"],
                duracao_meses=dados_compra["meses"],
                headless=True
            )

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

                resposta = f"""🎉 **LISTA CRIADA COM SUCESSO!**

**📺 SEUS DADOS DE ACESSO:**

🔗 **Link:** `{link}`
👤 **Usuário:** `{dados_compra['usuario']}`
🔐 **Senha:** `{dados_lista['senha']}`
📱 **Conexões:** {dados_compra['conexoes']}
⏰ **Expira em:** {data_expiracao_br}

💾 **Guarde esses dados com segurança!**"""
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
        """Executa automação de RENOVAÇÃO no BitPanel"""
        from whatsapp_bot import whatsapp_bot
        manager = None
        try:
            usuario = dados_renovacao['usuario_selecionado']
            meses = dados_renovacao['meses']

            whatsapp_bot.enviar_mensagem(
                telefone,
                f"✅ **Pagamento confirmado!** Estou renovando sua lista `{usuario}` no painel. Isso pode levar um minuto..."
            )

            manager = BitPanelManager()
            dados_lista_renovada = manager.renovar_lista(
                username=usuario, 
                duracao_meses=meses, 
                headless=True
            )

            if dados_lista_renovada and not dados_lista_renovada.get("erro"):
                print(f"[INFO] Renovação de '{usuario}' no BitPanel bem-sucedida. Dados: {dados_lista_renovada}")

                # Atualizar banco com dados capturados
                from datetime import datetime
                
                nova_data_expiracao = None
                if dados_lista_renovada.get("expira_em"):
                    try:
                        nova_data_expiracao = datetime.strptime(dados_lista_renovada["expira_em"], "%d/%m/%Y %H:%M")
                    except Exception as e:
                        print(f"[WARNING] Erro ao converter data: {e}")

                dados_atualizacao = {}
                if nova_data_expiracao:
                    dados_atualizacao["data_expiracao"] = nova_data_expiracao
                if dados_lista_renovada.get("plano"):
                    dados_atualizacao["plano"] = dados_lista_renovada["plano"]
                if dados_lista_renovada.get("conexoes"):
                    dados_atualizacao["conexoes"] = dados_lista_renovada["conexoes"]
                if dados_lista_renovada.get("senha"):
                    dados_atualizacao["senha_iptv"] = dados_lista_renovada["senha"]
                
                dados_atualizacao["ultima_sincronizacao"] = datetime.now()

                if dados_atualizacao:
                    conn = db.get_connection()
                    try:
                        # Atualizar pelo usuario_iptv
                        updates = []
                        params = []
                        for campo, valor in dados_atualizacao.items():
                            updates.append(f"{campo} = ?")
                            params.append(valor)
                        params.append(usuario)
                        
                        conn.execute(
                            f"UPDATE clientes SET {', '.join(updates)} WHERE usuario_iptv = ?",
                            params
                        )
                        conn.commit()
                        print(f"[INFO] Banco atualizado para '{usuario}'")
                    finally:
                        conn.close()

                link = db.get_config("link_acesso", Config.LINK_ACESSO_DEFAULT)
                data_expiracao_br = nova_data_expiracao.strftime("%d/%m/%Y") if nova_data_expiracao else "N/A"
                
                cliente_db = db.buscar_cliente_por_usuario_iptv(usuario)
                data_criacao_br = "N/A"
                if cliente_db and cliente_db.get("data_criacao"):
                    try:
                        data_criacao_br = datetime.fromisoformat(cliente_db["data_criacao"]).strftime("%d/%m/%Y")
                    except:
                        pass

                senha_br = dados_lista_renovada.get("senha", "Não informada")
                plano_br = dados_lista_renovada.get("plano", "Básico")
                conexoes_br = dados_lista_renovada.get("conexoes", 1)

                resposta = f"""🎉 **LISTA RENOVADA COM SUCESSO!**

**📺 SEUS DADOS DE ACESSO:**

🔗 **Link:** `{link}`
👤 **Usuário:** `{usuario}`
🔐 **Senha:** `{senha_br}`
📱 **Conexões:** {conexoes_br}
📅 **Criada em:** {data_criacao_br}
⏰ **Expira em:** {data_expiracao_br}
📋 **Plano:** {plano_br}

💾 **Guarde esses dados com segurança!**"""
                whatsapp_bot.enviar_mensagem(telefone, resposta)
            else:
                whatsapp_bot.enviar_mensagem(telefone, SUPORTE_MSG)
                db.log_sistema("erro", f"Falha ao renovar lista para '{usuario}' no BitPanel.")

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