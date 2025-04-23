import os

from fabric.api import env, lcd, local
from pydiploy.decorators import do_verbose


@do_verbose
def get_release_name():
    local_repo = local("pwd", capture=True)
    distant_repo = local("git config --get remote.origin.url", capture=True)
    temp_dir = local("mktemp -d", capture=True)
    working_dir = os.path.join(temp_dir, "git-clone")

    print("Local repo: {}".format(local_repo))
    print("Distant repo: {}".format(distant_repo))
    print("Temp dir: {}".format(temp_dir))
    print("Working dir: {}".format(working_dir))

    # First we git clone the local repo in the local tmp dir
    with lcd(temp_dir):
        print("Cloning local repo in {}".format(local("pwd", capture=True)))
        local("git clone {} {}".format(local_repo, working_dir))
    with lcd(working_dir):
        # As a result of the local git clone, the origin of the cloned repo is the local repo
        # So we reset it to be the distant repo
        print("Setting origin in the temp repo to be {}".format(distant_repo))
        local("git remote remove origin")
        local("git remote add origin {}".format(distant_repo))
        print("Checking out to deployed tag {}".format(env.tag))
        local("git checkout {}".format(env.tag))
        project_version = local("git describe --long --always", capture=True)
        print(
            "Getting project release name (for Sentry): ({})".format(project_version)
        )

    return project_version


@do_verbose
def declare_release(release_name):

    # Create a release
    print("Declaring new release to Sentry")
    local(
        "sentry-cli releases new -p {} {}".format(
            env.sentry_application_name, release_name
        )
    )

    # Associate commits with the release
    print("Associating commits with new release for Sentry")
    local("sentry-cli releases set-commits --ignore-missing --auto {}".format(release_name))

    # Declare deployment
    print("Declaring new deployment to Sentry")
    local("sentry-cli releases deploys {} new -e {}".format(release_name, env.goal))
