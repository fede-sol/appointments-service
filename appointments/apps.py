from django.apps import AppConfig
from decouple import config
import threading
import asyncio
import websockets

class AppointmentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'appointments'
    websocket_connection = None
    sqs_thread = None

    def ready(self):

        from appointments_menta_service.libreria_sns_client import init_sns_client, subscribe_to_topic, init_sqs_client, escuchar_sqs_mensajes

        # Suscripción a los tópicos al iniciar la aplicación
        # Credenciales de AWS SNS
        AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID')
        AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY')
        AWS_SESSION_TOKEN = config('AWS_SESSION_TOKEN')
        AWS_DEFAULT_REGION = config('AWS_DEFAULT_REGION', default='us-east-1')

        sns_client = init_sns_client(AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN, AWS_DEFAULT_REGION)

        # Suscribirse a los tópicos de reserva y backoffice
        #subscribe_to_topic(sns_client, config('TOPIC_ARN_RESERVA'), 'https', 'https://f6ec-190-174-49-242.ngrok-free.app/pagos/sns-webhook/')
        #subscribe_to_topic(sns_client, config('TOPIC_ARN_BACKOFFICE'), 'https', 'https://f6ec-190-174-49-242.ngrok-free.app/pagos/sns-webhook/')

        subscribe_to_topic(sns_client, config('TOPIC_ARN_USERPROFILE'), 'sqs', config('QUEUE_ARN_R'))
        subscribe_to_topic(sns_client, config('TOPIC_ARN_APPOINTMENTS'), 'sqs', config('QUEUE_ARN_R'))


        # Escuchar cola SQS
        sqs_client = init_sqs_client(AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN, AWS_DEFAULT_REGION)
        queue_url = config('QUEUE_URL_R')
        # Iniciar la escucha de la cola SQS en un hilo separado
        #thread = threading.Thread(target=escuchar_sqs_mensajes, args=(queue_url_backoffice, sqs_client), daemon=True)
        #thread.start()
        # print("Iniciado el hilo para escuchar mensajes de SQS")

        # Comprobar si el hilo ya está activo antes de iniciarlo
        # if not hasattr(threading.current_thread(), 'escuchar_thread'):
        #     #thread = threading.Thread(target=escuchar_topicos, daemon=True)
        #     thread = threading.Thread(target=escuchar_sqs_mensajes, args=(queue_url_reserva, sqs_client), daemon=True)
        #     thread.start()
        #     print("Hilo iniciado para escuchar tópicos de RabbitMQ")
        # else:
        #     print("El hilo ya está activo.")

        if not self.sqs_thread or not self.sqs_thread.is_alive():
            self.sqs_thread = threading.Thread(target=escuchar_sqs_mensajes, args=(queue_url, sqs_client), daemon=True)
            self.sqs_thread.start()
            print("Hilo iniciado para escuchar mensajes de SQS")
        else:
            print("El hilo de SQS ya está activo.")

        # Iniciar la conexión al WebSocket (otro hilo)
        threading.Thread(target=self.start_websocket_connection, daemon=True).start()


    def start_websocket_connection(self):
        asyncio.run(self.connect_to_websocket())

    async def connect_to_websocket(self):
        try:
            url = config('WEBSOCKET_URL', default=None)
            if not url:
                print("WEBSOCKET_URL no está configurado, omitiendo conexión WebSocket")
                return

            self.websocket_connection = await websockets.connect(url)
            print("Conexión al WebSocket establecida")
        except Exception as e:
            print(f"Error al conectar al WebSocket: {e}")
            print("La aplicación continuará funcionando sin conexión WebSocket")

    def close_websocket_connection(self):
        if self.websocket_connection:
            asyncio.run(self.websocket_connection.close())
            print("Conexión al WebSocket cerrada")
