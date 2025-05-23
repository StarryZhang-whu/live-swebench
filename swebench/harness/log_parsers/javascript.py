import re

from swebench.harness.constants import TestStatus
from swebench.harness.utils import ansi_escape


def parse_log_calypso(log: str) -> dict[str, str]:
    """
    Parser for test logs generated by Calypso test suite
    """
    test_status_map = {}
    suite = []

    get_test_name = lambda suite, match_pattern, line: " - ".join(
        [" - ".join([x[0] for x in suite]), re.match(match_pattern, line).group(1)]
    ).strip()

    for log in log.split(" ./node_modules/.bin/jest ")[1:]:
        for line in log.split("\n"):
            if any([line.startswith(x) for x in ["Test Suites", "  ● "]]):
                break
            elif line.strip().startswith("✓"):
                # Test passed
                match_pattern = (
                    r"^\s+✓\s(.*)\(\d+ms\)$"
                    if re.search(r"\(\d+ms\)", line) is not None
                    else r"^\s+✓\s(.*)"
                )
                test_status_map[get_test_name(suite, match_pattern, line)] = (
                    TestStatus.PASSED.value
                )
            elif line.strip().startswith("✕"):
                # Test failed
                match_pattern = (
                    r"^\s+✕\s(.*)\(\d+ms\)$"
                    if re.search(r"\(\d+ms\)", line) is not None
                    else r"^\s+✕\s(.*)"
                )
                test_status_map[get_test_name(suite, match_pattern, line)] = (
                    TestStatus.FAILED.value
                )
            elif len(line) - len(line.lstrip()) > 0:
                # Adjust suite name
                indent = len(line) - len(line.lstrip())
                if len(suite) == 0:
                    # If suite is empty, initialize it
                    suite = [(line.strip(), indent)]
                else:
                    while len(suite) > 0 and suite[-1][-1] >= indent:
                        # Pop until the last element with indent less than current indent
                        suite.pop()
                    suite.append([line.strip(), indent])

    return test_status_map


def parse_log_chart_js(log: str) -> dict[str, str]:
    """
    Parser for test logs generated by ChartJS test suite
    """
    test_status_map = {}
    failure_case_patterns = [
        (r"Chrome\s[\d\.]+\s\(.*?\)\s(.*)FAILED$", re.MULTILINE),
    ]
    for failure_case_pattern, flags in failure_case_patterns:
        failures = re.findall(failure_case_pattern, log, flags)
        if len(failures) == 0:
            continue
        for failure in failures:
            test_status_map[failure] = TestStatus.FAILED.value
    return test_status_map


def parse_log_marked(log: str) -> dict[str, str]:
    """
    Parser for test logs generated by Marked test suite
    """
    test_status_map = {}
    for line in log.split("\n"):
        if re.search(r"^\d+\)\s(.*)", line):
            test = re.search(r"^\d+\)\s(.*)", line).group(1)
            test_status_map[test.strip()] = TestStatus.FAILED.value
    return test_status_map


def parse_log_p5js(log_content: str) -> dict[str, str]:
    def remove_json_blocks(log):
        filtered_lines = []
        in_json_block = False
        in_json_list_block = False
        for line in log.split("\n"):
            stripped_line = line.rstrip()  # Remove trailing whitespace
            if stripped_line.endswith("{"):
                in_json_block = True
                continue
            if stripped_line.endswith("["):
                in_json_list_block = True
                continue
            if stripped_line == "}" and in_json_block:
                in_json_block = False
                continue
            if stripped_line == "]" and in_json_list_block:
                in_json_list_block = False
                continue
            if in_json_block or in_json_list_block:
                continue
            if stripped_line.startswith("{") and stripped_line.endswith("}"):
                continue
            if stripped_line.startswith("[") and stripped_line.endswith("]"):
                continue
            filtered_lines.append(line)
        return "\n".join(filtered_lines)

    def remove_xml_blocks(log):
        xml_pat = re.compile(r"<(\w+)>[\s\S]*?<\/\1>", re.MULTILINE)
        match = xml_pat.search(log)
        while match:
            # count the number of opening tags in the match
            opening_tags = match.group().count(rf"<{match.group(1)}>") - 1
            opening_tags = max(opening_tags, 0)
            start = match.start()
            end = match.end()
            log = log[:start] + f"<{match.group(1)}>" * opening_tags + log[end:]
            match = xml_pat.search(log)
        return log

    def is_valid_fail(match):
        last_line_indent = 0
        for line in match.group(2).split("\n"):
            line_indent = len(line) - len(line.lstrip())
            if line_indent <= last_line_indent:
                return False
            last_line_indent = line_indent
        return True

    log_content = ansi_escape(log_content)
    log_content = remove_json_blocks(log_content)
    log_content = remove_xml_blocks(log_content)
    test_results = {}

    # Parse failing tests
    fail_pattern = re.compile(r"^\s*(\d+)\)(.{0,1000}?):", re.MULTILINE | re.DOTALL)
    for match in fail_pattern.finditer(log_content):
        if is_valid_fail(match):
            test_names = list(map(str.strip, match.group(2).split("\n")))
            full_name = ":".join(test_names)
            test_results[full_name] = TestStatus.FAILED.value

    return test_results


def parse_log_react_pdf(log: str) -> dict[str, str]:
    """
    Parser for test logs generated by Carbon test suite
    """
    test_status_map = {}
    for line in log.split("\n"):
        for pattern in [
            (r"^PASS\s(.*)\s\([\d\.]+ms\)", TestStatus.PASSED.value),
            (r"^PASS\s(.*)\s\([\d\.]+\ss\)", TestStatus.PASSED.value),
            (r"^PASS\s(.*)\s\([\d\.]+s\)", TestStatus.PASSED.value),
            (r"^PASS\s(.*)", TestStatus.PASSED.value),
            (r"^FAIL\s(.*)\s\([\d\.]+ms\)", TestStatus.FAILED.value),
            (r"^FAIL\s(.*)\s\([\d\.]+\ss\)", TestStatus.FAILED.value),
            (r"^FAIL\s(.*)\s\([\d\.]+s\)", TestStatus.FAILED.value),
            (r"^FAIL\s(.*)", TestStatus.FAILED.value),
        ]:
            if re.search(pattern[0], line):
                test_name = re.match(pattern[0], line).group(1)
                test_status_map[test_name] = pattern[1]
                break
    return test_status_map


MAP_REPO_TO_PARSER_JS = {
    "Automattic/wp-calypso": parse_log_calypso,
    "chartjs/Chart.js": parse_log_chart_js,
    "markedjs/marked": parse_log_marked,
    "processing/p5.js": parse_log_p5js,
    "diegomura/react-pdf": parse_log_react_pdf,
}
