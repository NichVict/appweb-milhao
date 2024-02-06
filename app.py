from flask import Flask, render_template
from flask_socketio import SocketIO

def create_app(port, template_name):
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'your_secret_key'
    socketio = SocketIO(app, cors_allowed_origins=f"http://127.0.0.1:{port}")

    @app.route('/')
    def index():
        return render_template(template_name)

    return app, socketio

# Adicione a seguinte linha para exportar a instância de SocketIO
socketio = SocketIO()
app, socketio = create_app(5001, 'indexloss.html')


