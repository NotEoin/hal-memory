"""Tests for halmem.config, which reads its tables through halkit.config."""

import pytest
from halkit.config import ConfigError

from halmem import config


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    path = tmp_path / "config.toml"
    monkeypatch.setenv("HAL_CONFIG", str(path))
    monkeypatch.setenv("HAL_DATA_DIR", str(tmp_path / "data"))
    return path


def test_defaults_apply_without_a_config_file(cfg):
    assert config.settings()["answerer"] == "local"
    assert config.settings()["folders"]["conversation"] == "Conversations"


def test_memory_table_overrides_a_default(cfg):
    cfg.write_text("[memory]\nbatch = 5\n")
    assert config.settings()["batch"] == 5


def test_unknown_memory_key_is_refused_with_its_name(cfg):
    cfg.write_text("[memory]\nbatsh = 5\n")
    with pytest.raises(ConfigError, match="batsh"):
        config.settings()


def test_answerer_outside_its_choices_is_refused(cfg):
    cfg.write_text('[memory]\nanswerer = "cloud"\n')
    with pytest.raises(ConfigError, match="answerer"):
        config.settings()


def test_vault_comes_from_the_hal_table(cfg, tmp_path):
    cfg.write_text(f'[hal]\nvault = "{tmp_path}/v"\n')
    assert config.vault() == tmp_path / "v"


def test_data_dir_is_created_under_the_hal_data_dir(cfg, tmp_path):
    assert config.data_dir() == tmp_path / "data" / "memory"
    assert config.data_dir().is_dir()
