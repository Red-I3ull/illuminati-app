from django.contrib import admin
from .models import EntryPassword, CustomUser, Marker

@admin.register(EntryPassword)
class EntryPasswordAdmin(admin.ModelAdmin):
    list_display = ('id', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active',)


admin.register(CustomUser)
admin.site.register(Marker)