"""
Static catalog of PSX-listed companies (KSE-100 constituents) used to seed the
`stocks` table so users can search/browse by name, ticker or sector (PRD.md FR9).

Every symbol here was verified to return 5 years of daily history from Yahoo
Finance (as `<SYMBOL>.KA`) on 2026-10-08. Sector names follow PSX's sector list.
"""

PSX_COMPANIES: list[tuple[str, str, str]] = [
    # (ticker, name, sector)
    ("SYS", "Systems Limited", "Technology & Communication"),
    ("TRG", "TRG Pakistan Limited", "Technology & Communication"),
    ("NETSOL", "NetSol Technologies Limited", "Technology & Communication"),
    ("AIRLINK", "Air Link Communication Limited", "Technology & Communication"),
    ("PTC", "Pakistan Telecommunication Company Limited", "Technology & Communication"),
    ("HUBC", "The Hub Power Company Limited", "Power Generation & Distribution"),
    ("KEL", "K-Electric Limited", "Power Generation & Distribution"),
    ("KAPCO", "Kot Addu Power Company Limited", "Power Generation & Distribution"),
    ("OGDC", "Oil & Gas Development Company Limited", "Oil & Gas Exploration"),
    ("PPL", "Pakistan Petroleum Limited", "Oil & Gas Exploration"),
    ("MARI", "Mari Energies Limited", "Oil & Gas Exploration"),
    ("POL", "Pakistan Oilfields Limited", "Oil & Gas Exploration"),
    ("PSO", "Pakistan State Oil Company Limited", "Oil & Gas Marketing"),
    ("SNGP", "Sui Northern Gas Pipelines Limited", "Oil & Gas Marketing"),
    ("SSGC", "Sui Southern Gas Company Limited", "Oil & Gas Marketing"),
    ("ATRL", "Attock Refinery Limited", "Refinery"),
    ("NRL", "National Refinery Limited", "Refinery"),
    ("MCB", "MCB Bank Limited", "Commercial Banks"),
    ("UBL", "United Bank Limited", "Commercial Banks"),
    ("HBL", "Habib Bank Limited", "Commercial Banks"),
    ("MEBL", "Meezan Bank Limited", "Commercial Banks"),
    ("BAHL", "Bank AL Habib Limited", "Commercial Banks"),
    ("BAFL", "Bank Alfalah Limited", "Commercial Banks"),
    ("NBP", "National Bank of Pakistan", "Commercial Banks"),
    ("ABL", "Allied Bank Limited", "Commercial Banks"),
    ("FABL", "Faysal Bank Limited", "Commercial Banks"),
    ("AKBL", "Askari Bank Limited", "Commercial Banks"),
    ("EFERT", "Engro Fertilizers Limited", "Fertilizer"),
    ("FFC", "Fauji Fertilizer Company Limited", "Fertilizer"),
    ("LUCK", "Lucky Cement Limited", "Cement"),
    ("DGKC", "D.G. Khan Cement Company Limited", "Cement"),
    ("MLCF", "Maple Leaf Cement Factory Limited", "Cement"),
    ("FCCL", "Fauji Cement Company Limited", "Cement"),
    ("CHCC", "Cherat Cement Company Limited", "Cement"),
    ("KOHC", "Kohat Cement Company Limited", "Cement"),
    ("PIOC", "Pioneer Cement Limited", "Cement"),
    ("NML", "Nishat Mills Limited", "Textile Composite"),
    ("ILP", "Interloop Limited", "Textile Composite"),
    ("SEARL", "The Searle Company Limited", "Pharmaceuticals"),
    ("MTL", "Millat Tractors Limited", "Automobile Assembler"),
    ("INDU", "Indus Motor Company Limited", "Automobile Assembler"),
    ("HCAR", "Honda Atlas Cars (Pakistan) Limited", "Automobile Assembler"),
    ("SAZEW", "Sazgar Engineering Works Limited", "Automobile Assembler"),
    ("PAEL", "Pak Elektron Limited", "Cable & Electrical Goods"),
    ("EPCL", "Engro Polymer & Chemicals Limited", "Chemical"),
    ("LOTCHEM", "Lotte Chemical Pakistan Limited", "Chemical"),
    ("NESTLE", "Nestle Pakistan Limited", "Food & Personal Care Products"),
    ("UNITY", "Unity Foods Limited", "Food & Personal Care Products"),
    ("INIL", "International Industries Limited", "Engineering"),
    ("ISL", "International Steels Limited", "Engineering"),
]

CATALOG_BY_TICKER = {ticker: (name, sector) for ticker, name, sector in PSX_COMPANIES}
