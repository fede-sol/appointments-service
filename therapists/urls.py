from django.urls import path
from . import views

urlpatterns = [
    path('', views.TherapistListApi.as_view()),
    path('<int:therapist_id>/', views.TherapistDetailApi.as_view()),
    path('create/', views.CreateTherapistApi.as_view()),
]