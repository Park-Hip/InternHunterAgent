from __future__ import annotations

import re
import unittest

from src.agents.tools.time import get_current_time


class GetCurrentTimeToolTests(unittest.TestCase):
    def test_get_current_time_returns_hh_mm_ss_utc_string(self) -> None:
        result = get_current_time.invoke({})

        self.assertIsInstance(result, str)
        self.assertRegex(result, r"^\d{2}:\d{2}:\d{2} UTC$")
