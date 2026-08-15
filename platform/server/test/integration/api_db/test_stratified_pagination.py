def test_stratified_pages_cover_all_rows(client, sample_data):
    summary = client.get("/api/night-trains/summary").json()
    expected_total = summary["total_trains"]

    slice_totals = []

    for page in range(1, 11):
        response = client.get(
            "/api/night-trains/stratified",
            params={"slice_page": page, "sample_per_country": 1},
        )
        assert response.status_code == 200
        payload = response.json()

        assert payload["slice_page"] == page
        assert payload["page_count"] == 10
        assert payload["total_filtered"] == expected_total
        slice_totals.append(payload["slice_total"])

    # Les dix tranches sont disjointes et couvrent tout le jeu.
    assert sum(slice_totals) == expected_total


def test_stratified_response_exposes_country_breakdown(client, sample_data):
    response = client.get(
        "/api/night-trains/stratified",
        params={"slice_page": 1, "sample_per_country": 2},
    )

    assert response.status_code == 200
    payload = response.json()

    assert "by_country" in payload
    assert "items" in payload
    assert "actual_slice_percent" in payload

    for country in payload["by_country"]:
        assert "total_filtered" in country
        assert "slice_trains" in country
        assert "slice_percent" in country
        assert (
            country["night_trains"] + country["day_trains"]
            == country["slice_trains"]
        )
        assert (
            country["real_trains"] + country["synthetic_trains"]
            == country["slice_trains"]
        )


def test_train_facets(client, sample_data):
    response = client.get("/api/night-trains/facets")
    assert response.status_code == 200

    payload = response.json()
    assert payload["page_count"] == 10
    assert 2010 in payload["years"]
