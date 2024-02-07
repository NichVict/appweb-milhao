from flask import request, jsonify
import yfinance as yf
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import threading
from telegram import Bot
from telegram import ParseMode
import datetime
import time
from app import create_app
from banco_dado_sl import inserir_preco_atingido

# Use create_app para obter o app configurado
app, socketio = create_app(5001, 'indexloss.html')

#app = Flask(__name__)
#socketio = SocketIO(app, cors_allowed_origins="*")


dados_inseridos = []
lock = threading.Lock()

# Constantes
HORARIO_INICIO_PREGAO = datetime.time(13, 0, 0)
HORARIO_FIM_PREGAO = datetime.time(23, 0, 0)
INTERVALO_VERIFICACAO = 50
TEMPO_ACUMULADO_MAXIMO = 120
token_telegram = '6750587978:AAG-kPsoLKaL0tTebyc-JCZ-bkG9jZbN7fs'  # Substitua pelo seu token do Telegram - DO @xande_trade_bot



@socketio.on('mensagem_do_script')
def lidar_com_mensagem_do_script(mensagem):
    print(f'Mensagem do script recebida: {mensagem}')
    socketio.emit('atualizar_mensagens', {'mensagem': mensagem})

@socketio.on('connect')
def handle_connect():
    print("Cliente conectado.")

@socketio.on('disconnect')
def handle_disconnect():
    print("Cliente desconectado.")

@app.route('/enviar', methods=['POST'])
def receber_dados():
    global dados_inseridos

    # Receber os dados do cliente
    dados_recebidos = request.get_json()
    print("Dados Recebidos:", dados_recebidos)

    # Filtrar apenas o último identificador (o maior número)
    if dados_recebidos:
        ultimo_identificador = max(dado['identificador'] for dado in dados_recebidos)
        dados_inseridos = [dado for dado in dados_inseridos if dado['identificador'] != ultimo_identificador]

    # Adicionar os dados à lista
    dados_inseridos.extend(dados_recebidos)

    # Processar os dados como necessário
    processar_dados(dados_recebidos)

    return jsonify({"status": "success"})



# Adicione a nova rota para exclusão
@app.route('/excluir/<identificador>', methods=['DELETE'])
def excluir_registro(identificador):
    global dados_inseridos

    # Converta o identificador para um tipo adequado (por exemplo, int)
    identificador = int(identificador)

    # Crie uma nova lista que contém apenas os registros que não serão excluídos
    dados_inseridos = [registro for registro in dados_inseridos if registro.get('identificador') != identificador]

    # Obtenha o Ticker do registro excluído, ou 'identificador' se não encontrado
    ticker_symbol = next((registro.get('tickerSymbol', 'identificador') for registro in dados_inseridos if registro.get('identificador') == identificador), 'identificador')

    mensagem = f"Processando Exclusão de Ordem Enviada ao Servidor, id: {identificador}"
    imprimir_mensagem(mensagem)

    return jsonify({"status": "success", "message": mensagem})




def imprimir_mensagem(mensagem):
    print(mensagem)
    socketio.emit('atualizar_mensagens', {'mensagem': mensagem})


def processar_dados(dados):
    threads = []

    # Filtra apenas os dados do último identificador
    ultimo_identificador = max(dado['identificador'] for dado in dados)
    dados_filtrados = [dado for dado in dados if dado['identificador'] == ultimo_identificador]

    # Adicione aqui a lógica para processar os dados no lado do servidor
    for dado in dados_filtrados:
        identificador = dado.get('identificador')
        ticker_symbol = dado['tickerSymbol']
        preco_alvo = dado['precoAlvo']
        destinatario = dado['destinatario']
        operacao = dado['operacao']

        imprimir_mensagem(
            f"Dados recebidos: Id: {identificador}, Operação: {operacao}, Ticker: {ticker_symbol}, Preço Alvo: {preco_alvo}")

        # Inicie uma nova thread para verificar o preço-alvo
        thread = threading.Thread(target=verificar_preco_alvo,
                                  args=(ticker_symbol, preco_alvo, destinatario, operacao, identificador))
        thread.start()
        threads.append(thread)

    # Aguarda todas as threads terminarem
    for thread in threads:
        thread.join()

    # Enviar identificadores em processamento para o cliente
    socketio.emit('atualizar_identificadores_processamento', {'identificadoresProcessamento': dados_filtrados})


