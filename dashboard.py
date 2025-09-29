# dashboard.py - Dashboard ULTRA OTIMIZADO com logs de depuração e anti-cache
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, render_template_string, make_response
from datetime import datetime, timedelta
import json
from config import Config
from database import db
from whatsapp_bot import broadcast_para_clientes_ativos, broadcast_para_todos_clientes
from mercpag import mercado_pago
from bitpanel_automation import BitPanelManager
import time

app = Flask(__name__)
app.secret_key = Config.SECRET_KEY

# Template para redirecionamento com JavaScript ULTRA ROBUSTO
REDIRECT_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Redirecionando...</title>
    <meta charset="utf-8">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
</head>
<body>
    <div style="text-align: center; padding: 50px; font-family: Arial, sans-serif;">
        <h3>{{ message }}</h3>
        <p>Redirecionando em <span id="countdown">3</span> segundos...</p>
        <script>
            console.log("🔄 Iniciando redirecionamento para: {{ url }}");
            
            let countdown = 3;
            const countdownElement = document.getElementById('countdown');
            
            const timer = setInterval(function() {
                countdown--;
                countdownElement.textContent = countdown;
                
                if (countdown <= 0) {
                    clearInterval(timer);
                    
                    // Força limpeza de cache e redirecionamento
                    const timestamp = new Date().getTime();
                    const targetUrl = "{{ url }}?_cache_bust=" + timestamp + "&_force_reload=1";
                    
                    console.log("🚀 Redirecionando para:", targetUrl);
                    
                    // Múltiplas estratégias para forçar recarregamento
                    window.location.replace(targetUrl);
                    
                    // Fallback após 1 segundo
                    setTimeout(function() {
                        window.location.href = targetUrl;
                    }, 1000);
                }
            }, 1000);
        </script>
    </div>
