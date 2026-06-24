#!/usr/bin/env python3
"""Mock AS400 (DB2) data generator for the Customer 360 demo.

Emits five CSV files that mimic legacy AS400 core-banking extracts, preserving
the quirks called out in the BRD/PRD:
  * abbreviated, upper-case column headers (CMCIF, ACBAL, TXNDT, ...)
  * dates stored as NUMERIC(8) in YYYYMMDD format
  * single-char type/status codes (TXNTYP D/C, ACTYPE SV/DP, ACSTAT A/I/C)

Customers are generated from weighted **archetypes** so every Gold segment and
churn band is well populated (not 95% mass-retail). The customer master also
carries region, customer-since (tenure), and annual income for richer slicing.
The three named demo personas keep fixed CIFs. Corrupt fixtures under
``--corrupt-dir`` drive the TC-1.1 (bad load) and TC-3.1 (failed assertion) cases.

Usage:
    python generate_mock_as400.py --out-dir ./out --customers 1000 --seed 42
"""
from __future__ import annotations

import argparse
import csv
import os
import random
from dataclasses import dataclass, field
from datetime import date, timedelta

from faker import Faker

# --- AS400 source schemas (column order matters for fixed-position parsers) ---
SCHEMAS: dict[str, list[str]] = {
    "AS400_CUST_MAST": ["CMCIF", "CMNAME", "CMADR1", "CMDOB", "CMSEG", "CMPHNE", "CMRGN", "CMSINCE", "CMINC"],
    "AS400_SVDP_MAST": ["ACCNO", "AC_CIF", "ACTYPE", "ACBAL", "ACOPDT", "ACSTAT"],
    "AS400_CC_TXN": ["TXNID", "CRDNO", "CC_CIF", "TXNDT", "TXNTM", "TXNAMT", "TXN_CAT", "TXNTYP"],
    "AS400_DC_TXN": ["TXNID", "DCRDNO", "DC_CIF", "DC_ACCNO", "TXNDT", "TXNTM", "TXNAMT", "TXN_CAT", "TXNTYP"],
    "AS400_LOAN_MAST": ["LN_NO", "LN_CIF", "LNTYPE", "LN_AMT", "LN_BAL", "LNMTHP", "LN_DUE"],
    "AS400_PRODUCT_MAST": ["PRDCODE", "PRDNAME", "PRDCAT", "PRDCONTRACT", "PRDTYPE", "PRDRATE", "PRDDESC"],
    "AS400_PROD_HOLD": ["HOLDID", "PH_CIF", "PRDCODE", "PHSTAT", "PHOPDT", "PHBAL"],
}

