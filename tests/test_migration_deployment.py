"""Repository deployment contract; external deployer behavior still requires rollout checks."""

from pathlib import Path

import pytest
import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DATABASE_SERVICES = {
    "board-games": "board_games",
    "clubs": "clubs",
    "events": "events",
    "forms": "forms",
    "guard": "guard",
    "tabletennis": "tabletennis",
    "when2meet": "when2meet",
    "schedule": "schedule",
    "schedule-assistant": "schedule_assistant",
}


def test_database_services_have_migration_gate_and_database_readiness():
    compose = yaml.safe_load((REPOSITORY_ROOT / "docker-compose.yaml").read_text())
    services = compose["services"]
    for compose_name, python_name in DATABASE_SERVICES.items():
        service = services[compose_name]
        assert service["pre_start"] == [{"command": ["python", "-m", "src.migrations", python_name]}]
        assert "./settings.yaml:/app/settings.yaml:ro" in service["volumes"]
        database = "postgres" if python_name in ("schedule", "schedule_assistant") else "mongodb"
        assert service["depends_on"][database]["condition"] == "service_healthy"
    for name in ("maps", "room-booking", "student-affairs"):
        assert "pre_start" not in services[name]
    assert "schedule-alembic-migrate" not in services
    assert "schedule-assistant-alembic-migrate" not in services


def test_ci_uses_native_services_and_initializes_replica_set_before_tests():
    workflow = yaml.safe_load((REPOSITORY_ROOT / ".github/workflows/tests.yaml").read_text())
    job = workflow["jobs"]["test"]
    services = job["services"]
    local_services = yaml.safe_load((REPOSITORY_ROOT / "docker-compose.test.yaml").read_text())["services"]
    for name in ("postgres", "mongodb", "minio"):
        assert services[name]["image"] == local_services[f"test-{name}"]["image"]
    assert services["postgres"]["ports"] == ["35432:5432"]
    assert services["mongodb"]["ports"] == ["37017:27017"]
    assert services["minio"]["ports"] == ["19000:9000", "19001:9001"]
    assert services["minio"]["command"] == 'server /data --console-address ":9001"'
    mongo = services["mongodb"]
    assert mongo["entrypoint"] == "bash"
    assert "--replSet rs0" in mongo["command"]
    assert "--keyFile /data/configdb/replica-set.key" in mongo["command"]
    assert mongo["env"]["MONGO_REPLICA_HOST"] == "localhost:27017"

    steps = job["steps"]
    initialization_index = next(i for i, step in enumerate(steps) if step["name"] == "Initialize MongoDB replica set")
    test_index = next(i for i, step in enumerate(steps) if step.get("id") == "tests")
    assert initialization_index < test_index
    initialization = steps[initialization_index]
    assert initialization["env"]["MONGO_CONTAINER"] == "${{ job.services.mongodb.id }}"
    assert "scripts/mongodb/ready.js" in initialization["run"]
    assert "timeout 180s" in initialization["run"]
    assert "mongosh --quiet --nodb /tmp/replica-set-ready.js" in initialization["run"]
    assert all("docker compose" not in step.get("run", "") for step in steps)
    assert all(not step.get("uses", "").startswith("docker/setup-compose-action") for step in steps)


def test_targeted_and_all_deployments_share_environment_concurrency():
    path = REPOSITORY_ROOT / ".github/workflows/build-and-deploy.yaml"
    workflow = yaml.safe_load(path.read_text())
    # YAML 1.1 resolves GitHub's unquoted `on` key as True.
    service_input = workflow[True]["workflow_dispatch"]["inputs"]["service"]
    assert set(DATABASE_SERVICES) <= set(service_input["options"])
    assert service_input["default"] == "all"
    deploy = workflow["jobs"]["deploy"]
    assert deploy["concurrency"] == {
        "group": "deploy-${{ github.event.inputs.environment || 'staging' }}",
        "cancel-in-progress": False,
    }
    step = deploy["steps"][0]
    assert step["env"]["IMAGE_ID"] == "${{ needs.build-and-push-image.outputs.imageid }}"
    assert step["env"]["SERVICE"] == "${{ github.event.inputs.service || 'all' }}"
    assert 'if $service == "" or $service == "all" then [] else [$service] end' in step["run"]
    assert "Deployment did not complete successfully" in step["run"]
    assert "exit 1" in step["run"]


@pytest.mark.parametrize(
    ("filename", "service_name"),
    [("docker-compose.yaml", "mongodb"), ("docker-compose.test.yaml", "test-mongodb")],
)
def test_mongo_bootstrap_uses_persistent_key_and_primary_readiness(filename: str, service_name: str):
    compose = yaml.safe_load((REPOSITORY_ROOT / filename).read_text())
    service = compose["services"][service_name]
    assert service["entrypoint"] == ["bash", "/opt/mongodb/entrypoint.sh"]
    assert service["healthcheck"]["test"] == ["CMD", "mongosh", "--quiet", "--nodb", "/opt/mongodb/ready.js"]
    assert any(volume.endswith(":/data/configdb") for volume in service["volumes"])
    assert service["environment"]["MONGO_REPLICA_HOST"].endswith(":27017" if service_name == "mongodb" else ":37017")
