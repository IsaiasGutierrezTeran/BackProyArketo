"""Project routes, mounted under /api/ -> /api/projects/."""

from __future__ import annotations

from rest_framework.routers import DefaultRouter

from .views import CommentViewSet, InvitationViewSet, ProjectViewSet

router = DefaultRouter()
router.register("projects", ProjectViewSet, basename="project")
router.register("comments", CommentViewSet, basename="comment")
router.register("invitations", InvitationViewSet, basename="invitation")

urlpatterns = router.urls
