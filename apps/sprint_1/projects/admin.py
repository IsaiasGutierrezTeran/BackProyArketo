from django.contrib import admin

from .models import Comment, Project, ProjectMembership


class MembershipInline(admin.TabularInline):
    model = ProjectMembership
    extra = 0
    autocomplete_fields = ["user"]


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "status", "created_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["name", "owner__email"]
    autocomplete_fields = ["owner"]
    inlines = [MembershipInline]


@admin.register(ProjectMembership)
class ProjectMembershipAdmin(admin.ModelAdmin):
    list_display = ["project", "user", "role"]
    list_filter = ["role"]


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ["id", "project", "author", "created_at"]
    search_fields = ["body"]
