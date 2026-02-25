"""Tests for tag CLI helper functions."""

import pytest

from gtm_cli.cli.helpers import add_authuser
from gtm_cli.cli.tags import (
    _check_async_loading,
    _detect_pixels,
    _get_firing_trigger_names,
    _is_all_pages_trigger,
)


class TestAddAuthuser:
    def test_no_authuser(self):
        assert add_authuser("https://example.com/#/path", None) == "https://example.com/#/path"

    def test_empty_url(self):
        assert add_authuser("", 1) == ""

    def test_url_with_hash(self):
        result = add_authuser("https://tagmanager.google.com/#/container", 2)
        assert result == "https://tagmanager.google.com/?authuser=2#/container"

    def test_url_with_existing_query_and_hash(self):
        result = add_authuser("https://example.com/?foo=bar#/path", 1)
        assert result == "https://example.com/?foo=bar&authuser=1#/path"

    def test_url_without_hash(self):
        result = add_authuser("https://example.com/page", 0)
        assert result == "https://example.com/page?authuser=0"


class TestGetFiringTriggerNames:
    def test_with_triggers(self):
        tag = {"firingTriggerId": ["1", "2"]}
        trigger_names = {"1": "All Pages", "2": "Click"}
        assert _get_firing_trigger_names(tag, trigger_names) == "All Pages, Click"

    def test_empty_triggers(self):
        tag = {}
        assert _get_firing_trigger_names(tag, {}) == ""

    def test_missing_trigger_id_falls_back(self):
        tag = {"firingTriggerId": ["99"]}
        trigger_names = {"1": "All Pages"}
        assert _get_firing_trigger_names(tag, trigger_names) == "99"


class TestDetectPixels:
    def test_tiktok(self):
        html = """ttq.load('D1N9ADJC77UCN6B64M50');"""
        result = _detect_pixels(html)
        assert len(result) == 1
        assert result[0]["provider"] == "TikTok"
        assert result[0]["pixel_id"] == "D1N9ADJC77UCN6B64M50"

    def test_meta_facebook(self):
        html = """fbq('init', '1681830978728438');"""
        result = _detect_pixels(html)
        assert len(result) == 1
        assert result[0]["provider"] == "Meta/Facebook"
        assert result[0]["pixel_id"] == "1681830978728438"

    def test_google_ads(self):
        html = """gtag('config', 'AW-123456789');"""
        result = _detect_pixels(html)
        assert len(result) == 1
        assert result[0]["provider"] == "Google Ads"

    def test_no_match(self):
        html = """console.log('hello world');"""
        assert _detect_pixels(html) == []

    def test_multiple_pixels(self):
        html = """ttq.load('ABC123'); fbq('init', '999');"""
        result = _detect_pixels(html)
        assert len(result) == 2
        providers = {r["provider"] for r in result}
        assert providers == {"TikTok", "Meta/Facebook"}


class TestCheckAsyncLoading:
    def test_static_script_with_async(self):
        html = '<script async src="https://cdn.example.com/pixel.js"></script>'
        result = _check_async_loading(html)
        assert len(result) == 1
        assert result[0]["async"] == "yes"
        assert result[0]["method"] == "static"

    def test_static_script_without_async(self):
        html = '<script src="https://cdn.example.com/pixel.js"></script>'
        result = _check_async_loading(html)
        assert len(result) == 1
        assert result[0]["async"] == "NO"
        assert result[0]["method"] == "static"

    def test_static_script_with_defer(self):
        html = '<script defer src="https://cdn.example.com/pixel.js"></script>'
        result = _check_async_loading(html)
        assert len(result) == 1
        assert result[0]["defer"] == "yes"

    def test_inline_script_ignored(self):
        html = "<script>console.log('hi');</script>"
        result = _check_async_loading(html)
        assert len(result) == 0

    def test_dynamic_script_with_async(self):
        html = """
        var js = document.createElement('script');
        js.async = true;
        js.src = 'https://cdn.example.com/pixel.js';
        """
        result = _check_async_loading(html)
        assert len(result) == 1
        assert result[0]["async"] == "yes"
        assert result[0]["method"] == "dynamic"

    def test_dynamic_script_minified_async(self):
        html = """n=document.createElement("script");n.async=!0,n.src=r;"""
        result = _check_async_loading(html)
        assert len(result) == 1
        assert result[0]["async"] == "yes"
        assert result[0]["method"] == "dynamic"

    def test_dynamic_script_without_async(self):
        html = """
        var js = document.createElement('script');
        js.src = 'https://cdn.example.com/pixel.js';
        head.appendChild(js);
        """
        result = _check_async_loading(html)
        assert len(result) == 1
        assert result[0]["async"] == "NO"
        assert result[0]["method"] == "dynamic"

    def test_no_scripts(self):
        html = "<div>Just HTML</div>"
        assert _check_async_loading(html) == []


class TestIsAllPagesTrigger:
    @pytest.mark.parametrize(
        "name",
        [
            "All Pages",
            "all pages",
            "ALL PAGES",
            "All Pages - Global",
            "all_pages",
            "pageview",
            "page view",
        ],
    )
    def test_matches(self, name):
        assert _is_all_pages_trigger(name) is True

    @pytest.mark.parametrize(
        "name",
        [
            "Booking",
            "Click",
            "Campsite detail",
            "Search page",
            "Window Loaded",
        ],
    )
    def test_non_matches(self, name):
        assert _is_all_pages_trigger(name) is False
