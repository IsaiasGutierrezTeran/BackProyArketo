"""Budget routes, mounted under /api/."""

from __future__ import annotations

from rest_framework.routers import DefaultRouter

from .views import BudgetViewSet, MaterialCategoryViewSet, MaterialViewSet

router = DefaultRouter()
router.register(
    "material-categories",
    MaterialCategoryViewSet,
    basename="material-category",
)
router.register("materials", MaterialViewSet, basename="material")
router.register("budgets", BudgetViewSet, basename="budget")

urlpatterns = router.urls
