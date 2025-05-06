import time
import boto3, json
from botocore.exceptions import ClientError
from decouple import config
import requests

from appointments.models import Appointment
from therapists.models import Therapist

# Cargar credenciales desde .env
AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY')
AWS_SESSION_TOKEN = config('AWS_SESSION_TOKEN')
AWS_DEFAULT_REGION = config('AWS_DEFAULT_REGION')

# Inicializar el cliente SNS
def init_sns_client(AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN, AWS_DEFAULT_REGION):
    sns_client = boto3.client(
        'sns',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        aws_session_token=AWS_SESSION_TOKEN,
        region_name=AWS_DEFAULT_REGION)
    return sns_client

# Inicializar el cliente de WebSocket
def init_websocket_client():
    return boto3.client(
        'apigatewaymanagementapi',
        endpoint_url='https://25zb4cxwg1.execute-api.us-east-1.amazonaws.com/dev',
        region_name=AWS_DEFAULT_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        aws_session_token=AWS_SESSION_TOKEN
    )

# Función para enviar mensaje a WebSocket
def publish_to_websocket(connection_id, message, websocket_client):
    try:
        print(f"Enviando mensaje al WebSocket con ConnectionId: {connection_id}")
        response = websocket_client.post_to_connection(
            Data=message.encode("utf-8"),  # Corrigiendo encoding
            ConnectionId=connection_id
        )
        return response
    except Exception as e:
        print(f"Error publicando en WebSocket: {e}")
        raise


# Publicar un mensaje en un tópico de SNS
def publish_to_topic(sns_client, topic_arn, event_name, message):
    print(f"Publicando mensaje en el tópico {topic_arn}")
    try:
        response = sns_client.publish(
            TopicArn=topic_arn,
            Message=json.dumps(message),
            Subject=event_name
        )

        # Si la publicación fue exitosa, se obtiene el status code
        status = "success" if response['ResponseMetadata']['HTTPStatusCode'] == 200 else "error"
        print(f"Mensaje publicado exitosamente en el tópico {topic_arn}")
        return response

    except Exception as e:
        print(f"Error al publicar el mensaje: {e}")
        raise e  # Re-lanzar la excepción para manejarla en el llamador



# Suscripcion a un tópico de SNS
def subscribe_to_topic(sns_client, topic_arn_to_suscribe, protocol, direction):
    try:
        response = sns_client.subscribe(
            TopicArn=topic_arn_to_suscribe,
            Protocol=protocol,  # Ej: 'https', 'email', 'sms', etc.
            Endpoint=direction   # La URL o dirección donde se recibirán los mensajes
        )
        print(f"Suscripción exitosa: {response}")
        return response
    except ClientError as e:
        print(f"Error en la suscripción: {e}")
        raise e


# Función para obtener el último connectionId de un endpoint
def get_last_connection_id(endpoint_url):
    try:
        response = requests.get(endpoint_url)
        response.raise_for_status()  # Lanza un error si la respuesta es un código de estado 4xx o 5xx
        data = response.json()
        return data.get('connection_id')  # Asumiendo que la respuesta tiene un campo 'connectionId'
    except Exception as e:
        print(f"Error al obtener el connectionId de {endpoint_url}: {e}")
        return None

# Inicializar el cliente SQS
def init_sqs_client(AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN, AWS_DEFAULT_REGION):
    sqs_client = boto3.client(
        'sqs',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        aws_session_token=AWS_SESSION_TOKEN,
        region_name=AWS_DEFAULT_REGION)
    return sqs_client

# Recibe un mensaje de una cola SQS
def escuchar_sqs_mensajes(queue_url, sqs_client):
    while True:
        try:
            # Recibe mensajes de la cola
            response = sqs_client.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=10,  # Número máximo de mensajes por lote
                WaitTimeSeconds=20  # Espera hasta que haya mensajes en la cola (long polling)
            )
            messages = response.get('Messages', [])
            print(messages)
            if messages:
                for message in messages:
                    # Procesar cada mensaje recibido
                    procesar_mensaje_sqs(message, queue_url)

                    # Eliminar el mensaje de la cola una vez procesado
                    sqs_client.delete_message(
                        QueueUrl=queue_url,
                        ReceiptHandle=message['ReceiptHandle']
                    )
            else:
                print("No hay mensajes en la cola, esperando...")

        except Exception as e:
            print(f"Error al recibir mensajes de SQS: {e}")
        time.sleep(5)  # Esperar antes de intentar recibir mensajes nuevamente


# Procesar un mensaje de SQS recibido
def procesar_mensaje_sqs(message, queue_url):
    try:
        body = message['Body']
        #sqs_message = json.loads(body)  # Convertir cadena JSON a diccionario Python
        receipt_handle = message['ReceiptHandle']

        # Procesar el cuerpo del mensaje
        sqs_message_dict = json.loads(body) #dict
        print('mensaje', sqs_message_dict)
        sns_topic = sqs_message_dict.get('TopicArn', '')
        print('topic', sns_topic)
        sns_event_type = sqs_message_dict.get('Subject', '')
        sns_message = sqs_message_dict.get('Message', '')
        print('SNSMESAGEs', sns_message)
        data = json.loads(sns_message)

        if 'appointments' in sns_topic:
            if 'appointment-updated' in sns_event_type:
                appointment = Appointment.objects.get(id=data['appointment_id'])
                if 'status' in data.keys() and data['status']:
                    appointment.status = data['status']
                if 'link' in data.keys() and data['link']:
                    appointment.link = data['link']
                    appointment.status = 'programado'
                appointment.save()
        elif 'userprofile' in sns_topic:
            if sns_event_type == 'userprofile-created':
                Therapist.objects.create(
                    name=data['name'],
                    email=data['email'],
                    phone=data['phone'],
                    external_id=data['id']
                )
            elif sns_event_type == 'userprofile-updated':
                therapist = Therapist.objects.get(external_id=data['id'])
                therapist.name = data['name']
                therapist.email = data['email']
                therapist.phone = data['phone']
                therapist.save()

        # Eliminar el mensaje de la cola tras procesarlo exitosamente
        sqs = init_sqs_client(AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN, AWS_DEFAULT_REGION)
        sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)
        print(f"Mensaje eliminado de la cola: {body}")

    except Exception as e:
        print(f"Error procesando el mensaje de SQS: {e}")

def verify_sqs_subscription(sns_client, sqs_client, topic_arn, queue_url):
    """
    Verifica que la cola SQS esté correctamente suscrita al topic SNS
    """
    try:
        # Obtener el ARN de la cola SQS
        queue_attributes = sqs_client.get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=['QueueArn']
        )
        queue_arn = queue_attributes['Attributes']['QueueArn']

        # Listar suscripciones del topic
        subscriptions = sns_client.list_subscriptions_by_topic(
            TopicArn=topic_arn
        )

        # Verificar si la cola está suscrita
        is_subscribed = any(
            sub['Endpoint'] == queue_arn
            for sub in subscriptions['Subscriptions']
        )

        print(f"Cola SQS ARN: {queue_arn}")
        print(f"Está suscrita: {is_subscribed}")

        return is_subscribed

    except Exception as e:
        print(f"Error verificando suscripción: {e}")
        return False