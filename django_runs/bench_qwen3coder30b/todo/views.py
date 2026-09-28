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
