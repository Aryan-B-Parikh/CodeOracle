"""Parse a JaCoCo XML report into the canonical CodeOracle coverage JSON.

Expected input: the `jacoco.xml` produced by `jacoco:report`.
Prints a single-line JSON object to stdout.
"""

import json
import sys
import xml.etree.ElementTree as ET


def percent(missed: float, covered: float) -> float:
    total = missed + covered
    return round(covered / total * 100.0, 2) if total else 100.0


def main(report_path: str) -> int:
    root = ET.parse(report_path).getroot()
    counters = {c.attrib["type"]: c.attrib for c in root.findall("counter")}
    line = counters.get("LINE", {"missed": "0", "covered": "0"})
    branch = counters.get("BRANCH", {"missed": "0", "covered": "0"})

    uncovered: list[dict] = []
    for pkg in root.findall("package"):
        for source in pkg.findall("sourcefile"):
            for line_el in source.findall("line"):
                if int(line_el.attrib.get("mi", 0)) > 0:
                    uncovered.append(
                        {
                            "file": source.attrib["name"],
                            "line": int(line_el.attrib["nr"]),
                        }
                    )

    result = {
        "lineCoverage": percent(float(line["missed"]), float(line["covered"])),
        "branchCoverage": percent(float(branch["missed"]), float(branch["covered"])),
        "uncoveredLines": uncovered,
    }
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
