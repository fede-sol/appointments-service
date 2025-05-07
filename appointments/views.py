from rest_framework.views import APIView
from appointments.serializers import TherapistSerializer
from .models import Appointment
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework import status
from django.db import models
from appointments_menta_service.libreria_sns_client import publish_to_topic, init_sns_client
from decouple import config

class AppointmentsCreateApi(APIView):
    class InputSerializer(serializers.ModelSerializer):
        class Meta:
            model = Appointment
            fields = '__all__'

    def post(self, request):
        serializer = self.InputSerializer(data=request.data)
        if serializer.is_valid():
            new_begin = serializer.validated_data['begin_date']
            new_end = serializer.validated_data['end_date']
            therapist_id = serializer.validated_data['therapist']

            # Verificar superposición considerando todos los casos posibles
            overlapping_appointments = Appointment.objects.filter(
                therapist_id=therapist_id
            ).filter(
                # Caso 1: La cita existente comienza durante la nueva cita
                # begin_date está entre new_begin y new_end
                (models.Q(begin_date__gte=new_begin) & models.Q(begin_date__lt=new_end)) |
                # Caso 2: La cita existente termina durante la nueva cita
                # end_date está entre new_begin y new_end
                (models.Q(end_date__gt=new_begin) & models.Q(end_date__lte=new_end)) |
                # Caso 3: La cita existente abarca completamente la nueva cita
                # begin_date es anterior a new_begin y end_date es posterior a new_end
                (models.Q(begin_date__lte=new_begin) & models.Q(end_date__gte=new_end))
            )

            if overlapping_appointments.exists():
                return Response({'detail': 'Hay un turno superpuesto'}, status=status.HTTP_400_BAD_REQUEST)
            serializer.save()

            publish_to_topic(init_sns_client(config('AWS_ACCESS_KEY_ID'), config('AWS_SECRET_ACCESS_KEY'), config('AWS_SESSION_TOKEN'), config('AWS_DEFAULT_REGION')), config('TOPIC_ARN_APPOINTMENTS'), 'appointment-created', serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class AppointmentsListApi(APIView):
    class OutputSerializer(serializers.ModelSerializer):
        therapist = TherapistSerializer()
        class Meta:
            model = Appointment
            fields = ['id', 'begin_date', 'end_date', 'patient_id', 'patient_name', 'patient_email', 'patient_phone', 'therapist', 'status', 'link', 'created_at', 'last_updated']

    def get(self, request, patient_id):
        appointments = Appointment.objects.filter(patient_id=patient_id)
        serializer = self.OutputSerializer(appointments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class AppointmentsDetailApi(APIView):
    class OutputSerializer(serializers.ModelSerializer):
        therapist = TherapistSerializer()
        class Meta:
            model = Appointment
            fields = ['id', 'begin_date', 'end_date', 'patient_id', 'patient_name', 'patient_email', 'patient_phone', 'therapist', 'status', 'link', 'created_at', 'last_updated']

    def get(self, request, appointment_id):
        try:
            appointment = Appointment.objects.get(id=appointment_id)
            serializer = self.OutputSerializer(appointment)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Appointment.DoesNotExist:
            return Response({'detail': 'Appointment not found'}, status=status.HTTP_404_NOT_FOUND)
