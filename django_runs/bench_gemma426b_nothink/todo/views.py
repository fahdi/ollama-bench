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