# Bank Muamalat Malaysia (Islamic bank) consumer product catalog. Static reference list
# emitted as AS400_PRODUCT_MAST. (code, name, category, islamic_contract, type, indicative_rate%, desc)
PRODUCT_CATALOG = [
    ("DEP-BSA", "Basic Savings Account-i", "Deposits", "Wadiah", "DEPOSIT", 0.25, "Entry-level savings, no minimum balance"),
    ("DEP-SAV", "Savings Account-i", "Deposits", "Tawarruq", "DEPOSIT", 1.00, "Everyday savings with profit"),
    ("DEP-ELITE", "ELITE Savings Account-i", "Deposits", "Tawarruq", "DEPOSIT", 1.85, "Tiered high-balance savings"),
    ("DEP-JR", "Junior Pawket-i", "Deposits", "Wadiah", "DEPOSIT", 0.50, "Children's savings account"),
    ("DEP-PEN", "Pensioner Savings Account-i", "Deposits", "Wadiah", "DEPOSIT", 0.75, "Savings for pensioners"),
    ("DEP-CUR", "Current Account-i", "Deposits", "Tawarruq", "DEPOSIT", 0.00, "Transactional current account"),
    ("DEP-FTA", "Fixed Term Account-i", "Deposits", "Tawarruq", "DEPOSIT", 3.40, "Fixed-tenure term deposit"),
    ("FIN-CASH", "Cash-i Personal Financing", "Financing", "Tawarruq", "FINANCING", 6.50, "Unsecured personal financing"),
    ("FIN-CASHPREM", "Cash-i Muamalat Premier", "Financing", "Tawarruq", "FINANCING", 5.40, "Premier personal financing"),
    ("FIN-MORTHOME", "SMART Mortgage HOME-i", "Financing", "Musharakah Mutanaqisah", "FINANCING", 4.30, "Home financing"),
    ("FIN-MORTFLEXI", "SMART Mortgage FLEXI-i", "Financing", "Musharakah Mutanaqisah", "FINANCING", 4.45, "Flexi home financing with offset"),
    ("FIN-VEH", "Vehicle Financing-i", "Financing", "AITAB", "FINANCING", 3.50, "Auto financing (hire-purchase)"),
    ("FIN-BIKE", "Big Bike Financing-i", "Financing", "AITAB", "FINANCING", 4.75, "Motorcycle financing"),
    ("FIN-ASB", "ASB Financing-i", "Financing", "Tawarruq", "FINANCING", 5.00, "Unit-trust-linked financing"),
    ("FIN-CASHLINE", "Cashline-i Facility", "Financing", "Tawarruq", "FINANCING", 7.00, "Revolving overdraft-i"),
    ("FIN-ARRAHNU", "Ar-Rahnu", "Financing", "Qard & Rahnu", "FINANCING", 0.65, "Islamic pawn broking (gold)"),
    ("FIN-ARRPRESTIGE", "Ar-Rahnu PRESTIGE", "Financing", "Qard & Rahnu", "FINANCING", 0.60, "High-value Islamic pawn"),
    ("CARD-PLAT", "Visa Platinum-i", "Cards", "Ujrah", "CARD", 0.00, "Platinum credit card-i"),
    ("CARD-INF", "Visa Infinite-i", "Cards", "Ujrah", "CARD", 0.00, "Premium credit card-i"),
    ("CARD-DEBIT", "Debit Card-i", "Cards", "Wadiah", "CARD", 0.00, "Debit card-i"),
    ("INV-SURIA", "SURIA Investment Account-i", "Wealth & Investment", "Mudarabah", "INVESTMENT", 4.10, "Unrestricted investment account"),
    ("INV-TIA", "Term Investment Account-i", "Wealth & Investment", "Mudarabah", "INVESTMENT", 3.90, "Fixed-tenure investment account"),
    ("INV-GOLD", "Gold-i", "Wealth & Investment", "Bai' as-Sarf", "INVESTMENT", 0.00, "Gold investment account"),
    ("INV-UT", "e-Unit Trust", "Wealth & Investment", "Wakalah", "INVESTMENT", 0.00, "Online unit trust"),
    ("INV-ASNB", "ASNB Investment", "Wealth & Investment", "Wakalah", "INVESTMENT", 0.00, "ASNB fund investment"),
    ("INV-PMA", "Private Managed Account", "Wealth & Investment", "Wakalah", "INVESTMENT", 0.00, "Discretionary wealth mandate"),
    ("TKF-FAMILY", "Family Takaful", "Takaful", "Tabarru' & Wakalah", "PROTECTION", 0.00, "Family / life protection"),
    ("TKF-GENERAL", "General Takaful", "Takaful", "Tabarru' & Wakalah", "PROTECTION", 0.00, "Motor / home protection"),
    ("TKF-MEDICAL", "Medical Takaful", "Takaful", "Tabarru' & Wakalah", "PROTECTION", 0.00, "Medical / health protection"),
    ("EST-WASIAT", "Wasiat (Islamic Will)", "Estate Planning", "Wasiyyah", "ESTATE", 0.00, "Islamic will writing"),
    ("EST-ASSALIHIN", "As-Salihin Estate Planning", "Estate Planning", "Wasiyyah", "ESTATE", 0.00, "Estate planning service"),
    ("EST-HIBAH", "Hibah Trust", "Estate Planning", "Hibah", "ESTATE", 0.00, "Conditional gift trust"),
    ("DIG-IMUAMALAT", "i-Muamalat Internet Banking", "Digital & Services", "Ujrah", "SERVICE", 0.00, "Internet & mobile banking"),
    ("DIG-DUITNOW", "DuitNow", "Digital & Services", "Ujrah", "SERVICE", 0.00, "Instant transfers & QR pay"),
    ("SVC-SDB", "Safe Deposit Box", "Digital & Services", "Ijarah", "SERVICE", 0.00, "Safe deposit box rental"),
    ("SVC-HAJJ", "Tabung Haji Transfer", "Digital & Services", "Wakalah", "SERVICE", 0.00, "Hajj savings transfer"),
    ("SVC-ZAKAT", "Ez-Zakat Muamalat", "Digital & Services", "Wakalah", "SERVICE", 0.00, "Zakat payment service"),
]

