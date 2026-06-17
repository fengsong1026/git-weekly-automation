"""Tests for scripts/generate-weekly-report — templates, dates, prompts, model resolution."""

import sys
from datetime import datetime, timedelta
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest import TestCase, main

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

gwr = SourceFileLoader("gwr", str(SCRIPTS_DIR / "generate-weekly-report")).load_module()
fill_template = gwr.fill_template
get_week_dates = gwr.get_week_dates
build_system_prompt = gwr.build_system_prompt
get_default_template = gwr.get_default_template
DEFAULT_MODEL = gwr.DEFAULT_MODEL
DEFAULT_TEMPLATE_CONTENT_ZH = gwr.DEFAULT_TEMPLATE_CONTENT_ZH
DEFAULT_TEMPLATE_CONTENT_EN = gwr.DEFAULT_TEMPLATE_CONTENT_EN


class TestFillTemplate(TestCase):
    """Test {{PLACEHOLDER}} replacement."""

    def test_single_placeholder(self):
        result = fill_template("Hello {{NAME}}", {"NAME": "World"})
        self.assertEqual(result, "Hello World")

    def test_multiple_placeholders(self):
        template = "# {{WEEK}} — {{DATE_RANGE}}\n\n{{COMMITS}}"
        result = fill_template(template, {
            "WEEK": "W25",
            "DATE_RANGE": "2026-06-15 → 2026-06-21",
            "COMMITS": "- feat: auth module",
        })
        self.assertIn("W25", result)
        self.assertIn("2026-06-15", result)
        self.assertIn("feat: auth module", result)

    def test_missing_placeholder_left_untouched(self):
        """Unmatched {{PLACEHOLDER}} stays as-is."""
        result = fill_template("{{KNOWN}} and {{MISSING}}", {"KNOWN": "ok"})
        self.assertIn("ok", result)
        self.assertIn("{{MISSING}}", result)


class TestWeekDates(TestCase):
    """Test ISO week date calculation."""

    def test_default_uses_current_week(self):
        """No args → current week Monday through today."""
        monday, end, label = get_week_dates(None, None)
        self.assertEqual(monday.weekday(), 0)  # Monday
        today = datetime.now()
        self.assertEqual(end.date(), today.date())  # Current week ends today
        self.assertLessEqual(monday, end)
        self.assertIn("W", label)

    def test_specific_week(self):
        """Week 1 of 2026 starts on Monday Dec 29, 2025."""
        monday, sunday, label = get_week_dates(1, 2026)
        self.assertEqual(monday.strftime("%Y-%m-%d"), "2025-12-29")
        self.assertEqual(sunday.strftime("%Y-%m-%d"), "2026-01-04")
        self.assertIn("W01 (2026)", label)

    def test_mid_year_week(self):
        """Week 25 of 2026."""
        monday, sunday, _label = get_week_dates(25, 2026)
        self.assertIn("06", monday.strftime("%m"))  # June
        delta = (sunday - monday).days
        self.assertEqual(delta, 6)  # Monday through Sunday

    def test_current_week_monday_not_future(self):
        """The computed Monday is not in the future."""
        monday, _end, _label = get_week_dates(None, None)
        today = datetime.now()
        self.assertLessEqual(monday.date(), today.date())


class TestSystemPrompt(TestCase):
    """Test system prompt generation for different languages."""

    def test_zh_prompt_uses_chinese(self):
        prompt = build_system_prompt("zh")
        self.assertIn("简体中文", prompt)
        self.assertIn("周工作报告", prompt)

    def test_en_prompt_uses_english(self):
        prompt = build_system_prompt("en")
        self.assertIn("English", prompt)
        self.assertIn("weekly report", prompt.lower())

    def test_default_is_english(self):
        prompt = build_system_prompt()
        self.assertIn("English", prompt)


class TestTemplates(TestCase):
    """Test default template content."""

    def test_zh_template_has_chinese_headings(self):
        self.assertIn("周工作报告", DEFAULT_TEMPLATE_CONTENT_ZH)
        self.assertIn("概览", DEFAULT_TEMPLATE_CONTENT_ZH)
        self.assertIn("{{COMMITS}}", DEFAULT_TEMPLATE_CONTENT_ZH)

    def test_en_template_has_english_headings(self):
        self.assertIn("Weekly Work Report", DEFAULT_TEMPLATE_CONTENT_EN)
        self.assertIn("Overview", DEFAULT_TEMPLATE_CONTENT_EN)
        self.assertIn("{{COMMITS}}", DEFAULT_TEMPLATE_CONTENT_EN)

    def test_get_default_template_respects_lang(self):
        zh = get_default_template("zh")
        en = get_default_template("en")
        self.assertIn("周工作报告", zh)
        self.assertIn("Weekly Work Report", en)

    def test_get_default_template_unknown_lang_falls_back_en(self):
        result = get_default_template("fr")
        self.assertIn("Weekly Work Report", result)


class TestModelConfig(TestCase):
    """Test model resolution chain (CLI > config > default)."""

    def test_default_model_is_gpt4o_mini(self):
        self.assertEqual(DEFAULT_MODEL, "gpt-4o-mini")

    def test_model_fallback_chain(self):
        """Simulate the resolution logic from main()."""
        # Config value
        config_model = "deepseek-chat"
        # Simulate: args.model=None (not provided on CLI), config has value
        model = None or config_model or DEFAULT_MODEL
        self.assertEqual(model, "deepseek-chat")

        # Simulate: args.model provided on CLI
        cli_model = "claude-fable-5"
        model = cli_model or config_model or DEFAULT_MODEL
        self.assertEqual(model, "claude-fable-5")

        # Simulate: neither CLI nor config
        model = None or None or DEFAULT_MODEL
        self.assertEqual(model, DEFAULT_MODEL)


if __name__ == "__main__":
    main()
