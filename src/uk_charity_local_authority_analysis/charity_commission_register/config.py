"""Library processing settings and download URLs; local paths live in filepath.py."""

CHARITY_COMMISSION_DOWNLOAD_PAGE = "https://register-of-charities.charitycommission.gov.uk/en/register/full-register-download"
CHARITY_COMMISSION_CHARITY_URL = "https://ccewuksprdoneregsadata1.blob.core.windows.net/data/json/publicextract.charity.zip"
CHARITY_COMMISSION_CLASSIFICATION_URL = "https://ccewuksprdoneregsadata1.blob.core.windows.net/data/json/publicextract.charity_classification.zip"

ONS_POSTCODE_LOOKUP_ITEM_ID = "6fff67d204fd4f339591ed667a6e3642"
ONS_POSTCODE_LOOKUP_URL = (
    "https://www.arcgis.com/sharing/rest/content/items/"
    f"{ONS_POSTCODE_LOOKUP_ITEM_ID}/data"
)

UTLA_LOOKUP_URL = "https://www.arcgis.com/sharing/rest/content/items/bc8f6d1f6ee64111b6a59b22c6605f3b/data"
UTLA_ARCHIVE_FILENAME = "PCD_OA21_LSOA21_MSOA21_LTLA22_UTLA22_CAUTH22_NOV23_UK_LU_V2.zip"
UTLA_CSV_FILENAME = "PCD_OA21_LSOA21_MSOA21_LTLA22_UTLA22_CAUTH22_NOV23_UK_LU_v2.csv"

SMALL_INCOME_LIMIT = 25_000
MEDIUM_INCOME_LIMIT = 1_000_000

CATEGORY_MAPPING = {
    "Grantmaking_And_Financial_Support": [
        "classification_makes_grants_to_individuals",
        "classification_makes_grants_to_organisations",
        "classification_provides_other_finance",
    ],
    "Housing_And_Infrastructure": [
        "classification_accommodation/housing",
        "classification_provides_buildings/facilities/open_space",
    ],
    "Education_And_Research": [
        "classification_education/training",
        "classification_sponsors_or_undertakes_research",
    ],
    "Children_And_Youth": [
        "classification_children/young_people",
        "classification_amateur_sport",
    ],
    "Health_And_Disability": [
        "classification_the_advancement_of_health_or_saving_of_lives",
        "classification_disability",
        "classification_people_with_disabilities",
    ],
    "Advocacy_And_Human_Rights": [
        "classification_human_rights/religious_or_racial_harmony/equality_or_diversity",
        "classification_provides_advocacy/advice/information",
        "classification_people_of_a_particular_ethnic_or_racial_origin",
    ],
    "Religious_Activities": ["classification_religious_activities"],
    "Environment_And_Animals": [
        "classification_environment/conservation/heritage",
        "classification_animals",
    ],
    "Community_And_Social_Welfare": [
        "classification_economic/community_development/employment",
        "classification_general_charitable_purposes",
        "classification_the_prevention_or_relief_of_poverty",
        "classification_provides_services",
        "classification_other_charitable_activities",
        "classification_other_charitable_purposes",
    ],
    "Charity_Sector_Support": [
        "classification_acts_as_an_umbrella_or_resource_body",
        "classification_other_charities_or_voluntary_bodies",
        "classification_provides_human_resources",
    ],
    "International_And_Humanitarian": ["classification_overseas_aid/famine_relief"],
    "Elderly_Support": ["classification_elderly/old_people"],
    "General_Public_And_Misc": [
        "classification_the_general_public/mankind",
        "classification_other_defined_groups",
    ],
    "Arts_And_Recreation": [
        "classification_arts/culture/heritage/science",
        "classification_recreation",
    ],
    "Military_And_Civil_Efficiency": [
        "classification_armed_forces/emergency_service_efficiency",
    ],
}
