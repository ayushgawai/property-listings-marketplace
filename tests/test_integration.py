"""Integration: cross-service flows through the shared store + CLI e2e."""
from marketplace.cli import build_stack, cmd_e2e
from marketplace.search_service import SearchQuery
import argparse

def test_discovery_to_inquiry_connection():
    s = build_stack()
    agent = s["auth"].register("agent@example.com", "agent-pass-123", role="agent")
    buyer = s["auth"].register("buyer@example.com", "buyer-pass-123")
    s["ingestion"].seed(100, seed=11); s["search"].build_index()
    listing = s["listings"].create({"id": "I-1", "title": "Modern condo Downtown", "description": "Bright condo",
                                    "price": 400000, "city": "Seattle", "property_type": "condo", "bedrooms": 2,
                                    "area_sqft": 950, "agent_id": agent.id, "amenities": ["gym"]})
    s["search"].add(listing)
    hits = s["search"].search(SearchQuery(text="modern condo", city="Seattle", amenities=("gym",)))
    assert any(h["listing"]["id"] == "I-1" for h in hits["results"])
    s["saved"].save(buyer.id, "I-1")
    inq = s["inquiries"].create("I-1", buyer.id, "Can I tour Friday?")
    s["inquiries"].reply(inq.id, agent.id, "Friday 2pm works")
    assert len(s["notifications"].drain()) == 2
    board = s["analytics"].agent_leaderboard()
    assert any(r["agent_id"] == agent.id and r["inquiries"] == 1 for r in board)

def test_cli_e2e_command():
    assert cmd_e2e(argparse.Namespace()) == 0

def test_price_drop_reindex_flow():
    s = build_stack(); s["ingestion"].seed(50, seed=5); s["search"].build_index()
    l = s["store"].all_listings()[0]
    s["listings"].update(l.id, {"price": 1.0})
    r = s["search"].search(SearchQuery(max_price=10, limit=5))
    assert r["total"] >= 1
