# dashboard.py - Painel Web Corrigido SEM EMOJIS
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for
from datetime import datetime, timedelta
import json
from config import Config
from database import db
from whatsapp_bot import broadcast_para_clientes_ativos, broadcast_para_todos_clientes
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
        
        # Status do sistema
        try:
            bitpanel_manager = BitPanelManager()
            stats['bitpanel_online'] = bitpanel_manager.verificar_conexao(headless=True)
        except Exception as e:
            stats['bitpanel_online'] = False
            print(f"Erro ao verificar BitPanel: {e}")
        
        # Usar o template base se existir, senão usar o standalone
        try:
            return render_template('dashboard_base.html', stats=stats)
        except:
            return render_template('dashboard.html', stats=stats)
        
    except Exception as e:
        flash(f'Erro ao carregar dashboard: {str(e)}', 'error')
        return render_template('dashboard.html', stats={})

@app.route('/clientes')
def listar_clientes():
    """Listar todos os clientes"""
    try:
        conn = db.get_connection()
        clientes = conn.execute("""
            SELECT c.*, 
                   CASE 
                       WHEN c.data_expiracao > datetime('now') THEN 'Ativo'
                       WHEN c.data_expiracao IS NULL THEN 'Sem Lista'
                       ELSE 'Expirado'
                   END as status_lista
            FROM clientes c
            ORDER BY c.created_at DESC  
            """).fetchall()
        conn.close()
        
        clientes_list = [dict(cliente) for cliente in clientes]
        
        try:
            return render_template('clientes.html', clientes=clientes_list)
        except:
            # Template simples se não existir
            return f"<h1>Clientes ({len(clientes_list)})</h1><pre>{clientes_list}</pre>"
        
    except Exception as e:
        flash(f'Erro ao listar clientes: {str(e)}', 'error')
        return "Erro ao carregar clientes"

@app.route('/configuracoes')
def configuracoes():
    """Página de configurações"""
    config = {
        'link_acesso': db.get_config('link_acesso', Config.LINK_ACESSO_DEFAULT),
        'preco_mes': db.get_config('preco_mes', str(Config.PRECO_MES_DEFAULT)),
        'preco_conexao': db.get_config('preco_conexao', str(Config.PRECO_CONEXAO_DEFAULT))
    }
    
    try:
        return render_template('configuracoes.html', config=config)
    except:
        return f"<h1>Configurações</h1><pre>{config}</pre>"

@app.route('/atualizar-link', methods=['POST'])
def atualizar_link():
    """Atualizar link de acesso"""
    try:
        novo_link = request.form['link_acesso'].strip()
        
        if not novo_link.startswith(('http://', 'https://')):
            flash('Link deve começar com http:// ou https://', 'error')
            return redirect(url_for('configuracoes'))
        
        db.set_config('link_acesso', novo_link, 'Link de acesso principal')
        flash('Link atualizado com sucesso!', 'success')
        
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
        
        db.set_config('preco_mes', str(preco_mes), 'Preço por mês')
        db.set_config('preco_conexao', str(preco_conexao), 'Preço por conexão extra')
        
        flash(f'Preços atualizados: R$ {preco_mes:.2f}/mês, R$ {preco_conexao:.2f}/conexão', 'success')
        
        return redirect(url_for('configuracoes'))
        
    except Exception as e:
        flash(f'Erro ao atualizar preços: {str(e)}', 'error')
        return redirect(url_for('configuracoes'))

@app.route('/api/stats')
def api_stats():
    """API para obter estatísticas"""
    try:
        stats = db.get_estatisticas()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("Iniciando Dashboard IPTV...")
    try:
        app.run(
            host=Config.FLASK_HOST,
            port=Config.FLASK_PORT,
            debug=True
        )
    except Exception as e:
        print(f"Erro ao iniciar dashboard: {str(e)}")
