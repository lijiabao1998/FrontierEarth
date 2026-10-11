#!/usr/bin/env python3
"""Dependency-free registry and per-round gate. It checks records, not scientific truth."""
from __future__ import annotations
import argparse
from collections import defaultdict
import datetime as dt
import difflib
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlparse

# Version of the research contract implemented by this commit; see PROTOCOL_VERSIONS.md.
PROTOCOL_VERSION = '2.0.0'
BRANCH_TOPIC_RE = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*')
STATUSES = {'OPEN', 'PARTIAL', 'CLAIMED_RESOLVED', 'COMPLETED_EXTERNAL', 'COMPLETED_INTERNAL', 'PAUSED', 'RETRACTED'}
TERMINAL = {'COMPLETED_EXTERNAL', 'COMPLETED_INTERNAL'}
VERDICTS = {'NO_RESOLUTION_FOUND', 'PARTIAL_PROGRESS', 'CLAIMED_RESOLVED', 'RESOLVED_EXTERNAL', 'BLOCKED'}
CATEGORIES = {'general', 'discipline', 'solution', 'criticism'}
RESEARCH_VERDICTS = frozenset({'NO_RESOLUTION_FOUND', 'PARTIAL_PROGRESS'})
# Once a round has left DRAFT and been merged, these fields are its identity and its search; later changes may only
# move its state or record results (GATE_CONTRACT.md §2.2).
ROUND_FROZEN_FIELDS = ('round_id', 'problem_id', 'agent', 'branch', 'base_sha', 'started_at', 'admitted_at',
                       'acceptance', 'budget', 'preflight')
# A merged round in one of these states is over: its state no longer moves and it authorizes nothing new.
CLOSED_ROUND_STATES = frozenset({'FINISHED', 'PAUSED', 'CLOSED_EXTERNAL'})
UTC = dt.timezone.utc
PROBLEM_ID_RE = re.compile(r'(?:MATH|PHYS|BIO|CHEM|CS|STAT|MAT|ASTRO|EARTH|NEURO|ECON|ENG|MED|SOC|META)-\d{3}')

# GATE_CONTRACT.md §1: governance pin declarations. Only these positions are read; other SHAs are ignored.
GOVERNANCE_REPO = 'lijiabao1998/FrontierLab-Governance'
SHA_RE = re.compile(r'[0-9a-f]{40}')
WORKFLOW_KEY_RE = re.compile(r'''\s*(?:-\s+)?(["']?)(uses|governance_ref)\1\s*:\s*(.*)''')
WORKFLOW_USES_VALUE_RE = re.compile(r'([\w.-]+/FrontierLab-Governance)/\.github/workflows/[\w.-]+@(\S+)')
DOC_URL_RE = re.compile(r'https://(?:github\.com/lijiabao1998/FrontierLab-Governance/(?:tree|blob|commit|commits|raw)/'
                        r'|raw\.githubusercontent\.com/lijiabao1998/FrontierLab-Governance/)([^/\s)\]>#?"\'`]+)', re.I)
DOC_MARKER_RE = re.compile(r'<!--\s*governance-pin:\s*(\S+?)\s*-->', re.I)
DOC_PROSE_RE = re.compile(r'(?:治理|governance)(?:[ \t]*(?:commit|pin|ref|版本))?[ \t:：`]*([0-9a-f]{7,40})(?![0-9a-z])', re.I)
# YAML block scalar openers (`run: |`, `key: !!str >-`, `- |`); their body is data, never a pin declaration.
BLOCK_PROPS = r'(?:[!&]\S*\s+)*'
BLOCK_KEYED_RE = re.compile(rf'.*?:\s*{BLOCK_PROPS}[|>][-+1-9]*')
BLOCK_BARE_RE = re.compile(rf'{BLOCK_PROPS}[|>][-+1-9]*')

# GATE_CONTRACT.md §2: protected problem specification.
IMMUTABLE_FIELDS = frozenset({'id', 'domain'})
STATUS_FIELDS = frozenset({'status', 'resolution'})
KNOWLEDGE_FIELDS = frozenset({'known_result', 'open_gap'})
PROVENANCE_FIELDS = frozenset({'sources', 'screening_queries', 'screening_note'})
ROUND_FIELDS = KNOWLEDGE_FIELDS | PROVENANCE_FIELDS | {'first_task'}
NON_SPEC_FIELDS = IMMUTABLE_FIELDS | STATUS_FIELDS | ROUND_FIELDS | {'checked_on', 'priority'}
EDITORIAL_FIELDS = frozenset({'title', 'statement', 'evaluator', 'completion_criterion', 'validation_limits',
                              'known_result', 'open_gap', 'first_task', 'screening_note'})
HYGIENE_FIELDS = PROVENANCE_FIELDS | {'priority'}
DECISION_KINDS = {'spec-change', 'editorial', 'hygiene', 'status-change', 'new-problem'}
SPEC_IMPACTS = {'narrows', 'broadens', 'rescopes', 'clarifies'}
DECISION_STATUS_TARGETS = {'OPEN', 'PARTIAL', 'PAUSED', 'RETRACTED', 'COMPLETED_INTERNAL'}
EDITORIAL_MAX_CHARS = 12

# GATE_CONTRACT.md §3: research path ownership.
INFRA_FILES = frozenset({'README.md', 'AGENTS.md', 'CLAUDE.md', 'STATUS.md', 'VALIDATION.md', 'LICENSE', 'LICENSE.md',
                         'CONTRIBUTING.md', 'CITATION.cff', '.gitignore', '.gitattributes', 'lab.json',
                         'GOVERNANCE.lock.json', 'runs/README.md', 'decisions/README.md'})
INFRA_PREFIXES = ('.github/',)
DOMAIN_INFRA = {'math': frozenset({'lakefile.toml', 'lean-toolchain', 'lake-manifest.json', 'FrontierMath.lean',
                                   'FrontierMath/Smoke.lean', 'claims.json', 'tools/audit_lean.py'})}
