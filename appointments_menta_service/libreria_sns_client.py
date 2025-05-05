import time
import boto3, json
from botocore.exceptions import ClientError
from decouple import config
import requests
from hotels.models import Hotel, HotelImage, Room, RoomImage, Service
from notifications.models import Notification
from reservations.models import Payment, Reservation

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

        if 'backoffice' in sns_topic:
            if 'hotel-created' in sns_event_type:
                hotel = Hotel.objects.create(
                    name=data['name'],
                    description=data['description'],
                    external_id=data['id'],
                    address=data['address'],
                    city=data['city'],
                    country=data['country'],
                    phone=data['phone'],
                    email=data['email'],
                    stars=data['stars'],
                    latitude=data['latitude'],
                    longitude=data['longitude'],
                )

                hotel.close_locations.set(data['close_locations'])
                hotel.save()


            elif 'hotel-updated' in sns_event_type:
                hotel = Hotel.objects.get(external_id=data['id'])
                for key, value in data.items():
                    if hasattr(hotel, key) and key != 'id':
                        if key == 'close_locations':
                            hotel.close_locations.set(value)
                        else:
                            setattr(hotel, key, value)
                hotel.save()

            elif 'hotel-deleted' in sns_event_type:
                Hotel.objects.filter(external_id=data['id']).delete()

            elif 'hotel-image-created' in sns_event_type:
                hotel = Hotel.objects.get(external_id=data['hotel'])
                HotelImage.objects.create(
                    hotel=hotel,
                    image=data['image_url'],
                    external_id=data['id']
                )

            # Eventos relacionados con habitaciones
            elif 'room-created' in sns_event_type:
                hotel = Hotel.objects.get(external_id=data['hotel'])
                Room.objects.create(
                    hotel=hotel,
                    floor=data['floor'],
                    name=data['name'],
                    price=data['price'],
                    state=data['state'],
                    double_beds_amount=data['double_beds_amount'],
                    single_beds_amount=data['single_beds_amount'],
                    external_id=data['id']
                )

            elif 'room-updated' in sns_event_type:
                room = Room.objects.get(external_id=data['id'])
                for key, value in data.items():
                    if hasattr(room, key) and key != 'hotel' and key != 'id':
                        setattr(room, key, value)
                room.save()

            elif 'room-deleted' in sns_event_type:
                Room.objects.filter(external_id=data['id']).delete()

            elif 'room-image-created' in sns_event_type:
                room = Room.objects.get(external_id=data['room'])
                RoomImage.objects.create(
                    room=room,
                    image=data['image_url'],
                    external_id=data['id']
                )

            # Eventos relacionados con servicios
            elif 'service-created' in sns_event_type:
                hotel = Hotel.objects.get(external_id=data['hotel'])
                Service.objects.create(
                    hotel=hotel,
                    name=data['name'],
                    detail=data['detail'],
                    price=data['price'],
                    is_available=data.get('is_available', True),
                    external_id=data['id']
                )

            elif 'service-updated' in sns_event_type:
                service = Service.objects.get(external_id=data['id'])
                for key, value in data.items():
                    if hasattr(service, key) and key != 'hotel' and key != 'id':
                        setattr(service, key, value)
                service.save()

            elif 'service-deleted' in sns_event_type:
                Service.objects.filter(external_id=data['id']).delete()

            # Eventos relacionados con reservas
            elif 'reservation-updated' in sns_event_type:
                reservation = Reservation.objects.get(id=data['external_id'])
                previous_status = reservation.status
                reservation.status = data['status']
                reservation.start_date = data['start_date']
                reservation.end_date = data['end_date']
                reservation.save()

                if previous_status != 'cancelled' and reservation.status == 'cancelled':
                    Notification.objects.create(
                        user=reservation.user_profile.user,
                        object_type='reservation',
                        object_id=reservation.id,
                        message=f'Su reserva en el hotel {reservation.room.hotel.name} ha sido cancelada',
                    )

            else:
                print(f"Evento no manejado: {sns_message}")
        elif 'gatewaydepagos' in sns_topic:
            # Eventos de transacción
            if sns_event_type == 'valid-transaction':
                reservation = Reservation.objects.get(id=data['reservation'])
                Payment.objects.create(
                    reservation=reservation,
                    date_paid=data['date_paid'],
                    last_four_digits=data['last_four_digits'],
                    payment_method=data['payment_method'],
                    amount=data['amount'],
                    external_id=data['id']
                )
                reservation.status = 'confirmed'
                reservation.save()

            elif sns_event_type == 'failed-transaction':
                reservation = Reservation.objects.get(id=data['reservation'])
                reservation.status = 'cancelled'
                reservation.save()

            elif sns_event_type == 'generated-customer-invoice':
                pass

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