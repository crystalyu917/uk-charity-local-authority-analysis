"""Add UTLA to a local charity register and save a timestamped asset register."""

from datetime import datetime
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from uk_charity_local_authority_analysis.charity_commission_register.build_charity_register import latest_charity_register
from projects.council_asset_sales.pipeline.charity_asset_register import build_charity_asset_register

DATA_DIR = PROJECT_ROOT / "projects" / "council_asset_sales" / "datasets"
# None selects the latest register only within this project's input folder.
CHARITY_FILEPATH = None
CHARITY_BASE_FILEPATH = DATA_DIR / "charity_register_inputs" / "charity_register.parquet"
# None selects the latest downloaded UTLA CSV. Set an explicit path to pin it.
UTLA_LOOKUP_FILEPATH = None
UTLA_LOOKUP_DIR = DATA_DIR / "utla_lookup"
UTLA_CSV_FILENAME = "PCD_OA21_LSOA21_MSOA21_LTLA22_UTLA22_CAUTH22_NOV23_UK_LU_v2.csv"
OUTPUT_FILEPATH = DATA_DIR / "output" / "charity_asset_register.parquet"

# All current input columns plus UTLA and UTLA_NAME. Remove entries to choose columns to keep.
# UTLA holds the official 2022 authority code; UTLA_NAME holds its name.
# Set to None instead if future inputs should automatically keep every column.
COLUMNS_TO_KEEP = [
    'date_of_extract',
    'organisation_number',
    'registered_charity_number',
    'linked_charity_number',
    'charity_name',
    'charity_type',
    'charity_registration_status',
    'date_of_registration',
    'date_of_removal',
    'charity_reporting_status',
    'latest_acc_fin_period_start_date',
    'latest_acc_fin_period_end_date',
    'latest_income',
    'latest_expenditure',
    'charity_contact_address1',
    'charity_contact_address2',
    'charity_contact_address3',
    'charity_contact_address4',
    'charity_contact_address5',
    'charity_contact_postcode',
    'charity_contact_phone',
    'charity_contact_email',
    'charity_contact_web',
    'charity_company_registration_number',
    'charity_insolvent',
    'charity_in_administration',
    'charity_previously_excepted',
    'charity_is_cdf_or_cif',
    'charity_is_cio',
    'cio_is_dissolved',
    'date_cio_dissolution_notice',
    'charity_activities',
    'charity_gift_aid',
    'charity_has_land',
    'has_company_number',
    'charity_status',
    'registration_fy',
    'removal_fy',
    'size_category',
    'General_Public_And_Misc',
    'Religious_Activities',
    'Community_And_Social_Welfare',
    'Health_And_Disability',
    'Education_And_Research',
    'Elderly_Support',
    'Children_And_Youth',
    'Charity_Sector_Support',
    'Advocacy_And_Human_Rights',
    'Grantmaking_And_Financial_Support',
    'Housing_And_Infrastructure',
    'Arts_And_Recreation',
    'Environment_And_Animals',
    'International_And_Humanitarian',
    'Military_And_Civil_Efficiency',
    'CompanyName',
    'RegAddress.CareOf',
    'RegAddress.POBox',
    'RegAddress.AddressLine1',
    'RegAddress.AddressLine2',
    'RegAddress.PostTown',
    'RegAddress.County',
    'RegAddress.Country',
    'RegAddress.PostCode',
    'CompanyCategory',
    'CompanyStatus',
    'CountryOfOrigin',
    'DissolutionDate',
    'IncorporationDate',
    'Accounts.AccountRefDay',
    'Accounts.AccountRefMonth',
    'Accounts.NextDueDate',
    'Accounts.LastMadeUpDate',
    'Accounts.AccountCategory',
    'Returns.NextDueDate',
    'Returns.LastMadeUpDate',
    'Mortgages.NumMortCharges',
    'Mortgages.NumMortOutstanding',
    'Mortgages.NumMortPartSatisfied',
    'Mortgages.NumMortSatisfied',
    'SICCode.SicText_1',
    'SICCode.SicText_2',
    'SICCode.SicText_3',
    'SICCode.SicText_4',
    'LimitedPartnerships.NumGenPartners',
    'LimitedPartnerships.NumLimPartners',
    'URI',
    'PreviousName_1.CONDATE',
    'PreviousName_1.CompanyName',
    'PreviousName_2.CONDATE',
    'PreviousName_2.CompanyName',
    'PreviousName_3.CONDATE',
    'PreviousName_3.CompanyName',
    'PreviousName_4.CONDATE',
    'PreviousName_4.CompanyName',
    'PreviousName_5.CONDATE',
    'PreviousName_5.CompanyName',
    'PreviousName_6.CONDATE',
    'PreviousName_6.CompanyName',
    'PreviousName_7.CONDATE',
    'PreviousName_7.CompanyName',
    'PreviousName_8.CONDATE',
    'PreviousName_8.CompanyName',
    'PreviousName_9.CONDATE',
    'PreviousName_9.CompanyName',
    'PreviousName_10.CONDATE',
    'PreviousName_10.CompanyName',
    'ConfStmtNextDueDate',
    'ConfStmtLastMadeUpDate',
    'id',
    'charity_name_right',
    'companyNumber',
    'postalCode',
    'url',
    'latestIncome',
    'latestIncomeDate',
    'dateRegistered',
    'dateRemoved',
    'active',
    'dateModified',
    'orgIDs',
    'linked_orgs',
    'linked_orgs_verified',
    'organisationType',
    'organisationTypePrimary',
    'source',
    'charity_postcode',
    'local_authority_code',
    'UTLA',
    'UTLA_NAME',
]


def latest_utla_lookup() -> Path:
    candidates = []
    for folder in UTLA_LOOKUP_DIR.glob("*"):
        try:
            downloaded = datetime.strptime(folder.name, "%d%m%Y")
        except ValueError:
            continue
        for path in folder.rglob(UTLA_CSV_FILENAME):
            if path.is_file():
                candidates.append((downloaded, path))
    if not candidates:
        raise FileNotFoundError("UTLA lookup missing. Run projects/council_asset_sales/scripts/download_utla_lookup.py first.")
    return max(candidates, key=lambda item: item[0])[1]


if __name__ == "__main__":
    charity_path = CHARITY_FILEPATH if CHARITY_FILEPATH is not None else latest_charity_register(CHARITY_BASE_FILEPATH)
    lookup_path = UTLA_LOOKUP_FILEPATH if UTLA_LOOKUP_FILEPATH is not None else latest_utla_lookup()
    print(build_charity_asset_register(charity_path, lookup_path, OUTPUT_FILEPATH, COLUMNS_TO_KEEP))