</body>
</html>
"""

def add_no_cache_headers(response):
    """Adiciona headers para desabilitar cache completamente"""
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    response.headers['Last-Modified'] = datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')
    response.headers['ETag'] = str(int(time.time()))
    return response

@app.after_request
def after_request(response):
    """Aplicar headers anti-cache em todas as respostas"""
    return add_no_cache_headers(response)

@app.route("/")
def index():
    """Página inicial - Dashboard"""
    try:
        print("🏠 [DEBUG] Carregando página inicial do dashboard...")
        
        # Obter estatísticas
        stats = db.get_estatisticas()
        print(f"📊 [DEBUG] Estatísticas obtidas: {stats}")
        
        # Dados extras para o dashboard
        stats["link_atual"] = db.get_config("link_acesso", Config.LINK_ACESSO_DEFAULT)
        stats["preco_mes"] = db.get_config("preco_mes", str(Config.PRECO_MES_DEFAULT))
        stats["preco_conexao"] = db.get_config("preco_conexao", str(Config.PRECO_CONEXAO_DEFAULT))
        
        response = make_response(render_template("dashboard.html", stats=stats))
        return add_no_cache_headers(response)
        
    except Exception as e:
        print(f"❌ [DEBUG] Erro ao carregar dashboard: {str(e)}")
        flash(f"Erro ao carregar dashboard: {str(e)}", "error")
        response = make_response(render_template("dashboard.html", stats={}))
        return add_no_cache_headers(response)

@app.route("/clientes")
def listar_clientes():
    """Listar todos os clientes"""
    try:
        print("👥 [DEBUG] Carregando lista de clientes...")
        
        conn = db.get_connection()
        clientes = conn.execute("""
            SELECT c.*, 
                   CASE 
                       WHEN c.data_expiracao > datetime("now") THEN "Ativo"
                       WHEN c.data_expiracao IS NULL THEN "Sem Lista"
                       ELSE "Expirado"
                   END as status_lista
            FROM clientes c
            ORDER BY c.created_at DESC  
            """).fetchall()
        conn.close()
        
        clientes_list = []
        for cliente in clientes:
            cliente_dict = dict(cliente)
            clientes_list.append(cliente_dict)
        
        print(f"👥 [DEBUG] {len(clientes_list)} clientes carregados")
        
        # Log dos primeiros 3 clientes para depuração
        for i, cliente in enumerate(clientes_list[:3]):
            print(f"👤 [DEBUG] Cliente {i+1}: {cliente.get('nome', 'N/A')} - {cliente.get('usuario_iptv', 'N/A')} - Status: {cliente.get('status_lista', 'N/A')}")
        
        response = make_response(render_template("clientes.html", clientes=clientes_list))
        return add_no_cache_headers(response)
        
    except Exception as e:
        print(f"❌ [DEBUG] Erro ao listar clientes: {str(e)}")
        flash(f"Erro ao listar clientes: {str(e)}", "error")
        return redirect(url_for("index"))
    
    
@app.route("/api/contar-clientes/<tipo>")
def api_contar_clientes(tipo):
    """API para obter a contagem de clientes por tipo para a página de avisos."""
    try:
        conn = db.get_connection()
        count = 0
        
        if tipo == "ativos":
            # Conta clientes com data de expiração no futuro
            result = conn.execute('SELECT COUNT(*) FROM clientes WHERE data_expiracao > ?', (datetime.now(),)).fetchone()
            count = result[0] if result else 0
            
        elif tipo == "expirando":
            # Conta clientes expirando nos próximos 7 dias
            data_limite = datetime.now() + timedelta(days=7)
            result = conn.execute('SELECT COUNT(*) FROM clientes WHERE data_expiracao BETWEEN ? AND ?', (datetime.now(), data_limite)).fetchone()
            count = result[0] if result else 0
            
        elif tipo == "todos":
            # Conta todos os clientes que possuem um número de telefone
            result = conn.execute('SELECT COUNT(DISTINCT telefone) FROM clientes WHERE telefone IS NOT NULL').fetchone()
            count = result[0] if result else 0
            
        else:
            conn.close()
            return jsonify({"error": "Tipo inválido"}), 400
            
        conn.close()
        return jsonify({"count": count})

    except Exception as e:
        print(f"❌ [API COUNT] Erro ao contar clientes: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/clientes/gerenciar/<usuario_iptv>")
def gerenciar_cliente(usuario_iptv):
    """Página para gerenciar um cliente específico - APENAS DADOS LOCAIS"""
    try:
        print(f"⚙️ [DEBUG] Carregando gerenciamento do cliente: {usuario_iptv}")
        
        cliente = db.buscar_cliente_por_usuario_iptv(usuario_iptv)
        if not cliente:
            print(f"❌ [DEBUG] Cliente {usuario_iptv} não encontrado")
            flash("Cliente não encontrado", "error")
            return redirect(url_for("listar_clientes"))
        
        print(f"✅ [DEBUG] Cliente encontrado: {cliente}")
        
        # Adicionamos a função now() para ser usada no template
        def get_now():
            return datetime.now()

        # Convertendo as strings de data do banco para objetos datetime
        if cliente.get("data_expiracao"):
            cliente["data_expiracao_obj"] = datetime.fromisoformat(cliente["data_expiracao"])
        
        response = make_response(render_template("gerenciar_cliente.html", cliente=cliente, now=get_now))
        return add_no_cache_headers(response)
    
    except Exception as e:
        print(f"❌ [DEBUG] Erro ao carregar dados do cliente: {str(e)}")
        flash(f"Erro ao carregar dados do cliente: {str(e)}", "error")
        return redirect(url_for("listar_clientes"))


@app.route("/api/cliente/<usuario_iptv>/info")
def api_cliente_info(usuario_iptv):
    """API para obter informações atualizadas de um cliente específico"""
    try:
        cliente = db.buscar_cliente_por_usuario_iptv(usuario_iptv)
        if cliente:
            # Adicionar informações extras
            if cliente.get('data_expiracao'):
                try:
                    data_exp = datetime.fromisoformat(cliente['data_expiracao'])
                    dias_restantes = (data_exp - datetime.now()).days
                    cliente['dias_restantes'] = dias_restantes
                    cliente['status_calculado'] = 'ativo' if dias_restantes > 0 else 'expirado'
                except:
                    cliente['dias_restantes'] = None
                    cliente['status_calculado'] = 'indefinido'
            
            cliente['timestamp_consulta'] = datetime.now().isoformat()
            
            response = make_response(jsonify(cliente))
            return add_no_cache_headers(response)
        else:
            response = make_response(jsonify({"error": "Cliente não encontrado"}), 404)
            return add_no_cache_headers(response)
    except Exception as e:
        response = make_response(jsonify({"error": str(e)}), 500)
        return add_no_cache_headers(response)

@app.route("/clientes/sincronizar/<usuario_iptv>", methods=["POST"])
def sincronizar_cliente(usuario_iptv):
    """
    Sincroniza dados do cliente com o BitPanel - VERSÃO CORRIGIDA
    """
    try:
        print(f"🔄 [SYNC] Iniciando sincronização do cliente: {usuario_iptv}")
        
        # Verificar se cliente existe no banco local
        cliente_local = db.buscar_cliente_por_usuario_iptv(usuario_iptv)
        if not cliente_local:
            print(f"❌ [SYNC] Cliente {usuario_iptv} não encontrado no banco local")
            flash(f"Cliente {usuario_iptv} não encontrado", "error")
            return redirect(url_for("listar_clientes"))
        
        print(f"📋 [SYNC] Cliente local antes da sync: {cliente_local}")
        
        from bitpanel_automation import BitPanelManager
        
        manager = BitPanelManager()
        
        # Fazer login no BitPanel
        if not manager.login(headless=True):
            print(f"❌ [SYNC] Falha no login do BitPanel")
            flash("Erro ao conectar com o BitPanel", "error")
            return redirect(url_for("gerenciar_cliente", usuario_iptv=usuario_iptv))
        
        # Sincronizar dados do usuário
        dados_sync = manager.sincronizar_dados_usuario(usuario_iptv, headless=True)
        print(f"📥 [SYNC] Dados recebidos do BitPanel: {dados_sync}")
        
        if "erro" in dados_sync:
            print(f"❌ [SYNC] Erro na sincronização: {dados_sync['erro']}")
            flash(f"Erro na sincronização: {dados_sync['erro']}", "error")
            manager.close()
            return redirect(url_for("gerenciar_cliente", usuario_iptv=usuario_iptv))
        
        # ATUALIZAR O BANCO DE DADOS
        print(f"💾 [SYNC] Salvando dados no banco...")
        sucesso = db.atualizar_dados_sincronizados(usuario_iptv, dados_sync)
        
        if sucesso:
            print(f"✅ [SYNC] Dados salvos com sucesso!")
            
            # VERIFICAR SE OS DADOS FORAM REALMENTE SALVOS
            cliente_atualizado = db.buscar_cliente_por_usuario_iptv(usuario_iptv)
            print(f"🔍 [SYNC] Cliente após atualização: {cliente_atualizado}")
            
            # COMPARAR ANTES E DEPOIS
            mudancas = []
            if cliente_local.get('data_expiracao') != cliente_atualizado.get('data_expiracao'):
                mudancas.append(f"Data exp: {cliente_local.get('data_expiracao')} → {cliente_atualizado.get('data_expiracao')}")
            if cliente_local.get('conexoes') != cliente_atualizado.get('conexoes'):
                mudancas.append(f"Conexões: {cliente_local.get('conexoes')} → {cliente_atualizado.get('conexoes')}")
            if cliente_local.get('senha_iptv') != cliente_atualizado.get('senha_iptv'):
                mudancas.append("Senha atualizada")
            
            if mudancas:
                print(f"📊 [SYNC] Mudanças detectadas: {mudancas}")
                flash(f"Dados sincronizados com sucesso! Mudanças: {'; '.join(mudancas)}", "success")
            else:
                print(f"ℹ️ [SYNC] Nenhuma mudança detectada - dados já estavam atualizados")
                flash(f"Dados sincronizados - nenhuma mudança necessária", "info")
            
            # FORÇAR RECARREGAMENTO COM CACHE BUSTING
            timestamp = int(time.time())
            redirect_url = url_for("listar_clientes") + f"?sync_success={timestamp}&user={usuario_iptv}"
            
            manager.close()
            
            # Usar template JavaScript para forçar recarregamento TOTAL
            return render_template_string(f"""
