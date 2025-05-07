from therapists.models import Therapist
from rest_framework import serializers

class TherapistSerializer(serializers.ModelSerializer):
    class Meta:
        model = Therapist
        fields = ['id', 'name', 'email', 'phone', 'created_at', 'last_updated']
