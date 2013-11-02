import copy
from django.conf import settings
from django.db import connection
from south import migration
from south.migration.base import Migrations
from south.management.commands.migrate import Command as MigrateCommand
from tenant_schemas.management.commands import SyncCommon
from tenant_schemas.utils import get_tenant_model, get_public_schema_name


class Command(SyncCommon):
    help = "Migrate schemas with South"
    option_list = MigrateCommand.option_list + SyncCommon.option_list

    def handle_noargs(self, **options):
        super(Command, self).handle_noargs(**options)

        # save original settings
        OLD_INSTALLED_APPS = copy.copy(settings.INSTALLED_APPS)

        if self.sync_public:
            self.migrate_public_apps()
        if self.sync_tenant:
            self.migrate_tenant_apps(self.schema_name)

        # restore settings
        self._reset_app_cache()
        settings.INSTALLED_APPS = OLD_INSTALLED_APPS

    def _migrate_schema(self, tenant):
        connection.set_tenant(tenant, include_public=False)
        MigrateCommand().execute(**self.options)

    def migrate_tenant_apps(self, schema_name=None):
        apps = self.tenant_apps or self.installed_apps
        self._set_managed_apps(included_apps=apps)

        if schema_name:
            self._notice("=== Running migrate for schema: %s" % schema_name)
            connection.set_schema_to_public()
            tenant = get_tenant_model().objects.get(schema_name=schema_name)
            self._migrate_schema(tenant)
        else:
            all_tenants = get_tenant_model().objects.exclude(schema_name=get_public_schema_name())
            if not all_tenants:
                self._notice("No tenants found")

            for tenant in all_tenants:
                Migrations._dependencies_done = False  # very important, the dependencies need to be purged from cache
                self._notice("=== Running migrate for schema %s" % tenant.schema_name)
                self._migrate_schema(tenant)

    def migrate_public_apps(self):
        apps = self.shared_apps or self.installed_apps
        self._set_managed_apps(included_apps=apps)

        self._notice("=== Running migrate for schema public")
        MigrateCommand().execute(**self.options)