<!DOCTYPE html>
<html>
<head>
    <title>Sincronização Concluída</title>
    <meta charset="utf-8">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
</head>
<body>
    <div style="text-align: center; padding: 50px; font-family: Arial, sans-serif;">
        <h3>✅ Sincronização concluída com sucesso!</h3>
        <p>Cliente <strong>{usuario_iptv}</strong> foi sincronizado.</p>
        <p>Redirecionando e atualizando dashboard...</p>
        <script>
            console.log("🔄 Forçando reload completo do dashboard...");
            
            // Limpar todos os caches possíveis
            if ('caches' in window) {{
                caches.keys().then(names => {{
                    names.forEach(name => {{
                        caches.delete(name);
                    }});
                }});
            }}
            
            // Forçar reload com múltiplas estratégias
            const timestamp = new Date().getTime();
            const url = "{redirect_url}&_t=" + timestamp;
            
            setTimeout(() => {{
                window.location.replace(url);
            }}, 1000);
            
            // Fallback
            setTimeout(() => {{
                window.location.href = url;
            }}, 2000);
        </script>
    </div>
</body>
</html>
            """)
            
        else:
            print(f"❌ [SYNC] Falha ao salvar dados no banco")
            flash(f"Falha ao salvar dados sincronizados no banco", "error")
        
        manager.close()
        
    except Exception as e:
        print(f"❌ [SYNC] Erro crítico na sincronização: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f"Erro na sincronização: {str(e)}", "error")
        db.log_sistema("erro", f"Erro sincronização {usuario_iptv}: {str(e)}")
    
    return redirect(url_for("gerenciar_cliente", usuario_iptv=usuario_iptv))


@app.route("/clientes/editar/<usuario_iptv>", methods=["POST"])
def editar_cliente_route(usuario_iptv):
    """
    Edita dados do cliente APENAS NO BANCO DE DADOS LOCAL.
    Esta função NÃO se comunica com o BitPanel.
    """
    try:
        print(f"✏️ [DEBUG] Editando cliente: {usuario_iptv}")
        
        # Obter dados do formulário da página "gerenciar_cliente.html"
        conexoes = request.form.get("conexoes")
        meses = request.form.get("meses", type=int)
        nome = request.form.get("nome", "").strip()
        
        print(f"📝 [DEBUG] Dados do formulário - Nome: {nome}, Conexões: {conexoes}, Meses: {meses}")
        
        novos_dados_banco = {}
        
        # Atualiza o nome, se foi preenchido
        if nome:
            novos_dados_banco["nome"] = nome

        # Atualiza o número de conexões, se foi preenchido
        if conexoes and conexoes.isdigit():
            novos_dados_banco["conexoes"] = int(conexoes)
        
        # Adiciona meses à data de expiração, se foi preenchido
        if meses and meses > 0:
            cliente_atual = db.buscar_cliente_por_usuario_iptv(usuario_iptv)
            data_base = datetime.now()
            
            if cliente_atual and cliente_atual.get("data_expiracao"):
                try:
                    # Usa a data de expiração atual como base se ela ainda for válida
                    data_expiracao_atual = datetime.fromisoformat(cliente_atual["data_expiracao"])
                    if data_expiracao_atual > data_base:
                        data_base = data_expiracao_atual
                except:
                    pass # Usa a data de hoje se a data antiga for inválida
            
            nova_expiracao = data_base + timedelta(days=30 * meses)
            novos_dados_banco["data_expiracao"] = nova_expiracao
            novos_dados_banco["status"] = "ativo" # Garante que a lista seja marcada como ativa
        
        print(f"💾 [DEBUG] Dados para atualizar: {novos_dados_banco}")
        
        # Se houver dados para atualizar, salva no banco
        if novos_dados_banco:
            if db.atualizar_cliente_manual(usuario_iptv, novos_dados_banco):
                print(f"✅ [DEBUG] Cliente atualizado com sucesso!")
                
                # Verificar se os dados foram realmente salvos
                cliente_atualizado = db.buscar_cliente_por_usuario_iptv(usuario_iptv)
                print(f"🔍 [DEBUG] Cliente após edição: {cliente_atualizado}")
                
                # Usar template JavaScript para forçar recarregamento
                return render_template_string(REDIRECT_TEMPLATE, 
                    message=f"Cliente {usuario_iptv} atualizado com sucesso!",
                    url=url_for("listar_clientes"))
            else:
                print(f"❌ [DEBUG] Falha ao salvar alterações no banco")
                flash("Falha ao salvar alterações no banco local.", "error")
        else:
            print(f"ℹ️ [DEBUG] Nenhuma alteração foi feita")
            flash("Nenhuma alteração foi feita.", "info")
    
    except Exception as e:
        print(f"❌ [DEBUG] Erro ao editar cliente: {str(e)}")
        flash(f"Erro ao editar cliente: {str(e)}", "error")
    
    return redirect(url_for("gerenciar_cliente", usuario_iptv=usuario_iptv))

@app.route("/clientes/excluir/<usuario_iptv>", methods=["POST"])
def excluir_cliente_route(usuario_iptv):
    """Exclui cliente APENAS do banco local - NÃO MEXE NO BITPANEL"""
    try:
        print(f"🗑️ [DEBUG] Excluindo cliente: {usuario_iptv}")
        
        # Excluir apenas do banco local
        excluido_banco = db.excluir_cliente(usuario_iptv)
        
        if excluido_banco:
            print(f"✅ [DEBUG] Cliente excluído com sucesso!")
            
            # Usar template JavaScript para forçar recarregamento
            return render_template_string(REDIRECT_TEMPLATE, 
                message=f"Cliente {usuario_iptv} excluído com sucesso!",
                url=url_for("listar_clientes"))
        else:
            print(f"❌ [DEBUG] Falha ao excluir cliente do banco")
            flash(f"Falha ao excluir cliente {usuario_iptv} do banco local", "error")
    
    except Exception as e:
        print(f"❌ [DEBUG] Erro ao excluir cliente: {str(e)}")
        flash(f"Erro ao excluir cliente: {str(e)}", "error")
        db.log_sistema("erro", f"Erro excluir local {usuario_iptv}: {str(e)}")
    
    return redirect(url_for("listar_clientes"))

@app.route("/clientes/adicionar", methods=["GET", "POST"])
def adicionar_cliente():
    """Adicionar cliente manualmente"""
    if request.method == "POST":
        try:
            print(f"➕ [DEBUG] Adicionando novo cliente...")
            
            telefone = request.form["telefone"].strip()
            nome = request.form.get("nome", "").strip() or None
            usuario_iptv = request.form.get("usuario_iptv", "").strip() or None
            senha_iptv = request.form.get("senha_iptv", "").strip() or None
            conexoes = int(request.form.get("conexoes", 1))
            meses = int(request.form.get("meses", 1))

            print(f"📝 [DEBUG] Dados do novo cliente - Telefone: {telefone}, Nome: {nome}, Usuário: {usuario_iptv}")

            if not telefone:
                flash("O campo Telefone é obrigatório.", "error")
                return render_template("adicionar_cliente.html")

            conn = db.get_connection()
            try:
                # A única verificação necessária é se o nome de usuário IPTV já existe
                if usuario_iptv:
                    existe = conn.execute("SELECT id FROM clientes WHERE usuario_iptv = ?", (usuario_iptv,)).fetchone()
                    if existe:
                        flash(f"O usuário IPTV \"{usuario_iptv}\" já está em uso. Por favor, escolha outro.", "error")
                        return render_template("adicionar_cliente.html")

                # Insere o novo registro do cliente/lista
                cursor = conn.execute("""
                    INSERT INTO clientes (telefone, nome, usuario_iptv, senha_iptv, conexoes, status)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (telefone, nome, usuario_iptv, senha_iptv, conexoes, "manual"))
                cliente_id = cursor.lastrowid

                # Se os detalhes da lista foram fornecidos, calcula a data de expiração
                if usuario_iptv and senha_iptv:
                    data_criacao = datetime.now()
                    data_expiracao = data_criacao + timedelta(days=30 * meses)
                    conn.execute("""
                        UPDATE clientes 
                        SET data_criacao = ?, data_expiracao = ?, status = "ativo"
                        WHERE id = ?
                    """, (data_criacao, data_expiracao, cliente_id))
                
                conn.commit()
                
                print(f"✅ [DEBUG] Cliente adicionado com sucesso! ID: {cliente_id}")
                
                # Usar template JavaScript para forçar recarregamento
                return render_template_string(REDIRECT_TEMPLATE, 
                    message=f"Cliente/Lista para o telefone {telefone} adicionado com sucesso!",
                    url=url_for("listar_clientes"))

            finally:
                conn.close()

        except Exception as e:
            print(f"❌ [DEBUG] Erro ao adicionar cliente: {str(e)}")
            flash(f"Ocorreu um erro ao adicionar o cliente: {str(e)}", "error")
            return render_template("adicionar_cliente.html")

    # Método GET: apenas exibe o formulário
    response = make_response(render_template("adicionar_cliente.html"))
    return add_no_cache_headers(response)

