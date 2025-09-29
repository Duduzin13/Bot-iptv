# dashboard.py - Painel Web Completo (Corrigido)
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for
from datetime import datetime, timedelta
import json
from config import Config
from database import db
from whatsapp_bot import broadcast_para_clientes_ativos, broadcast_para_todos_clientes
# CORRIGIDO: Importa BitPanelManager do novo arquivo
from bitpanel_automation import BitPanelManager
from mercpag import mercado_pago

app = Flask(__name__)
app.secret_key = Config.SECRET_KEY

@app.route('/')
def index():
    """Página inicial - Dashboard"""
    try:
        # Obter estatísticas
        stats = db.get_estatisticas()
        
        # Dados extras para o dashboard
        stats['link_atual'] = db.get_config('link_acesso', Config.LINK_ACESSO_DEFAULT)
        stats['preco_mes'] = db.get_config('preco_mes', str(Config.PRECO_MES_DEFAULT))
        stats['preco_conexao'] = db.get_config('preco_conexao', str(Config.PRECO_CONEXAO_DEFAULT))
        
        # Status do sistema (CORRIGIDO: usa headless)
        try:
            bitpanel_manager = BitPanelManager()
            stats['bitpanel_online'] = bitpanel_manager.verificar_conexao(headless=True)
        except Exception as e:
            stats['bitpanel_online'] = False
            print(f"Erro ao verificar BitPanel: {e}")
        
        return render_template('dashboard.html', stats=stats)
        
    except Exception as e:
        flash(f'Erro ao carregar dashboard: {str(e)}', 'error')
        return render_template('dashboard.html', stats={})

@app.route('/clientes')
def listar_clientes():
    """Listar todos os clientes"""
    try:
        # Buscar todos os clientes
        conn = db.get_connection()
        clientes = conn.execute('''
            SELECT c.*, 
                   CASE 
                       WHEN c.data_expiracao > datetime('now') THEN 'Ativo'
                       WHEN c.data_expiracao IS NULL THEN 'Sem Lista'
                       ELSE 'Expirado'
                   END as status_lista,
                   CASE 
                       WHEN c.data_expiracao > datetime('now') 
                       THEN CAST((julianday(c.data_expiracao) - julianday('now')) AS INTEGER)
                       ELSE 0
                   END as dias_restantes
            FROM clientes c
            ORDER BY c.created_at DESC
        ''').fetchall()
        conn.close()
        
        clientes_list = [dict(cliente) for cliente in clientes]
        
        return render_template('clientes.html', clientes=clientes_list)
        
    except Exception as e:
        flash(f'Erro ao listar clientes: {str(e)}', 'error')
        return render_template('clientes.html', clientes=[])

@app.route('/configuracoes')
def configuracoes():
    """Página de configurações"""
    config = {
        'link_acesso': db.get_config('link_acesso', Config.LINK_ACESSO_DEFAULT),
        'preco_mes': db.get_config('preco_mes', str(Config.PRECO_MES_DEFAULT)),
        'preco_conexao': db.get_config('preco_conexao', str(Config.PRECO_CONEXAO_DEFAULT)),
        'plano_padrao': db.get_config('plano_padrao', Config.PLANO_DEFAULT),
        'teste_duracao': db.get_config('teste_duracao', '2'),
        'teste_intervalo': db.get_config('teste_intervalo', '24')
    }
    
    return render_template('configuracoes.html', config=config)

