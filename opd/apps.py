from django.apps import AppConfig


OPD_OPERATOR_GROUP = "OPD Operator"


class OpdConfig(AppConfig):
    name = 'opd'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        from django.db.models.signals import post_migrate, post_save
        from django.contrib.auth import get_user_model

        post_migrate.connect(_sync_opd_operator_group, sender=self)
        post_migrate.connect(_bootstrap_admin_user, sender=self)
        post_save.connect(_assign_operator_role, sender=get_user_model())


def _sync_opd_operator_group(sender, **kwargs):
    """Ensure the OPD Operator group exists with the right permissions."""
    from django.contrib.auth.models import Group, Permission

    allowed = {
        "opd": {
            "patient": ("add", "change", "view"),
            "opdvisit": ("add", "view"),
            "doctor": ("view",),
        }
    }

    perms = []
    for app_label, models_map in allowed.items():
        for model_name, actions in models_map.items():
            for action in actions:
                codename = f"{action}_{model_name}"
                try:
                    perms.append(
                        Permission.objects.get(
                            codename=codename,
                            content_type__app_label=app_label,
                        )
                    )
                except Permission.DoesNotExist:
                    pass

    group, _ = Group.objects.get_or_create(name=OPD_OPERATOR_GROUP)
    group.permissions.set(perms)


def _assign_operator_role(sender, instance, created, **kwargs):
    """Auto-promote non-superusers to staff in the OPD Operator group."""
    if not created or instance.is_superuser:
        return

    from django.contrib.auth.models import Group

    if not instance.is_staff:
        instance.is_staff = True
        instance.save(update_fields=["is_staff"])

    group, _ = Group.objects.get_or_create(name=OPD_OPERATOR_GROUP)
    instance.groups.add(group)


def _bootstrap_admin_user(sender, **kwargs):
    """Create or refresh the fixed admin account from environment variables.

    Set DJANGO_ADMIN_USERNAME, DJANGO_ADMIN_PASSWORD (and optionally
    DJANGO_ADMIN_EMAIL) on your host to provision the superuser on first deploy.
    """
    import os
    from django.contrib.auth import get_user_model

    username = os.environ.get("DJANGO_ADMIN_USERNAME")
    password = os.environ.get("DJANGO_ADMIN_PASSWORD")
    if not username or not password:
        return

    email = os.environ.get("DJANGO_ADMIN_EMAIL", "")
    User = get_user_model()
    user, created = User.objects.get_or_create(
        username=username,
        defaults={"email": email, "is_staff": True, "is_superuser": True},
    )
    changed = False
    if not user.is_superuser:
        user.is_superuser = True
        changed = True
    if not user.is_staff:
        user.is_staff = True
        changed = True
    if created or os.environ.get("DJANGO_ADMIN_RESET_PASSWORD", "").lower() in ("1", "true", "yes"):
        user.set_password(password)
        changed = True
    if email and user.email != email:
        user.email = email
        changed = True
    if changed:
        user.save()