@app.route("/configuracoes", methods=["GET", "POST"])
def configuracoes():
    """Página de configurações"""
    try:
        config = {
            "link_acesso": db.get_config("link_acesso", Config.LINK_ACESSO_DEFAULT),
            "preco_mes": db.get_config("preco_mes", str(Config.PRECO_MES_DEFAULT)),
            "preco_conexao": db.get_config("preco_conexao", str(Config.PRECO_CONEXAO_DEFAULT))
        }
        response = make_response(render_template("configuracoes.html", config=config))
        return add_no_cache_headers(response)
    except Exception as e:
        flash(f"Erro ao carregar configurações: {str(e)}", "error")
        return redirect(url_for("index"))

@app.route("/atualizar-link", methods=["POST"])
def atualizar_link():
    """Atualizar link de acesso"""
    try:
        link_acesso = request.form["link_acesso"].strip()
        if link_acesso:
            db.set_config("link_acesso", link_acesso, "Link de acesso IPTV")
            flash("Link atualizado com sucesso!", "success")
        else:
            flash("Link não pode estar vazio", "error")
    except Exception as e:
        flash(f"Erro ao atualizar link: {str(e)}", "error")
    
    return redirect(url_for("configuracoes"))

@app.route("/atualizar-precos", methods=["POST"])
def atualizar_precos():
    """Atualizar preços"""
    try:
        preco_mes = request.form["preco_mes"].strip()
        preco_conexao = request.form["preco_conexao"].strip()
        
        if preco_mes:
            db.set_config("preco_mes", preco_mes, "Preço por mês")
        if preco_conexao:
            db.set_config("preco_conexao", preco_conexao, "Preço por conexão extra")
            
        flash("Preços atualizados com sucesso!", "success")
    except Exception as e:
        flash(f"Erro ao atualizar preços: {str(e)}", "error")
    
    return redirect(url_for("configuracoes"))

