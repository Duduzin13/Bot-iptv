# config.py - VERSÃO CORRIGIDA E SIMPLIFICADA

import os
from dotenv import load_dotenv

# Esta função carrega as variáveis do arquivo .env para o programa
load_dotenv()

class Config:
    # --- WhatsApp & Meta ---
    WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN')
    WHATSAPP_PHONE_ID = os.getenv('WHATSAPP_PHONE_ID')
    WEBHOOK_VERIFY_TOKEN = os.getenv('WEBHOOK_VERIFY_TOKEN')
    
    # --- Gemini AI ---
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    
    # --- Mercado Pago ---
    MERCADOPAGO_ACCESS_TOKEN = os.getenv('MERCADOPAGO_ACCESS_TOKEN')
    MERCADOPAGO_PUBLIC_KEY = os.getenv('MERCADOPAGO_PUBLIC_KEY')

    # --- BitPanel ---
    BITPANEL_URL = os.getenv('BITPANEL_URL')
    BITPANEL_USER = os.getenv('BITPANEL_USER')
    BITPANEL_PASS = os.getenv('BITPANEL_PASS')
    
    # --- URL Pública (Ngrok) ---
    BASE_URL = os.getenv('BASE_URL') # <-- ESSENCIAL PARA O QR CODE
    
    # --- Sistema ---
    FLASK_PORT = 5000
    WHATSAPP_PORT = 5000
    FLASK_HOST = '0.0.0.0'
    DATABASE_PATH = 'iptv_system.db'
    SECRET_KEY = 'iptv_secret_key_2024_secure'
    LINK_ACESSO_DEFAULT = 'http://play.biturl.vip'
    
        # Preços padrão (serão sobrescritos pelo banco)
    PRECO_MES_DEFAULT = 30  
    PRECO_CONEXAO_DEFAULT = 30
    
    # Link padrão (será sobrescrito pelo banco)
    LINK_ACESSO_DEFAULT = 'http://play.biturl.vip'
    
    # Plano padrão
    PLANO_DEFAULT = 'Full HD + H265 + HD + SD + VOD + Adulto + LGBT'

    TEST_MODE = os.getenv('TEST_MODE', 'False').lower() in ('true', '1', 't')
    