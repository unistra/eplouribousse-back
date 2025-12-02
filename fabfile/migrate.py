import os

import fabric
import fabtools

# Django tenants uses a tenant-aware version to migrate schemas
import pydiploy
from fabric.api import env, hide
from pydiploy.decorators import do_verbose
from pydiploy.django import wrap_deploy


@do_verbose
def django_prepare():
    """
    We override this from pydiploy because we need to use a custom migrate command
    """

    # remove old statics from local tmp dir before collecting new ones
    with fabric.api.lcd(env.local_tmp_dir):
        fabric.api.local("rm -rf assets/*")

    with fabtools.python.virtualenv(env.remote_virtualenv_dir):
        with fabric.api.cd(env.remote_current_path):
            with fabric.api.settings(sudo_user=env.remote_owner):
                with fabric.api.settings(warn_only=True):
                    fabric.api.sudo("python manage.py migrate")
                    with hide("warnings"):
                        fabric.api.sudo("python manage.py compilemessages")
                fabric.api.sudo("python manage.py collectstatic --noinput")

    fabric.api.get(os.path.join(env.remote_current_path, "assets"), local_path=env.local_tmp_dir)


def deploy_backend(upgrade_pkg=False, **kwargs):
    """We override this from pydiploy because we need to override `django_prepare`"""
    with wrap_deploy():
        fabric.api.execute(pydiploy.require.releases_manager.setup)
        fabric.api.execute(pydiploy.require.releases_manager.deploy_code)
        fabric.api.execute(pydiploy.require.django.utils.deploy_manage_file)
        fabric.api.execute(pydiploy.require.django.utils.deploy_wsgi_file)
        fabric.api.execute(pydiploy.require.python.utils.application_dependencies, upgrade_pkg)
        fabric.api.execute(pydiploy.require.django.utils.app_settings, **kwargs)
        fabric.api.execute(django_prepare)
        fabric.api.execute(pydiploy.require.system.permissions)
        fabric.api.execute(pydiploy.require.circus.app_reload)
        fabric.api.execute(pydiploy.require.releases_manager.cleanup)
