"""Tests for Makefile deploy-all and destroy-all dependency graphs.

Parses the deployment Makefile, builds the dependency DAG, and asserts
ordering constraints that prevent the race conditions and resource
conflicts we've encountered in production.

Run with:  pytest tests/test_makefile_dependencies.py -v
"""

import re
import pytest
from pathlib import Path
from collections import defaultdict, deque

MAKEFILE_PATH = Path(__file__).parent.parent / "deployment" / "Makefile"


# ---------------------------------------------------------------------------
# Makefile parser
# ---------------------------------------------------------------------------

def parse_makefile_targets(makefile_path):
    """Parse a Makefile and return a dict of target -> [prerequisites]."""
    content = makefile_path.read_text()

    # Join backslash-continuation lines
    content = re.sub(r"\\\n\s*", " ", content)

    targets = {}
    for line in content.split("\n"):
        stripped = line.strip()

        # Skip blank lines, comments, recipe lines (start with tab)
        if not stripped or stripped.startswith("#") or line.startswith("\t"):
            continue

        # Skip Make directives
        if any(
            stripped.startswith(k)
            for k in ("ifeq", "ifneq", "ifdef", "ifndef", "else", "endif",
                       "include", "export", "-include", "define", "endef")
        ):
            continue

        # Skip variable assignments  (VAR =, VAR :=, VAR ?=, VAR +=)
        if re.match(r"^[\w.-]+\s*[:?+]?=", stripped):
            continue

        # Match  target: [prerequisites ...]
        m = re.match(r"^([a-zA-Z_][\w-]*)\s*:\s*(.*?)$", stripped)
        if m:
            target = m.group(1)
            prereq_str = m.group(2).strip()
            prereqs = [p for p in prereq_str.split() if p]
            targets[target] = prereqs

    return targets


# ---------------------------------------------------------------------------
# Graph helpers
# ---------------------------------------------------------------------------

def get_ancestors(targets, target):
    """Return all transitive prerequisites of *target*."""
    ancestors = set()
    queue = deque(targets.get(target, []))
    while queue:
        dep = queue.popleft()
        if dep not in ancestors:
            ancestors.add(dep)
            queue.extend(targets.get(dep, []))
    return ancestors


def is_before(targets, prerequisite, target):
    """True if *prerequisite* is a (transitive) dependency of *target*.

    In other words, Make guarantees *prerequisite* completes before *target*
    starts.
    """
    return prerequisite in get_ancestors(targets, target)


def are_independent(targets, a, b):
    """True if neither target is an ancestor of the other (can run in parallel)."""
    return not is_before(targets, a, b) and not is_before(targets, b, a)


def all_targets_in_chain(targets, root):
    """Return *root* plus every target transitively reachable from it."""
    return get_ancestors(targets, root) | {root}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def makefile_targets():
    return parse_makefile_targets(MAKEFILE_PATH)


# ---------------------------------------------------------------------------
# Parser sanity checks
# ---------------------------------------------------------------------------

class TestParser:
    def test_makefile_exists(self):
        assert MAKEFILE_PATH.exists(), f"Makefile not found at {MAKEFILE_PATH}"

    def test_finds_deploy_all(self, makefile_targets):
        assert "deploy-all" in makefile_targets

    def test_finds_destroy_all(self, makefile_targets):
        assert "destroy-all" in makefile_targets

    def test_deploy_all_has_expected_targets(self, makefile_targets):
        deps = makefile_targets["deploy-all"]
        for expected in ("primary_ecs", "standby_ecs", "global_routing",
                         "region-switch", "secrets-rotation", "monitoring"):
            assert expected in deps, f"{expected} missing from deploy-all"


# ---------------------------------------------------------------------------
# Deploy-all ordering constraints
# ---------------------------------------------------------------------------

