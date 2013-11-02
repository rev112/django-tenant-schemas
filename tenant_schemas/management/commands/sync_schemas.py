import copy
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db.models import get_apps, get_models
from django.db.models.loading import AppCache
from django.utils.datastructures import SortedDict

if "south" in settings.INSTALLED_APPS:
    from south.management.commands.syncdb import Command as SyncdbCommand
else:
    from django.core.management.commands.syncdb import Command as SyncdbCommand
from django.db import connection
from tenant_schemas.utils import get_tenant_model, get_public_schema_name
from tenant_schemas.management.commands import SyncCommon


class Command(SyncCommon):
    help = "Sync schemas based on TENANT_APPS and SHARED_APPS settings"
    option_list = SyncdbCommand.option_list + SyncCommon.option_list

    def handle_noargs(self, **options):
        super(Command, self).handle_noargs(**options)

        if "south" in settings.INSTALLED_APPS:
            self.options["migrate"] = False

        # save original settings
        OLD_INSTALLED_APPS = copy.copy(settings.INSTALLED_APPS)

        # clear content type's cache as they might different on a tenant
        ContentType.objects.clear_cache()

        if self.sync_public:
            self.sync_public_apps()
        if self.sync_tenant:
            self.sync_tenant_apps(self.schema_name)

        # restore settings
        self._reset_app_cache()
        settings.INSTALLED_APPS = OLD_INSTALLED_APPS

    def _reset_app_cache(self):
        AppCache().loaded = False
        AppCache().app_store = SortedDict()
        #AppCache().app_models = SortedDict()
        AppCache().app_errors = {}
        AppCache().handled = {}

    def _set_managed_apps(self, included_apps):
        """ sets which apps are managed by syncdb """
        self._reset_app_cache()
        settings.INSTALLED_APPS = included_apps

    def _sync_tenant(self, tenant):
        self._notice("=== Running syncdb for schema: %s" % tenant.schema_name)
        connection.set_tenant(tenant, include_public=False)
        SyncdbCommand().execute(**self.options)

    def sync_tenant_apps(self, schema_name=None):
        apps = self.tenant_apps or self.installed_apps
        self._set_managed_apps(apps)
        if schema_name:
            tenant = get_tenant_model().objects.filter(schema_name=schema_name).get()
            self._sync_tenant(tenant)
        else:
            all_tenants = get_tenant_model().objects.exclude(schema_name=get_public_schema_name())
            if not all_tenants:
                self._notice("No tenants found!")

            for tenant in all_tenants:
                self._sync_tenant(tenant)

    def sync_public_apps(self):
        apps = self.shared_apps or self.installed_apps
        self._set_managed_apps(apps)
        SyncdbCommand().execute(**self.options)
        self._notice("=== Running syncdb for schema public")
