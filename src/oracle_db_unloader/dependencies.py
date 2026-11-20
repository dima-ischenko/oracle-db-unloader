from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Set, Tuple

from sqlalchemy import text
from sqlalchemy.engine import Engine

from .dml import format_table
from .inventory import (
    TYPE_FOLDERS,
    TYPE_SUFFIX,
    DbObject,
    fetch_inventory,
)
from .logger import get_logger
from .resources import load_sql

logger = get_logger(__name__)

DEP_COLUMNS = (
    'xref_path',
    'owner',
    'name',
    'type',
    'ref_type',
    'full_ref_object_name',
    'priority',
    'lvl',
)


@dataclass(frozen=True)
class Node:
    owner: str
    name: str
    type: str

    @property
    def label(self) -> str:
        return f'{self.owner.lower()}.{self.name.lower()}({self.type.lower()})'

    @property
    def full_name(self) -> str:
        return f'{self.owner.lower()}.{self.name.lower()}'


@dataclass(frozen=True)
class DepRow:
    xref_path: str
    owner: str
    name: str
    type: str
    ref_type: str
    full_ref_object_name: str
    priority: int
    lvl: int

    def as_tuple(self) -> Tuple[str, str, str, str, str, str, int, int]:
        return (
            self.xref_path,
            self.owner,
            self.name,
            self.type,
            self.ref_type,
            self.full_ref_object_name,
            self.priority,
            self.lvl,
        )


@dataclass(frozen=True)
class DependencyGraph:
    dependents: Dict[Node, Tuple[Node, ...]]
    references: Dict[Node, Tuple[Node, ...]]


def node_from_object(obj: DbObject) -> Node:
    return Node(obj.owner, obj.name, obj.object_type)


def build_graph(edges: Iterable[Tuple[Node, Node]]) -> DependencyGraph:
    dependents: Dict[Node, List[Node]] = defaultdict(list)
    references: Dict[Node, List[Node]] = defaultdict(list)
    seen: Set[Tuple[Node, Node]] = set()
    for depender, referenced in edges:
        pair = (depender, referenced)
        if pair in seen:
            continue
        seen.add(pair)
        references[depender].append(referenced)
        dependents[referenced].append(depender)
    return DependencyGraph(
        dependents={key: tuple(value) for key, value in dependents.items()},
        references={key: tuple(value) for key, value in references.items()},
    )


def fetch_dependency_edges(engine: Engine) -> List[Tuple[Node, Node]]:
    sql = load_sql('dependency_edges.sql')
    edges: List[Tuple[Node, Node]] = []
    with engine.connect() as conn:
        for owner, name, typ, ref_owner, ref_name, ref_type in conn.execute(text(sql)):
            edges.append(
                (
                    Node(str(owner), str(name), str(typ)),
                    Node(str(ref_owner), str(ref_name), str(ref_type)),
                )
            )
    return edges


def dependency_rows(graph: DependencyGraph, root: Node) -> List[DepRow]:
    rows = _walk_upstream(graph, root)
    rows.extend(_walk_downstream(graph, root))
    rows.sort(
        key=lambda row: (row.priority, row.xref_path, row.owner, row.name, row.type)
    )
    return rows


def _neighbors(mapping: Dict[Node, Tuple[Node, ...]], node: Node) -> Tuple[Node, ...]:
    return mapping.get(node, ())


def _walk_upstream(graph: DependencyGraph, root: Node) -> List[DepRow]:
    rows: List[DepRow] = []
    for first in _neighbors(graph.dependents, root):
        stack: List[Tuple[Node, Tuple[Node, ...], int]] = [(first, (first,), 1)]
        while stack:
            current, path, depth = stack.pop()
            kids = tuple(
                kid
                for kid in _neighbors(graph.dependents, current)
                if kid not in path and kid != root
            )
            if kids:
                for kid in kids:
                    stack.append((kid, path + (kid,), depth + 1))
                continue
            rows.append(
                DepRow(
                    xref_path=' > '.join(
                        [node.label for node in reversed(path)] + [root.label]
                    ),
                    owner=current.owner,
                    name=current.name,
                    type=current.type,
                    ref_type='upstream',
                    full_ref_object_name=root.full_name,
                    priority=0,
                    lvl=depth,
                )
            )
    return rows


