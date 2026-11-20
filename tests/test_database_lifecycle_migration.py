from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20261120080000_enforce_owner_state_transitions.sql"


class DatabaseLifecycleMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sql = MIGRATION.read_text(encoding="utf-8").lower()

    def test_installs_guards_for_all_lifecycle_tables(self):
        for name in (
            "autoearn_guard_opportunity_state",
            "autoearn_guard_task_state",
            "autoearn_guard_reward_state",
            "autoearn_guard_reward_delete",
        ):
            with self.subTest(function=name):
                self.assertIn(f"function public.{name}()", self.sql)

        for name in (
            "autoearn_opportunity_state_guard",
            "autoearn_task_state_guard",
            "autoearn_reward_state_guard",
            "autoearn_reward_delete_guard",
        ):
            with self.subTest(trigger=name):
                self.assertIn(f"create trigger {name}", self.sql)

    def test_opportunities_cannot_be_promoted_to_eligible_by_owner_updates(self):
        self.assertIn("new.status in ('reviewing', 'ineligible', 'archived')", self.sql)
        self.assertNotIn("new.status = 'eligible'", self.sql)
        self.assertIn("owners insert discovered opportunities", self.sql)

    def test_tasks_have_one_way_approval_and_completion_transitions(self):
        self.assertIn("old.status = 'pending_approval' and new.status = 'approved'", self.sql)
        self.assertIn("old.status = 'approved' and new.status = 'completed'", self.sql)
        self.assertIn("new.approved_at := pg_catalog.clock_timestamp()", self.sql)
        self.assertIn("new.completed_at := pg_catalog.clock_timestamp()", self.sql)

    def test_rewards_must_start_pending_and_paid_requires_reference(self):
        self.assertIn("new.status <> 'pending'", self.sql)
        self.assertIn("a paid reward requires a payment reference", self.sql)
        self.assertIn("old.status = 'confirmed' and new.status in ('paid', 'rejected')", self.sql)
        self.assertIn("confirmed or paid reward records cannot be deleted", self.sql)

    def test_reward_link_is_cleared_only_when_linked_opportunity_is_deleted(self):
        self.assertIn("new.opportunity_id is distinct from old.opportunity_id", self.sql)
        self.assertIn("new.opportunity_id is not null", self.sql)
        self.assertIn("exists (", self.sql)
        self.assertIn("from public.opportunities", self.sql)
        self.assertIn("where id = old.opportunity_id", self.sql)
        self.assertIn(
            "reward opportunity association is immutable except when its opportunity is deleted",
            self.sql,
        )

    def test_replaces_broad_owner_policies_with_explicit_operations(self):
        self.assertIn('drop policy if exists "owner manages opportunities"', self.sql)
        self.assertIn('drop policy if exists "owner manages tasks"', self.sql)
        self.assertIn('drop policy if exists "owner manages rewards"', self.sql)
        for policy in (
            "owners read opportunities",
            "owners insert discovered opportunities",
            "owners update opportunities",
            "owners delete opportunities",
            "owners read tasks",
            "owners insert pending tasks",
            "owners update tasks",
            "owners delete tasks",
            "owners read rewards",
            "owners insert pending rewards",
            "owners update rewards",
            "owners delete rewards",
        ):
            with self.subTest(policy=policy):
                self.assertIn(f'create policy "{policy}"', self.sql)


if __name__ == "__main__":
    unittest.main()
