"""HMRC SA103 (self-employment short/full) expense boxes used for categorisation."""

SA103 = {
    17: "Cost of goods bought for resale / materials",
    18: "Construction industry – payments to subcontractors",
    19: "Wages, salaries and other staff costs",
    20: "Car, van and travel expenses",
    21: "Rent, rates, power and insurance costs",
    22: "Repairs and maintenance of property and equipment",
    23: "Phone, fax, stationery and other office costs",
    24: "Advertising and business entertainment costs",
    25: "Interest on bank and other loans",
    26: "Bank, credit card and other financial charges",
    27: "Irrecoverable debts written off",
    28: "Accountancy, legal and other professional fees",
    29: "Depreciation and loss/profit on sale of assets (disallowable; capital allowances instead)",
    30: "Other business expenses",
    39: "Disallowable expenses (e.g. client entertainment)",
}
VALID_BOXES = set(SA103)


def box_label(box: int | None) -> str:
    if box is None:
        return "–"
    return f"{box} · {SA103[box].split(' (')[0]}"


def prompt_table() -> str:
    return "\n".join(f"{b}: {d}" for b, d in SA103.items())
