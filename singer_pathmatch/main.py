import sys
import json
import argparse

from collections import namedtuple
from singer import metadata
from pathmatch.wildmatch import WildmatchPattern

Field = namedtuple(
    "MatchedField",
    [
        "stream_name",
        "breadcrumb",
        "path",
    ],
)
FieldPattern = namedtuple(
    "FieldPattern",
    [
        "string",
        "negation",
        "compiled",
    ],
)


class UnusedPatternsError(Exception):
    pass


def make_path(stream_name, breadcrumb):
    return "/".join((stream_name,) + breadcrumb[1:])


def yield_available_fields(catalog):
    """Yield every select-able field in the schema, along with a path string."""

    for stream in catalog["streams"]:
        stream_name = stream["stream"]
        stream_map = metadata.to_map(stream["metadata"])
        matchable_inclusions = {"available"}

        if stream_map.get((), {}).get("inclusion") == "available":
            # include automatic fields as match-able if the stream itself is
            # optional, because the stream will be selected (only) if one of
            # its fields is matched
            matchable_inclusions.add("automatic")

        for breadcrumb, field in stream_map.items():
            if breadcrumb[:1] != ("properties",):
                continue
            if field.get("inclusion") not in matchable_inclusions:
                continue

            yield Field(
                stream_name,
                breadcrumb,
                make_path(stream_name, breadcrumb),
            )


def yield_patterns(strings):
    for raw_string in strings:
        string = raw_string.strip()

        if string.startswith("#"):
            continue

        negation = string.startswith("!")

        if negation:
            compiled = WildmatchPattern(string[1:])
        else:
            compiled = WildmatchPattern(string)

        yield FieldPattern(string, negation, compiled)


def match_path(patterns, path):
    matching = None
    positive = False

    for pattern in patterns:
        if pattern.compiled.match(path) and pattern.negation == positive:
            matching = pattern
            positive = not positive

    return (matching, positive)


def match_catalog(patterns, catalog):
    matched = []
    unmatched = []
    unused = set(patterns)

    for field in yield_available_fields(catalog):
        (pattern, positive) = match_path(patterns, field.path)

        if positive:
            matched.append(field)
        else:
            unmatched.append(field)

        unused.discard(pattern)

    return (matched, unmatched, unused)


def produce_matched(catalog, out_file, matched, unmatched):
    out_file.writelines([m.path + "\n" for m in matched])


def produce_unmatched(catalog, out_file, matched, unmatched):
    out_file.writelines([m.path + "\n" for m in unmatched])


def produce_catalog(catalog, out_file, matched, unmatched):
    matches_by_stream = {s["stream"]: [] for s in catalog["streams"]}

    for field in matched:
        matches_by_stream[field.stream_name].append(field)

    for stream in catalog["streams"]:
        stream_map = metadata.to_map(stream["metadata"])
        stream_matches = matches_by_stream[stream["stream"]]

        for field in stream_matches:
            stream_map = metadata.write(stream_map, field.breadcrumb, "selected", True)

        if stream_map.get((), {}).get("inclusion") == "available":
            stream_map = metadata.write(stream_map, (), "selected", len(stream_matches) > 0)

        stream["metadata"] = metadata.to_list(stream_map)

    json.dump(catalog, out_file, indent=2)


def main(
        catalog_file,
        out_file,
        producer,
        patterns_file=None,
        ignore_unused_patterns=False,
    ):
    catalog = json.load(catalog_file)
    patterns = list(
        yield_patterns(
            ["**"] if patterns_file is None else patterns_file,
        )
    )
    (matched, unmatched, unused) = match_catalog(patterns, catalog)

    if len(unused) > 0 and not ignore_unused_patterns:
        raise UnusedPatternsError(
            "some pattern(s) matched no fields",
            sorted(p.string for p in unused),
        )

    return producer(catalog, out_file, matched, unmatched)


def console_main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "catalog_file",
        type=argparse.FileType("rt"),
        help="read this Singer catalog JSON file"
    )
    parser.add_argument(
        "-p",
        "--patterns",
        dest="patterns_file",
        metavar="PATH",
        type=argparse.FileType("rt"),
        help="select fields matching a git-style patterns file"
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="out_file",
        metavar="PATH",
        type=argparse.FileType("wt"),
        default=sys.stdout,
        help="write output to path instead of stdout"
    )
    parser.add_argument(
        "-m",
        "--matched",
        dest="producer",
        action="store_const",
        const=produce_matched,
        help="instead of catalog, produce list of matched fields"
    )
    parser.add_argument(
        "-u",
        "--unmatched",
        dest="producer",
        action="store_const",
        const=produce_unmatched,
        help="instead of catalog, produce list of unmatched fields"
    )
    parser.add_argument(
        "--ignore-unused-patterns",
        action="store_true",
        help="suppress requirement that every pattern matches some field(s)"
    )
    parser.set_defaults(producer=produce_catalog)

    args = parser.parse_args()

    main(**vars(args))
