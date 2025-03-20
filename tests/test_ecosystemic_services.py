from ecobalyse_data.export import food


def test_load_ecs_dic(ecs_factors_csv_file, ecs_factors_json):
    content = food.load_ecosystemic_dic(ecs_factors_csv_file)

    assert len(content) == 35
    assert "AUTRES CULTURES INDUSTRIELLES" in content
    assert content["AUTRES CULTURES INDUSTRIELLES"]["cropDiversity"]["organic"] == 9.196
