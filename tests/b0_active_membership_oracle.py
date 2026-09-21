"""Accepted pre-optimization rule, restored only for bounded offline comparison.

This does not import historical modules or alter current source bindings. The
entire restored validator AST must equal the accepted pre-optimization function;
only the marked local index and membership-query statements are substituted.
"""

import ast
import hashlib
import inspect
import re
import textwrap


ACCEPTED_REVISION = "736994bdf2ded68c4c0c2f432a599b1a796bada9"
ACCEPTED_VALIDATE_AST_SHA256 = "fb99f1d0f6b990cb458066f4bbfbb62f3c9fa8f7cacfef988ab5f0c582f63bc6"
OLD_QUERY = ('expected_active = {v for v, times in obs["departed_events"].items() '
             'if len(times)==1 and times[0] <= time and (v not in '
             'obs["arrival_events"] or time < obs["arrival_events"][v][0])}')


def reference_active(departed_events, arrival_events, sample_time):
    """Exact old membership rule, including its short circuit/error behavior."""
    return {v for v, times in departed_events.items()
            if len(times) == 1 and times[0] <= sample_time
            and (v not in arrival_events or sample_time < arrival_events[v][0])}


def make_reference_validate_run(core):
    source = textwrap.dedent(inspect.getsource(core._validate_run))
    for part, replacement in (("INDEX", ""), ("QUERY", OLD_QUERY)):
        expression = (r"(?m)^(?P<indent> +)# ACTIVE_MEMBERSHIP_" + part
                      + r"_BEGIN\n.*?^(?P=indent)# ACTIVE_MEMBERSHIP_" + part
                      + r"_END\n")
        def replace(match):
            return match["indent"] + replacement + "\n" if replacement else ""
        source, count = re.subn(expression, replace, source, flags=re.S)
        if count != 1:
            raise AssertionError("EXACTLY_ONE_REVIEWED_ACTIVE_BLOCK_REQUIRED:" + part)
    tree = ast.parse(source)
    function, = tree.body
    actual = hashlib.sha256(ast.dump(function, include_attributes=False).encode()).hexdigest()
    if actual != ACCEPTED_VALIDATE_AST_SHA256:
        raise AssertionError("REFERENCE_VALIDATOR_AST_CHANGED")
    namespace = dict(vars(core))
    exec(compile(tree, "<accepted-active-membership-reference>", "exec"), namespace)
    return namespace["_validate_run"]
