import asyncio
import json
from unittest.mock import patch

from app.config import Config
from app.database import (
    get_connection,
    init_db,
    insert_match_queue_item,
    insert_product,
    insert_promotion,
    insert_raw_message,
)
from app.products.enrichment_worker import (
    MAX_ATTEMPTS,
    process_match_queue_once,
    run_enrichment_cycle,
)
from app.products.ollama_client import OllamaExtractionResult, OllamaMatchResult


def _active_config():
    """Configuração explícita dos testes do modo legado com escrita habilitada."""
    return Config(ollama_shadow_mode=False)


def _seed_queue_item(conn, *, price=999.90, candidate_ids=None, specs=None):
    raw_id = insert_raw_message(
        conn, telegram_message_id=1, chat_id=1, chat_title="Grupo Teste",
        sender_id=None, message_text="Moto G56 5G 256GB 8GB RAM",
        message_date="2026-07-16T10:00:00",
    )
    promotion_id = insert_promotion(
        conn, raw_message_id=raw_id, price=price, status="APPROVED",
        source_chat_title="Grupo Teste", store_domain="loja.com.br", coupon="BUG10",
    )
    specs = specs or {"brand": "motorola", "model": "moto g56 5g", "storage_gb": 256, "ram_gb": 8}
    candidates_json = json.dumps([{"product_id": cid, "confidence": 0.7, "reason": "similar"}
                                   for cid in (candidate_ids or [])])
    queue_id = insert_match_queue_item(
        conn, promotion_id=promotion_id,
        extracted_specs_json=json.dumps(specs),
        candidate_products_json=candidates_json,
    )
    return promotion_id, queue_id


def test_empty_queue_returns_false(db_conn):
    assert process_match_queue_once(db_conn, _active_config()) is False


def test_match_decision_finalizes_product_and_records_price(db_conn):
    existing_id = insert_product(
        db_conn, canonical_title="Motorola Moto G55 5G 256GB",
        variant_key="motorola|moto g55 5g|256|8", brand="motorola", model="moto g55 5g",
        storage_gb=256, ram_gb=8,
    )
    promotion_id, _ = _seed_queue_item(db_conn, candidate_ids=[existing_id])

    fake_result = OllamaMatchResult(decision="MATCH", product_id=existing_id, confidence=0.9, reason="mesmo produto")
    with patch("app.products.enrichment_worker.disambiguate_product", return_value=fake_result):
        processed = process_match_queue_once(db_conn, _active_config())

    assert processed is True
    promo = db_conn.execute("SELECT * FROM promotions WHERE id = ?", (promotion_id,)).fetchone()
    assert promo["product_id"] == existing_id
    assert promo["product_match_status"] == "AUTO_MATCH_AI"

    history = db_conn.execute(
        "SELECT * FROM product_price_history WHERE product_id = ?", (existing_id,)
    ).fetchone()
    assert history is not None
    assert history["price"] == 999.90


def test_new_decision_creates_product(db_conn):
    promotion_id, _ = _seed_queue_item(db_conn, candidate_ids=[])

    fake_result = OllamaMatchResult(
        decision="NEW", confidence=1.0, canonical_title="Motorola Moto G56 5G 256GB",
        brand="motorola", model="moto g56 5g", storage_gb=256, ram_gb=8, reason="produto novo",
    )
    with patch("app.products.enrichment_worker.disambiguate_product", return_value=fake_result):
        processed = process_match_queue_once(db_conn, _active_config())

    assert processed is True
    promo = db_conn.execute("SELECT * FROM promotions WHERE id = ?", (promotion_id,)).fetchone()
    assert promo["product_id"] is not None
    assert promo["product_match_status"] == "AUTO_NEW_AI"

    product = db_conn.execute("SELECT * FROM products WHERE id = ?", (promo["product_id"],)).fetchone()
    assert product["brand"] == "motorola"


def test_unsure_stays_pending_until_max_attempts(db_conn):
    _seed_queue_item(db_conn, candidate_ids=[])
    fake_result = OllamaMatchResult(decision="UNSURE", confidence=0.4, reason="não deu pra confirmar")

    with patch("app.products.enrichment_worker.disambiguate_product", return_value=fake_result):
        for expected_attempts in range(1, MAX_ATTEMPTS):
            process_match_queue_once(db_conn, _active_config())
            row = db_conn.execute("SELECT * FROM product_match_queue").fetchone()
            assert row["status"] == "PENDING"
            assert row["attempts"] == expected_attempts

        process_match_queue_once(db_conn, _active_config())
        row = db_conn.execute("SELECT * FROM product_match_queue").fetchone()
        assert row["status"] == "NEEDS_HUMAN"
        assert row["attempts"] == MAX_ATTEMPTS


