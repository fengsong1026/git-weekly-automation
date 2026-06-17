#!/usr/bin/env python3
"""Run all tests for git-weekly-automation."""

import os
import sys
import unittest

# Ensure the scripts directory is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = loader.discover(
        start_dir=os.path.dirname(__file__),
        pattern="test_*.py",
    )
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
