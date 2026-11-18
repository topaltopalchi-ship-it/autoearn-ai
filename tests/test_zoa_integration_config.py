from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ZOA = ROOT / "integrations" / "zoa"


def test_zoa_runtime_pins_upstream_and_does_not_bake_in_credentials():
    dockerfile = (ZOA / "Dockerfile").read_text()
    env_example = (ZOA / ".env.example").read_text()
    assert "4016552105862093699c5d20a6aff6255c86fc9c" in dockerfile
    assert "npm ci" in dockerfile
    assert "REPLACE_WITH_YOUR_ZOA_AGENT_KEY" in env_example
    assert "in2it_agt_" not in dockerfile
    assert not (ZOA / ".env").exists()


def test_zoa_worker_is_persistent_but_exposes_no_inbound_ports():
    compose = (ZOA / "docker-compose.yml").read_text()
    assert "restart: unless-stopped" in compose
    assert "env_file:" in compose
    assert "ports:" not in compose
    assert "https://play.zoagames.com" in compose


def test_zoa_setup_documents_human_consent_and_prize_uncertainty():
    readme = (ZOA / "README.md").read_text().lower()
    assert "create a zoa account yourself" in readme
    assert "no prize pool" in readme
    assert "no earnings are guaranteed" in readme
    assert "never paste it into a chat" in readme
    assert "does not yet control, monitor, or store this worker's api" in readme
