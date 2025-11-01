from django.contrib import admin
from .models import EntryPassword, CustomUser, Marker, VoteType, Vote, UserVote, BlacklistedIP
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

@admin.register(EntryPassword)
class EntryPasswordAdmin(admin.ModelAdmin):
    list_display = ('id', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active',)

class CustomUserAdmin(BaseUserAdmin):
    list_display = ('email', 'username', 'role', 'is_inquisitor', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_active', 'is_inquisitor')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Custom Fields', {'fields': ('role', 'is_inquisitor', 'last_promotion_attempt')}),
    )
    ordering = ('email',)


admin.site.register(CustomUser, CustomUserAdmin)

admin.site.register(Marker)

@admin.register(VoteType)
class VoteTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'nomination_duration_hours', 'duration_hours', 'pass_condition', 'inquisitor_can_initiate',
                    'eligible_voter_roles')
    list_filter = ('pass_condition', 'inquisitor_can_initiate')
    search_fields = ('name',)


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ('id', 'vote_type', 'initiator', 'target_user', 'status', 'outcome', 'start_time',
                    'nomination_end_time', 'end_time')
    list_filter = ('status', 'outcome', 'vote_type__name')
    search_fields = ('initiator__username', 'target_user__username')
    readonly_fields = ('start_time',)


@admin.register(UserVote)
class UserVoteAdmin(admin.ModelAdmin):
    list_display = ('id', 'vote_id', 'voter', 'decision', 'voted_at')
    list_filter = ('decision',)
    search_fields = ('voter__username', 'vote__id')

    def vote_id(self, obj):
        return obj.vote.id

    vote_id.short_description = 'Vote ID'
    vote_id.admin_order_field = 'vote__id'

@admin.register(BlacklistedIP)
class BlacklistedIPAdmin(admin.ModelAdmin):
    list_display = ('ip_address', 'reason', 'created_at')
    search_fields = ('ip_address', 'reason')
    readonly_fields = ('created_at',)

