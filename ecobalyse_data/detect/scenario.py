from ..export import food
from . import _name


def _get(obj):
    return obj.get("scenario")


def _set(obj, density):
    obj["scenario"] = density
    return obj


class Detector:
    def detect(self, obj):
        return food.scenario(obj)


def update(input_json, threshold, debug=False):
    output_json = []
    detector = Detector()

    print("Trying to find scenario for all ingredients:")
    for obj in input_json:
        if not _get(obj):
            continue

        scenario = detector.detect(obj)
        _set(obj, scenario)
        output_json.append(obj)
        if debug:
            print(f"{_name(obj)}")
            print(f"scenario: {scenario}")
            print("")
        else:
            print(".", end="")

    return output_json