PATH_RULES = (
    ('problem', re.compile(rf'problems/({PROBLEM_ID_RE.pattern})/problem\.json')),
    ('artifact', re.compile(rf'problems/({PROBLEM_ID_RE.pattern})/(?:experiments|proofs|results)/.+')),
    ('round', re.compile(r'runs/([^/]+)/round\.json')),
    ('attachment', re.compile(r'runs/([^/]+)/.+')),
    ('decision', re.compile(r'decisions/([^/]+)/decision\.json')),
)
# GATE_CONTRACT.md §3.4: extra research roots a repo declares in lab.json (e.g. a Lake-importable Lean namespace).
ARTIFACT_KINDS = ('experiments', 'proofs', 'results')
RESERVED_ROOT_PREFIXES = ('problems/', 'runs/', 'decisions/', '.github/')
ROOT_PATH_RE = re.compile(r'(?:[A-Za-z0-9_][A-Za-z0-9_.-]*/)+')


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def load(path: Path) -> dict:
    with path.open(encoding='utf-8') as f:
        obj = json.load(f)
    require(isinstance(obj, dict), f'{path}: expected JSON object')
    return obj


def save(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def stamp(value: object, field: str = 'timestamp') -> dt.datetime:
    require(isinstance(value, str) and bool(value.strip()), f'{field}: missing ISO 8601 timestamp')
    try:
        t = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as e:
        raise ValueError(f'{field}: not an ISO 8601 timestamp ({value!r})') from e
    require(t.tzinfo is not None, f'{field}: timestamp must include UTC offset')
    return t.astimezone(UTC)


def branch_ok(branch: str, agent: str, problem_id: str) -> bool:
    """<agent>/<problem-id>-<topic>[-<round>]; the problem id is case-insensitive, the topic is a lowercase slug."""
    head, cut = f'{agent}/', len(agent) + 1 + len(problem_id) + 1
    return (branch.startswith(head) and branch[len(head):cut].upper() == problem_id + '-'
            and BRANCH_TOPIC_RE.fullmatch(branch[cut:]) is not None)


def nonempty(obj: dict, keys: tuple[str, ...], context: str) -> None:
    for k in keys:
        require(isinstance(obj.get(k), str) and bool(obj[k].strip()), f'{context}: missing {k}')


def source(ref: dict) -> None:
    nonempty(ref, ('title', 'url', 'kind', 'supports'), 'source')
    p = urlparse(ref['url'])
    require(p.scheme == 'https' and bool(p.netloc), 'source needs HTTPS URL')
    require(p.netloc not in {'example.com', 'example.org'}, 'placeholder source')


def validate_resolution(obj: dict, problem_id: str) -> None:
    nonempty(obj, ('problem_id', 'scope_statement', 'basis', 'confirmed_by', 'independent_check'), 'resolution')
    require(obj['problem_id'] == problem_id, 'resolution belongs to another problem')
    require(obj.get('scope_match') is True, 'a subproblem does not close its parent')
    require(obj.get('independently_verified') is True, 'resolution needs independent verification')
    refs = obj.get('sources', [])
    require(len({r.get('url') for r in refs}) >= 2, 'resolution needs primary source plus corroboration/certificate')
    for r in refs:
        source(r)
    require(any(r['kind'] == 'primary' for r in refs), 'resolution missing primary source')
    stamp(obj['confirmed_at'])


def validate_preflight(r: dict, fresh: bool = False) -> str:
    nonempty(r, ('round_id', 'problem_id', 'agent', 'branch', 'base_sha', 'acceptance', 'not_done'), 'round')
    if fresh:
        # Admission of a new round follows the full branch contract. Records admitted by older tools keep the
        # original rule below, so upgrading the governance pin does not invalidate existing history.
        require(re.fullmatch(r'[a-z0-9-]+', r['agent']) is not None, 'round: agent must be a lowercase slug')
        require(branch_ok(r['branch'], r['agent'], r['problem_id']),
                f"work on an agent branch <agent>/<problem-id>-<topic>[-<round>], not {r['branch']!r}")
    else:
        require(re.fullmatch(r'[a-z0-9-]+/.+', r['branch']) is not None, 'work on an agent branch, not main')
    require(re.fullmatch(r'[0-9a-f]{40}', r['base_sha']) is not None, 'record exact base commit SHA')
    started = stamp(r.get('started_at'), 'round.started_at')
    p = r.get('preflight')
    require(isinstance(p, dict), 'round: missing preflight object')
    checked = stamp(p.get('checked_at'), 'preflight.checked_at')
    require(started <= checked <= started + dt.timedelta(hours=24), 'each round needs its own start-time search')
    if fresh:
        now = dt.datetime.now(UTC)
        require(now - dt.timedelta(hours=24) <= checked <= now + dt.timedelta(minutes=5), 'stale or future search; repeat preflight')
    for name in ('sources_read', 'scope_compared', 'retractions_checked', 'licenses_checked', 'safety_checked', 'baseline_identified', 'acceptance_frozen'):
        require(p.get(name) is True, f'preflight incomplete: {name}')
    nonempty(p, ('limitations', 'scope_comparison', 'baseline'), 'preflight')
    queries = p.get('queries', [])
    require(CATEGORIES <= {q.get('category') for q in queries}, 'need general / discipline / solution / criticism searches')
    require(len({q.get('query') for q in queries}) >= 4, 'need four distinct actual queries')
    for q in queries:
        nonempty(q, ('query', 'engine', 'category', 'outcome'), 'query')
    refs = p.get('sources', [])
    require(len({s.get('url') for s in refs}) >= 2, 'read at least two distinct sources')
    for ref in refs:
        source(ref)
    require(any(s['kind'] == 'primary' for s in refs), 'at least one source must be primary')
    verdict = p.get('verdict')
    require(verdict in VERDICTS, 'unknown novelty verdict')
    budget = r.get('budget', {})
    require(0 < budget.get('wall_minutes', 0) <= 120, 'bounded run: 1–120 minutes')
    require(budget.get('usd', -1) >= 0, 'explicit USD budget required')
    require(0 < budget.get('max_trials', 0), 'explicit trial limit required')
    if verdict == 'RESOLVED_EXTERNAL':
        validate_resolution(p.get('resolution', {}), r['problem_id'])
    return verdict


def problem_path(root: Path, problem_id: str) -> Path:
    require(PROBLEM_ID_RE.fullmatch(problem_id) is not None, 'invalid problem id')
    return root / 'problems' / problem_id / 'problem.json'


def validate_problem(p: dict) -> None:
    nonempty(p, ('id', 'title', 'domain', 'statement', 'known_result', 'open_gap', 'first_task', 'evaluator', 'validation_limits', 'completion_criterion', 'screening_note'), 'problem')
    require(p['status'] in STATUSES, 'invalid problem status')
    require(p['priority'] in {'A', 'B', 'C'}, 'priority must be A/B/C')
    date = dt.date.fromisoformat(p['checked_on'])
    # checked_on is date-only and may be written in a local timezone ahead of UTC (for example UTC+08).
    require(date <= dt.datetime.now(UTC).date() + dt.timedelta(days=1), 'future literature check')
    require(len(p.get('screening_queries', [])) >= 1, 'record bootstrap search query')
    require(len(p.get('sources', [])) >= 1, 'problem needs a source')
    for ref in p['sources']:
        source(ref)
    if p['status'] in TERMINAL:
        validate_resolution(p.get('resolution', {}), p['id'])


def decision_may_change(kind: str, field: str) -> bool:
    if field in IMMUTABLE_FIELDS or field == 'checked_on':
        return False
    if field in STATUS_FIELDS:
        return kind == 'status-change'
    return {'spec-change': True, 'editorial': field in EDITORIAL_FIELDS, 'hygiene': field in HYGIENE_FIELDS}.get(kind, False)


def validate_decision(d: dict, decision_id: str | None = None) -> None:
    nonempty(d, ('decision_id', 'problem_id', 'kind', 'author', 'rationale', 'base_sha', 'created_at'), 'decision')
    require(decision_id is None or d['decision_id'] == decision_id, 'decision_id must match its directory name')
    require(PROBLEM_ID_RE.fullmatch(d['problem_id']) is not None, 'decision: invalid problem id')
    require(d['kind'] in DECISION_KINDS, f"decision: unknown kind {d['kind']!r}")
    require(SHA_RE.fullmatch(d['base_sha']) is not None, 'decision: record exact base commit SHA')
    stamp(d['created_at'])
    for ref in d.get('sources', []):
        source(ref)
    if d['kind'] == 'new-problem':
        return
    fields = d.get('fields')
    require(isinstance(fields, list) and bool(fields) and all(isinstance(x, str) for x in fields)
            and len(set(fields)) == len(fields), 'decision: list the exact changed fields')
    denied = sorted(x for x in fields if not decision_may_change(d['kind'], x))
    require(not denied, f"decision kind {d['kind']} cannot authorize {denied} (GATE_CONTRACT.md §2.1)")
    if d['kind'] == 'spec-change':
        require(d.get('impact') in SPEC_IMPACTS, f'spec-change must declare impact: {sorted(SPEC_IMPACTS)}')
    if d['kind'] == 'status-change':
        # A resolution-only correction keeps the status, so a CLAIMED_RESOLVED card can also fix its resolution.
        correction = d.get('to') == d.get('from') == 'CLAIMED_RESOLVED' and fields == ['resolution']
        require(d.get('from') in STATUSES and (d.get('to') in DECISION_STATUS_TARGETS or correction),
                f'status-change needs from and to; decisions can target {sorted(DECISION_STATUS_TARGETS)}')
        if d['to'] == 'COMPLETED_INTERNAL':
            rounds = d.get('rounds')
            require(isinstance(rounds, list) and bool(rounds) and all(isinstance(x, str) and x for x in rounds),
                    'COMPLETED_INTERNAL needs the finished round ids')
            nonempty(d, ('verifier',), 'decision')


def strip_yaml_comment(line: str) -> str:
    quote = None
    for i, ch in enumerate(line):
        if quote:
            quote = None if ch == quote else quote
        elif ch in '"\'':
            quote = ch
        elif ch == '#' and (i == 0 or line[i - 1].isspace()):
            return line[:i].rstrip()
    return line.rstrip()


def block_scalar_indent(line: str) -> int | None:
    """If `line` opens a block scalar, the column its body must be indented beyond; else None."""
    lead, dashes, rest = re.fullmatch(r'(\s*)((?:-\s+)*)(.*)', line).groups()
    if BLOCK_BARE_RE.fullmatch(rest):  # `- |`: the body belongs to the sequence entry (column of the last dash)
        return len(lead) + dashes.rstrip().rfind('-') if dashes else len(lead)
    if BLOCK_KEYED_RE.fullmatch(rest):  # `- run: |`: the body belongs to the key (column after the dashes)
        return len(lead) + len(dashes)
    return None


def workflow_pins(text: str) -> tuple[list[tuple[str, str]], list[str], list[int]]:
    """Operative `uses:` / `governance_ref:` declarations (comments ignored, quoted keys and values accepted).
    Any other non-comment line that mentions the governance workflow or governance_ref is returned as unknown."""
    uses, refs, unknown = [], [], []
    block = None  # indentation of the key that opened a block scalar
    for n, raw in enumerate(text.splitlines(), 1):
        if block is not None:
            if not raw.strip() or len(raw) - len(raw.lstrip()) > block:
                if 'FrontierLab-Governance' in raw or 'governance_ref' in raw:
                    unknown.append(n)
                continue
            block = None
        line = strip_yaml_comment(raw)
        block = block_scalar_indent(line)
        m = WORKFLOW_KEY_RE.fullmatch(line)
        value = m.group(3).strip().strip('"\'') if m else ''
        if m and m.group(2) == 'governance_ref':
            refs.append(value)
        elif m and WORKFLOW_USES_VALUE_RE.fullmatch(value):
            uses.append(WORKFLOW_USES_VALUE_RE.fullmatch(value).groups())
        elif 'FrontierLab-Governance' in line or 'governance_ref' in line:
            unknown.append(n)
    return uses, refs, unknown


def doc_pins(text: str) -> list[tuple[str, str]]:
    return ([('url', x.lower()) for x in DOC_URL_RE.findall(text)] + [('marker', x.lower()) for x in DOC_MARKER_RE.findall(text)]
            + [('prose', x.lower()) for x in DOC_PROSE_RE.findall(text)])


def check_pins(root: Path) -> str:
    """GATE_CONTRACT.md §1: lock, workflow, README and AGENTS must name the same governance commit."""
    lock = load(root / 'GOVERNANCE.lock.json')
    require(lock.get('repository') == GOVERNANCE_REPO, f'GOVERNANCE.lock.json: repository must be {GOVERNANCE_REPO}')
    commit = lock.get('commit')
    require(isinstance(commit, str) and SHA_RE.fullmatch(commit) is not None, 'GOVERNANCE.lock.json: commit must be a full 40-hex SHA')
    errors = []
    wf = root / '.github' / 'workflows' / 'research.yml'
    uses, refs, unknown = workflow_pins(wf.read_text(encoding='utf-8')) if wf.is_file() else ([], [], [])
    for n in unknown:
        errors.append(f'{wf.relative_to(root)}:{n}: unrecognized governance reference; use a plain `uses:` / `governance_ref:` line')
    if not uses:
        errors.append(f'{wf.relative_to(root)}: no uses: {GOVERNANCE_REPO}/.github/workflows/…@<commit>')
    if not refs:
        errors.append(f'{wf.relative_to(root)}: no governance_ref')
    for repo, ref in uses:
        if repo != GOVERNANCE_REPO:
            errors.append(f'{wf.relative_to(root)}: uses {repo}, lock says {GOVERNANCE_REPO}')
        if ref != commit:
            errors.append(f'{wf.relative_to(root)}: uses @{ref}, lock says {commit}')
    for ref in refs:
        if ref != commit:
            errors.append(f'{wf.relative_to(root)}: governance_ref {ref}, lock says {commit}')
    for name in ('README.md', 'AGENTS.md'):
        path = root / name
        found = doc_pins(path.read_text(encoding='utf-8')) if path.is_file() else []
        if not found:
            errors.append(f'{name}: no governance pin declaration (GATE_CONTRACT.md §1)')
        for kind, ref in found:
            ok = commit.startswith(ref) if kind == 'prose' else ref == commit
            if not ok:
                errors.append(f'{name}: governance {kind} pin {ref}, lock says {commit}')
    require(not errors, 'governance pin mismatch:\n  ' + '\n  '.join(errors))
    return commit


def artifact_roots(lab: dict, known_ids: set | None = None) -> tuple[tuple[str, str, str], ...]:
    """GATE_CONTRACT.md §3.4: validated (path, problem_id, kind) research roots declared in lab.json."""
    raw = lab.get('artifact_roots', [])
    require(isinstance(raw, list), 'lab.json artifact_roots must be a list')
    infra = INFRA_FILES | DOMAIN_INFRA.get(lab.get('domain'), frozenset())
    roots = []
    for i, entry in enumerate(raw):
        ctx = f'lab.json artifact_roots[{i}]'
        require(isinstance(entry, dict), f'{ctx}: expected an object')
        path, pid, kind = entry.get('path'), entry.get('problem_id'), entry.get('kind')
        require(isinstance(path, str) and ROOT_PATH_RE.fullmatch(path) is not None,
                f'{ctx}: path must be a relative directory ending in "/" (no "..", no hidden or absolute segments)')
        require(not path.startswith(RESERVED_ROOT_PREFIXES), f'{ctx}: {path} overlaps a reserved directory')
        require(not any(f.startswith(path) for f in infra), f'{ctx}: {path} would contain infrastructure files')
        require(isinstance(pid, str) and PROBLEM_ID_RE.fullmatch(pid) is not None, f'{ctx}: invalid problem_id')
        require(known_ids is None or pid in known_ids, f'{ctx}: {pid} is not a problem in this repository')
        require(kind in ARTIFACT_KINDS, f'{ctx}: kind must be one of {list(ARTIFACT_KINDS)}')
        for other, _, _ in roots:
            require(not (path.startswith(other) or other.startswith(path)), f'{ctx}: {path} nests with {other}')
        roots.append((path, pid, kind))
    return tuple(roots)


def classify(path: str, domain: str, roots: tuple = ()) -> tuple[str, str | None]:
    """GATE_CONTRACT.md §3.1: every repository path has exactly one owner class."""
    if path in INFRA_FILES or path.startswith(INFRA_PREFIXES) or path in DOMAIN_INFRA.get(domain, ()):
        return 'infra', None
    for kind, pattern in PATH_RULES:
        m = pattern.fullmatch(path)
        if m:
            return kind, m.group(1)
    for root, pid, _ in roots:
        if path.startswith(root) and len(path) > len(root):
            return 'artifact', pid
    return 'unregistered', None


def tracked_files(root: Path) -> list[str]:
    try:
        top = git(root, 'rev-parse', '--show-toplevel')
    except (subprocess.CalledProcessError, OSError):
        top = None
    if top and Path(top).resolve() == root.resolve():
        return [x for x in git(root, 'ls-files', '-z').split('\0') if x]
    return sorted(p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and '.git' not in p.relative_to(root).parts)


def validate_repo(root: Path) -> None:
    lab = load(root / 'lab.json')
    for filename in ('README.md', 'AGENTS.md', 'STATUS.md'):
        require((root / filename).is_file(), f'missing {filename}')
    if lab['domain'] == 'governance':
        require(not (root / 'problems').exists() and not (root / 'GOVERNANCE.lock.json').exists(),
                'a research repository (problems/ or GOVERNANCE.lock.json present) cannot declare domain governance')
        require(lab.get('protocol_version') == PROTOCOL_VERSION, f'lab.json protocol_version must be {PROTOCOL_VERSION}')
        print('Governance documents present; run unit tests separately.')
        return
    declared = load(root / 'GOVERNANCE.lock.json').get('protocol_version')
    require(declared == PROTOCOL_VERSION, f'GOVERNANCE.lock.json declares protocol {declared}, but this governance checkout '
            f'implements {PROTOCOL_VERSION}; check out the locked governance commit (PROTOCOL_VERSIONS.md)')
    files = sorted((root / 'problems').glob('*/problem.json'))
    require(len(files) == lab['expected_problem_count'], 'problem count does not match lab.json')
    seen = set()
    for path in files:
        p = load(path)
        validate_problem(p)
        require(p['id'] not in seen and path.parent.name == p['id'], 'duplicate or mismatched problem id')
        require(p['domain'] == lab['domain'], 'cross-domain problem contamination')
        seen.add(p['id'])
    admitted = {}
    for path in sorted((root / 'runs').glob('*/round.json')):
        r = load(path)
        require(r['problem_id'] in seen, 'round points to absent problem')
        if r.get('state') != 'DRAFT':
            validate_preflight(r)
            admitted[path.parent.name] = r
    commit = check_pins(root)
    for path in sorted((root / 'decisions').glob('*/decision.json')):
        d = load(path)
        validate_decision(d, path.parent.name)
        require(d['problem_id'] in seen, f'{path.relative_to(root)}: decision points to absent problem')
    researched = {r['problem_id'] for r in admitted.values() if r['preflight']['verdict'] in RESEARCH_VERDICTS}
    roots = artifact_roots(lab, seen)
    errors = []
    for rel in tracked_files(root):
        kind, key = classify(rel, lab['domain'], roots)
        if kind == 'unregistered':
            errors.append(f'{rel}: unregistered path (GATE_CONTRACT.md §3.1)')
        elif kind == 'artifact' and key not in researched:
            errors.append(f'{rel}: research artifact without an admitted {key} round in runs/ '
                          f'(verdict {" or ".join(sorted(RESEARCH_VERDICTS))})')
        elif kind == 'attachment' and key not in admitted:
            errors.append(f'{rel}: runs/{key}/ has no admitted round.json')
    require(not errors, 'path contract:\n  ' + '\n  '.join(errors))
    print(f'PASS: {len(files)} problem records; governance pin {commit[:12]} consistent; paths registered. '
          'Metadata checks only, not proof of openness or discovery.')


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


def show_json(root: Path, rev: str, path: str) -> dict | None:
    run = subprocess.run(['git', '-C', str(root), 'show', f'{rev}:{path}'], capture_output=True, text=True, encoding='utf-8')
    if run.returncode:
        return None
    try:
        obj = json.loads(run.stdout)
    except json.JSONDecodeError as e:
        raise ValueError(f'{path}@{rev[:12]}: invalid JSON ({e})') from e
    require(isinstance(obj, dict), f'{path}: expected JSON object')
    return obj


def exists(root: Path, rev: str, path: str) -> bool:
    return subprocess.run(['git', '-C', str(root), 'cat-file', '-e', f'{rev}:{path}'], capture_output=True).returncode == 0


def edit_size(a: str, b: str) -> int:
    ops = difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes()
    return sum(max(i2 - i1, j2 - j1) for tag, i1, i2, j1, j2 in ops if tag != 'equal')


def dates_match(checked_on: object, checked_at: str) -> bool:
    try:
        day = dt.date.fromisoformat(checked_on)
    except (TypeError, ValueError):
        return False
    return abs((day - stamp(checked_at).date()).days) <= 1


def status_basis_errors(pid: str, old: dict, new: dict, rounds: list, decisions: list, root: Path, mb: str,
                        head: str) -> list[str]:
    """GATE_CONTRACT.md §2.3: a status or resolution change must match the completion semantics."""
    old_s, new_s = old.get('status'), new.get('status')
    verdicts = {r['preflight']['verdict'] for r in rounds}
    moves = [d for d in decisions if d['kind'] == 'status-change']
    # Every status-change record in the change must describe the transition that actually happens.
    stray = [f'{pid}: status-change decision says {d.get("from")} -> {d.get("to")}, but the card moves {old_s} -> {new_s}'
             for d in moves if (d.get('from'), d.get('to')) != (old_s, new_s)]
    same_resolution = old.get('resolution') == new.get('resolution')
    # Round verdicts may move a status, but never out of a completed status and never to rewrite a resolution alone.
    by_round = new_s != old_s and old_s not in TERMINAL
    if by_round and new_s == 'COMPLETED_EXTERNAL':
        if moves:
            return [f'{pid}: external completion comes from a RESOLVED_EXTERNAL round, not a status-change decision']
        if not any(r['preflight']['verdict'] == 'RESOLVED_EXTERNAL' and r.get('state') == 'CLOSED_EXTERNAL'
                   and r['preflight'].get('resolution') == new.get('resolution') for r in rounds):
            return [f'{pid}: COMPLETED_EXTERNAL needs a {pid} round in this change with verdict RESOLVED_EXTERNAL, '
                    'state CLOSED_EXTERNAL and the same resolution as the card']
        return []
    if by_round and new_s == 'CLAIMED_RESOLVED':
        if 'CLAIMED_RESOLVED' not in verdicts:
            return [f'{pid}: CLAIMED_RESOLVED needs a {pid} round with that verdict']
        return stray if same_resolution else [f'{pid}: a round verdict does not change resolution']
    if by_round and new_s == 'PARTIAL' and 'PARTIAL_PROGRESS' in verdicts and same_resolution:
        return stray
    match = [d for d in moves if d.get('from') == old_s and d.get('to') == new_s]
    if not match:
        return [f'{pid}: status {old_s} -> {new_s} needs a status-change decision with from={old_s} to={new_s}']
    if old_s != new_s and not any('status' in d['fields'] for d in match):
        return [f'{pid}: status {old_s} -> {new_s}: the status-change decision must list status']
    if old.get('resolution') != new.get('resolution') and not any('resolution' in d['fields'] for d in match):
        return [f'{pid}: resolution changed but the status-change decision does not list it']
    if new_s != 'COMPLETED_INTERNAL':
        return stray
    errors = list(stray)
    try:
        validate_problem(new)
    except (ValueError, KeyError, TypeError) as e:
        errors.append(f'{pid}: COMPLETED_INTERNAL card is incomplete: {e}')
    for d in match:
        agents = set()
        for rid in d['rounds']:
            r = show_json(root, head, f'runs/{rid}/round.json')
            if r is None or r.get('problem_id') != pid or r.get('state') != 'FINISHED':
                errors.append(f'{pid}: COMPLETED_INTERNAL cites runs/{rid}, which is not a FINISHED {pid} round')
                continue
            merged = show_json(root, mb, f'runs/{rid}/round.json')
            if not merged or merged.get('state') == 'DRAFT':
                errors.append(f'{pid}: COMPLETED_INTERNAL cites runs/{rid}, which was not merged as an admitted round '
                              'before this change; cite rounds reviewed earlier')
                continue
            verdict = (r.get('preflight') or {}).get('verdict')
            if verdict not in RESEARCH_VERDICTS:
                errors.append(f'{pid}: COMPLETED_INTERNAL cites runs/{rid}, whose verdict {verdict} is not a research verdict')
                continue
            try:
                validate_preflight(r)
            except (ValueError, KeyError, TypeError) as e:
                errors.append(f'runs/{rid}/round.json: {e}')
            agents.add(r.get('agent'))
        if d['verifier'] in agents:
            errors.append(f'{pid}: verifier {d["verifier"]} is also an author of the cited rounds')
        if d['verifier'] == d['author']:
            errors.append(f'{pid}: verifier {d["verifier"]} is the author of the decision')
    return errors


def problem_change_errors(pid: str, change: str, old: dict | None, new: dict | None, rounds: list, decisions: list,
                          has_research: bool, root: Path, mb: str, head: str, notes: list) -> list[str]:
    """GATE_CONTRACT.md §2: which record may change which problem field."""
    if change == 'D':
        return [f'{pid}: problem cards are not deleted; retire with PAUSED/RETRACTED and a status-change decision']
    if change == 'A':
        if not any(d['kind'] == 'new-problem' for d in decisions):
            return [f'{pid}: a new problem card needs a new-problem decision record']
        return [] if new.get('status') == 'OPEN' else [f'{pid}: a new problem card must start OPEN']
    changed = {k for k in set(old) | set(new) if old.get(k) != new.get(k)}
    errors = [f'{pid}: new-problem decision on an existing card' for d in decisions if d['kind'] == 'new-problem']
    if not changed:
        return errors
    errors += [f'{pid}: {k} is immutable' for k in sorted(changed & IMMUTABLE_FIELDS)]
    spec = changed - NON_SPEC_FIELDS
    status = changed & STATUS_FIELDS
    if spec and has_research:
        errors.append(f'{pid}: specification fields {sorted(spec)} changed together with {pid} research artifacts; split the PR')
    if spec and status:
        errors.append(f'{pid}: specification fields {sorted(spec)} and status changed in one change; split the PR')
    live = [r for r in rounds if r['preflight']['verdict'] != 'BLOCKED']
    covered = set(changed & ROUND_FIELDS) if live else set()
    if 'checked_on' in changed:
        if any(dates_match(new.get('checked_on'), r['preflight']['checked_at']) for r in live):
            covered.add('checked_on')
        else:
            errors.append(f'{pid}: checked_on moves only with a {pid} round whose preflight.checked_at is that date')
    for d in decisions:
        declared = set(d.get('fields', []))
        if declared - changed:
            errors.append(f'{pid}: decision {d["decision_id"]} lists unchanged fields {sorted(declared - changed)}')
        for field in sorted((declared & changed) - STATUS_FIELDS):
            if d['kind'] == 'editorial':
                a, b = old.get(field), new.get(field)
                if not (isinstance(a, str) and isinstance(b, str)):
                    errors.append(f'{pid}: editorial decision cannot change non-text field {field}')
                    continue
                size = edit_size(a, b)
                if size > EDITORIAL_MAX_CHARS:
                    errors.append(f'{pid}: editorial change to {field} is {size} chars (> {EDITORIAL_MAX_CHARS}); use spec-change')
                    continue
            covered.add(field)
    if status:
        basis = status_basis_errors(pid, old, new, rounds, decisions, root, mb, head)
        errors += basis
        if not basis:
            covered |= status
    uncovered = changed - covered - IMMUTABLE_FIELDS - STATUS_FIELDS - {'checked_on'}  # those report their own errors
    if uncovered:
        errors.append(f'{pid}: {sorted(uncovered)} changed without a matching round or decision (GATE_CONTRACT.md §2.1)')
    for field in sorted(spec):
        notes.append(f'REVIEW {pid}.{field}:\n    - {old.get(field)!r}\n    + {new.get(field)!r}')
    return errors


def terminal_status(root: Path, rev: str, pid: str) -> str | None:
    card = show_json(root, rev, f'problems/{pid}/problem.json') if PROBLEM_ID_RE.fullmatch(pid or '') else None
    return card.get('status') if card and card.get('status') in TERMINAL else None


def check_diff(root: Path, base: str, head: str) -> None:
    """GATE_CONTRACT.md §2 and §3.3 for one change (PR base...head)."""
    lab = show_json(root, head, 'lab.json')
    require(lab is not None, 'lab.json missing at head')
    mb = git(root, 'merge-base', base, head)
    base_lab = show_json(root, mb, 'lab.json')
    # The domain decides which contract applies, so a change may not switch it (for example to skip the gates).
    require(base_lab is None or base_lab.get('domain') == lab.get('domain'),
            f"lab.json: domain is immutable ({(base_lab or {}).get('domain')} -> {lab.get('domain')})")
    if lab.get('domain') == 'governance':
        # Checked on the head tree itself, so it also holds when the merge base predates lab.json.
        require(not exists(root, head, 'problems') and not exists(root, head, 'GOVERNANCE.lock.json'),
                'a research repository (problems/ or GOVERNANCE.lock.json present) cannot declare domain governance')
        print('SKIP: governance repository; research path and problem contracts do not apply (unit tests guard the gate).')
        return
    errors, notes = [], []
    # Paths are classified by the roots declared at the merge base, so a root must be merged before work lands in it.
    # A base declaration that this gate rejects classifies nothing (fail closed) but must not block the PR fixing it.
    try:
        roots = artifact_roots(base_lab or {})
    except ValueError as e:
        roots = ()
        notes.append(f'REVIEW lab.json artifact_roots at the merge base are invalid under this gate and classify nothing: {e}')
    head_roots = artifact_roots(lab)
    raw = [x for x in git(root, 'diff', '--name-status', '--no-renames', '-z', f'{base}...{head}').split('\0') if x]
    changes = list(zip(raw[0::2], raw[1::2]))
    rounds, closed, decisions, problems = {}, {}, defaultdict(list), []
    artifacts, attachments = defaultdict(list), defaultdict(list)
    for change, path in changes:
        kind, key = classify(path, lab['domain'], roots)
        if kind == 'infra' or (kind == 'unregistered' and change == 'D'):
            continue
        if kind == 'unregistered':
            errors.append(f'{path}: unregistered path; research files belong in problems/<ID>/{{experiments,proofs,results}}/, '
                          'runs/<round_id>/, or a root declared in lab.json artifact_roots by an earlier PR (GATE_CONTRACT.md §3)')
        elif kind in ('round', 'attachment') and change == 'D':
            errors.append(f'{path}: round records are append-only; do not delete')
        elif kind == 'attachment':
            attachments[key].append(path)
        elif kind == 'artifact':
            artifacts[key].append(path)
        elif kind == 'problem':
            problems.append((change, key, path))
        elif kind == 'decision':
            if change != 'A':
                errors.append(f'{path}: decision records are immutable once merged')
                continue
            try:
                d = show_json(root, head, path)
                validate_decision(d, key)
                decisions[d['problem_id']].append(d)
            except (ValueError, KeyError, TypeError) as e:
                errors.append(f'{path}: {e}')
        elif kind == 'round':
            try:
                r = show_json(root, head, path)
                require(r.get('round_id') == key, 'round_id must match its directory name')
                old = show_json(root, mb, path) if change == 'M' else None
                merged = old is not None and old.get('state') != 'DRAFT'  # admitted and merged before this change
                if merged:
                    frozen = [k for k in ROUND_FROZEN_FIELDS if old.get(k) != r.get(k)]
                    if old.get('state') in CLOSED_ROUND_STATES and r.get('state') != old.get('state'):
                        frozen.append('state')
                    require(not frozen, f'an admitted round keeps its identity and search; changed {sorted(frozen)}')
                if r.get('state') == 'DRAFT':
                    continue
                validate_preflight(r)
                base_status = terminal_status(root, mb, r['problem_id'])
                require(merged or base_status is None, f"{r['problem_id']} is {base_status}; completed problems take no new "
                        'rounds (admit refuses them): open a replication problem or retract first')
                if base_status or (merged and old.get('state') in CLOSED_ROUND_STATES):
                    closed[key] = base_status or f"closed ({old['state']})"  # kept as a record; authorizes nothing new
                    continue
                rounds[key] = r
            except (ValueError, KeyError, TypeError, AttributeError) as e:
                errors.append(f'{path}: {e}')
    by_pid = defaultdict(list)
    for r in rounds.values():
        by_pid[r['problem_id']].append(r)
    research = set(artifacts)
    for rid, paths in attachments.items():
        if rid in rounds:
            research.add(rounds[rid]['problem_id'])
        elif rid in closed:
            errors.append(f'runs/{rid}/: {len(paths)} new file(s) on a round whose problem or state is {closed[rid]}; '
                          'new work needs a new round')
        else:
            errors.append(f'runs/{rid}/: {len(paths)} attachment(s) need runs/{rid}/round.json changed in this PR and admitted (not DRAFT)')
    for pid, paths in sorted(artifacts.items()):
        base_status = terminal_status(root, mb, pid)
        if show_json(root, head, f'problems/{pid}/problem.json') is None:
            errors.append(f'{paths[0]}: research artifact for absent problem {pid}')
        elif base_status:
            errors.append(f'{paths[0]}: {pid} is {base_status}; completed problems take no new research')
        elif not any(r['preflight']['verdict'] in RESEARCH_VERDICTS for r in by_pid[pid]):
            errors.append(f'{pid}: research changes lack a completed per-round search record ({len(paths)} file(s), e.g. {paths[0]})')
    touched = set()
    for change, pid, path in problems:
        touched.add(pid)
        try:
            errors += problem_change_errors(pid, change, show_json(root, mb, path), show_json(root, head, path),
                                            by_pid[pid], decisions[pid], pid in research, root, mb, head, notes)
        except (ValueError, KeyError, TypeError) as e:
            errors.append(f'{path}: {e}')
    for pid in sorted(set(decisions) - touched):
        errors.append(f'{pid}: decision record(s) without a matching problem card change')
    if head_roots != roots:
        notes.append(f'REVIEW lab.json artifact_roots:\n    - {list(roots)}\n    + {list(head_roots)}')
    for note in notes:
        print(note)
    require(not errors, 'check-diff:\n  ' + '\n  '.join(errors))
    print(f'PASS: {len(changes)} changed paths; {len(artifacts)} research scope(s), {len(problems)} problem card(s), '
          f'{sum(map(len, decisions.values()))} decision(s), {len(rounds)} admitted round(s) checked.')


def start(root: Path, pid: str, agent: str, topic: str = 'round') -> None:
    p = load(problem_path(root, pid))
    require(p['status'] not in TERMINAL, 'already completed: select another problem or open a replication task')
    require(re.fullmatch(r'[a-z0-9-]+', agent) is not None, 'use an agent slug')
    require(BRANCH_TOPIC_RE.fullmatch(topic) is not None and len(topic) <= 40, 'topic must be a lowercase slug, e.g. baseline')
    now = dt.datetime.now(UTC)
    rid = now.strftime('%Y%m%dT%H%M%S%fZ') + '-' + agent + '-' + pid
    branch = f"{agent}/{pid}-{topic}-{now.strftime('%Y%m%dt%H%M%S%fz')}"
    record = {'round_id': rid, 'problem_id': pid, 'agent': agent, 'branch': branch, 'base_sha': git(root, 'rev-parse', 'HEAD'), 'started_at': now.isoformat(), 'state': 'DRAFT', 'acceptance': '', 'not_done': '尚未檢索、尚未實驗；本記錄不是研究成果。', 'budget': {'wall_minutes': 30, 'usd': 0, 'max_trials': 100}, 'preflight': {'checked_at': None, 'verdict': 'BLOCKED', 'queries': [], 'sources': [], 'limitations': '', 'scope_comparison': '', 'baseline': ''}, 'artifacts': [], 'result': None}
    path = root / 'runs' / rid / 'round.json'
    save(path, record)
    print(path)
    print(f'branch: git switch -c {branch}')
    print('BLOCKED: browse now, read primary sources, complete preflight, then run admit. No autonomous search has occurred.')


def admit(root: Path, path: Path) -> None:
    r = load(path)
    verdict = validate_preflight(r, fresh=True)
    pp = problem_path(root, r['problem_id'])
    p = load(pp)
    require(p['status'] not in TERMINAL, 'target already completed')
    if verdict == 'RESOLVED_EXTERNAL':
        p['status'] = 'COMPLETED_EXTERNAL'
        p['resolution'] = r['preflight']['resolution']
        p['checked_on'] = stamp(r['preflight']['checked_at']).date().isoformat()
        save(pp, p)
        r['state'] = 'CLOSED_EXTERNAL'
        save(path, r)
        print('COMPLETED_EXTERNAL: record updated on this working branch; stop searching for a new solution. PR still requires review.')
    elif verdict in {'CLAIMED_RESOLVED', 'BLOCKED'}:
        r['state'] = 'PAUSED'
        save(path, r)
        raise ValueError('STOP: investigate the resolution claim or restore access; no discovery run admitted')
    else:
        r['state'] = 'ADMITTED'
        r['admitted_at'] = dt.datetime.now(UTC).isoformat()
        save(path, r)
        print('ADMITTED: one budgeted round. Preserve code, seeds, checksums, stdout, failures and limitations.')


def decide(root: Path, pid: str, kind: str, agent: str, fields: list[str], rationale: str, extra: dict) -> Path:
    """Write a GATE_CONTRACT.md §2.2 decision record; the PR still needs owner review."""
    require(re.fullmatch(r'[a-z0-9-]+', agent) is not None, 'use an agent slug')
    current = load(problem_path(root, pid)) if kind != 'new-problem' else {}
    now = dt.datetime.now(UTC)
    did = now.strftime('%Y%m%dT%H%M%S%fZ') + '-' + agent + '-' + pid + '-' + kind
    record = {'decision_id': did, 'problem_id': pid, 'kind': kind, 'fields': fields, 'author': agent,
              'created_at': now.isoformat(), 'base_sha': git(root, 'rev-parse', 'HEAD'), 'rationale': rationale}
    if kind == 'status-change':
        record['from'] = current.get('status')
    record.update({k: v for k, v in extra.items() if v})
    validate_decision(record, did)
    path = root / 'decisions' / did / 'decision.json'
    save(path, record)
    print(path)
    print('Decision recorded on this branch. Edit the card in the same PR; CI checks that the listed fields changed.')
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='cmd', required=True)
    v = sub.add_parser('validate'); v.add_argument('root', type=Path)
    d = sub.add_parser('check-diff'); d.add_argument('root', type=Path); d.add_argument('base'); d.add_argument('head')
    s = sub.add_parser('start'); s.add_argument('root', type=Path); s.add_argument('problem'); s.add_argument('--agent', required=True); s.add_argument('--topic', default='round')
    a = sub.add_parser('admit'); a.add_argument('root', type=Path); a.add_argument('record', type=Path)
    c = sub.add_parser('check-pins'); c.add_argument('root', type=Path)
    k = sub.add_parser('decide'); k.add_argument('root', type=Path); k.add_argument('problem')
    k.add_argument('--kind', required=True, choices=sorted(DECISION_KINDS)); k.add_argument('--agent', required=True)
    k.add_argument('--fields', default='', help='comma-separated changed fields'); k.add_argument('--rationale', required=True)
    k.add_argument('--impact', choices=sorted(SPEC_IMPACTS)); k.add_argument('--to', choices=sorted(DECISION_STATUS_TARGETS | {'CLAIMED_RESOLVED'}),
                   help='CLAIMED_RESOLVED only for a resolution-only correction of a CLAIMED_RESOLVED card')
    k.add_argument('--rounds', default='', help='COMPLETED_INTERNAL: comma-separated round ids'); k.add_argument('--verifier')
    args = parser.parse_args()
    try:
        if args.cmd == 'validate': validate_repo(args.root)
        elif args.cmd == 'check-diff': check_diff(args.root, args.base, args.head)
        elif args.cmd == 'start': start(args.root, args.problem, args.agent, args.topic)
        elif args.cmd == 'admit': admit(args.root, args.record)
        elif args.cmd == 'check-pins': print(f'PASS: governance pin {check_pins(args.root)} consistent in lock, workflow, README and AGENTS.')
        elif args.cmd == 'decide':
            decide(args.root, args.problem, args.kind, args.agent, [x for x in args.fields.split(',') if x], args.rationale,
                   {'impact': args.impact, 'to': args.to, 'verifier': args.verifier,
                    'rounds': [x for x in args.rounds.split(',') if x]})
        return 0
    except (ValueError, KeyError, TypeError, AttributeError, OSError, subprocess.CalledProcessError) as e:
        print(f'BLOCKED: {e}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
