"""Official endpoint for the ONS Postcode Directory."""

from typing import Final

ONS_POSTCODE_LOOKUP_ITEM_ID: Final = "6fff67d204fd4f339591ed667a6e3642"
ONS_POSTCODE_LOOKUP_URL: Final = (
    "https://www.arcgis.com/sharing/rest/content/items/"
    f"{ONS_POSTCODE_LOOKUP_ITEM_ID}/data"
)
ONS_POSTCODE_LOOKUP_FILENAME: Final = "ONSPD_MAY_2026.zip"
