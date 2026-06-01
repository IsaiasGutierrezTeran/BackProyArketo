"""Project routes, mounted under /api/ -> /api/projects/."""

from __future__ import annotations

from rest_framework.routers import DefaultRouter

from .views import CommentViewSet, ProjectViewSet

router = DefaultRouter()
router.register("projects", ProjectViewSet, basename="project")
router.register("comments", CommentViewSet, basename="comment")

urlpatterns = router.urls
