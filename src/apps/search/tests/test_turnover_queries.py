import pytest

from apps.search.contracts import TurnoverQuery
from apps.search.queries import turnover


@pytest.mark.unit
def test_movements_body_has_throughput_movers_and_window():
    body = turnover.build_movements_body(TurnoverQuery(window_days=30))
    aggs = body["aggs"]
    assert aggs["throughput"]["aggs"]["by_week"]["date_histogram"]["calendar_interval"] == "week"
    assert aggs["top_movers"]["aggs"]["products"]["terms"]["field"] == "product_name.keyword"
    assert aggs["dispensed_units"]["aggs"]["q"]["sum"]["field"] == "quantity"


@pytest.mark.unit
def test_parse_movements():
    response = {
        "took": 7,
        "aggregations": {
            "dispensed_units": {"q": {"value": 120.0}},
            "received_units": {"q": {"value": 300.0}},
            "throughput": {
                "by_week": {
                    "buckets": [
                        {
                            "key_as_string": "2026-05-25",
                            "dispensed": {"q": {"value": 30.0}},
                            "received": {"q": {"value": 80.0}},
                        }
                    ]
                }
            },
            "top_movers": {"products": {"buckets": [{"key": "Panadol", "units": {"value": 50.0}}]}},
            "dispensed_products": {
                "products": {"buckets": [{"key": "Panadol"}, {"key": "Brufen"}]}
            },
        },
    }
    parsed = turnover.parse_movements(response)
    assert parsed["dispensed_units"] == 120
    assert parsed["received_units"] == 300
    assert parsed["throughput"][0].dispensed == 30
    assert parsed["throughput"][0].received == 80
    assert parsed["top_movers"][0].product == "Panadol"
    assert parsed["dispensed_products"] == {"Panadol", "Brufen"}


@pytest.mark.unit
def test_dead_stock_excludes_dispensed_and_totals():
    instock = {
        "aggregations": {
            "products": {
                "buckets": [
                    {"key": "Lantus", "units": {"value": 40.0}, "value": {"value": 800.0}},
                    {"key": "Panadol", "units": {"value": 100.0}, "value": {"value": 200.0}},
                    {"key": "Cortef", "units": {"value": 10.0}, "value": {"value": 150.0}},
                ]
            }
        }
    }
    rows, total = turnover.dead_stock(instock, dispensed_products={"Panadol"})
    products = [r.product for r in rows]
    assert "Panadol" not in products
    assert products == ["Lantus", "Cortef"]  # sorted by value desc
    assert total == 950.0
