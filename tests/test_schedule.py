"""Tests for scripts/schedule — schedule parsing, plist building, label generation."""

import sys
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

schedule = SourceFileLoader("schedule", str(SCRIPTS_DIR / "schedule")).load_module()
parse_schedule = schedule.parse_schedule
schedule_to_string = schedule.schedule_to_string
build_plist = schedule.build_plist
plist_path = schedule.plist_path
LABEL_PREFIX = schedule.LABEL_PREFIX


class TestScheduleParsing(unittest.TestCase):
    """Test human-readable schedule → launchd calendar interval parsing."""

    def test_daily(self):
        """'daily 08:00' → no weekday/day constraint."""
        result = parse_schedule("daily 08:00")
        self.assertEqual(result, {"Hour": 8, "Minute": 0})

    def test_single_day(self):
        """'Mon 09:00' → single Weekday entry."""
        result = parse_schedule("Mon 09:00")
        self.assertEqual(result, {"Weekday": 1, "Hour": 9, "Minute": 0})

    def test_multi_day(self):
        """'Mon,Wed,Fri 14:00' → list of Weekday entries."""
        result = parse_schedule("Mon,Wed,Fri 14:00")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 3)
        weekdays = sorted(e["Weekday"] for e in result)
        self.assertEqual(weekdays, [1, 3, 5])

    def test_weekday(self):
        """'weekday 09:00' → Mon-Fri entries."""
        result = parse_schedule("weekday 09:00")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 5)
        weekdays = sorted(e["Weekday"] for e in result)
        self.assertEqual(weekdays, [1, 2, 3, 4, 5])

    def test_weekend(self):
        """'weekend 10:00' → Sat+Sun entries."""
        result = parse_schedule("weekend 10:00")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        weekdays = sorted(e["Weekday"] for e in result)
        self.assertEqual(weekdays, [0, 6])

    def test_day_range(self):
        """'Mon-Fri 18:00' → Mon through Fri."""
        result = parse_schedule("Mon-Fri 18:00")
        self.assertIsInstance(result, list)
        weekdays = sorted(e["Weekday"] for e in result)
        self.assertEqual(weekdays, [1, 2, 3, 4, 5])

    def test_day_of_month(self):
        """'1,15 10:00' → Day entries."""
        result = parse_schedule("1,15 10:00")
        self.assertIsInstance(result, list)
        days = sorted(e["Day"] for e in result)
        self.assertEqual(days, [1, 15])

    def test_case_insensitive(self):
        """Day names are case-insensitive."""
        r1 = parse_schedule("mon 09:00")
        r2 = parse_schedule("MON 09:00")
        r3 = parse_schedule("Monday 09:00")
        self.assertEqual(r1, r2)
        self.assertEqual(r1, r3)

    def test_24h_hour(self):
        """22:00 parses as hour 22."""
        result = parse_schedule("Fri 22:00")
        self.assertEqual(result["Hour"], 22)

    def test_invalid_hour(self):
        """Hour > 23 raises ValueError."""
        with self.assertRaises(ValueError):
            parse_schedule("Mon 25:00")

    def test_invalid_minute(self):
        """Minute > 59 raises ValueError."""
        with self.assertRaises(ValueError):
            parse_schedule("Mon 09:60")

    def test_no_time(self):
        """Missing time raises ValueError."""
        with self.assertRaises(ValueError):
            parse_schedule("Mon")

    def test_invalid_day(self):
        """Unknown day name raises ValueError."""
        with self.assertRaises(ValueError):
            parse_schedule("Blah 09:00")