# Função para verificar o preço-alvo
def verificar_preco_alvo(ticker_symbol, preco_alvo, destinatario, operacao, identificador):
    # Adiciona .SA se necessário
    if not ticker_symbol.endswith('.SA'):
        ticker_symbol += '.SA'
        print(ticker_symbol)
        # Converte o preço alvo para float, tratando vírgula ou ponto
    try:
        preco_alvo = float(preco_alvo.replace(',', '.'))
    except ValueError:
        print("Erro ao converter o preço alvo para float. Certifique-se de usar um formato numérico válido.")


    ticker_data = yf.Ticker(ticker_symbol)
    print("ticker data = ", ticker_data)

    tempo_acumulado = 0
    dentro_do_pregao = False
    primeira_verificacao = False  # Adiciona uma flag para controlar a primeira verificação

    try:

        while True:
            # Obtém o preço atual
            preco_atual = ticker_data.history(period='3d')['Close'].iloc[-1]

            # Verifica se estamos dentro do horário do pregão
            horario_pregao = datetime.datetime.now().time()

            if HORARIO_INICIO_PREGAO <= horario_pregao <= HORARIO_FIM_PREGAO:
                # Coloque aqui o código que você deseja executar durante o pregão
                if not primeira_verificacao:
                    imprimir_mensagem(f"Dentro do horário do pregão. Realizando buscas do ticker {ticker_symbol}...")
                    primeira_verificacao = True
            else:
                imprimir_mensagem("Fora do horário do pregão. Aguardando até o início do pregão...")

                agora = datetime.datetime.now()
                inicio_pregao_hoje = agora.replace(hour=HORARIO_INICIO_PREGAO.hour, minute=0, second=0, microsecond=0)

                # Se o horário atual for antes do início do pregão, inicia as buscas hoje
                if agora < inicio_pregao_hoje:
                    proximo_dia = inicio_pregao_hoje
                    imprimir_mensagem("Início das buscas ocorrerá no mesmo dia.")
                else:
                    # Caso contrário, inicia as buscas no próximo dia
                    proximo_dia = agora + datetime.timedelta(hours=14)
                    proximo_dia = proximo_dia.replace(hour=HORARIO_INICIO_PREGAO.hour, minute=0, second=0,
                                                      microsecond=0)
                    imprimir_mensagem("Início das buscas ocorrerá no dia seguinte.")

                tempo_espera = (proximo_dia - agora).total_seconds()
                time.sleep(tempo_espera)

                continue  # Continua para o próximo ticker no mesmo dia ou no próximo dia


            # Verifica se o registro ainda está presente
            if not any(registro.get('identificador') == identificador for registro in dados_inseridos):
                imprimir_mensagem(
                    f"Ordem do ticker {ticker_symbol} excluída do Servidor com sucesso!")
                break

            # Verifica se o preço atingiu ou ultrapassou o alvo
            if (operacao == 'compra' and preco_atual >= preco_alvo) or (
                    operacao == 'venda' and preco_atual <= preco_alvo):
                if ticker_symbol not in estados_tickers:
                    estados_tickers[ticker_symbol] = 1
                    imprimir_mensagem(f"Ticker {ticker_symbol} atingiu o preço alvo pela primeira vez.")
                elif estados_tickers[ticker_symbol] == 1:
                    # Primeira verificação positiva
                    estados_tickers[ticker_symbol] = 2
                    dentro_do_pregao = True  # Indica que estamos dentro do pregão
                    imprimir_mensagem(
                        f"Ticker {ticker_symbol} iniciará a contagem de tempo acumulado...")
                elif estados_tickers[ticker_symbol] == 2 and dentro_do_pregao:
                    # Segunda verificação durante o pregão
                    if (operacao == 'compra' and preco_atual >= preco_alvo) or (
                            operacao == 'venda' and preco_atual <= preco_alvo):

                        if not primeira_verificacao:
                            # Se for a primeira verificação positiva, inicia o tempo acumulado
                            primeira_verificacao = True
                            #imprimir_mensagem(
                                #f"Ticker {ticker_symbol} atingiu o preço-alvo pela primeira vez. Aguardando segunda verificacao.")

                        if primeira_verificacao:
                            tempo_acumulado += (INTERVALO_VERIFICACAO+10)  # Adiciona 30 segundos ao tempo acumulado
                            imprimir_mensagem(
                                f"Tempo acumulado para {ticker_symbol}: {tempo_acumulado}s")

                            # Verifica se o tempo acumulado atingiu 25 minutos
                            if tempo_acumulado >= TEMPO_ACUMULADO_MAXIMO:
                                # Modificação aqui: Adiciona data de saída e stop_loss
                                data_saida = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                stop_loss = preco_atual
                                inserir_preco_atingido(ticker_symbol, preco_alvo, preco_atual, data_saida, stop_loss)
                                imprimir_mensagem(f"Dados inseridos no banco de dados para {ticker_symbol}, Preço Atual: {preco_atual}")


                                notificar_preco_alvo_alcancado(ticker_symbol, preco_alvo, preco_atual, destinatario,
                                                               operacao, token_telegram)
                                imprimir_mensagem(f"Ticker {ticker_symbol} atingiu o tempo acumulado de 26 min durante o pregão. Notificações para e-mail e Telegram enviadas com sucesso!")
                                # Não verifica mais o ticker no mesmo dia
                                break
                    else:
                        # Se não atender aos critérios, volta ao estado 0
                        estados_tickers[ticker_symbol] = 0
                        imprimir_mensagem(
                            f"Ticker {ticker_symbol} não acumulou 26 minutos durante o pregão . Continuando a verificação.")
                        break  # Não verifica mais o ticker no mesmo dia
                else:
                    # Se não estiver no estado 1 ou 2, continua verificando
                    imprimir_mensagem(f"Ticker {ticker_symbol} está sendo verificado pela segunda vez.")
                    break  # Não verifica mais o ticker no mesmo dia

            # Adiciona um intervalo de tempo para evitar verificações frequentes
            time.sleep(INTERVALO_VERIFICACAO)  # Aguarda 50 segundos entre as verificações

    except Exception as e:
        imprimir_mensagem(f"Ocorreu um erro ao verificar o preço para {ticker_symbol}: {str(e)}")