SPEND_CATEGORIES = ["RETAIL", "GROCERY", "TRAVEL", "DINING", "DIGITAL", "UTILITY", "FUEL", "HEALTH", "ENTERTAINMENT"]
DEBIT_CATEGORIES = ["RETAIL", "GROCERY", "DINING", "FUEL", "ATM", "UTILITY", "TRANSPORT"]
LOAN_TYPES = ["MORTGAGE", "CAR", "PERSONAL", "EDUCATION", "CREDIT_LINE"]
LOAN_PRINCIPAL = {"MORTGAGE": 320_000, "CAR": 35_000, "PERSONAL": 15_000, "EDUCATION": 25_000, "CREDIT_LINE": 10_000}
# Regions (Malaysia), weighted toward the capital / Klang Valley.
REGIONS = ["KUALA LUMPUR", "KUALA LUMPUR", "KUALA LUMPUR", "JOHOR BAHRU", "JOHOR BAHRU",
           "GEORGE TOWN", "IPOH", "SHAH ALAM", "KOTA KINABALU", "KUCHING", "MALACCA"]
INCOME_BY_TIER = {"MASS": (20_000, 90_000), "AFFLUENT": (90_000, 250_000), "HNW": (250_000, 1_500_000)}


def yyyymmdd(d: date) -> int:
    return int(d.strftime("%Y%m%d"))


# Realistic intraday card-spend curve: light overnight, lunch (12) + evening (19) peaks.
TXN_HOURS = list(range(24))
TXN_HOUR_WEIGHTS = [1, 1, 1, 1, 2, 3, 5, 8, 12, 14, 14, 16,
                    20, 18, 14, 13, 13, 15, 18, 20, 16, 12, 7, 3]


@dataclass
class GeneratedRows:
    customers: list[list] = field(default_factory=list)
    products: list[list] = field(default_factory=list)
    holdings: list[list] = field(default_factory=list)
    accounts: list[list] = field(default_factory=list)
    cards: list[list] = field(default_factory=list)
    debit_cards: list[list] = field(default_factory=list)
    loans: list[list] = field(default_factory=list)