class TestDeployOrdering:
    """Verify the deploy dependency chain is correctly ordered."""

    def test_infrastructure_after_vpc(self, makefile_targets):
        assert is_before(makefile_targets, "create-peer", "primary_infrastructure")
        assert is_before(makefile_targets, "create-peer", "standby_infrastructure")

    def test_codebuild_after_infra(self, makefile_targets):
        assert is_before(makefile_targets, "primary_infrastructure", "codebuild-infra")

    def test_build_images_after_infra_and_codebuild(self, makefile_targets):
        """Images can't be built until ECR repos (infra) and CodeBuild project exist."""
        assert is_before(makefile_targets, "primary_infrastructure", "build-images")
        assert is_before(makefile_targets, "standby_infrastructure", "build-images")
        assert is_before(makefile_targets, "codebuild-infra", "build-images")

    def test_ecs_after_builds(self, makefile_targets):
        assert is_before(makefile_targets, "build-images", "primary_ecs")
        assert is_before(makefile_targets, "build-images", "standby_ecs")

    def test_ecs_after_databases(self, makefile_targets):
        assert is_before(makefile_targets, "primary_region_catalog-db", "primary_ecs")
        assert is_before(makefile_targets, "orders-dsql-db", "primary_ecs")
        assert is_before(makefile_targets, "carts-db", "primary_ecs")
        assert is_before(makefile_targets, "standby_region_catalog-db", "standby_ecs")
        assert is_before(makefile_targets, "orders-dsql-db-standby", "standby_ecs")

    def test_databases_after_infrastructure(self, makefile_targets):
        assert is_before(makefile_targets, "primary_infrastructure", "primary_region_catalog-db")
        assert is_before(makefile_targets, "primary_infrastructure", "orders-dsql-db")
        assert is_before(makefile_targets, "primary_infrastructure", "carts-db")

    def test_standby_catalog_db_after_primary(self, makefile_targets):
        """Global Aurora cluster: standby needs primary created first."""
        assert is_before(makefile_targets, "primary_region_catalog-db", "standby_region_catalog-db")
        assert is_before(makefile_targets, "standby_infrastructure", "standby_region_catalog-db")

    def test_global_routing_after_both_ecs(self, makefile_targets):
        assert is_before(makefile_targets, "primary_ecs", "global_routing")
        assert is_before(makefile_targets, "standby_ecs", "global_routing")

    def test_canaries_after_routing(self, makefile_targets):
        assert is_before(makefile_targets, "global_routing", "canaries_primary")
        assert is_before(makefile_targets, "global_routing", "canaries_standby")

    def test_region_switch_after_routing(self, makefile_targets):
        assert is_before(makefile_targets, "global_routing", "region-switch-plan")
        assert is_before(makefile_targets, "region-switch-plan", "region-switch")

    def test_secrets_rotation_after_catalog_db(self, makefile_targets):
        assert is_before(makefile_targets, "primary_region_catalog-db", "secrets-rotation")

    def test_reconciliation_after_standby_catalog_db(self, makefile_targets):
        assert is_before(makefile_targets, "standby_region_catalog-db", "restore-reconciliation")

    def test_monitoring_after_reconciliation(self, makefile_targets):
        assert is_before(makefile_targets, "restore-reconciliation", "monitoring")


# ---------------------------------------------------------------------------
# Destroy-all ordering constraints
# ---------------------------------------------------------------------------

class TestDestroyOrdering:
    """Verify the destroy dependency chain prevents resource conflicts.

    Key invariant: any stack whose IAM roles or resources reference
    Secrets Manager secrets in another stack must be fully deleted
    *before* the stack owning those secrets is deleted.
    """

    # -- Secrets / IAM role race conditions --

    def test_reconciliation_ssm_before_crdr_roles(self, makefile_targets):
        """SSM automation docs reference CRDRSSMAutomationRoleArn secret from crdr-roles stack.
        SSM stacks must be deleted before crdr-roles (which owns the secret)."""
        assert is_before(makefile_targets, "destroy-restore-reconciliation-ssm", "destroy-crdr-roles")

    def test_crdr_roles_before_databases_primary(self, makefile_targets):
        """crdr-roles IAM role references catalog DB secret."""
        assert is_before(makefile_targets, "destroy-crdr-roles", "destroy-databases-primary")

    def test_secrets_rotation_before_databases_primary(self, makefile_targets):
        """secrets-rotation Lambda references catalog DB secret."""
        assert is_before(makefile_targets, "destroy-secrets-rotation", "destroy-databases-primary")

    def test_reconciliation_before_databases_standby(self, makefile_targets):
        """reconciliation Lambda role references catalog DB secret in standby."""
        assert is_before(makefile_targets, "destroy-restore-reconciliation-ssm", "destroy-databases-standby")

    def test_canaries_before_apps(self, makefile_targets):
        """Canary execution roles reference secrets from the apps stack.
        Canaries must be fully deleted before apps (which own the secrets)."""
        assert is_before(makefile_targets, "destroy-canaries-primary", "destroy-apps-primary")
        assert is_before(makefile_targets, "destroy-canaries-standby", "destroy-apps-primary")
        assert is_before(makefile_targets, "destroy-canaries-primary", "destroy-apps-standby")
        assert is_before(makefile_targets, "destroy-canaries-standby", "destroy-apps-standby")

    # -- Standard reverse-deploy ordering --

    def test_apps_before_ecr_cleanup(self, makefile_targets):
        assert is_before(makefile_targets, "destroy-apps-primary", "destroy-ecr-primary")
        assert is_before(makefile_targets, "destroy-apps-standby", "destroy-ecr-standby")

    def test_ecr_before_infra(self, makefile_targets):
        """ECR repos must be emptied before baseInfra stack is deleted."""
        assert is_before(makefile_targets, "destroy-ecr-primary", "destroy-infra")
        assert is_before(makefile_targets, "destroy-ecr-standby", "destroy-infra")

    def test_databases_before_infra(self, makefile_targets):
        assert is_before(makefile_targets, "destroy-databases-primary", "destroy-infra")
        assert is_before(makefile_targets, "destroy-databases-standby", "destroy-infra")

    def test_global_routing_before_infra(self, makefile_targets):
        assert is_before(makefile_targets, "destroy-global_routing", "destroy-infra")

    def test_canaries_before_global_routing(self, makefile_targets):
        assert is_before(makefile_targets, "destroy-canaries-primary", "destroy-global_routing")
        assert is_before(makefile_targets, "destroy-canaries-standby", "destroy-global_routing")

    def test_region_switch_before_global_routing(self, makefile_targets):
        assert is_before(makefile_targets, "destroy-region-switch", "destroy-global_routing")

    def test_infra_before_vpc(self, makefile_targets):
        assert is_before(makefile_targets, "destroy-infra", "destroy-peer")

    def test_standby_vpc_before_primary_vpc(self, makefile_targets):
        """Peering must be removed from standby side first."""
        assert is_before(makefile_targets, "destroy-peer_standby", "destroy-peer_primary")

    # -- Completeness: every destroy-* target is reachable from destroy-all --

    def test_all_destroy_targets_reachable(self, makefile_targets):
        """Every destroy-* target must be in the destroy-all dependency chain,
        otherwise that stack would never be deleted."""
        reachable = all_targets_in_chain(makefile_targets, "destroy-all")
        destroy_targets = [t for t in makefile_targets if t.startswith("destroy-")]
        unreachable = [t for t in destroy_targets if t not in reachable]
        assert unreachable == [], \
            f"These destroy targets are not reachable from destroy-all: {unreachable}"


