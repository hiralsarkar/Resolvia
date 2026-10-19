"""
Static reference data shared by the generator, the feature builder and the
execution simulator. In a bank this would come from the SSI and counterparty
master files.
"""

HOME_CURRENCY = "INR"

COUNTERPARTIES = ["ICICI-CUST", "HDFC-CUST", "KOTAK-CUST", "DEUTSCHE-BROKER",
                  "MORGANSTANLEY-BROKER", "NOMURA-BROKER"]

# Standing settlement instruction we expect for each counterparty. The codes
# are spread out on purpose so a wrong SSI can't be mistaken for a typo.
EXPECTED_SSI = {
    "ICICI-CUST": "SSI-IN-0091", "HDFC-CUST": "SSI-IN-0147",
    "KOTAK-CUST": "SSI-IN-0203", "DEUTSCHE-BROKER": "SSI-DE-5510",
    "MORGANSTANLEY-BROKER": "SSI-US-7742", "NOMURA-BROKER": "SSI-JP-3389",
}
