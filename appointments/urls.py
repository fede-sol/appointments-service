from django.urls import path
from . import views

urlpatterns = [
    path('create/', views.AppointmentsCreateApi.as_view()),
    path('patient/<int:patient_id>/', views.AppointmentsListApi.as_view()),
    path('<int:appointment_id>/', views.AppointmentsDetailApi.as_view()),
]