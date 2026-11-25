import re

from app.agents.tools import KNOWN_SPENDERS, NFT_MARKETPLACES, REGISTRY

ADDRESS = re.compile(r"^0x[0-9a-f]{40}$")


def test_every_entry_is_well_formed_and_sourced() -> None:
    assert set(REGISTRY) == {1, 143}
    for chain, entries in REGISTRY.items():
        addresses = [entry["address"] for entry in entries]
        assert len(addresses) == len(set(addresses)), f"duplicate address on chain {chain}"
        for entry in entries:
            assert ADDRESS.match(entry["address"]), entry
            assert entry["name"].strip(), entry
            assert entry["source"].startswith("https://"), entry
            assert set(entry) <= {"address", "name", "source", "nft_marketplace"}, entry


def test_lookup_tables_follow_the_registry() -> None:
    assert KNOWN_SPENDERS[1]["0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2"] == "Aave V3 Pool"
    assert "0x0d97dc33264bfc1c226207428a79b26757fb9dc3" in KNOWN_SPENDERS[143]
    assert len(KNOWN_SPENDERS[1]) >= 25 and len(KNOWN_SPENDERS[143]) >= 10


def test_nft_marketplaces_are_only_seaport_and_its_conduit() -> None:
    names = {
        entry["name"]
        for entries in REGISTRY.values()
        for entry in entries
        if entry["address"] in NFT_MARKETPLACES
    }
    assert names == {"OpenSea Seaport 1.5", "OpenSea Seaport 1.6", "OpenSea Conduit"}
    # The conduit has no code on Monad, so it must not be listed there.
    assert "0x1e0049783f008a0085193e00003d00cd54003c71" not in KNOWN_SPENDERS[143]
