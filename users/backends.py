from django.contrib.auth.backends import ModelBackend

class RoleBackend(ModelBackend):
    """
    Custom authentication backend to check permissions granted via the user's custom Role.
    """
    def _get_role_permissions(self, user_obj):
        if not hasattr(user_obj, '_role_perm_cache'):
            if user_obj.is_active and hasattr(user_obj, 'role') and user_obj.role:
                perms = user_obj.role.permissions.all().select_related('content_type')
                user_obj._role_perm_cache = {f"{p.content_type.app_label}.{p.codename}" for p in perms}
            else:
                user_obj._role_perm_cache = set()
        return user_obj._role_perm_cache

    def get_user_permissions(self, user_obj, obj=None):
        return set()

    def get_group_permissions(self, user_obj, obj=None):
        return self._get_role_permissions(user_obj)

    def get_all_permissions(self, user_obj, obj=None):
        if not user_obj.is_active or user_obj.is_anonymous or obj is not None:
            return set()
        return self._get_role_permissions(user_obj)

    def has_perm(self, user_obj, perm, obj=None):
        return perm in self.get_all_permissions(user_obj, obj)