class Generator:
    def __init__(self, fake: Faker, rng: random.Random, today: date, time_rng: random.Random,
                 prod_rng: random.Random):
        self.fake = fake
        self.rng = rng
        # Separate RNG streams so adding TXNTM / product holdings does not perturb the main
        # rng sequence (existing balances/regions/dates/txns stay identical across regen).
        self.time_rng = time_rng
        self.prod_rng = prod_rng
        self.archetype: dict[str, str] = {}  # cif -> archetype, for product-holding assignment
        self.today = today
        self.rows = GeneratedRows()
        self._cif_seq = 19283740
        self._txn_seq = 99887760
        self._dctxn_seq = 55443320
        self._hold_seq = 70011000

    # -- id helpers ---------------------------------------------------------
    def next_cif(self) -> str:
        self._cif_seq += self.rng.randint(1, 7)
        return f"{self._cif_seq:010d}"

    def next_txn_id(self) -> str:
        self._txn_seq += 1
        return f"TXNCC{self._txn_seq}"

    def next_dc_txn_id(self) -> str:
        self._dctxn_seq += 1
        return f"TXNDC{self._dctxn_seq}"

    def masked_card(self) -> str:
        return "4111" + "".join(str(self.rng.randint(0, 9)) for _ in range(12))

    def masked_debit_card(self) -> str:
        return "5555" + "".join(str(self.rng.randint(0, 9)) for _ in range(12))

    # -- emitters -----------------------------------------------------------
    def add_customer(self, cif, segment, dob, region=None, since=None, income=None) -> None:
        region = region or self.rng.choice(REGIONS)
        since = since or (self.today - timedelta(days=self.rng.randint(365, 25 * 365)))
        if income is None:
            lo, hi = INCOME_BY_TIER.get(segment, INCOME_BY_TIER["MASS"])
            income = self.rng.uniform(lo, hi)
        self.rows.customers.append([
            cif, self.fake.name(), self.fake.street_address(), yyyymmdd(dob),
            segment, self.fake.numerify("+1-555-####"), region, yyyymmdd(since), round(income, 2),
        ])

    def add_account(self, cif, actype, balance, status="A") -> str:
        prefix = "SV" if actype == "SV" else "DP"
        account_id = f"{prefix}-{self.rng.randint(100000000, 999999999)}"
        open_date = self.today - timedelta(days=self.rng.randint(120, 3600))
        self.rows.accounts.append([account_id, cif, actype, round(balance, 2), yyyymmdd(open_date), status])
        return account_id

    def rand_txn_time(self) -> int:
        """HHMMSS time-of-day, drawn from the dedicated time_rng (realistic intraday curve)."""
        hour = self.time_rng.choices(TXN_HOURS, weights=TXN_HOUR_WEIGHTS)[0]
        return hour * 10000 + self.time_rng.randint(0, 59) * 100 + self.time_rng.randint(0, 59)

    def add_card_txns(self, cif, n, categories, max_amt, max_days_back=90) -> None:
        card = self.masked_card()
        for _ in range(n):
            txn_date = self.today - timedelta(days=self.rng.randint(0, max_days_back))
            txntyp = "D" if self.rng.random() > 0.15 else "C"
            self.rows.cards.append([
                self.next_txn_id(), card, cif, yyyymmdd(txn_date), self.rand_txn_time(),
                round(self.rng.uniform(8.0, max_amt), 2), self.rng.choice(categories), txntyp,
            ])

    def add_debit_txns(self, cif, account_id, n, categories, max_amt) -> None:
        card = self.masked_debit_card()
        for _ in range(n):
            txn_date = self.today - timedelta(days=self.rng.randint(0, 90))
            txntyp = "D" if self.rng.random() > 0.08 else "C"
            self.rows.debit_cards.append([
                self.next_dc_txn_id(), card, cif, account_id, yyyymmdd(txn_date), self.rand_txn_time(),
                round(self.rng.uniform(5.0, max_amt), 2), self.rng.choice(categories), txntyp,
            ])

    def add_loan(self, cif, ltype, principal, balance, monthly) -> None:
        due = self.today + timedelta(days=self.rng.randint(5, 40))
        self.rows.loans.append([
            f"LN-{self.rng.randint(10000000, 99999999)}", cif, ltype,
            round(principal, 2), round(balance, 2), round(monthly, 2), yyyymmdd(due),
        ])

    def add_random_loan(self, cif, ltype=None) -> None:
        ltype = ltype or self.rng.choice(LOAN_TYPES)
        principal = LOAN_PRINCIPAL[ltype] * self.rng.uniform(0.7, 1.5)
        self.add_loan(cif, ltype, principal, principal * self.rng.uniform(0.4, 0.95),
                      principal / self.rng.randint(24, 300))

    def rand_dob(self, lo=1955, hi=2003) -> date:
        return date(self.rng.randint(lo, hi), self.rng.randint(1, 12), self.rng.randint(1, 28))

    # -- archetype builders -------------------------------------------------
    def build(self, archetype: str) -> None:
        cif = self.next_cif()
        self.archetype[cif] = archetype
        r = self.rng
        if archetype == "hnw_investor":
            self.add_customer(cif, "HNW", self.rand_dob(1955, 1985))
            sv = self.add_account(cif, "SV", r.uniform(260_000, 900_000))
            self.add_account(cif, "DP", r.uniform(50_000, 400_000))
            self.add_card_txns(cif, r.randint(5, 15), ["TRAVEL", "DINING", "HEALTH"], 900)
            self.add_debit_txns(cif, sv, r.randint(4, 12), ["DINING", "ATM", "FUEL"], 300)
        elif archetype == "affluent_saver":
            self.add_customer(cif, "AFFLUENT", self.rand_dob(1960, 1990))
            sv = self.add_account(cif, "SV", r.uniform(90_000, 240_000))
            if r.random() > 0.4:
                self.add_account(cif, "DP", r.uniform(20_000, 150_000))
            self.add_card_txns(cif, r.randint(8, 25), SPEND_CATEGORIES, 600)
            self.add_debit_txns(cif, sv, r.randint(6, 20), DEBIT_CATEGORIES, 250)
            if r.random() < 0.4:
                self.add_random_loan(cif, r.choice(["MORTGAGE", "CAR", "EDUCATION"]))
        elif archetype == "digital_shopper":
            self.add_customer(cif, r.choice(["MASS", "AFFLUENT"]), self.rand_dob(1988, 2003))
            sv = self.add_account(cif, "SV", r.uniform(5_000, 40_000))
            # Heavy recent (<30d) credit spend -> DIGITAL_SHOPPER (> $5k/30d).
            self.add_card_txns(cif, r.randint(45, 70), ["DIGITAL", "RETAIL", "DINING", "ENTERTAINMENT"], 320, max_days_back=29)
            self.add_debit_txns(cif, sv, r.randint(10, 30), ["RETAIL", "DINING", "TRANSPORT"], 150)
        elif archetype == "leveraged_borrower":
            self.add_customer(cif, "MASS", self.rand_dob(1975, 1995))
            sv = self.add_account(cif, "SV", r.uniform(500, 9_000))
            self.add_loan(cif, "MORTGAGE", r.uniform(220_000, 480_000), r.uniform(200_000, 420_000), r.uniform(1500, 2600))
            if r.random() < 0.5:
                self.add_random_loan(cif, r.choice(["CAR", "CREDIT_LINE"]))
            self.add_card_txns(cif, r.randint(15, 35), ["GROCERY", "UTILITY", "FUEL"], 400)
            self.add_debit_txns(cif, sv, r.randint(15, 35), ["GROCERY", "ATM", "UTILITY"], 150)
        elif archetype == "churn_risk":
            # Thin savings, heavy ATM cash-out, DORMANT card (only old txns) -> high churn.
            self.add_customer(cif, "MASS", self.rand_dob(1970, 2000))
            sv = self.add_account(cif, "SV", r.uniform(200, 4_500),
                                  status=r.choices(["A", "I"], weights=[0.8, 0.2])[0])
            self.add_card_txns(cif, r.randint(2, 8), SPEND_CATEGORIES, 200, max_days_back=90)  # nothing in last 30d → dormant
            # frequent recent ATM withdrawals
            card = self.masked_debit_card()
            for _ in range(r.randint(6, 14)):
                d = self.today - timedelta(days=r.randint(0, 30))
                self.rows.debit_cards.append([self.next_dc_txn_id(), card, cif, sv, yyyymmdd(d),
                                              self.rand_txn_time(),
                                              round(r.uniform(20, 200), 2), "ATM", "D"])
        else:  # standard retail — varied
            seg = r.choices(["MASS", "AFFLUENT"], weights=[0.85, 0.15])[0]
            self.add_customer(cif, seg, self.rand_dob())
            sv = self.add_account(cif, "SV", r.uniform(1_000, 80_000),
                                  status=r.choices(["A", "I", "C"], weights=[0.85, 0.1, 0.05])[0])
            if r.random() > 0.5:
                self.add_account(cif, "DP", r.uniform(5_000, 120_000))
            if r.random() > 0.2:
                self.add_card_txns(cif, r.randint(3, 30), SPEND_CATEGORIES, 500)
            if r.random() > 0.2:
                self.add_debit_txns(cif, sv, r.randint(4, 30), DEBIT_CATEGORIES, 250)
            if r.random() < 0.3:
                self.add_random_loan(cif)

    ARCHETYPES = (
        ["hnw_investor"] * 12 + ["affluent_saver"] * 13 + ["digital_shopper"] * 15
        + ["leveraged_borrower"] * 12 + ["churn_risk"] * 8 + ["standard"] * 40
    )

    def add_population(self, n: int) -> None:
        for _ in range(n):
            self.build(self.rng.choice(self.ARCHETYPES))

    # -- product holdings (new categories; separate prod_rng keeps base data stable) -------
    def _new_holdings_for(self, archetype: str) -> list[tuple[str, float]]:
        r = self.prod_rng
        out: list[tuple[str, float]] = []
        add = lambda code, bal=0.0: out.append((code, bal))
        if r.random() < 0.9: add("DIG-IMUAMALAT")
        if r.random() < 0.8: add("DIG-DUITNOW")
        if archetype == "hnw_investor":
            add("INV-SURIA", r.uniform(50_000, 400_000))
            add("INV-GOLD", r.uniform(20_000, 150_000))
            if r.random() < 0.7: add("INV-UT", r.uniform(30_000, 200_000))
            if r.random() < 0.5: add("INV-PMA", r.uniform(100_000, 800_000))
            add("TKF-FAMILY")
            if r.random() < 0.7: add("EST-WASIAT")
            if r.random() < 0.4: add("EST-ASSALIHIN")
            if r.random() < 0.5: add("SVC-SDB")
        elif archetype == "affluent_saver":
            add("INV-TIA", r.uniform(20_000, 120_000))
            if r.random() < 0.6: add("INV-UT", r.uniform(10_000, 80_000))
            if r.random() < 0.5: add("INV-ASNB", r.uniform(5_000, 50_000))
            if r.random() < 0.7: add("TKF-FAMILY")
            if r.random() < 0.4: add("TKF-MEDICAL")
            if r.random() < 0.4: add("EST-WASIAT")
        elif archetype == "digital_shopper":
            if r.random() < 0.6: add("INV-GOLD", r.uniform(1_000, 15_000))
            if r.random() < 0.5: add("INV-ASNB", r.uniform(1_000, 20_000))
            if r.random() < 0.3: add("TKF-MEDICAL")
            if r.random() < 0.3: add("SVC-HAJJ")
        elif archetype == "leveraged_borrower":
            add("TKF-GENERAL")
            if r.random() < 0.5: add("TKF-FAMILY")
            if r.random() < 0.4: add("FIN-ARRAHNU", r.uniform(2_000, 20_000))
        elif archetype == "churn_risk":
            if r.random() < 0.4: add("SVC-ZAKAT")
        else:  # standard retail
            if r.random() < 0.4: add("INV-ASNB", r.uniform(1_000, 30_000))
            if r.random() < 0.3: add("INV-GOLD", r.uniform(1_000, 20_000))
            if r.random() < 0.4: add("TKF-FAMILY")
            if r.random() < 0.3: add("TKF-MEDICAL")
            if r.random() < 0.2: add("EST-WASIAT")
            if r.random() < 0.3: add("SVC-HAJJ")
        return out

    def build_product_holdings(self) -> None:
        """Emit the product catalog + per-customer holdings for the NEW categories
        (investment, Takaful, estate, digital, Ar-Rahnu). Existing accounts/loans/cards are
        mapped to catalog products downstream in Silver, not duplicated here."""
        self.rows.products = [list(p) for p in PRODUCT_CATALOG]
        for c in self.rows.customers:
            cif = c[0]
            for code, bal in self._new_holdings_for(self.archetype.get(cif, "standard")):
                self._hold_seq += 1
                open_date = self.today - timedelta(days=self.prod_rng.randint(30, 3000))
                self.rows.holdings.append(
                    [f"PH{self._hold_seq}", cif, code, "A", yyyymmdd(open_date), round(bal, 2)]
                )

    # -- personas (fixed CIFs) ---------------------------------------------
    def add_personas(self) -> None:
        hnw = "0010000001"
        self.archetype[hnw] = "hnw_investor"
        self.add_customer(hnw, "HNW", date(1968, 4, 12), "KUALA LUMPUR", date(2009, 3, 1), 680_000)
        hnw_sv = self.add_account(hnw, "SV", 420_000.00)
        self.add_account(hnw, "DP", 150_000.00)
        self.add_card_txns(hnw, 6, ["TRAVEL", "DINING"], 900)
        self.add_debit_txns(hnw, hnw_sv, 8, ["DINING", "ATM", "FUEL"], 300)

        sqz = "0010000002"
        self.archetype[sqz] = "leveraged_borrower"
        self.add_customer(sqz, "MASS", date(1985, 9, 2), "JOHOR BAHRU", date(2016, 7, 15), 64_000)
        sqz_sv = self.add_account(sqz, "SV", 3_500.00)
        self.add_loan(sqz, "MORTGAGE", 350_000.00, 285_320.10, 1850.00)
        self.add_card_txns(sqz, 24, ["GROCERY", "UTILITY", "FUEL"], 400)
        self.add_debit_txns(sqz, sqz_sv, 30, ["GROCERY", "ATM", "TRANSPORT", "FUEL"], 150)

        mil = "0010000003"
        self.archetype[mil] = "digital_shopper"
        self.add_customer(mil, "MASS", date(1995, 6, 20), "GEORGE TOWN", date(2020, 1, 10), 48_000)
        mil_sv = self.add_account(mil, "SV", 18_000.00)
        self.add_debit_txns(mil, mil_sv, 18, ["RETAIL", "DINING", "TRANSPORT"], 120)
        card = self.masked_card()
        for _ in range(40):
            d = self.today - timedelta(days=self.rng.randint(0, 25))
            self.rows.cards.append([self.next_txn_id(), card, mil, yyyymmdd(d), self.rand_txn_time(),
                                    round(self.rng.uniform(120.0, 350.0), 2),
                                    self.rng.choice(["DIGITAL", "RETAIL", "DINING"]), "D"])


