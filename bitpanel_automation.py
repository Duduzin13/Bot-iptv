'''
bitpanel_automation.py - Automação BitPanel com Selenium (Versão com Tratamento de Popups)

Este script é projetado para ser usado em conjunto com o seu arquivo `config.py`.
Certifique-se de que `config.py` e `bitpanel_automation.py` estejam na mesma pasta.
'''
import time
import random
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from config import Config
from selenium.webdriver.common.keys import Keys



# Mock do objeto 'db' para o código funcionar de forma independente
class MockDB:
    def log_sistema(self, tipo, mensagem):
        print(f"LOG [{tipo.upper()}]: {mensagem}")

db = MockDB()

class BitPanelManager:
    def __init__(self):
        """Inicializa o gerenciador do BitPanel."""
        self.config = Config()
        if not self.config.BITPANEL_USER or not self.config.BITPANEL_PASS:
            raise ValueError("As credenciais BITPANEL_USER e BITPANEL_PASS não foram encontradas no arquivo config.py.")
        self.driver = None
        self.is_logged_in = False

    def setup_driver(self, headless=True):
        """Configura o driver do Chrome com opções otimizadas para lidar com popups."""
        options = Options()
        
        # Configurações headless
        if headless:
            options.add_argument('--headless')
        
        # Opções para estabilizar a conexão e evitar detecção
        options.add_experimental_option("detach", True)
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument('--log-level=3')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1920,1080')
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-extensions")
        options.add_argument("--single-process") 

        
        # Desativa completamente o gerenciador de senhas do Chrome
        options.add_experimental_option("prefs", {
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
            "profile.default_content_setting_values.notifications": 2,
            "profile.default_content_settings.popups": 0,
            "profile.managed_default_content_settings.popups": 0
        })
        
        # Usa o chromedriver.exe que está na mesma pasta do script
        try:
            service = Service(executable_path="chromedriver.exe")
            self.driver = webdriver.Chrome(service=service, options=options)
        except Exception as e:
            print(f"Erro ao configurar ChromeDriver: {e}")
            # Tenta usar o chromedriver do PATH
            self.driver = webdriver.Chrome(options=options)
            
        # Configurar timeouts
        self.driver.implicitly_wait(10)
        self.driver.set_page_load_timeout(30)

    def login(self, headless=True) -> bool:
        """Faz login no BitPanel usando as credenciais do config.py."""
        if self.is_logged_in:
            return True
        if not self.driver:
            self.setup_driver(headless=headless)

        try:
            print("🔐 Fazendo login no BitPanel...")
            self.driver.get(f"{self.config.BITPANEL_URL}/login")

            wait = WebDriverWait(self.driver, 10)

            print("   - Aguardando página carregar completamente...")
            time.sleep(2)  # Aguarda carregamento inicial
            
            print("   - Aguardando campo de usuário...")
            username_field = wait.until(EC.presence_of_element_located((By.NAME, "username")))
            
            print("   - Aguardando campo de senha...")
            password_field = wait.until(EC.presence_of_element_located((By.NAME, "password")))
            
            print("   - Preenchendo credenciais...")
            username_field.clear()
            username_field.send_keys(self.config.BITPANEL_USER)

            password_field.clear()
            password_field.send_keys(self.config.BITPANEL_PASS)
            
            print("   - Clicando em entrar...")
            login_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']")))
            login_button.click()
            time.sleep(8)

            print("   - Verificando se o login foi bem-sucedido...")

            # Depois do login:
            time.sleep(8)
            # Abre nova aba/guia e fecha a antiga para "matar" popup de senha
            self.driver.execute_script("window.open(arguments[0], '_blank');", self.config.BITPANEL_URL + "/dashboard")
            self.driver.close()          # fecha a guia antiga
            self.driver.switch_to.window(self.driver.window_handles[0])

            # Verifica se chegou ao dashboard
            try:
                self.driver.switch_to.active_element.send_keys(Keys.ENTER)
                wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Dashboard')]")))
                self.is_logged_in = True
                print("✅ Login realizado com sucesso!")
                return True
                
            except TimeoutException:
                # Se não encontrou "Dashboard", verifica se está na URL correta
                if "dashboard" in self.driver.current_url.lower() or "painel" in self.driver.current_url.lower():
                    self.is_logged_in = True
                    print("✅ Login realizado com sucesso (verificação por URL)!")
                    return True
                else:
                    print(f"❌ URL atual: {self.driver.current_url}")
                    raise TimeoutException("Não conseguiu confirmar o login")

        except TimeoutException:
            print("❌ Erro no login: A página demorou muito para carregar ou a confirmação de login não foi encontrada.")
            print(f"   URL atual: {self.driver.current_url}")
            return False
        except Exception as e:
            print(f"❌ Erro inesperado no login: {e}")
            return False

    def navegar_para_listas(self):
        """Navega para a página de listas com tratamento de popups"""
        try:
            list_url = f"{self.config.BITPANEL_URL}list"
            print(f"🔄 Navegando para: {list_url}")
            
            self.driver.get(list_url)
            
            print("✅ Navegação para /list concluída")
            return True
            
        except Exception as e:
            print(f"❌ Erro ao navegar para listas: {e}")
            return False

    def verificar_conexao(self, headless=True) -> bool:
        """Verifica se é possível fazer login no BitPanel."""
        print("🌐 Verificando conexão com o BitPanel...")
        try:
            resultado = self.login(headless=headless)
            if resultado and not headless:
                # Se não for headless, testa navegação para /list
                self.navegar_para_listas()
            
            if self.driver and headless:
                # Se for headless, fecha automaticamente após verificação
                self.close()
            return resultado
        except Exception as e:
            print(f"❌ Erro na verificação: {e}")
            return False

    def _get_list_info_from_page(self) -> dict:
        """Extrai as informações da lista da página de detalhes."""
        wait = WebDriverWait(self.driver, 15)
        try:
            user_info_element = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "user-infor")))
            info_text = user_info_element.text
            
            info = {}
            for line in info_text.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    info[key.strip().lower()] = value.strip()
            
            info.pop('clique aqui para ver o link da lista', None)
            print(f"ℹ️ Informações da lista extraídas: {info}")
            return info
        except TimeoutException:
            print("❌ Erro: Não foi possível encontrar as informações da lista (classe 'user-infor').")
            return None
        except Exception as e:
            print(f"❌ Erro inesperado ao extrair informações da lista: {e}")
            return None

    def _extrair_dados_lista(self, wait: WebDriverWait) -> dict:
        """
        Extrai TODOS os dados da página de informações do BitPanel.
        VERSÃO FINAL: Captura as datas EXATAMENTE como aparecem no BitPanel.
        """
        try:
            print("\n" + "="*60)
            print("[EXTRAÇÃO] Aguardando página de detalhes da lista...")
            print("="*60)
            
            # Espera o container 'user-infor' ficar visível
            info_container = wait.until(EC.visibility_of_element_located((
                By.CLASS_NAME, "user-infor"
            )))
        
            print("[EXTRAÇÃO] ✓ Container encontrado")
            
            # Pega todos os itens <li> dentro do container
            list_items = info_container.find_elements(By.TAG_NAME, "li")
            
            print(f"[EXTRAÇÃO] Encontrados {len(list_items)} campos de informação\n")
        
            dados_lista = {}
            
            for i, item in enumerate(list_items, 1):
                texto_completo = item.text.strip()
                
                # Ignorar campos vazios ou inúteis
                if not texto_completo or "clique aqui" in texto_completo.lower():
                    continue
                
                print(f"[EXTRAÇÃO] Campo {i}: '{texto_completo}'")
                
                if ":" in texto_completo:
                    # Dividir apenas no primeiro ":"
                    partes = texto_completo.split(":", 1)
                    if len(partes) == 2:
                        chave_original = partes[0].strip()
                        valor_original = partes[1].strip()
                        
                        # ========================================================
                        # MAPEAMENTO COMPLETO DE TODOS OS CAMPOS DO BITPANEL
                        # ========================================================
                        mapeamento_chaves = {
                            # Usuário
                            'usuário': 'usuario',
                            'usuario': 'usuario',
                            'usuário iptv': 'usuario',
                            'nome do usuário': 'usuario',
                            'nome do usuario': 'usuario',
                            'username': 'usuario',
                            'user': 'usuario',
                            
                            # Senha
                            'senha': 'senha',
                            'password': 'senha',
                            'pass': 'senha',
                            
                            # Conexões
                            'conexões': 'conexoes',
                            'conexoes': 'conexoes',
                            'connections': 'conexoes',
                            'max connections': 'conexoes',
                            'numero de conexões': 'conexoes',
                            'número de conexões': 'conexoes',
                            
                            # Data de Criação (CRÍTICO)
                            'criado em': 'criado_em',
                            'criado': 'criado_em',
                            'Data de criação': 'criado_em',
                            'data criação': 'criado_em',
                            'data criacao': 'criado_em',
                            'created at': 'criado_em',
                            'created': 'criado_em',
                            'creation date': 'criado_em',
                            
                            # Data de Expiração (CRÍTICO)
                            'expira em': 'expira_em',
                            'expira': 'expira_em',
                            'data de expiração': 'expira_em',
                            'data expiracao': 'expira_em',
                            'data expiração': 'expira_em',
                            'validade': 'expira_em',
                            'Data de validade': 'expira_em',
                            'expires at': 'expira_em',
                            'expires': 'expira_em',
                            'expiration date': 'expira_em',
                            'valid until': 'expira_em',
                            
                            # Plano
                            'plano': 'plano',
                            'plan': 'plano',
                            'pacote': 'plano',
                            'package': 'plano',
                            'plano de tv': 'plano',
                            'tv plan': 'plano',
                            
                            # Status
                            'status': 'status_bitpanel',
                            'estado': 'status_bitpanel',
                            'ativo': 'status_bitpanel',
                            'active': 'status_bitpanel',
                            'state': 'status_bitpanel',
                        }
                        
                        # Normalizar chave (minúsculas, sem espaços extras)
                        chave_normalizada = chave_original.lower().strip()
                        
                        # Buscar no mapeamento
                        chave_final = mapeamento_chaves.get(chave_normalizada)
                        
                        # Se não encontrou no mapeamento, criar chave genérica
                        if not chave_final:
                            chave_final = chave_normalizada.replace(" ", "_").replace("ã", "a").replace("ç", "c").replace("é", "e")
                        
                        # Salvar o dado
                        dados_lista[chave_final] = valor_original
                        
                        # Log do mapeamento
                        print(f"  → Mapeado: '{chave_original}' → '{chave_final}' = '{valor_original}'")
            
            print("\n" + "="*60)
            print("[EXTRAÇÃO] Dados finais extraídos:")
            print("="*60)
            for chave, valor in dados_lista.items():
                print(f"  {chave}: {valor}")
            print("="*60 + "\n")
            
            # ========================================================
            # VALIDAÇÃO CRÍTICA: Verificar se os campos essenciais existem
            # ========================================================
            campos_essenciais = ['usuario', 'senha', 'expira_em']
            campos_faltando = []
            
            for campo in campos_essenciais:
                if campo not in dados_lista:
                    campos_faltando.append(campo)
            
            if campos_faltando:
                print(f"[EXTRAÇÃO] ⚠ AVISO: Campos essenciais não encontrados: {campos_faltando}")
                print(f"[EXTRAÇÃO]   Campos disponíveis: {list(dados_lista.keys())}")
            
            # Data de criação não é obrigatória (algumas listas antigas podem não ter)
            if 'criado_em' not in dados_lista:
                print(f"[EXTRAÇÃO] ⚠ AVISO: Campo 'criado_em' não encontrado - lista antiga?")
            
            return dados_lista

        except TimeoutException:
            print("\n[EXTRAÇÃO] ❌ TIMEOUT: Container 'user-infor' não carregou")
            print("[EXTRAÇÃO]   Tentando capturar qualquer texto visível...")
            
            try:
                # Tentar pegar todo o texto da página
                body_text = self.driver.find_element(By.TAG_NAME, "body").text
                print(f"[EXTRAÇÃO]   Texto da página:\n{body_text[:500]}...")
                
                # Salvar screenshot
                screenshot_name = f"erro_timeout_extracao_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                self.driver.save_screenshot(screenshot_name)
                print(f"[EXTRAÇÃO]   Screenshot salvo: {screenshot_name}")
            except:
                print("[EXTRAÇÃO]   Não foi possível capturar informações da página")
            
            return None
            
        except Exception as e:
            print(f"\n[EXTRAÇÃO] ❌ ERRO INESPERADO: {type(e).__name__}: {str(e)}")
            
            try:
                screenshot_name = f"erro_extracao_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                self.driver.save_screenshot(screenshot_name)
                print(f"[EXTRAÇÃO]   Screenshot salvo: {screenshot_name}")
            except:
                pass
            
            import traceback
            traceback.print_exc()
            
            return None

    
    def criar_lista(self, username: str, conexoes: int, duracao_meses: int, headless=False):
        """
        Cria uma nova lista de usuário no painel usando seletores precisos e robustos.
        """
        if not self.login(headless=headless):
            print("❌ Falha no login. Abortando criação de lista.")
            return None

        try:
            print(f"🔧 Iniciando criação da lista para o usuário: {username}")
            if not self.navegar_para_listas():
                return None
        
            wait = WebDriverWait(self.driver, 20)
        
            # --- PASSO 0: Clicar no botão de adicionar ---
            print("   - 0. Clicando no botão de adicionar...")
            add_button = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "button.v-btn--fab .mdi-plus")))
            self.driver.execute_script("arguments[0].click();", add_button)
        
            # --- PASSO 1: Digitar o Nome de Usuário ---
            print(f"   - 1. Preenchendo nome de usuário: '{username}'")
            username_field = wait.until(EC.visibility_of_element_located((
            By.XPATH,
            "//label[contains(text(), 'Nome do usuário')]/../input"
            )))
            username_field.send_keys(username)

            # --- PASSO 2: Selecionar o Plano de TV (CORRIGIDO) ---
            print("   - 2. Selecionando plano de TV...")

            # 1. Clica no campo do dropdown para abrir a lista de opções (esta parte já estava correta)
            plan_tv_dropdown = wait.until(EC.element_to_be_clickable((
                By.XPATH, 
                "//div[@role='button' and .//label[contains(text(), 'Selecione o plano de tv')]]"
            )))
            self.driver.execute_script("arguments[0].click();", plan_tv_dropdown)

            # 2. Espera a opção com o TEXTO EXATO aparecer e clica nela (ESTA É A PARTE CORRIGIDA)
            plan_tv_option = wait.until(EC.element_to_be_clickable((
                By.XPATH, 
                "//div[contains(@class, 'v-list-item__title') and normalize-space(text()) = 'Full HD + H265 + HD + SD + VOD + Adulto + LGBT']"
            )))
            self.driver.execute_script("arguments[0].click();", plan_tv_option)         

            # --- PASSO 3: Selecionar o Plano de Preço (CORRIGIDO E ROBUSTO) ---
            print("   - 3. Selecionando plano de preço (Basico)...")

            # 1. Clica no campo do dropdown para abrir a lista de opções
            plan_price_dropdown = wait.until(EC.element_to_be_clickable((           
            By.XPATH, 
            # Encontra o campo clicável que contém o label "Selecione o plano"
            "//div[@role='button' and .//label[contains(text(), 'Selecione o plano') and not(contains(text(), 'de tv'))]]"
            )))
            self.driver.execute_script("arguments[0].click();", plan_price_dropdown)

            # 2. Espera a opção com o texto exato "Basico, R$ 30,00" aparecer e clica nela
            plan_price_option = wait.until(EC.element_to_be_clickable((
                By.XPATH, 
                "//div[contains(@class, 'v-list-item__title') and normalize-space(text()) = 'Basico, R$ 30,00']"
            )))
            self.driver.execute_script("arguments[0].click();", plan_price_option)

            # --- PASSO 4: Configurar Conexões (Versão Final Robusta) ---
            print(f"   - 4. Configurando para {conexoes} conexão(ões)...")

            if 1 <= conexoes <= 10:
                # 1. Encontra o container principal do slider, que é o alvo para as teclas.
                slider = wait.until(EC.visibility_of_element_located((
                    By.XPATH,
                    "//div[contains(text(), 'Selecione a quantidade de conexões')]/following-sibling::div//div[@role='slider']"
                )))

                # 2. Encontra a "trilha" do slider (a barra) para clicar e ativar o componente.
                slider_track = wait.until(EC.element_to_be_clickable((
                    By.XPATH,
                    "//div[contains(text(), 'Selecione a quantidade de conexões')]/following-sibling::div//div[contains(@class, 'v-slider__track-container')]"
                )))

                # 3. CLICA na trilha para garantir que o slider está focado.
                # Usamos JavaScript para um clique mais confiável.
                self.driver.execute_script("arguments[0].click();", slider_track)
                time.sleep(0.3)

                # 4. Obtém o valor inicial do slider.
                try:
                    current_value = int(slider.get_attribute('aria-valuenow'))
                except (ValueError, TypeError):
                    current_value = 0

                # 5. Calcula quantos passos para a direita o robô precisa dar.
                steps_to_move = conexoes - current_value
    
                # 6. Pressiona a seta para a direita o número de vezes necessário.
                if steps_to_move > 0:
                    print(f"   - Movendo o slider {steps_to_move} vez(es) para a direita...")
                    for _ in range(steps_to_move):
                        slider.send_keys(Keys.ARROW_RIGHT)
                        time.sleep(0.1)

            else:
                print(f"AVISO: Número de conexões '{conexoes}' inválido. Deixando o valor padrão.")

            # --- PASSO 5: Selecionar a Validade em Meses (CORRIGIDO E ROBUSTO) ---
            print(f"   - 5. Selecionando validade de {duracao_meses} mês(es)...")

            # 1. Clica no campo do dropdown para abrir a lista de opções
            validade_dropdown = wait.until(EC.element_to_be_clickable((
                By.XPATH,
                # Seletor refinado para encontrar o campo clicável pela sua função e texto
                "//div[@role='button' and .//label[contains(text(), 'Selecione a validade')]]"
            )))
            self.driver.execute_script("arguments[0].click();", validade_dropdown)

            # 2. Espera a opção desejada aparecer e clica nela
            if 1 <= duracao_meses <= 12:
                # Determina o texto correto (singular ou plural)
                texto_opcao = f"{duracao_meses} Mês" if duracao_meses == 1 else f"{duracao_meses} Meses"
                
                mes_option = wait.until(EC.element_to_be_clickable((
                    By.XPATH,
                    f"//div[contains(@class, 'v-list-item__title') and normalize-space(text()) = '{texto_opcao}']"
                )))
                self.driver.execute_script("arguments[0].click();", mes_option)
            else:
                print(f"AVISO: Duração '{duracao_meses}' inválida. Deixando o valor padrão.")

            # --- PASSO 6: Clicar no Botão "Criar" ---
            print("   - 6. Clicando no botão 'Criar'...")
            criar_button = wait.until(EC.element_to_be_clickable((
                By.XPATH,
                "//div[contains(@class, 'v-dialog--active')]//span[normalize-space(text())='Criar']/parent::button"
            )))
            self.driver.execute_script("arguments[0].click();", criar_button)
            
            # --- PASSO 7: Extrair os Dados da Lista Criada ---
            # A função auxiliar fará a espera e a extração
            dados_finais = self._extrair_dados_lista(wait)
        
            if dados_finais:
                print(f"\n🎉 SUCESSO! Lista para '{dados_finais.get('usuario', username)}' foi criada e dados foram capturados.")
                return dados_finais
            else:
                print("\n⚠️ AVISO: A lista pode ter sido criada, mas não foi possível capturar os dados da página de confirmação.")
                return {"status": "parcial", "usuario": username, "mensagem": "Lista criada, mas falha ao capturar dados."}

        except TimeoutException as e:
            print(f"❌ ERRO DE AUTOMAÇÃO (TIMEOUT): Um elemento não foi encontrado a tempo. Verifique o seletor ou a velocidade da sua internet. Erro: {e}")
            self.driver.save_screenshot('erro_timeout.png')
            print("   - Screenshot 'erro_timeout.png' salvo para análise.")
            return None
        except Exception as e:
            print(f"❌ ERRO INESPERADO ao criar lista: {e}")
            self.driver.save_screenshot('erro_inesperado.png')
            print("   - Screenshot 'erro_inesperado.png' salvo para análise.")
            return None

    def renovar_lista(self, username: str, duracao_meses: int, headless=False) -> dict:
        """
        Busca um usuário pelo nome e renova sua assinatura.
        CORRIGIDO: Agora captura e retorna as informações atualizadas da lista.
        """
        if not self.login(headless=headless):
            print("❌ Falha no login. Abortando renovação.")
            return {"erro": "Falha no login"}

        try:
            print(f"🔄 Renovando lista para o usuário: {username} por {duracao_meses} mês(es)")
            if not self.navegar_para_listas():
                return {"erro": "Falha ao navegar para listas"}

            wait = WebDriverWait(self.driver, 20)

            # --- PASSO 1: Buscar pelo usuário ---
            print(f"   - 1. Buscando usuário '{username}' na lista...")
            search_field = wait.until(EC.visibility_of_element_located((
                By.XPATH,
                "//label[contains(text(), 'Buscar por nome')]/following-sibling::input"
             )))
            search_field.click()
            search_field.clear()
            search_field.send_keys(username)
            search_field.send_keys(Keys.ENTER)
            time.sleep(2)  # tempo para a tabela atualizar

            # --- PASSO 2a: Clicar no menu sanduíche do usuário ---
            print("   - 2a. Clicando no menu sanduíche do usuário...")
            menu_button = wait.until(EC.element_to_be_clickable((       
                By.XPATH,
                f"//td[normalize-space(text())='{username}']/following-sibling::td//i[contains(@class,'mdi-dots-vertical')]"
            )))
            self.driver.execute_script("arguments[0].click();", menu_button)

            # --- PASSO 2b: Clicar na opção "Renovar" no menu aberto ---
            print("   - 2b. Clicando na opção 'Renovar'...")
            renovar_option = wait.until(EC.element_to_be_clickable((
                By.XPATH,
                "//div[@role='menuitem']//div[contains(@class,'v-list-item__title') and normalize-space(text())='Renovar']"
            )))
            self.driver.execute_script("arguments[0].click();", renovar_option)
            
            # --- PASSO 3: Selecionar plano ---
            print("   - 3. Selecionando plano de preço (Basico)...")
            plan_price_dropdown = wait.until(EC.element_to_be_clickable((
                 By.XPATH,
                "//div[@role='button' and .//label[contains(text(), 'Selecione o plano') and not(contains(text(), 'de tv'))]]"
            )))
            self.driver.execute_script("arguments[0].click();", plan_price_dropdown)

            plan_price_option = wait.until(EC.element_to_be_clickable((
                By.XPATH,
                "//div[contains(@class, 'v-list-item__title') and normalize-space(text()) = 'Basico, R$ 30,00']"
            )))
            self.driver.execute_script("arguments[0].click();", plan_price_option)
            
            # --- PASSO 4: Selecionar validade ---
            print(f"   - 4. Selecionando validade de {duracao_meses} mês(es)...")
            validade_dropdown = wait.until(EC.element_to_be_clickable((
                By.XPATH,
                "//div[@role='button' and .//label[contains(text(), 'Selecione a validade')]]"
            )))
            self.driver.execute_script("arguments[0].click();", validade_dropdown)

            texto_opcao = f"{duracao_meses} Mês" if duracao_meses == 1 else f"{duracao_meses} Meses"
            mes_option = wait.until(EC.element_to_be_clickable((
                By.XPATH,
                f"//div[contains(@class, 'v-list-item__title') and normalize-space(text()) = '{texto_opcao}']"
            )))
            self.driver.execute_script("arguments[0].click();", mes_option)

            # --- PASSO 5: Clicar no botão Renovar ---
            print("   - 5. Salvando alterações...")
            renovar_button = wait.until(EC.element_to_be_clickable((
                By.XPATH,
                "//div[contains(@class, 'v-dialog--active')]//span[normalize-space(text())='Renovar']/parent::button"
            )))
            self.driver.execute_script("arguments[0].click();", renovar_button)
            
            # --- PASSO 6: Extrair os Dados da Lista Renovada ---
            print("   - 6. Capturando informações atualizadas da lista...")
            dados_finais = self._extrair_dados_lista(wait)
        
            if dados_finais:
                print(f"\n🎉 SUCESSO! Lista '{username}' foi renovada e dados foram capturados.")
                return dados_finais
            else:
                print("\n⚠️ AVISO: A lista pode ter sido renovada, mas não foi possível capturar os dados da página de confirmação.")
                return {"status": "parcial", "usuario": username, "mensagem": "Renovação enviada, mas falha ao capturar dados."}

        except TimeoutException as e:
            print(f"❌ ERRO DE AUTOMAÇÃO (TIMEOUT): Um elemento não foi encontrado a tempo. Erro: {e}")
            self.driver.save_screenshot('erro_timeout_renovacao.png')
            return {"erro": f"Timeout: {str(e)}"}
        except Exception as e:
            print(f"❌ ERRO INESPERADO ao renovar lista: {e}")
            self.driver.save_screenshot('erro_renovacao.png')
            return {"erro": f"Erro inesperado: {str(e)}"}

    def sincronizar_dados_usuario(self, username: str, headless=True) -> dict:
        """
        Busca um usuário pelo nome e captura suas informações atualizadas.
        VERSÃO MELHORADA com logs detalhados
        """
        if not self.login(headless=headless):
            print("❌ Falha no login. Abortando sincronização.")
            return {"erro": "Falha no login"}

        try:
            print(f"🔄 Sincronizando dados do usuário: {username}")
            if not self.navegar_para_listas():
                return {"erro": "Falha ao navegar para listas"}

            wait = WebDriverWait(self.driver, 20)

            # --- PASSO 1: Buscar pelo usuário ---
            print(f"   - 1. Buscando usuário '{username}' na lista...")
            
            try:
                search_field = wait.until(EC.visibility_of_element_located((
                    By.XPATH,
                    "//label[contains(text(), 'Buscar por nome')]/following-sibling::input"
                )))
                search_field.click()
                search_field.clear()
                search_field.send_keys(username)
                search_field.send_keys(Keys.ENTER)
                time.sleep(3)  # tempo para a tabela atualizar
                print(f"   - Busca realizada, aguardando resultados...")
            except TimeoutException:
                print(f"   - ❌ Campo de busca não encontrado")
                return {"erro": "Campo de busca não encontrado"}

            # Verificar se o usuário apareceu nos resultados
            try:
                usuario_na_tabela = self.driver.find_element(
                    By.XPATH,
                    f"//td[normalize-space(text())='{username}']"
                )
                print(f"   - ✅ Usuário encontrado na tabela")
            except NoSuchElementException:
                print(f"   - ❌ Usuário '{username}' não encontrado nos resultados")
                return {"erro": f"Usuário '{username}' não encontrado"}

            # --- PASSO 2a: Clicar no menu sanduíche do usuário ---
            print("   - 2a. Clicando no menu sanduíche do usuário...")
            try:
                menu_button = wait.until(EC.element_to_be_clickable((       
                    By.XPATH,
                    f"//td[normalize-space(text())='{username}']/following-sibling::td//i[contains(@class,'mdi-dots-vertical')]"
                )))
                self.driver.execute_script("arguments[0].click();", menu_button)
                print(f"   - ✅ Menu aberto")
            except TimeoutException:
                print(f"   - ❌ Menu sanduíche não encontrado")
                return {"erro": "Menu não encontrado"}

            # --- PASSO 2b: Clicar na opção "Ver informações" no menu aberto ---
            print("   - 2b. Clicando na opção 'Ver informações'...")
            try:
                ver_info_option = wait.until(EC.element_to_be_clickable((
                    By.XPATH,
                    "//a[contains(@class, 'v-list-item--link') and .//div[contains(@class,'v-list-item__title') and normalize-space(text())='Ver informações']]"
                )))
                self.driver.execute_script("arguments[0].click();", ver_info_option)
                print(f"   - ✅ Navegando para página de informações")
            except TimeoutException:
                print(f"   - ❌ Opção 'Ver informações' não encontrada")
                return {"erro": "Opção 'Ver informações' não encontrada"}
            
            # --- PASSO 3: Extrair os Dados da Lista ---
            print("   - 3. Aguardando e capturando informações da lista...")
            dados_finais = self._extrair_dados_lista(wait)
        
            if dados_finais:
                print(f"\n✅ SUCESSO! Dados do usuário '{username}' sincronizados.")
                print(f"📊 Dados capturados: {dados_finais}")
                return dados_finais
            else:
                print(f"\n⚠️ AVISO: Não foi possível capturar os dados da página de informações.")
                return {"erro": "Falha ao capturar dados da página"}

        except TimeoutException as e:
            print(f"❌ ERRO DE AUTOMAÇÃO (TIMEOUT): Um elemento não foi encontrado a tempo. Erro: {e}")
            
            # Salvar screenshot para debug
            try:
                screenshot_name = f'erro_timeout_sync_{username}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
                self.driver.save_screenshot(screenshot_name)
                print(f"   - Screenshot '{screenshot_name}' salvo para análise.")
            except:
                pass
            
            return {"erro": f"Timeout: {str(e)}"}
        except Exception as e:
            print(f"❌ ERRO INESPERADO ao sincronizar dados: {e}")
            
            # Salvar screenshot para debug
            try:
                screenshot_name = f'erro_sync_{username}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
                self.driver.save_screenshot(screenshot_name)
                print(f"   - Screenshot '{screenshot_name}' salvo para análise.")
            except:
                pass
            
            import traceback
            traceback.print_exc()
            
            return {"erro": f"Erro inesperado: {str(e)}"}
        
        finally:
            # Não fechar o driver aqui se for reutilizado
            pass
    
    def close(self):
        if self.driver:
            try:
                self.driver.quit()
                print("🚪 Navegador fechado.")
            finally:
                self.driver = None
                self.is_logged_in = False

# --- Bloco de Execução Principal ---
if __name__ == "__main__":  
    manager = None
    try:
        manager = BitPanelManager()
        
        # Teste com interface gráfica para debug
        print("🧪 Testando conexão com BitPanel...")
        if manager.verificar_conexao(headless=False):
            print("\n--- Teste de Navegação ---")
            print("✅ Conexão estabelecida!")
            print("🔍 Verifique se consegue acessar a página /list sem popups")
            
            input("\nPressione Enter para continuar com teste de criação (opcional)...")
            
            # Teste opcional de criação
            criar_teste = input("Quer testar criação de lista? (s/N): ").lower().strip()
            if criar_teste == 's':
                nova_lista = manager.criar_lista(username="teste_popup", conexoes=1, duracao_meses=1, headless=False)
                if nova_lista:
                    print(f"\n✅ Lista criada: {nova_lista}")
        else:
            print("❌ Falha na conexão")

    except Exception as e:
        print(f"Ocorreu um erro: {e}")
    finally:
        if manager and input("\nFechar navegador? (s/N): ").lower().strip() == 's':
            manager.close()

