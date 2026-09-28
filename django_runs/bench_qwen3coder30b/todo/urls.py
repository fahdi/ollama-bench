from django.urls import path
from . import views

urlpatterns = [
    path('health/', views.health_check, name='health'),
    path('projects/', views.list_projects, name='list_projects'),
    path('projects/', views.create_project, name='create_project'),
    path('projects/<int:project_id>/tasks/', views.list_tasks, name='list_tasks'),
    path('projects/<int:project_id>/tasks/', views.create_task, name='create_task'),
    path('tasks/<int:task_id>/', views.update_task, name='update_task'),
    path('tasks/<int:task_id>/', views.delete_task, name='delete_task'),
]
