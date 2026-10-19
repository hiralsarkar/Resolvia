"""
Static reference data shared by the generator, the feature builder and the
execution simulator. In a bank this would come from the SSI and counterparty
master files.
"""

HOME_CURRENCY = "INR"

COUNTERPARTIES = ["ICICI-CUST", "HDFC-CUST", "KOTAK-CUST", "DEUTSCHE-BROKER",
                  "MORGANSTANLEY-BROKER", "NOMURA-BROKER"]

# Standing settlement instruction I expect for each counterparty. The codes
# are spread out on purpose so a wrong SSI can't be mistaken for a typo.
EXPECTED_SSI = {
    "ICICI-CUST": "SSI-IN-0091", "HDFC-CUST": "SSI-IN-0147",
    "KOTAK-CUST": "SSI-IN-0203", "DEUTSCHE-BROKER": "SSI-DE-5510",
    "MORGANSTANLEY-BROKER": "SSI-US-7742", "NOMURA-BROKER": "SSI-JP-3389",
}

# how the same stock gets written in emails and chats
SYMBOL_ALIASES = {
    "RELIANCE": ["RELIANCE", "RIL", "Reliance Industries"],
    "TCS": ["TCS", "Tata Consultancy Services", "Tata Consultancy"],
    "INFY": ["INFY", "Infosys", "Infosys Ltd"],
    "HDFCBANK": ["HDFCBANK", "HDFC Bank"],
    "ICICIBANK": ["ICICIBANK", "ICICI Bank"],
    "SBIN": ["SBIN", "SBI", "State Bank of India"],
    "BHARTIARTL": ["BHARTIARTL", "Bharti Airtel", "Airtel"],
    "ITC": ["ITC", "ITC Ltd"],
    "LT": ["LT", "L&T", "Larsen & Toubro"],
    "AXISBANK": ["AXISBANK", "Axis Bank"],
    "KOTAKBANK": ["KOTAKBANK", "Kotak Bank", "Kotak Mahindra Bank"],
    "WIPRO": ["WIPRO", "Wipro Ltd"],
    "HINDUNILVR": ["HINDUNILVR", "HUL", "Hindustan Unilever"],
    "MARUTI": ["MARUTI", "Maruti Suzuki"],
    "TATASTEEL": ["TATASTEEL", "Tata Steel"],
}
