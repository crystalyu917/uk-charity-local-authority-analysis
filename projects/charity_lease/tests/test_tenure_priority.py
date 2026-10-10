import unittest
from datetime import date

import polars as pl

from charity_lease.pipeline.core import deduplicate_charities
from charity_lease.pipeline.lease_terms import add_lease_terms


class TenurePriorityTests(unittest.TestCase):
    def test_priority_and_evidence(self):
        cases = [
            (True, True, "Freehold", "Helping Hands Trust", "freehold"),
            (True, True, "Freehold", "Unrelated Estates", "leasehold"),
            (True, False, "Freehold", "Unrelated Estates", "freehold"),
            (True, False, "Leasehold", None, "leasehold"),
            (False, True, None, None, "leasehold"),
            (False, False, None, None, None),
            (True, True, "Freehold", None, "leasehold"),
            (True, True, "Leasehold", "Helping Hands Trust", "leasehold"),
        ]
        rows = [dict(charity_name="Helping Hand Trust", ccod_matched=c,
                     registered_lease_matched=l, ccod_tenure=t,
                     ccod_proprietor_name_1="Different Owner",
                     ccod_proprietor_name_4=n,
                     ccod_company_registration_no_1="00123456",
                     lease_term="99 years from 1 January 2020",
                     lease_date_of_lease="2020-01-01")
                for c, l, t, n, _ in cases]
        result = add_lease_terms(pl.DataFrame(rows), date(2026, 9, 29))
        self.assertEqual(result["lease_status"].to_list(), [c[-1] for c in cases])
        self.assertEqual(result["charity_is_freeholder"].to_list(), [True] + [False] * 7)
        self.assertEqual(result["ccod_company_registration_no_1"].to_list(), ["00123456"] * 8)
        self.assertEqual(result["ccod_matched"].to_list(), [c[0] for c in cases])
        self.assertIsNone(result["lease_years_remaining"][0])
        self.assertIsNotNone(result["lease_years_remaining"][1])
        self.assertGreaterEqual(result["ccod_proprietor_name_match_score"][0], 92)
        self.assertLess(result["ccod_proprietor_name_match_score"][0], 100)
        self.assertEqual(result["ccod_best_matching_proprietor_name"][0], "Helping Hands Trust")

    def test_freeholder_survives_deduplication(self):
        frame = pl.DataFrame({"registered_charity_number": [1, 1],
                              "charity_is_freeholder": [False, True],
                              "lease_years_remaining": [80.0, None]})
        self.assertTrue(deduplicate_charities(frame)["charity_is_freeholder"][0])

    def test_empty_input(self):
        frame = pl.DataFrame(schema={"lease_term": pl.String,
                                     "lease_date_of_lease": pl.String,
                                     "registered_lease_matched": pl.Boolean})
        self.assertEqual(add_lease_terms(frame, date(2026, 9, 29)).height, 0)

    def test_missing_names_do_not_fall_back_to_charity(self):
        frame = pl.DataFrame({"charity_name": ["Helping Hands Trust", None],
                              "ccod_proprietor_name_1": [None, "Helping Hands Trust"],
                              "ccod_matched": [True, True],
                              "ccod_tenure": ["Freehold", "Freehold"],
                              "registered_lease_matched": [True, True],
                              "lease_term": [None, None],
                              "lease_date_of_lease": [None, None]})
        result = add_lease_terms(frame, date(2026, 9, 29))
        self.assertEqual(result["lease_status"].to_list(), ["leasehold", "leasehold"])
        self.assertEqual(result["ccod_proprietor_name_match_score"].to_list(), [None, None])


if __name__ == "__main__":
    unittest.main()