def test_match_with_product_id_outside_candidates_is_treated_as_unsure(db_conn):
    other_product_id = insert_product(
        db_conn, canonical_title="Outro produto qualquer", variant_key="x|y|z|w",
    )
    _seed_queue_item(db_conn, candidate_ids=[])  # sem candidatos reais

    # a IA "inventou" um product_id que nao estava entre os candidatos
    fake_result = OllamaMatchResult(decision="MATCH", product_id=other_product_id, confidence=0.9, reason="?")
    with patch("app.products.enrichment_worker.disambiguate_product", return_value=fake_result):
        process_match_queue_once(db_conn, _active_config())

    row = db_conn.execute("SELECT * FROM product_match_queue").fetchone()
    assert row["status"] == "PENDING"  # cai no fallback de seguranca, nao confia cegamente


def test_run_enrichment_cycle_drains_multiple_items(tmp_path):
    # run_enrichment_cycle fecha a conexão a cada iteração (mesmo padrão de
    # "conexão nova por chamada" usado no watcher real) — por isso usa um
    # banco em arquivo aqui, já que fechar uma conexão :memory: compartilhada
    # destruiria os dados entre as iterações.
    db_path = str(tmp_path / "enrichment_test.sqlite3")
    setup_conn = init_db(db_path)
    _seed_queue_item(setup_conn, candidate_ids=[])
    _seed_queue_item(setup_conn, candidate_ids=[])
    setup_conn.close()

    fake_result = OllamaMatchResult(
        decision="NEW", confidence=1.0, brand="motorola", model="moto g56", reason="ok")
    with patch("app.products.enrichment_worker.disambiguate_product", return_value=fake_result):
        processed_count = asyncio.get_event_loop().run_until_complete(
            run_enrichment_cycle(lambda: get_connection(db_path), _active_config())
        )

    assert processed_count == 2
    verify_conn = get_connection(db_path)
    remaining = verify_conn.execute(
        "SELECT COUNT(*) FROM product_match_queue WHERE status = 'PENDING'"
    ).fetchone()[0]
    assert remaining == 0
    verify_conn.close()


def test_low_confidence_new_decision_does_not_create_product(db_conn):
    promotion_id, _ = _seed_queue_item(db_conn, candidate_ids=[])
    fake_result = OllamaMatchResult(
        decision="NEW", confidence=0.70, brand="motorola", model="moto g56", reason="incerto",
    )

    with patch("app.products.enrichment_worker.disambiguate_product", return_value=fake_result):
        process_match_queue_once(db_conn, _active_config())

    promotion = db_conn.execute(
        "SELECT * FROM promotions WHERE id = ?", (promotion_id,)
    ).fetchone()
    queue = db_conn.execute("SELECT * FROM product_match_queue").fetchone()
    assert promotion["product_id"] is None
    assert queue["status"] == "PENDING"
    assert db_conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0


def test_low_confidence_match_does_not_link_product(db_conn):
    existing_id = insert_product(
        db_conn, canonical_title="Motorola Moto G55",
        variant_key="motorola|moto g55|256|8", brand="motorola", model="moto g55",
        storage_gb=256, ram_gb=8,
    )
    promotion_id, _ = _seed_queue_item(db_conn, candidate_ids=[existing_id])
    fake_result = OllamaMatchResult(
        decision="MATCH", product_id=existing_id, confidence=0.60, reason="incerto",
    )

    with patch("app.products.enrichment_worker.disambiguate_product", return_value=fake_result):
        process_match_queue_once(db_conn, _active_config())

    promotion = db_conn.execute(
        "SELECT * FROM promotions WHERE id = ?", (promotion_id,)
    ).fetchone()
    assert promotion["product_id"] is None


def test_multiple_products_never_reach_ollama_or_create_product(db_conn):
    promotion_id, _ = _seed_queue_item(
        db_conn, specs={"review_reason": "MULTIPLE_PRODUCTS"},
    )

    with (
        patch("app.products.enrichment_worker.extract_specs_via_ollama") as mock_extract,
        patch("app.products.enrichment_worker.disambiguate_product") as mock_match,
    ):
        process_match_queue_once(db_conn, _active_config())

    queue = db_conn.execute("SELECT * FROM product_match_queue").fetchone()
    promotion = db_conn.execute(
        "SELECT * FROM promotions WHERE id = ?", (promotion_id,)
    ).fetchone()
    assert queue["status"] == "NEEDS_HUMAN"
    assert promotion["product_match_status"] == "NEEDS_HUMAN"
    assert db_conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0
    mock_extract.assert_not_called()
    mock_match.assert_not_called()