@app.route("/avisos")
def avisos():
    """Página de envio de avisos"""
    response = make_response(render_template("avisos.html"))
    return add_no_cache_headers(response)

@app.route("/enviar-aviso", methods=["POST"])
def enviar_aviso():
    """Enviar aviso para clientes"""
    try:
        tipo = request.form["tipo"]
        mensagem = request.form["mensagem"].strip()
        
        if not mensagem:
            flash("Mensagem não pode estar vazia", "error")
            return redirect(url_for("avisos"))
        
        if tipo == "ativos":
            sucesso, erro = broadcast_para_clientes_ativos(mensagem)
            tipo_desc = "clientes ativos"
        elif tipo == "expirando":
            from whatsapp_bot import broadcast_para_clientes_expirando
            sucesso, erro = broadcast_para_clientes_expirando(mensagem, 7)
            tipo_desc = "clientes expirando"
        elif tipo == "todos":
            sucesso, erro = broadcast_para_todos_clientes(mensagem)
            tipo_desc = "todos os clientes"
        else:
            flash("Tipo de envio inválido", "error")
            return redirect(url_for("avisos"))
        
        if sucesso > 0:
            flash(f"Aviso enviado para {sucesso} {tipo_desc}. {erro} falhas.", "success")
        else:
            flash(f"Nenhum aviso foi enviado. {erro} falhas.", "error")
        
        return redirect(url_for("avisos"))
        
    except Exception as e:
        flash(f"Erro ao enviar aviso: {str(e)}", "error")
        return redirect(url_for("avisos"))