# Função para notificar o preço-alvo atingido
def notificar_preco_alvo_alcancado(ticker_symbol, preco_alvo, preco_atual, destinatario, operacao, token_telegram):
    ticker_symbol_sem_extensao = ticker_symbol.replace('.SA', '')
    preco_atual_formatado = "{:.2f}".format(preco_atual)

    if (operacao == 'compra' and preco_atual >= preco_alvo) or (operacao == 'venda' and preco_atual <= preco_alvo):
        # Verificar operação anterior e ajustar a mensagem
        if operacao == 'venda':
            mensagem_operacao_anterior = "COMPRA"
        else:
            mensagem_operacao_anterior = "VENDA A DESCOBERTO"

        mensagem = f"Encerramento da operação de {mensagem_operacao_anterior} em {ticker_symbol_sem_extensao}!\n"\
                   f"Realize a operação de {operacao.upper()} para zerar sua posição.\n"\
                   f"STOP {preco_alvo:.2f} foi atingido ou ultrapassado.\n"\
                   f"Preço atual: {preco_atual_formatado}\n\n\n\n\n"
        mensagem_compliance = "COMPLIANCE: Esta mensagem é uma sugestão de compra/venda baseada em nossa lista Semanal. A compra ou venda é de total decisão e responsabilidade do Destinatário. Este e-mail contém informação CONFIDENCIAL de propriedade do Canal 1milhao e de seu DESTINATÁRIO tão somente. Se você NÃO for DESTINATÁRIO ou pessoa autorizada a recebê-lo, NÃO PODE usar, copiar, transmitir, retransmitir ou divulgar seu conteúdo (no todo ou em partes), estando sujeito às penalidades da LEI. A Lista de Ações do Canal 1milhao é devidamente REGISTRADA."
        mensagem += mensagem_compliance
        imprimir_mensagem(mensagem)

        assunto = f"*ALERTA* Encerramento da Operação de {mensagem_operacao_anterior} em {ticker_symbol_sem_extensao}"
        remetente = 'testeestudos2024@gmail.com'
        senha_ou_token = 'fuba dsun jpdk wqnu'  # ou seu token, se estiver usando

        # Chamar a função enviar_notificacao apenas uma vez
        try:
            enviar_notificacao(destinatario, assunto, mensagem, remetente, senha_ou_token, token_telegram)
            imprimir_mensagem("Enviando notificações aos clientes por e-mail e Telegram ...")
        except Exception as e:
            imprimir_mensagem(f"Erro ao enviar notificação: {str(e)}")

# Variáveis compartilhadas para o estado de cada ticker
estados_tickers = {}

# ...

# Variáveis compartilhadas para o estado de cada ticker
estados_tickers_var = {}



# Função para enviar e-mail
def enviar_email(destinatario, assunto, corpo, remetente, senha_ou_token):
    mensagem = MIMEMultipart()
    mensagem['From'] = remetente
    mensagem['To'] = destinatario
    mensagem['Subject'] = assunto
    mensagem.attach(MIMEText(corpo, 'plain'))

    with smtplib.SMTP('smtp.gmail.com', 587) as servidor_smtp:
        servidor_smtp.starttls()
        servidor_smtp.login(remetente, senha_ou_token)
        servidor_smtp.send_message(mensagem)

# Função para enviar notificação por e-mail e no Telegram
def enviar_notificacao(destinatario, assunto, corpo, remetente, senha_ou_token, token_telegram):
    # Enviar e-mail
    enviar_email(destinatario, assunto, corpo, remetente, senha_ou_token)

    # Enviar mensagem no Telegram
    bot = Bot(token=token_telegram)
    chat_id = '-1002046197953'  # Substitua pelo seu ID de chat do Telegram - CHAT ID DO GRUPO ALERTA TRADES
    mensagem_telegram = f"{corpo}\n\nRobot Canal 1 Milhão."
    bot.send_message(chat_id=chat_id, text=mensagem_telegram, parse_mode=ParseMode.MARKDOWN)


if __name__ == "__main__":
    socketio.run(app, port=5001, debug=True, use_reloader=False, allow_unsafe_werkzeug=True)