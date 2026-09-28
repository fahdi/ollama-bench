### FILE: requirements.txt
```text
django>=5.0,<5.1
psycopg[binary]>=3.1.18
gunicorn>=22.0.0
```

### FILE: Dockerfile
```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
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
      interval: 5s
      timeout: 5s
      retries: 5

  web:
    build: .
    command: >
      sh -c "python manage.py makemigrations todo &&
             python manage.py migrate --noinput &&
             gunicorn config.wsgi:application --bind 0.0.0.0:8000"
    volumes:
      - .:/app
    ports:
      - "${WEB_PORT:-8000}:8000"
    environment:
      POSTGRES_DB: todo
      POSTGRES_USER: todo
      POSTGRES_PASSWORD: todo
      POSTGRES_HOST: db
      DJANGO_SECRET_KEY: "change-me-in-production-12345"
      DJANGO_DEBUG: "0"
    depends_on:
      db:
        condition: service_healthy
```

### FILE: manage.py
```python
#!/usr/bin/env python
import os
import sys

def main():
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

if __name__ == '__main__':
    main()
```

### FILE: config/__init__.py
```python
```

### FILE: config/settings.py
```python
import os

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'fallback-secret-key')
DEBUG = os.environ.get('DJANGO_DEBUG', '0') == '1'
ALLOWED_HOSTS = ['*']

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

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'

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
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=200)
    done = models.BooleanField(default=False)
    priority = models.IntegerField(default=3)
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
```

### FILE: todo/admin.py
```python
from django.contrib import admin
from .models import Project, Task

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'project', 'done', 'priority', 'due_date')
    list_filter = ('done', 'priority', 'project')
```

### FILE: todo/urls.py
```python
from django.urls import path
from . import views

urlpatterns = [
    path('health/', views.health_check, name='health'),
    path('projects/', views.project_list_create, name='project_list_create'),
    path('projects/<int:project_id>/tasks/', views.task_list_create, name='task_list_create'),
    path('tasks/<int:task_id>/', views.task_detail_update_delete, name='task_detail'),
]
```

### FILE: todo/migrations/__init__.py
```python
```

### FILE: todo/views.py
```python
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db import IntegrityError
from django.db.models import Count
from datetime import datetime
from .models import Project, Task

def json_response_error(request, message, status=400):
    return JsonResponse({"error": message}, status=status)

@csrf_exempt
@require_http_methods(["GET"])
def health_check(request):
    try:
        # Check DB connectivity
        Project.objects.exists()
        db_ok = True
    except Exception:
        db_ok = False
    return JsonResponse({"status": "ok", "db": db_ok})

@csrf_exempt
@require_http_methods(["GET", "POST"])
def project_list_create(request):
    if request.method == "GET":
        projects = Project.objects.annotate(task_count=Count('tasks')).order_by('name')
        data = [
            {"id": p.id, "name": p.name, "task_count": p.task_count}
            for p in projects
        ]
        return JsonResponse(data)

    if request.method == "POST":
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return json_response_error(request, "Invalid JSON", 400)

        name = body.get("name")
        if not name or not str(name).strip():
            return json_response_error(request, "Name is required")

        try:
            project = Project.objects.create(name=name.strip())
            return JsonResponse({
                "id": project.id,
                "name": project.name,
                "task_count": 0
            }, status=201)
        except IntegrityError:
            return json_response_error(request, "Project name already exists")

@csrf_exempt
@require_http_methods(["GET", "POST"])
def task_list_create(request, project_id):
    try:
        project = Project.objects.get(pk=project_id)
    except Project.DoesNotExist:
        return JsonResponse({"error": "Project not found"}, status=404)

    if request.method == "GET":
        done_param = request.GET.get('done')
        tasks = project.tasks.all()
        if done_param is not None:
            val = done_param.lower() == 'true'
            tasks = tasks.filter(done=val)
        
        tasks = tasks.order_by('-priority', 'id')
        data = [
            {
                "id": t.id,
                "project_id": t.project_id,
                "title": t.title,
                "done": t.done,
                "priority": t.priority,
                "due_date": t.due_date.isoformat() if t.due_date else None
            } for t in tasks
        ]
        return JsonResponse(data)

    if request.method == "POST":
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return json_response_error(request, "Invalid JSON")

        title = body.get("title")
        if not title or not str(title).strip():
            return json_response_error(request, "Title is required")

        priority = body.get("priority", 3)
        try:
            priority = int(priority)
            if not (1 <= priority <= 5):
                raise ValueError()
        except (ValueError, TypeError):
            return json_response_error(request, "Priority must be integer 1-5")

        due_date = body.get("due_date")
        if due_date:
            try:
                due_date = datetime.strptime(due_date, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                return json_response_error(request, "Invalid date format. Use YYYY-MM-DD")
        else:
            due_date = None

        task = Task.objects.create(
            project=project,
            title=title.strip(),
            priority=priority,
            due_date=due_date
        )
        return JsonResponse({
            "id": task.id,
            "project_id": task.project_id,
            "title": task.title,
            "done": task.done,
            "priority": task.priority,
            "due_date": task.due_date.isoformat() if task.due_date else None
        }, status=201)

@csrf_exempt
@require_http_methods(["PATCH", "DELETE"])
def task_detail_update_delete(request, task_id):
    try:
        task = Task.objects.get(pk=task_id)
    except Task.DoesNotExist:
        return JsonResponse({"error": "Task not found"}, status=404)

    if request.method == "PATCH":
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return json_response_error(request, "Invalid JSON")

        if "title" in body:
            title = body["title"]
            if not title or not str(title).strip():
                return json_response_error(request, "Title cannot be blank")
            task.title = title.strip()

        if "done" in body:
            if not isinstance(body["done"], bool):
                return json_response_error(request, "Done must be boolean")
            task.done = body["done"]

        if "priority" in body:
            try:
                p = int(body["priority"])
                if not (1 <= p <= 5):
                    raise ValueError()
                task.priority = p
            except (ValueError, TypeError):
                return json_response_error(request, "Priority must be integer 1-5")

        if "due_date" in body:
            dd = body["due_date"]
            if dd is None:
                task.due_date = None
            else:
                try:
                    task.due_date = datetime.strptime(dd, "%Y-%m-%d").date()
                except (ValueError, TypeError):
                    return json_response_error(request, "Invalid date format. Use YYYY-MM-DD")

        task.save()
        return JsonResponse({
            "id": task.id,
            "project_id": task.project_id,
            "title": task.title,
            "done": task.done,
            "priority": task.priority,
            "due_date": task.due_date.isoformat() if task.due_date else None
        })

    if request.method == "DELETE":
        task.delete()
        return JsonResponse({}, status=204)
```