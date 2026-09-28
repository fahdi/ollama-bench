### FILE: requirements.txt
```txt
Django>=5.0,<6.0
psycopg[binary]>=3.1.12
gunicorn>=21.2.0
```

### FILE: Dockerfile
```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["sh", "-c", "python manage.py makemigrations todo && python manage.py migrate --noinput && gunicorn config.wsgi --bind 0.0.0.0:8000"]
```

### FILE: docker-compose.yml
```yaml
version: '3.8'

services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: todo
      POSTGRES_USER: todo
      POSTGRES_PASSWORD: todo
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U todo -d todo"]
      interval: 10s
      timeout: 5s
      retries: 5
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - todo-network

  web:
    build: .
    depends_on:
      db:
        condition: service_healthy
    environment:
      POSTGRES_DB: todo
      POSTGRES_USER: todo
      POSTGRES_PASSWORD: todo
      POSTGRES_HOST: db
      DJANGO_SECRET_KEY: ${DJANGO_SECRET_KEY:-not-so-secret-key-for-dev}
      DJANGO_DEBUG: 0
    ports:
      - "${WEB_PORT:-8000}:8000"
    networks:
      - todo-network

volumes:
  postgres_data:

networks:
  todo-network:
```

### FILE: manage.py
```python
#!/usr/bin/env python
import os
import sys

if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)
```

### FILE: config/__init__.py
```python
```

### FILE: config/settings.py
```python
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-default-key-for-dev')

DEBUG = os.environ.get('DJANGO_DEBUG', '0') == '1'

ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'todo',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('POSTGRES_DB', 'todo'),
        'USER': os.environ.get('POSTGRES_USER', 'todo'),
        'PASSWORD': os.environ.get('POSTGRES_PASSWORD', 'todo'),
        'HOST': os.environ.get('POSTGRES_HOST', 'db'),
        'PORT': '5432',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
```

### FILE: config/urls.py
```python
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('todo.urls')),
]
```

### FILE: config/wsgi.py
```python
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_wsgi_application()
```

### FILE: todo/__init__.py
```python
```

### FILE: todo/apps.py
```python
from django.apps import AppConfig

class TodoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'todo'
```

### FILE: todo/models.py
```python
from django.db import models

class Project(models.Model):
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Task(models.Model):
    project = models.ForeignKey(Project, related_name='tasks', on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    done = models.BooleanField(default=False)
    priority = models.IntegerField(default=3, validators=[lambda x: 1 <= x <= 5])
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
```

### FILE: todo/views.py
```python
import json
from datetime import datetime
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db import transaction
from .models import Project, Task

def health_check(request):
    try:
        Project.objects.exists()
        db_ok = True
    except Exception:
        db_ok = False
    return JsonResponse({"status": "ok", "db": db_ok})

@csrf_exempt
@require_http_methods(["POST"])
def create_project(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    name = data.get("name")
    if not name or not name.strip():
        return JsonResponse({"error": "Name is required"}, status=400)

    try:
        with transaction.atomic():
            project = Project.objects.create(name=name.strip())
    except Exception:
        return JsonResponse({"error": "Project name already exists"}, status=400)

    return JsonResponse({
        "id": project.id,
        "name": project.name,
        "task_count": 0
    }, status=201)

def list_projects(request):
    projects = Project.objects.annotate(task_count=models.Count('tasks')).order_by('name')
    result = [
        {
            "id": p.id,
            "name": p.name,
            "task_count": p.task_count
        } for p in projects
    ]
    return JsonResponse(result, safe=False)

@csrf_exempt
@require_http_methods(["POST"])
def create_task(request, project_id):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        return JsonResponse({"error": "Project not found"}, status=404)

    title = data.get("title")
    if not title or not title.strip():
        return JsonResponse({"error": "Title is required"}, status=400)

    priority = data.get("priority", 3)
    if not isinstance(priority, int) or not (1 <= priority <= 5):
        return JsonResponse({"error": "Priority must be an integer between 1 and 5"}, status=400)

    due_date_str = data.get("due_date")
    due_date = None
    if due_date_str:
        try:
            due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
        except ValueError:
            return JsonResponse({"error": "Invalid date format. Use YYYY-MM-DD"}, status=400)

    task = Task.objects.create(
        project=project,
        title=title.strip(),
        priority=priority,
        due_date=due_date
    )

    return JsonResponse({
        "id": task.id,
        "project_id": task.project.id,
        "title": task.title,
        "done": task.done,
        "priority": task.priority,
        "due_date": task.due_date.isoformat() if task.due_date else None
    }, status=201)

def list_tasks(request, project_id):
    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        return JsonResponse({"error": "Project not found"}, status=404)

    tasks = Task.objects.filter(project=project).order_by('-priority', 'id')

    done_filter = request.GET.get('done')
    if done_filter is not None:
        done_bool = done_filter.lower() == 'true'
        tasks = tasks.filter(done=done_bool)

    result = [
        {
            "id": t.id,
            "project_id": t.project.id,
            "title": t.title,
            "done": t.done,
            "priority": t.priority,
            "due_date": t.due_date.isoformat() if t.due_date else None
        } for t in tasks
    ]
    return JsonResponse(result, safe=False)

@csrf_exempt
@require_http_methods(["PATCH"])
def update_task(request, task_id):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    try:
        task = Task.objects.get(id=task_id)
    except Task.DoesNotExist:
        return JsonResponse({"error": "Task not found"}, status=404)

    if 'title' in data:
        title = data['title']
        if not title or not title.strip():
            return JsonResponse({"error": "Title is required"}, status=400)
        task.title = title.strip()

    if 'priority' in data:
        priority = data['priority']
        if not isinstance(priority, int) or not (1 <= priority <= 5):
            return JsonResponse({"error": "Priority must be an integer between 1 and 5"}, status=400)
        task.priority = priority

    if 'due_date' in data:
        due_date_str = data['due_date']
        due_date = None
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
            except ValueError:
                return JsonResponse({"error": "Invalid date format. Use YYYY-MM-DD"}, status=400)
        task.due_date = due_date

    if 'done' in data:
        done = data['done']
        if not isinstance(done, bool):
            return JsonResponse({"error": "Done must be a boolean"}, status=400)
        task.done = done

    task.save()

    return JsonResponse({
        "id": task.id,
        "project_id": task.project.id,
        "title": task.title,
        "done": task.done,
        "priority": task.priority,
        "due_date": task.due_date.isoformat() if task.due_date else None
    })

@csrf_exempt
@require_http_methods(["DELETE"])
def delete_task(request, task_id):
    try:
        task = Task.objects.get(id=task_id)
    except Task.DoesNotExist:
        return JsonResponse({"error": "Task not found"}, status=404)

    task.delete()
    return JsonResponse({}, status=204)
```

### FILE: todo/urls.py
```python
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
```

### FILE: todo/admin.py
```python
from django.contrib import admin
from .models import Project, Task

admin.site.register(Project)
admin.site.register(Task)
```

### FILE: todo/migrations/__init__.py
```python
```