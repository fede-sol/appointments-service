from rest_framework.views import APIView
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework import status
from .models import Therapist
from datetime import datetime, timedelta
import pytz
from appointments.models import Appointment
from django.db import models

class TherapistListApi(APIView):
    class OutputSerializer(serializers.ModelSerializer):
        class Meta:
            model = Therapist
            fields = '__all__'

    def get(self, request):
        therapists = Therapist.objects.all()
        serializer = self.OutputSerializer(therapists, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class TherapistDetailApi(APIView):
    class OutputSerializer(serializers.ModelSerializer):
        class Meta:
            model = Therapist
            fields = '__all__'

    def get(self, request, therapist_id):
        try:
            therapist = Therapist.objects.get(id=therapist_id)
            serializer = self.OutputSerializer(therapist)

            # Obtener zona horaria de Buenos Aires
            buenos_aires_tz = pytz.timezone('America/Argentina/Buenos_Aires')
            
            # Obtener fecha actual y generar rango de una semana (en zona horaria de Buenos Aires)
            today = datetime.now(buenos_aires_tz).replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = today + timedelta(days=7)

            # Definir horarios disponibles (de 9 a 19)
            available_hours = [f"{h:02d}:00" for h in range(9, 20)]

            # Obtener todas las citas del terapeuta en el rango de fechas
            appointments = Appointment.objects.filter(
                therapist_id=therapist_id,
                begin_date__gte=today,
                begin_date__lt=end_date
            )

            # Crear diccionario con disponibilidad
            availability = {}

            # Para cada día en el rango
            current_date = today
            while current_date < end_date:
                date_str = current_date.strftime("%Y-%m-%d")
                availability[date_str] = {}

                # Para cada hora disponible
                for hour_str in available_hours:
                    hour = int(hour_str.split(':')[0])
                    # Crear datetime con la hora específica en zona horaria de Buenos Aires
                    current_datetime = current_date.replace(hour=hour, minute=0, second=0, microsecond=0)

                    # Verificar si hay alguna cita que se superponga con esta hora
                    hour_end = current_datetime + timedelta(hours=1)

                    # Buscar si hay citas que se superpongan con este horario
                    is_available = not appointments.filter(
                        models.Q(begin_date__lt=hour_end) &
                        models.Q(end_date__gt=current_datetime)
                    ).exists()

                    availability[date_str][hour_str] = is_available

                # Avanzar al siguiente día
                current_date += timedelta(days=1)

            # Añadir disponibilidad a la respuesta
            response_data = serializer.data
            response_data['available_slots'] = availability

            return Response(response_data, status=status.HTTP_200_OK)
        except Therapist.DoesNotExist:
            return Response({'detail': 'Terapeuta no encontrado'}, status=status.HTTP_404_NOT_FOUND)
