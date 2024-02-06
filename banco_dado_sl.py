import sqlite3
from datetime import datetime


def inicializar_tabela():
    conn = sqlite3.connect('banco_dados.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS precos_atingidos (
            id INTEGER PRIMARY KEY,
            date TEXT,
            operacao TEXT,
            ticker_symbol TEXT,
            preco_alvo NUMERIC(10, 2),
            preco_atual NUMERIC(10, 2),
            data_saida TEXT,
            stop_loss NUMERIC(10, 2)
        )
    ''')

    conn.commit()
    conn.close()

def inserir_preco_atingido(ticker_symbol, preco_alvo, preco_atual, data_saida, stop_loss):
    conn = sqlite3.connect('banco_dados.db')
    cursor = conn.cursor()

    # Verifica se o ticker_symbol já existe na tabela
    cursor.execute('SELECT * FROM precos_atingidos WHERE ticker_symbol = ?', (ticker_symbol,))
    existing_entry = cursor.fetchone()

    if existing_entry:
        # Se o ticker_symbol já existe, atualiza a linha existente com data_saida e stop_loss
        cursor.execute('''
            UPDATE precos_atingidos
            SET data_saida = ?, stop_loss = ?
            WHERE ticker_symbol = ?
        ''', (data_saida, stop_loss, ticker_symbol))
    else:
        # Se o ticker_symbol não existe, insere uma nova linha com todas as informações
        data_atual = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            INSERT INTO precos_atingidos (date, ticker_symbol, preco_alvo, preco_atual, data_saida, stop_loss)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (data_atual, ticker_symbol, preco_alvo, preco_atual, data_saida, stop_loss))

    conn.commit()
    conn.close()

def consultar_precos_atingidos():
    conn = sqlite3.connect('banco_dados.db')
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM precos_atingidos')
    precos_atingidos = cursor.fetchall()

    conn.close()

    return precos_atingidos
