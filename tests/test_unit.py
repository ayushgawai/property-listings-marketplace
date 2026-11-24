import pytest
from marketplace.cli import build_stack
from marketplace.listing_service import ValidationError
from marketplace.search_service import SearchQuery, haversine_km, percentile
from marketplace.auth import AuthError

def stack_with(n=50):
    s = build_stack(); s["ingestion"].seed(n, seed=3); s["search"].build_index(); return s

def test_listing_validation_rejects_bad_price():
    s = build_stack()
    with pytest.raises(ValidationError):
        s["listings"].create({"id": "X1", "title": "Nice home", "description": "d", "price": -5, "city": "Austin"})

def test_listing_crud_and_status():
    s = build_stack()
    l = s["listings"].create({"id": "X1", "title": "Nice home", "description": "d", "price": 100000, "city": "Austin", "agent_id": "a1"})
    assert s["listings"].get("X1").price == 100000
    assert s["listings"].set_status("X1", "sold").status == "sold"
    assert s["listings"].delete("X1") is True and s["listings"].get("X1") is None

def test_search_filters_and_geo():
    s = stack_with(200)
    r = s["search"].search(SearchQuery(city="Austin", max_price=10_000_000, limit=5))
    assert r["total"] > 0 and all(x["listing"]["city"] == "Austin" for x in r["results"])
    assert haversine_km(30.267, -97.743, 30.267, -97.743) == 0
    assert percentile([1, 2, 3, 4], 50) == 2.5

def test_search_excludes_sold():
    s = stack_with(20)
    first = s["store"].all_listings()[0]
    s["listings"].set_status(first.id, "sold")
    r = s["search"].search(SearchQuery(limit=100))
    assert all(x["listing"]["id"] != first.id for x in r["results"])

def test_auth_register_login_roles():
    s = build_stack()
    u = s["auth"].register("a@example.com", "password-123", role="agent")
    token = s["auth"].login("a@example.com", "password-123")
    assert s["auth"].require_role(token, "agent").id == u.id
    with pytest.raises(AuthError): s["auth"].login("a@example.com", "wrong-password")
    with pytest.raises(AuthError): s["auth"].register("a@example.com", "password-123")
    with pytest.raises(AuthError): s["auth"].register("bad", "short")

def test_saved_roundtrip():
    s = stack_with(10); lid = s["store"].all_listings()[0].id
    s["saved"].save("u1", lid, note="check")
    assert s["saved"].is_saved("u1", lid) and len(s["saved"].list_saved("u1")) == 1
    assert s["saved"].unsave("u1", lid) and not s["saved"].is_saved("u1", lid)
    with pytest.raises(ValueError): s["saved"].save("u1", "missing")

def test_inquiry_flow_and_notifications():
    s = stack_with(10); l = s["store"].all_listings()[0]
    inq = s["inquiries"].create(l.id, "buyer-1", "Available?")
    assert inq.agent_id == l.agent_id and s["notifications"].pending() == 1
    s["inquiries"].reply(inq.id, l.agent_id, "Yes")
    assert inq.status == "replied" and s["notifications"].pending() == 2
    with pytest.raises(ValueError): s["inquiries"].create(l.id, l.agent_id, "own listing")
    s["inquiries"].close(inq.id, "buyer-1"); assert inq.status == "closed"

def test_ingestion_dedupe_and_bad_records():
    s = build_stack()
    good = {"id": "D1", "title": "Dup home", "description": "d", "price": 200000, "city": "Denver", "bedrooms": 2, "area_sqft": 900}
    rep = s["ingestion"].ingest([good, dict(good, id="D2"), {"id": "BAD", "title": "x", "price": -1, "city": ""}])
    assert rep.accepted == 1 and rep.duplicates == 1 and rep.rejected == 1

def test_ingestion_csv():
    s = build_stack()
    csv_text = "id,title,description,price,city,property_type,bedrooms,area_sqft,amenities\nC1,CSV home,d,150000,Austin,house,3,1200,pool;parking\n"
    rep = s["ingestion"].ingest_csv(csv_text)
    assert rep.accepted == 1 and s["listings"].get("C1").amenities == ["pool", "parking"]

def test_analytics():
    s = stack_with(30); lid = s["store"].all_listings()[0].id
    s["saved"].save("u1", lid); s["inquiries"].create(lid, "b1", "Hello there")
    ov = s["analytics"].overview()
    assert ov["listings"] == 30 and ov["inquiries"] == 1 and ov["saved"] == 1
    assert s["analytics"].price_by_city() and s["analytics"].top_saved()[0]["listing_id"] == lid
    assert s["analytics"].demand()
