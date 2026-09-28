from django.urls import path
from . import views

urlpatterns = [
    path('health/', views.health_check, name='health'),
    path('projects/', views.project_list_create, name='project_list_create'),
    path('projects/<int:project_id>/tasks/', views.task_list_create, name='task_list_create'),
    path('tasks/<int:task_id>/', views.task_detail_update_delete, name='task_detail'),
]