def test_ollama_extraction_only_fills_missing_specs(db_conn):
    _seed_queue_item(
        db_conn,
        specs={
            "brand": "motorola",
            "model": None,
            "storage_gb": 256,
            "ram_gb": None,
            "category": "smartphone",
            "completeness_confidence": 0.67,
        },
    )
    extraction = OllamaExtractionResult(
        ok=True,
        brand="marca-inventada",
        model="moto g56 5g",
        storage_gb=128,
        ram_gb=8,
        category="outra",
    )
    unsure = OllamaMatchResult(decision="UNSURE", confidence=0.4, reason="revisar")

    with (
        patch(
            "app.products.enrichment_worker.extract_specs_via_ollama",
            return_value=extraction,
        ),
        patch(
            "app.products.enrichment_worker.disambiguate_product",
            return_value=unsure,
        ) as mock_match,
    ):
        process_match_queue_once(db_conn, _active_config())

    enriched = mock_match.call_args.kwargs["extracted"]
    assert enriched["brand"] == "motorola"
    assert enriched["model"] == "moto g56 5g"
    assert enriched["storage_gb"] == 256
    assert enriched["ram_gb"] == 8
    assert enriched["category"] == "smartphone"


def test_shadow_mode_rejects_ai_fields_without_textual_evidence(db_conn):
    _seed_queue_item(
        db_conn,
        specs={
            "brand": None,
            "model": None,
            "storage_gb": None,
            "ram_gb": None,
            "category": "smartphone",
            "completeness_confidence": 0.0,
        },
    )
    extraction = OllamaExtractionResult(
        ok=True,
        brand="nike",
        model="air zoom",
        storage_gb=1329,
        ram_gb=1329,
        category="smartphone",
    )
    unsure = OllamaMatchResult(decision="UNSURE", confidence=0.2, reason="revisar")

    with (
        patch(
            "app.products.enrichment_worker.extract_specs_via_ollama",
            return_value=extraction,
        ),
        patch(
            "app.products.enrichment_worker.disambiguate_product",
            return_value=unsure,
        ) as mock_match,
    ):
        process_match_queue_once(db_conn, Config(ollama_shadow_mode=True))

    assert mock_match.call_args.kwargs["extracted"]["storage_gb"] is None
    assert mock_match.call_args.kwargs["extracted"]["ram_gb"] is None
    queue = db_conn.execute("SELECT * FROM product_match_queue").fetchone()
    hybrid = json.loads(queue["result_json"])["hybrid_classification"]
    assert set(hybrid["rejected_ai_fields"]) == {"brand", "model", "storage_gb", "ram_gb"}


def test_shadow_mode_records_ai_result_without_mutating_catalog(db_conn):
    promotion_id, queue_id = _seed_queue_item(db_conn, candidate_ids=[])
    fake_result = OllamaMatchResult(
        decision="NEW",
        confidence=1.0,
        canonical_title="Motorola Moto G56 5G 256GB",
        brand="motorola",
        model="moto g56 5g",
        storage_gb=256,
        ram_gb=8,
        reason="produto novo",
    )

    with (
        patch(
            "app.products.enrichment_worker.extract_specs_via_ollama",
            return_value=OllamaExtractionResult(ok=False),
        ),
        patch("app.products.enrichment_worker.disambiguate_product", return_value=fake_result),
    ):
        processed = process_match_queue_once(
            db_conn,
            Config(ollama_shadow_mode=True),
        )

    assert processed is True
    promotion = db_conn.execute(
        "SELECT * FROM promotions WHERE id = ?", (promotion_id,)
    ).fetchone()
    queue = db_conn.execute(
        "SELECT * FROM product_match_queue WHERE id = ?", (queue_id,)
    ).fetchone()
    result = json.loads(queue["result_json"])

    assert promotion["product_id"] is None
    assert db_conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0
    assert db_conn.execute("SELECT COUNT(*) FROM product_price_history").fetchone()[0] == 0
    assert queue["status"] == "SHADOW_DONE"
    assert queue["attempts"] == 1
    assert result["decision"] == "NEW"
    assert result["confidence"] == 1.0
    assert result["hybrid_classification"]["status"] == "UNRESOLVED"
    assert result["hybrid_classification"]["catalog_version"] == "1.0.0"