class TestScheduleToString(unittest.TestCase):
    """Test calendar interval → human-readable string conversion."""

    def test_single_day(self):
        s = schedule_to_string({"Weekday": 1, "Hour": 9, "Minute": 0})
        self.assertIn("Mon", s)
        self.assertIn("09:00", s)

    def test_daily(self):
        s = schedule_to_string({"Hour": 8, "Minute": 30})
        self.assertIn("Daily", s)
        self.assertIn("08:30", s)

    def test_day_of_month(self):
        s = schedule_to_string({"Day": 15, "Hour": 10, "Minute": 0})
        self.assertIn("Day 15", s)
        self.assertIn("10:00", s)

    def test_list_of_intervals(self):
        s = schedule_to_string([
            {"Weekday": 1, "Hour": 9, "Minute": 0},
            {"Weekday": 3, "Hour": 9, "Minute": 0},
            {"Weekday": 5, "Hour": 9, "Minute": 0},
        ])
        self.assertIn("Mon", s)
        self.assertIn("Wed", s)
        self.assertIn("Fri", s)


class TestPlistBuilding(unittest.TestCase):
    """Test launchd plist dictionary generation."""

    def test_build_plist_basic(self):
        """build_plist returns valid plist dict with correct structure."""
        plist, label = build_plist(
            name="test-task",
            command="echo hello",
            schedule_str="Mon 09:00",
        )
        self.assertEqual(label, "com.git-weekly-automation.test-task")
        self.assertEqual(plist["Label"], label)
        self.assertIn("ProgramArguments", plist)
        self.assertIn("StartCalendarInterval", plist)
        self.assertIn("EnvironmentVariables", plist)
        self.assertEqual(plist["RunAtLoad"], False)

    def test_build_plist_python_script(self):
        """Python scripts get wrapped with sys.executable."""
        plist, label = build_plist(
            name="py-task",
            command="generate-weekly-report",
            schedule_str="Fri 17:00",
        )
        # ProgramArguments should be ["/bin/sh", "-c", "..."]
        self.assertEqual(plist["ProgramArguments"][0], "/bin/sh")
        self.assertEqual(plist["ProgramArguments"][1], "-c")
        # Wrapper script should contain both the project guard and the command
        wrapper = plist["ProgramArguments"][2]
        self.assertIn("PROJECT_DIR", wrapper)
        self.assertIn("generate-weekly-report", wrapper)

    def test_build_plist_env_vars(self):
        """EnvironmentVariables contain PROJECT_DIR, PLIST_PATH, LAUNCHD_LABEL."""
        plist, label = build_plist(
            name="env-test",
            command="echo x",
            schedule_str="daily 08:00",
            api_key="sk-fake",
        )
        env = plist["EnvironmentVariables"]
        self.assertIn("PROJECT_DIR", env)
        self.assertIn("PLIST_PATH", env)
        self.assertIn("LAUNCHD_LABEL", env)
        self.assertEqual(env["LAUNCHD_LABEL"], label)
        self.assertEqual(env["OPENAI_API_KEY"], "sk-fake")
        # PATH and HOME are always included
        self.assertIn("PATH", env)
        self.assertIn("HOME", env)

    def test_build_plist_self_destruct_wrapper(self):
        """Wrapper script contains self-destruct logic for deleted projects."""
        plist, _label = build_plist(
            name="sd-test",
            command="echo test",
            schedule_str="Mon 09:00",
        )
        wrapper = plist["ProgramArguments"][2]
        self.assertIn('if [ -d "$PROJECT_DIR" ]', wrapper)
        self.assertIn("launchctl bootout", wrapper)
        self.assertIn("rm -f", wrapper)


class TestPlistPath(unittest.TestCase):
    """Test plist file path generation."""

    def test_plist_path_format(self):
        result = plist_path("My Task!")
        self.assertIn(LABEL_PREFIX, str(result))
        self.assertIn(".plist", str(result))
        self.assertIn("LaunchAgents", str(result))

    def test_plist_path_sanitizes_name(self):
        """Special characters are sanitized."""
        result = plist_path("Hello World & More!!!")
        name_part = result.stem
        self.assertNotIn(" ", name_part)
        self.assertNotIn("&", name_part)
        self.assertNotIn("!", name_part)


if __name__ == "__main__":
    unittest.main()
