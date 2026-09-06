"""Build the charity-removals and capital-receipts panel."""

from uk_charity_local_authority_analysis.council_asset_sales.preprocessing import (
    write_charity_receipts_panel,
)


if __name__ == "__main__":
    print(write_charity_receipts_panel())