def _walk_downstream(graph: DependencyGraph, root: Node) -> List[DepRow]:
    rows: List[DepRow] = []
    for first in _neighbors(graph.references, root):
        stack: List[Tuple[Node, Tuple[Node, ...], int]] = [(first, (first,), 1)]
        while stack:
            current, path, depth = stack.pop()
            kids = tuple(
                kid
                for kid in _neighbors(graph.references, current)
                if kid not in path and kid != root
            )
            if kids:
                for kid in kids:
                    stack.append((kid, path + (kid,), depth + 1))
                continue
            rows.append(
                DepRow(
                    xref_path=' > '.join([root.label] + [node.label for node in path]),
                    owner=current.owner,
                    name=current.name,
                    type=current.type,
                    ref_type='downstream',
                    full_ref_object_name=current.full_name,
                    priority=1,
                    lvl=depth,
                )
            )
    return rows


def walk_deps_files(
    output_dir: Path,
    schema: str,
    object_types: Sequence[str],
) -> Set[str]:
    found: Set[str] = set()
    for object_type in object_types:
        found.update(_walk_type_deps_files(output_dir, schema, object_type))
    return found


def _walk_type_deps_files(output_dir: Path, schema: str, object_type: str) -> Set[str]:
    folder = TYPE_FOLDERS[object_type]
    directory = Path(output_dir) / schema.lower() / '_deps' / folder
    if not directory.is_dir():
        return set()
    suffix = TYPE_SUFFIX.get(object_type)
    sibling_suffixes = [
        TYPE_SUFFIX[other]
        for other, other_folder in TYPE_FOLDERS.items()
        if other_folder == folder and other in TYPE_SUFFIX and other != object_type
    ]
    found: Set[str] = set()
    for path in directory.glob('*.md'):
        name = path.name.lower()
        if suffix:
            if not name.endswith(f'{suffix}.md'):
                continue
        elif any(name.endswith(f'{item}.md') for item in sibling_suffixes):
            continue
        found.add(path.relative_to(output_dir).as_posix())
    return found


def write_schema_dependencies(
    output_dir: Path,
    schema: str,
    inventory: Sequence[DbObject],
    object_types: Sequence[str],
    graph: DependencyGraph,
) -> int:
    selected = set(object_types)
    known: Set[str] = set()
    written = 0
    for obj in inventory:
        if obj.object_type not in selected:
            continue
        rows = dependency_rows(graph, node_from_object(obj))
        if not rows:
            continue
        relpath = obj.deps_relpath
        known.add(relpath)
        target = Path(output_dir) / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            format_table(DEP_COLUMNS, [row.as_tuple() for row in rows]),
            encoding='utf-8',
        )
        written += 1
        logger.info(
            'dependencies %s schema=%s type=%s rows=%d',
            target.as_posix(),
            schema,
            obj.object_type,
            len(rows),
        )

    stale = walk_deps_files(output_dir, schema, object_types) - known
    deleted = 0
    for relpath in sorted(stale):
        path = Path(output_dir) / relpath
        if path.is_file():
            path.unlink()
            deleted += 1
            logger.info('deleted %s schema=%s', path.as_posix(), schema)
    logger.info(
        'dependencies schema %s: write=%d delete=%d',
        schema,
        written,
        deleted,
    )
    return written


def dump_dependencies(
    engine: Engine,
    output_dir: Path,
    schemas: Sequence[str],
    object_types: Sequence[str],
) -> int:
    schema_list = [schema.strip().upper() for schema in schemas if schema.strip()]
    if not schema_list:
        return 0
    edges = fetch_dependency_edges(engine)
    logger.info(
        'dependencies: loaded %d edge(s) for %d schema(s)', len(edges), len(schema_list)
    )
    graph = build_graph(edges)
    dumped = 0
    for schema in schema_list:
        inventory = fetch_inventory(engine, schema)
        dumped += write_schema_dependencies(
            output_dir,
            schema,
            inventory,
            object_types,
            graph,
        )
    logger.info('dependencies: wrote %d file(s)', dumped)
    return dumped