# ---------------------------------------------------------------------------
# Parallelism: targets that SHOULD be independent
# ---------------------------------------------------------------------------

class TestParallelism:
    """Verify that targets we expect to run concurrently have no
    ordering dependency between them."""

    # -- Deploy parallelism --

    def test_deploy_infra_regions_parallel(self, makefile_targets):
        assert are_independent(makefile_targets, "primary_infrastructure", "standby_infrastructure")

    def test_deploy_ecs_regions_parallel(self, makefile_targets):
        assert are_independent(makefile_targets, "primary_ecs", "standby_ecs")

    def test_deploy_clients_parallel(self, makefile_targets):
        assert are_independent(makefile_targets, "client-primary", "client-standby")

    def test_deploy_canaries_parallel(self, makefile_targets):
        assert are_independent(makefile_targets, "canaries_primary", "canaries_standby")

    # -- Destroy parallelism --

    def test_destroy_apps_regions_parallel(self, makefile_targets):
        assert are_independent(makefile_targets, "destroy-apps-primary", "destroy-apps-standby")

    def test_destroy_apps_and_clients_parallel(self, makefile_targets):
        assert are_independent(makefile_targets, "destroy-apps-primary", "destroy-client-primary")

    def test_destroy_apps_and_global_routing_parallel(self, makefile_targets):
        """Apps and global routing are decoupled for parallel deletion."""
        assert are_independent(makefile_targets, "destroy-apps-primary", "destroy-global_routing")

    def test_destroy_chaos_and_apps_parallel(self, makefile_targets):
        assert are_independent(makefile_targets, "destroy-chaos-engineering", "destroy-apps-primary")

    def test_destroy_monitoring_and_apps_parallel(self, makefile_targets):
        assert are_independent(makefile_targets, "destroy-monitoring", "destroy-apps-primary")

    def test_destroy_canaries_parallel(self, makefile_targets):
        assert are_independent(makefile_targets, "destroy-canaries-primary", "destroy-canaries-standby")

    def test_destroy_secrets_rotation_and_apps_parallel(self, makefile_targets):
        """secrets-rotation has no dependency on apps — can start immediately."""
        assert are_independent(makefile_targets, "destroy-secrets-rotation", "destroy-apps-primary")

    def test_destroy_crdr_roles_and_apps_parallel(self, makefile_targets):
        """crdr-roles has no dependency on apps — can start immediately."""
        assert are_independent(makefile_targets, "destroy-crdr-roles", "destroy-apps-primary")


# ---------------------------------------------------------------------------
# Cycle detection
# ---------------------------------------------------------------------------

class TestNoCycles:
    def test_dependency_graph_is_acyclic(self, makefile_targets):
        """The dependency graph must be a DAG."""
        # Collect all nodes
        all_nodes = set(makefile_targets.keys())
        for deps in makefile_targets.values():
            all_nodes.update(deps)

        # Build adjacency list (prerequisite -> targets that depend on it)
        adj = defaultdict(list)
        in_degree = defaultdict(int)
        for node in all_nodes:
            in_degree.setdefault(node, 0)
        for target, deps in makefile_targets.items():
            for dep in deps:
                adj[dep].append(target)
                in_degree[target] += 1

        # Kahn's algorithm
        queue = deque(n for n in all_nodes if in_degree[n] == 0)
        visited = 0
        while queue:
            node = queue.popleft()
            visited += 1
            for neighbor in adj[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        assert visited == len(all_nodes), \
            f"Cycle detected — only {visited}/{len(all_nodes)} nodes resolved"
