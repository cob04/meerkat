import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.catalog.models import Drug, InventoryItem, Location, Product

LOCATIONS = [
    {
        "name": "Westlands Pharmacy",
        "location_type": Location.LocationType.PHARMACY,
        "latitude": Decimal("-1.265700"),
        "longitude": Decimal("36.812400"),
        "address": "Westlands, Nairobi",
    },
    {
        "name": "Karen Pharmacy",
        "location_type": Location.LocationType.PHARMACY,
        "latitude": Decimal("-1.319167"),
        "longitude": Decimal("36.706944"),
        "address": "Karen, Nairobi",
    },
    {
        "name": "Eastleigh Pharmacy",
        "location_type": Location.LocationType.PHARMACY,
        "latitude": Decimal("-1.275000"),
        "longitude": Decimal("36.851000"),
        "address": "Eastleigh, Nairobi",
    },
    {
        "name": "Kilimani Pharmacy",
        "location_type": Location.LocationType.PHARMACY,
        "latitude": Decimal("-1.291600"),
        "longitude": Decimal("36.787800"),
        "address": "Kilimani, Nairobi",
    },
    {
        "name": "Mombasa Road Warehouse",
        "location_type": Location.LocationType.WAREHOUSE,
        "latitude": Decimal("-1.323200"),
        "longitude": Decimal("36.870000"),
        "address": "Mombasa Road, Nairobi",
    },
    {
        "name": "Mombasa Branch",
        "location_type": Location.LocationType.PHARMACY,
        "latitude": Decimal("-4.043477"),
        "longitude": Decimal("39.668207"),
        "address": "Nyali, Mombasa",
    },
    {
        "name": "General Ward",
        "location_type": Location.LocationType.WARD,
        "latitude": None,
        "longitude": None,
        "address": "Ward storage, no GPS",
    },
]

DRUGS = [
    ("Paracetamol", "Panadol", "N02BE01", "tablet", "500", "mg", "GSK", "analgesic", False, ""),
    ("Ibuprofen", "Brufen", "M01AE01", "tablet", "400", "mg", "Abbott", "analgesic", False, ""),
    ("Amoxicillin", "Amoxil", "J01CA04", "capsule", "500", "mg", "GSK", "antibiotic", True, ""),
    (
        "Azithromycin",
        "Zithromax",
        "J01FA10",
        "tablet",
        "250",
        "mg",
        "Pfizer",
        "antibiotic",
        True,
        "",
    ),
    ("Metformin", "Glucophage", "A10BA02", "tablet", "500", "mg", "Merck", "diabetes", True, ""),
    (
        "Atorvastatin",
        "Lipitor",
        "C10AA05",
        "tablet",
        "20",
        "mg",
        "Pfizer",
        "cardiovascular",
        True,
        "",
    ),
    ("Salbutamol", "Ventolin", "R03AC02", "inhaler", "100", "mcg", "GSK", "respiratory", True, ""),
    (
        "Omeprazole",
        "Losec",
        "A02BC01",
        "capsule",
        "20",
        "mg",
        "AstraZeneca",
        "gastrointestinal",
        False,
        "",
    ),
    ("Ciprofloxacin", "Cipro", "J01MA02", "tablet", "500", "mg", "Bayer", "antibiotic", True, ""),
    (
        "Loratadine",
        "Claritin",
        "R06AX13",
        "tablet",
        "10",
        "mg",
        "Bayer",
        "antihistamine",
        False,
        "",
    ),
    (
        "Insulin glargine",
        "Lantus",
        "A10AE04",
        "injection",
        "100",
        "IU/ml",
        "Sanofi",
        "diabetes",
        True,
        "",
    ),
    (
        "Hydrocortisone",
        "Cortef",
        "D07AA02",
        "cream",
        "1",
        "%",
        "Pfizer",
        "dermatological",
        False,
        "",
    ),
    ("Diazepam", "Valium", "N05BA01", "tablet", "5", "mg", "Roche", "psychotropic", True, "IV"),
    ("Morphine sulfate", "MST", "N02AA01", "tablet", "10", "mg", "Napp", "analgesic", True, "II"),
    (
        "Lisinopril",
        "Zestril",
        "C09AA03",
        "tablet",
        "10",
        "mg",
        "AstraZeneca",
        "cardiovascular",
        True,
        "",
    ),
]

NON_DRUG_PRODUCTS = [
    ("Surgical gloves", "GLOVE-M", "supplies", Decimal("4.50")),
    ("N95 masks", "MASK-N95", "supplies", Decimal("3.20")),
    ("Bandage roll", "BAND-10", "supplies", Decimal("1.80")),
    ("Glucose meter", "GLUC-METER", "devices", Decimal("28.00")),
    ("Thermometer digital", "THERM-DIG", "devices", Decimal("9.50")),
]


