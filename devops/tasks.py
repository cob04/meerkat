from pathlib import Path

from invoke import task

ROOT = Path(__file__).resolve().parent.parent


@task
def build(c):
    c.run(f"docker compose -f {ROOT}/docker/docker-compose.yml build", pty=True)


@task
def up(c):
    c.run(f"docker compose -f {ROOT}/docker/docker-compose.yml up -d", pty=True)


@task
def down(c):
    c.run(f"docker compose -f {ROOT}/docker/docker-compose.yml down", pty=True)


@task
def logs(c):
    c.run(f"docker compose -f {ROOT}/docker/docker-compose.yml logs -f web", pty=True)


@task
def manage(c, command):
    c.run(
        f"docker compose -f {ROOT}/docker/docker-compose.yml exec web uv run python manage.py {command}",
        pty=True,
    )


@task
def shell(c):
    c.run(
        f"docker compose -f {ROOT}/docker/docker-compose.yml exec web uv run python manage.py shell_plus",
        pty=True,
    )


@task
def test(c):
    c.run(
        f"docker compose -f {ROOT}/docker/docker-compose.yml exec web uv run pytest",
        pty=True,
    )


@task
def fmt(c):
    exec_web = f"docker compose -f {ROOT}/docker/docker-compose.yml exec web"
    uv_run = "uv run --project /opt/meerkat/src"
    c.run(
        f"{exec_web} {uv_run} black . && {exec_web} {uv_run} isort .",
        pty=True,
    )
    tailwind_build(c)


@task
def migrate(c):
    manage(c, "migrate")


@task
def makemigrations(c):
    manage(c, "makemigrations")


@task(name="seed-demo")
def seed_demo(c, reset=False):
    args = "seed_demo"
    if reset:
        args += " --reset"
    manage(c, args)


CDC_SERVICES = "redpanda redpanda-console connect opensearch cdc-consumer"


@task(name="cdc-up")
def cdc_up(c):
    c.run(
        f"docker compose -f {ROOT}/docker/docker-compose.yml up -d {CDC_SERVICES}",
        pty=True,
    )


@task(name="cdc-logs")
def cdc_logs(c, service="redpanda"):
    c.run(f"docker compose -f {ROOT}/docker/docker-compose.yml logs -f {service}", pty=True)


@task(name="cdc-setup")
def cdc_setup(c):
    manage(c, "setup_opensearch")
    manage(c, "register_connector")
    manage(c, "start_consumer")


@task(name="cdc-status")
def cdc_status(c):
    c.run(
        f"docker exec meerkat-redpanda rpk cluster info",
        pty=True,
    )


TAILWIND_RUN = (
    f"docker run --rm -v {ROOT}/src:/app "
    f"-w /app meerkat-tailwind"
)


@task
def tailwind(c):
    c.run(f"{TAILWIND_RUN} -i ./assets/css/input.css -o ./assets/css/tailwind.out.css --watch", pty=True)


@task
def tailwind_build(c):
    c.run(f"{TAILWIND_RUN} -i ./assets/css/input.css -o ./assets/css/tailwind.out.css --minify", pty=True)


@task(name="tailwind-image")
def tailwind_image(c):
    c.run(f"docker build --network=host -t meerkat-tailwind {ROOT}/docker/tailwind", pty=True)


@task(
    help={
        "test_path": "Specific test file or directory (e.g. e2e/test_toast_notifications.py)",
        "headed": "Run in headed mode (visible browser)",
        "keyword": "Filter tests by keyword expression",
    }
)
def e2e(c, test_path="e2e/", headed=False, keyword=""):
    """Run Playwright E2E tests against the running dev server."""
    manage(c, "ensure_test_user")
    args = [test_path, "-v"]
    if keyword:
        args.append(f"-k '{keyword}'")
    args_str = " ".join(args)
    browser_arg = "--headed" if headed else ""
    c.run(
        f"docker compose -f {ROOT}/docker/docker-compose.e2e.yml run --rm playwright "
        f"pytest {args_str} {browser_arg}",
        pty=True,
    )
