"""Tests for lifespan startup configuration error handling"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.auth.utils import lifespan
from config import config


def test_startup_fails_when_supabase_config_missing(monkeypatch):
    """Test startup fails gracefully when both Supabase configs are missing"""
    monkeypatch.setattr(config, "SUPABASE_URL", None)
    monkeypatch.setattr(config, "SUPABASE_ANON_KEY", None)

    app = FastAPI(lifespan=lifespan)

    with pytest.raises(RuntimeError, match="Supabase configuration missing"):
        with TestClient(app):
            pass


def test_startup_fails_when_only_url_missing(monkeypatch):
    """Test startup fails when only URL is missing"""
    monkeypatch.setattr(config, "SUPABASE_URL", None)
    monkeypatch.setattr(config, "SUPABASE_ANON_KEY", "valid-key")

    app = FastAPI(lifespan=lifespan)

    with pytest.raises(RuntimeError, match="Supabase configuration missing"):
        with TestClient(app):
            pass


def test_startup_fails_when_only_key_missing(monkeypatch):
    """Test startup fails when only key is missing"""
    monkeypatch.setattr(config, "SUPABASE_URL", "http://test.supabase.co")
    monkeypatch.setattr(config, "SUPABASE_ANON_KEY", None)

    app = FastAPI(lifespan=lifespan)

    with pytest.raises(RuntimeError, match="Supabase configuration missing"):
        with TestClient(app):
            pass