def write_csv(path: str, header: list[str], rows: list[list]) -> None:
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def write_outputs(out_dir: str, gen: Generator) -> None:
    os.makedirs(out_dir, exist_ok=True)
    for name, rows in [
        ("AS400_CUST_MAST", gen.rows.customers), ("AS400_SVDP_MAST", gen.rows.accounts),
        ("AS400_CC_TXN", gen.rows.cards), ("AS400_DC_TXN", gen.rows.debit_cards),
        ("AS400_LOAN_MAST", gen.rows.loans),
        ("AS400_PRODUCT_MAST", gen.rows.products), ("AS400_PROD_HOLD", gen.rows.holdings),
    ]:
        write_csv(os.path.join(out_dir, f"{name}.csv"), SCHEMAS[name], rows)


def write_corrupt_fixtures(corrupt_dir: str, gen: Generator) -> None:
    """Fixtures that intentionally break validation, for TC-1.1 and TC-3.1."""
    os.makedirs(corrupt_dir, exist_ok=True)
    # TC-3.1: a Savings account with a negative balance -> assert_balanced_accounts fails.
    bad_accounts = list(gen.rows.accounts)
    bad_accounts.append(["SV-000000001", "0010000001", "SV", -5000.00,
                         yyyymmdd(gen.today - timedelta(days=10)), "A"])
    write_csv(os.path.join(corrupt_dir, "AS400_SVDP_MAST.csv"), SCHEMAS["AS400_SVDP_MAST"], bad_accounts)
    # TC-1.1: customer file missing the CMSEG column -> Bronze load schema mismatch.
    cols = SCHEMAS["AS400_CUST_MAST"]
    seg_idx = cols.index("CMSEG")
    write_csv(os.path.join(corrupt_dir, "AS400_CUST_MAST.csv"),
              [c for c in cols if c != "CMSEG"],
              [[v for i, v in enumerate(r) if i != seg_idx] for r in gen.rows.customers])


