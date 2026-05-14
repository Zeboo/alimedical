from django.apps import AppConfig


OPD_OPERATOR_GROUP = "OPD Operator"


class OpdConfig(AppConfig):
    name = 'opd'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        from django.db.models.signals import post_migrate, post_save
        from django.contrib.auth import get_user_model

        post_migrate.connect(_sync_opd_operator_group, sender=self)
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
