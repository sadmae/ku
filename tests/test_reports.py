from calc import assess_nodes, assess_options, demand_metrics, example_profile
from reports import csv_bytes, fmt_int, fmt_pb, fmt_pct, pdf_bytes, summary_rows


def test_formatters_use_russian_grouping():
    assert fmt_int(150000) == "150 000"
    assert fmt_int(None) == "—"
    assert fmt_pct(150_000 / 1_800_000) == "8,3%"
    assert fmt_pb(float("inf")) == "∞"
    assert fmt_pb(12) == "12,0"


def test_ainura_csv_and_pdf():
    business, nodes, options = example_profile()
    demand = demand_metrics(business)
    node_result = assess_nodes(nodes, business.total_revenue, business.node_spend)
    payback = assess_options(options)
    rows = summary_rows("ru", demand, node_result)
    payload = csv_bytes(rows).decode("utf-8")
    assert payload.startswith("\ufeff")
    assert "Выручка;1 800 000" in payload
    assert "КУ-спрос;8,3%" in payload
    assert "Узлов без замены;3" in payload
    assert "Суммарная уязвимость;615 000" in payload
    pdf = pdf_bytes("ru", demand, node_result, payback, ["Расходы на продажи в норме."])
    assert pdf is not None
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000
