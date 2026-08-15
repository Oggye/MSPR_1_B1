def test_operator_timeline(client, sample_data):
    response = client.get("/api/operators/1/timeline")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, list)

    for row in data:
        assert (
            row["night_trains"] + row["day_trains"]
            == row["total_trains"]
        )
        assert (
            row["real_trains"] + row["synthetic_trains"]
            == row["total_trains"]
        )