@app.route('/atualizar-link', methods=['POST'])
def atualizar_link():
    """Atualizar link de acesso e notificar clientes"""
    try:
        novo_link = request.form['link_acesso'].strip()
        
        if not novo_link.startswith(('http://', 'https://')):
            flash('Link deve começar com http:// ou https://', 'error')
            return redirect(url_for('configuracoes'))
        
        link_antigo = db.get_config('link_acesso', Config.LINK_ACESSO_DEFAULT)
        
        # Atualizar configuração
        db.set_config('link_acesso', novo_link, 'Link de acesso principal dos clientes')
        
        # Se o link mudou, notificar clientes
        if novo_link != link_antigo:
            mensagem_aviso = f"""🔄 **ATUALIZAÇÃO IMPORTANTE!**

O link de acesso do seu IPTV foi atualizado:

🔗 **Novo link**: {novo_link}
❌ **Link antigo não funcionará mais**: {link_antigo}

Por favor, atualize seus dispositivos com o novo link!

💡 **Como atualizar:**
1. Acesse as configurações do seu app/dispositivo
2. Troque o link antigo pelo novo
3. Salve as configurações

Qualquer dúvida, estamos aqui para ajudar! 😊"""
            
            # Enviar para todos os clientes ativos
            sucesso, erro = broadcast_para_clientes_ativos(mensagem_aviso)
            
            flash(f'Link atualizado! Notificação enviada para {sucesso} clientes ativos.', 'success')
            db.log_sistema('info', f'Link atualizado de {link_antigo} para {novo_link} - {sucesso} notificações enviadas')
        else:
            flash('Link atualizado (sem mudanças).', 'info')
        
        return redirect(url_for('configuracoes'))
        
    except Exception as e:
        flash(f'Erro ao atualizar link: {str(e)}', 'error')
        return redirect(url_for('configuracoes'))

@app.route('/atualizar-precos', methods=['POST'])
def atualizar_precos():
    """Atualizar preços do sistema"""
    try:
        preco_mes = float(request.form['preco_mes'])
        preco_conexao = float(request.form['preco_conexao'])
        
        if preco_mes < 0 or preco_conexao < 0:
            flash('Preços devem ser positivos!', 'error')
            return redirect(url_for('configuracoes'))
        
        # Atualizar preços
        db.set_config('preco_mes', str(preco_mes), 'Preço por mês em R')
        db.set_config('preco_conexao', str(preco_conexao), 'Preço por conexão adicional em R')
        
        flash(f'Preços atualizados: R$ {preco_mes:.2f}/mês, R$ {preco_conexao:.2f}/conexão', 'success')
        db.log_sistema('info', f'Preços atualizados: R$ {preco_mes}/mês, R$ {preco_conexao}/conexão')
        
        return redirect(url_for('configuracoes'))
        
    except ValueError:
        flash('Valores inválidos! Use números válidos.', 'error')
        return redirect(url_for('configuracoes'))
    except Exception as e:
        flash(f'Erro ao atualizar preços: {str(e)}', 'error')
        return redirect(url_for('configuracoes'))

@app.route('/avisos')
def avisos():
    """Página para enviar avisos"""
    return render_template('avisos.html')

@app.route('/enviar-aviso', methods=['POST'])
def enviar_aviso():
    """Enviar aviso para clientes"""
    try:
        tipo_aviso = request.form['tipo']
        mensagem = request.form['mensagem'].strip()
        
        if not mensagem:
            flash('Mensagem não pode estar vazia!', 'error')
            return redirect(url_for('avisos'))
        
        sucesso = 0
        erro = 0
        
        if tipo_aviso == 'todos':
            # Todos os clientes (ativos e inativos)
            sucesso, erro = broadcast_para_todos_clientes(mensagem)
            flash(f'Aviso enviado para TODOS os clientes! ✅ {sucesso} enviados, ❌ {erro} erros', 'success')
            
        elif tipo_aviso == 'ativos':
            # Apenas clientes com listas ativas
            sucesso, erro = broadcast_para_clientes_ativos(mensagem)
            flash(f'Aviso enviado para clientes ATIVOS! ✅ {sucesso} enviados, ❌ {erro} erros', 'success')
            
        elif tipo_aviso == 'expirando':
            # Clientes com listas expirando em 7 dias
            clientes_expirando = db.listar_clientes_expirando(7)
            
            from whatsapp_bot import whatsapp_bot
            telefones = []
            
            for cliente in clientes_expirando:
                data_exp = datetime.fromisoformat(cliente['data_expiracao'])
                dias_restantes = (data_exp - datetime.now()).days
                
                mensagem_personalizada = f"""{mensagem}

⚠️ **Lembrete**: Sua lista expira em {dias_restantes} dia{'s' if dias_restantes > 1 else ''}!
🔄 Digite "renovar" para continuar aproveitando!"""
                
                telefones.append(cliente['telefone'])
            
            if telefones:
                sucesso, erro = whatsapp_bot.broadcast_mensagem(telefones, mensagem_personalizada)
                flash(f'Aviso enviado para {len(telefones)} clientes EXPIRANDO! ✅ {sucesso} enviados, ❌ {erro} erros', 'success')
            else:
                flash('Nenhum cliente expirando encontrado.', 'info')
        
        # Log da ação
        db.log_sistema('info', f'Aviso enviado ({tipo_aviso}): {sucesso} sucessos, {erro} erros')
        
        return redirect(url_for('avisos'))
        
    except Exception as e:
        flash(f'Erro ao enviar aviso: {str(e)}', 'error')
        db.log_sistema('erro', f'Erro enviar aviso: {str(e)}')
        return redirect(url_for('avisos'))

