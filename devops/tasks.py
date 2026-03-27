from pathlib import Path

from invoke import task

ROOT = Path(__file__).resolve().parent.parent


@task
def build(c):
    c.run(f"docker compose -f {ROOT}/docker-compose.yml build", pty=True)


@task
def up(c):
    c.run(f"docker compose -f {ROOT}/docker-compose.yml up -d", pty=True)


@task
def down(c):
    c.run(f"docker compose -f {ROOT}/docker-compose.yml down", pty=True)


@task
def logs(c):
    c.run(f"docker compose -f {ROOT}/docker-compose.yml logs -f web", pty=True)


@task
def manage(c, command):
    c.run(
        f"docker compose -f {ROOT}/docker-compose.yml exec web uv run python manage.py {command}",
        pty=True,
    )


@task
def shell(c):
    c.run(
        f"docker compose -f {ROOT}/docker-compose.yml exec web uv run python manage.py shell_plus",
        pty=True,
    )


@task
def test(c):
    c.run(
        f"docker compose -f {ROOT}/docker-compose.yml exec web uv run pytest",
        pty=True,
    )


@task
def fmt(c):
    c.run(
        f"docker compose -f {ROOT}/docker-compose.yml exec web uv run black . "
        f"&& docker compose -f {ROOT}/docker-compose.yml exec web uv run isort .",
        pty=True,
    )


@task
def migrate(c):
    manage(c, "migrate")


@task
def makemigrations(c):
    manage(c, "makemigrations")


CDC_SERVICES = "redpanda redpanda-console connect opensearch cdc-consumer"


@task(name="cdc-up")
def cdc_up(c):
    c.run(
        f"docker compose -f {ROOT}/docker-compose.yml up -d {CDC_SERVICES}",
        pty=True,
    )


@task(name="cdc-logs")
def cdc_logs(c, service="redpanda"):
    c.run(f"docker compose -f {ROOT}/docker-compose.yml logs -f {service}", pty=True)


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


@task
def tailwind(c):
    c.run(
        f"docker compose -f {ROOT}/docker-compose.yml exec web "
        "tailwindcss -i ./assets/css/input.css -o ./assets/css/tailwind.out.css --watch",
        pty=True,
    )


@task
def tailwind_build(c):
    c.run(
        f"docker compose -f {ROOT}/docker-compose.yml exec web "
        "tailwindcss -i ./assets/css/input.css -o ./assets/css/tailwind.out.css --minify",
        pty=True,
    )