def main() -> None:
    p = argparse.ArgumentParser(description="Generate mock AS400 core-banking CSV extracts.")
    p.add_argument("--out-dir", default="./out")
    p.add_argument("--corrupt-dir", default="./out/corrupt")
    p.add_argument("--customers", type=int, default=1000, help="Number of archetype customers (excl. personas).")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--today", default=None, help="Override 'today' as YYYY-MM-DD.")
    args = p.parse_args()

    rng = random.Random(args.seed)
    time_rng = random.Random(args.seed + 7)
    prod_rng = random.Random(args.seed + 13)
    fake = Faker()
    Faker.seed(args.seed)
    today = date.fromisoformat(args.today) if args.today else date.today()

    gen = Generator(fake, rng, today, time_rng, prod_rng)
    gen.add_personas()
    gen.add_population(args.customers)
    gen.build_product_holdings()

    write_outputs(args.out_dir, gen)
    write_corrupt_fixtures(args.corrupt_dir, gen)

    print(f"Wrote extracts to {args.out_dir}:")
    print(f"  AS400_CUST_MAST.csv  {len(gen.rows.customers):>7} rows")
    print(f"  AS400_SVDP_MAST.csv  {len(gen.rows.accounts):>7} rows")
    print(f"  AS400_CC_TXN.csv     {len(gen.rows.cards):>7} rows")
    print(f"  AS400_DC_TXN.csv     {len(gen.rows.debit_cards):>7} rows")
    print(f"  AS400_LOAN_MAST.csv  {len(gen.rows.loans):>7} rows")
    print(f"  AS400_PRODUCT_MAST.csv {len(gen.rows.products):>5} rows")
    print(f"  AS400_PROD_HOLD.csv  {len(gen.rows.holdings):>7} rows")
    print(f"Corrupt fixtures (TC-1.1 / TC-3.1) in {args.corrupt_dir}")
    print("Personas: 0010000001=HNW_INVESTOR  0010000002=LEVERAGED_BORROWER  0010000003=DIGITAL_SHOPPER")


if __name__ == "__main__":
    main()