@app.route('/logs')
def logs():
    """Página de logs do sistema"""
    try:
        # Buscar logs recentes (últimos 100)
        conn = db.get_connection()
        logs_list = conn.execute('''
            SELECT * FROM logs_sistema 
            ORDER BY data_log DESC 
            LIMIT 100
        ''').fetchall()
        conn.close()
        
        logs = [dict(log) for log in logs_list]
        
        return render_template('logs.html', logs=logs)
        
    except Exception as e:
        flash(f'Erro ao carregar logs: {str(e)}', 'error')
        return render_template('logs.html', logs=[])

@app.route('/api/stats')
def api_stats():
    """API para obter estatísticas em tempo real"""
    try:
        stats = db.get_estatisticas()
        # CORRIGIDO: usa headless para não abrir navegador
        try:
            bitpanel_manager = BitPanelManager()
            stats['bitpanel_online'] = bitpanel_manager.verificar_conexao(headless=True)
        except:
            stats['bitpanel_online'] = False
        
        return jsonify(stats)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/cliente/<telefone>')
def api_cliente(telefone):
    """API para obter dados de um cliente"""
    try:
        cliente = db.buscar_cliente_por_telefone(telefone)
        if cliente:
            return jsonify(cliente)
        else:
            return jsonify({'error': 'Cliente não encontrado'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/renovar-cliente', methods=['POST'])
def api_renovar_cliente():
    """API para renovar cliente manualmente"""
    try:
        data = request.get_json()
        telefone = data.get('telefone')
        meses = int(data.get('meses', 1))
        
        cliente = db.buscar_cliente_por_telefone(telefone)
        if not cliente:
            return jsonify({'error': 'Cliente não encontrado'}), 404
        
        # Renovar no BitPanel (CORRIGIDO: usa headless)
        bitpanel_manager = BitPanelManager()
        sucesso = bitpanel_manager.renovar_lista(cliente['usuario_iptv'], meses, headless=True)
        bitpanel_manager.close()
        
        if sucesso:
            # Atualizar no banco
            db.renovar_lista_cliente(telefone, meses)
            
            db.log_sistema('info', f'Renovação manual: {cliente["usuario_iptv"]} - {meses} meses')
            
            return jsonify({'success': True, 'message': f'Lista renovada por {meses} meses'})
        else:
            return jsonify({'error': 'Erro ao renovar no BitPanel'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500



if __name__ == '__main__':
    # Iniciar dashboard
    print("🖥️ Iniciando Dashboard IPTV...")
    
    try:
        app.run(
            host=Config.FLASK_HOST,
            port=Config.FLASK_PORT,
            debug=True
        )
    except Exception as e:
        print(f"❌ Erro ao iniciar dashboard: {str(e)}")
        db.log_sistema('erro', f'Erro iniciar dashboard: {str(e)}')