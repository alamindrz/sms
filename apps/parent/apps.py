from django.apps import AppConfig

class ParentConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.parent'
    verbose_name = 'Parent Portal'