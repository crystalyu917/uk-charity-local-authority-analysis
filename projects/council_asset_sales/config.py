"""Panel years, charity size groups, and LA receipts settings."""

LA_RECEIPTS_URL = "https://assets.publishing.service.gov.uk/media/69c2a55b13f1436476e4436c/Capital_time_series_data_wide_24_03_26.csv"
PANEL_START_YEAR = 2018
PANEL_END_YEAR = 2023
LA_RECEIPTS_PUBLICATION_URL = "https://www.gov.uk/government/statistics/local-authority-capital-expenditure-and-receipts-in-england-final-outturn-time-series"
# Charity income groups from the shared register, not local-authority sizes.
CHARITY_SIZE_CATEGORIES = ("Small", "Medium", "Large")
# Financial-year lags applied to LA receipts.
LA_RECEIPTS_LAG_PERIODS = (1, 2, 3)