class Command(BaseCommand):
    help = "Populate the catalog with realistic demo data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true", help="Wipe existing catalog rows first."
        )
        parser.add_argument(
            "--items", type=int, default=180, help="Approx. inventory items to create."
        )
        parser.add_argument("--seed", type=int, default=42, help="RNG seed for repeatable output.")

    @transaction.atomic
    def handle(self, *args, **options):
        rng = random.Random(options["seed"])

        if options["reset"]:
            self._reset()

        locations = self._seed_locations()
        drug_products = self._seed_drugs()
        other_products = self._seed_non_drug_products()
        items = self._seed_inventory(
            rng, locations, drug_products + other_products, options["items"]
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(locations)} locations, "
                f"{len(drug_products)} drugs, "
                f"{len(other_products)} other products, "
                f"{len(items)} inventory items."
            )
        )

    def _reset(self):
        InventoryItem.all_objects.all().delete()
        Drug.all_objects.all().delete()
        Product.all_objects.all().delete()
        Location.all_objects.all().delete()
        self.stdout.write(self.style.WARNING("Wiped existing catalog rows."))

    def _seed_locations(self) -> list[Location]:
        objects = []
        for spec in LOCATIONS:
            obj, _ = Location.objects.update_or_create(
                name=spec["name"],
                defaults={
                    "location_type": spec["location_type"],
                    "latitude": spec["latitude"],
                    "longitude": spec["longitude"],
                    "address": spec["address"],
                },
            )
            objects.append(obj)
        return objects

    def _seed_drugs(self) -> list[Product]:
        products = []
        for inn, brand, atc, form, strength, unit, mfr, category, prescription, schedule in DRUGS:
            sku = f"DRUG-{atc}"
            product, _ = Product.objects.update_or_create(
                sku=sku,
                defaults={
                    "name": brand or inn,
                    "category": category,
                    "unit_price": Decimal("4.50"),
                    "is_active": True,
                },
            )
            Drug.objects.update_or_create(
                product=product,
                defaults={
                    "inn_name": inn,
                    "brand_name": brand,
                    "atc_code": atc,
                    "dosage_form": form,
                    "strength": strength,
                    "unit": unit,
                    "manufacturer": mfr,
                    "requires_prescription": prescription,
                    "schedule": schedule,
                },
            )
            products.append(product)
        return products

    def _seed_non_drug_products(self) -> list[Product]:
        products = []
        for name, sku, category, price in NON_DRUG_PRODUCTS:
            product, _ = Product.objects.update_or_create(
                sku=sku,
                defaults={
                    "name": name,
                    "category": category,
                    "unit_price": price,
                    "is_active": True,
                },
            )
            products.append(product)
        return products

    def _seed_inventory(
        self,
        rng: random.Random,
        locations: list[Location],
        products: list[Product],
        target_count: int,
    ) -> list[InventoryItem]:
        today = date.today()
        statuses = (
            [InventoryItem.Status.AVAILABLE] * 12
            + [InventoryItem.Status.RESERVED] * 2
            + [InventoryItem.Status.EXPIRED] * 1
            + [InventoryItem.Status.RECALLED] * 1
        )
        expiry_buckets = [
            ("expired", -90, -1),
            ("30d", 1, 30),
            ("90d", 31, 90),
            ("90plus", 91, 365),
        ]

        items = []
        for i in range(target_count):
            product = rng.choice(products)
            location = rng.choice(locations)
            status = rng.choice(statuses)
            bucket_name, lo, hi = rng.choices(expiry_buckets, weights=[1, 3, 4, 6], k=1)[0]
            expiry = today + timedelta(days=rng.randint(lo, hi))

            if status == InventoryItem.Status.EXPIRED:
                expiry = today - timedelta(days=rng.randint(1, 60))
            quantity = rng.choice([0, 0, 2, 5, 8, 12, 25, 40, 75, 120])

            item_name = f"{product.name} {bucket_name[:3]}-{i:03d}"
            batch = f"B{rng.randint(1000, 9999)}-{i:03d}"

            items.append(
                InventoryItem.objects.create(
                    item_name=item_name,
                    product=product,
                    location=location,
                    batch_number=batch,
                    quantity=quantity,
                    expiry_date=expiry,
                    unit_cost=Decimal(rng.randint(50, 5000)) / Decimal(100),
                    status=status,
                )
            )
        return items