@app.route("/clientes/sincronizacao")
def relatorio_sincronizacao():
    """Página com o relatório de sincronização dos clientes."""
    try:
        # Usar a nova função que retorna dados JSON-serializáveis
        dados_sync = db.obter_dados_sincronizacao_para_template()
        
        # Adiciona a função now() ao contexto do template para cálculos de tempo
        def get_now():
            return datetime.now()

        response = make_response(render_template(
            "relatorio_sincronizacao.html",
            nunca_sincronizados=dados_sync["nunca_sincronizados"],
            ultimas_sync=dados_sync["ultimas_sync"],
            stats=dados_sync["stats"],
            now=get_now 
        ))
        return add_no_cache_headers(response)
    except Exception as e:
        print(f"Erro ao gerar relatório de sincronização: {e}")
        flash(f"Erro ao gerar relatório de sincronização: {str(e)}", "error")
        return redirect(url_for("listar_clientes"))

@app.route("/clientes/sincronizar/todos", methods=["POST"])
def sincronizar_todos_clientes():
    """
    Sincroniza todos os clientes do banco de dados com o BitPanel - VERSÃO CORRIGIDA
    """
    try:
        print(f"🔄 [SYNC MASSA] Iniciando sincronização em massa...")
        
        usuarios_iptv = db.obter_todos_usuarios_iptv()
        if not usuarios_iptv:
            flash("Nenhum cliente com usuário IPTV para sincronizar.", "info")
            return redirect(url_for("listar_clientes"))

        print(f"👥 [SYNC MASSA] {len(usuarios_iptv)} usuários para sincronizar")

        from bitpanel_automation import BitPanelManager
        manager = BitPanelManager()
        sucessos = 0
        falhas = 0
        detalhes_sync = []
        
        if not manager.login(headless=True):
            flash("Não foi possível fazer login no BitPanel. Verifique as credenciais.", "error")
            return redirect(url_for("relatorio_sincronizacao"))

        for i, usuario in enumerate(usuarios_iptv, 1):
            print(f"🔄 [SYNC MASSA] Sincronizando {i}/{len(usuarios_iptv)}: {usuario}")
            
            # Pequena pausa para não sobrecarregar
            time.sleep(1) 
            
            dados_sync = manager.sincronizar_dados_usuario(usuario, headless=True)
            
            if "erro" in dados_sync:
                print(f"❌ [SYNC MASSA] Falha na sincronização de {usuario}: {dados_sync.get('erro')}")
                falhas += 1
                detalhes_sync.append(f"{usuario}: FALHA")
            else:
                if db.atualizar_dados_sincronizados(usuario, dados_sync):
                    print(f"✅ [SYNC MASSA] {usuario} sincronizado com sucesso")
                    sucessos += 1
                    detalhes_sync.append(f"{usuario}: OK")
                else:
                    print(f"❌ [SYNC MASSA] Falha ao salvar dados de {usuario}")
                    falhas += 1
                    detalhes_sync.append(f"{usuario}: FALHA (banco)")
        
        manager.close()
        
        print(f"📊 [SYNC MASSA] Sincronização em massa concluída - Sucessos: {sucessos}, Falhas: {falhas}")
        
        # Salvar log detalhado
        log_detalhes = "\n".join(detalhes_sync[:10])  # Primeiros 10 para não sobrecarregar
        db.log_sistema("info", f"Sync massa: {sucessos} sucessos, {falhas} falhas. Detalhes: {log_detalhes}")
        
        # Forçar recarregamento completo
        timestamp = int(time.time())
        
        return render_template_string(f"""
<!DOCTYPE html>
<html>
<head>
    <title>Sincronização em Massa Concluída</title>
    <meta charset="utf-8">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta http-equiv="Pragma" content="no-cache">
    <meta http-equiv="Expires" content="0">
</head>
<body>
    <div style="text-align: center; padding: 50px; font-family: Arial, sans-serif;">
        <h3>📊 Sincronização em Massa Concluída!</h3>
        <p><strong>✅ Sucessos:</strong> {sucessos}</p>
        <p><strong>❌ Falhas:</strong> {falhas}</p>
        <p>Atualizando dashboard com dados sincronizados...</p>
        <script>
            console.log("🔄 Sincronização massa concluída, forçando reload completo...");
            
            // Limpar caches
            if ('caches' in window) {{
                caches.keys().then(names => {{
                    names.forEach(name => {{
                        caches.delete(name);
                    }});
                }});
            }}
            
            // Múltiplas estratégias de reload
            const timestamp = new Date().getTime();
            const url = "{url_for('listar_clientes')}?sync_massa={timestamp}&s={sucessos}&f={falhas}";
            
            setTimeout(() => {{
                window.location.replace(url);
            }}, 1500);
            
            setTimeout(() => {{
                window.location.href = url;
            }}, 3000);
        </script>
    </div>
</body>
</html>
        """)
        
    except Exception as e:
        print(f"❌ [SYNC MASSA] Erro crítico na sincronização em massa: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f"Erro na sincronização em massa: {str(e)}", "error")

    return redirect(url_for("relatorio_sincronizacao"))

@app.route("/api/stats")
def api_stats():
    """API para estatísticas (usado pelo auto-refresh) - MELHORADA"""
    try:
        stats = db.get_estatisticas()
        
        # BitPanel status apenas quando realmente necessário
        # Para otimização, sempre retorna False para evitar lentidão
        stats["bitpanel_online"] = False
        
        # *** CORREÇÃO: TIMESTAMP PARA FORÇAR ATUALIZAÇÃO ***
        stats["timestamp"] = datetime.now().isoformat()
        
        response = make_response(jsonify(stats))
        return add_no_cache_headers(response)
    except Exception as e:
        response = make_response(jsonify({"error": str(e)}), 500)
        return add_no_cache_headers(response)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

