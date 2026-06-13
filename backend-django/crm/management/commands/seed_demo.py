import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from crm import scoring
from crm.models import (
    Activity,
    CustomFieldDefinition,
    EmailTemplate,
    Lead,
    Notification,
    PipelineStage,
    Task,
    User,
)


class Command(BaseCommand):
    help = "Wipe and seed demo data (users, leads, activities, tasks, templates)."

    def handle(self, *args, **options):
        self.stdout.write("Clearing existing data…")
        for model in (Activity, Task, Notification, Lead, EmailTemplate, CustomFieldDefinition, PipelineStage):
            model.objects.all().delete()
        User.objects.all().delete()

        # Pipeline stages
        stage_defs = [
            ("New", "new", 1, "#3b82f6", False, False),
            ("Contacted", "contacted", 2, "#8b5cf6", False, False),
            ("Qualified", "qualified", 3, "#f59e0b", False, False),
            ("Negotiating", "negotiating", 4, "#f97316", False, False),
            ("Won", "won", 5, "#22c55e", True, False),
            ("Lost", "lost", 6, "#ef4444", False, True),
        ]
        stages = {}
        for name, slug, pos, color, won, lost in stage_defs:
            stages[slug] = PipelineStage.objects.create(
                name=name, slug=slug, position=pos, color=color, is_won=won, is_lost=lost
            )

        # Users
        def mk(name, email, role, phone):
            u = User(username=email, name=name, email=email, role=role, phone=phone,
                     is_staff=(role in ("admin", "manager")), is_superuser=(role == "admin"))
            u.set_password("password")
            u.save()
            return u

        admin = mk("Parul Saxena", "admin@quibus.in", "admin", "+91 98290 00001")
        manager = mk("Rohit Sharma", "manager@quibus.in", "manager", "+91 98290 00002")
        rep1 = mk("Anjali Verma", "anjali@quibus.in", "rep", "+91 98290 00003")
        rep2 = mk("Vikram Singh", "vikram@quibus.in", "rep", "+91 98290 00004")

        # Custom fields
        CustomFieldDefinition.objects.create(label="Budget Range", key="budget_range", type="select",
                                             options=["< ₹50k", "₹50k–₹2L", "₹2L–₹5L", "> ₹5L"])
        CustomFieldDefinition.objects.create(label="Industry", key="industry", type="text")
        CustomFieldDefinition.objects.create(label="Decision Maker", key="decision_maker", type="boolean")

        # Email templates
        EmailTemplate.objects.create(
            name="Welcome / First Touch", created_by=admin,
            subject="Great connecting with you, {{first_name}}!",
            body="Hi {{first_name}},\n\nThanks for your interest in our services. I'd love to set up a quick 15-minute call to understand {{company}}'s goals.\n\nBest,\nQuibus Team")
        EmailTemplate.objects.create(
            name="Follow-up After Call", created_by=manager,
            subject="Next steps for {{company}}",
            body="Hi {{first_name}},\n\nGreat speaking with you today. As discussed, I'm attaching our proposal.\n\nBest,\nQuibus Team")
        EmailTemplate.objects.create(
            name="Proposal Reminder", created_by=manager,
            subject="Checking in on the proposal, {{first_name}}",
            body="Hi {{first_name}},\n\nJust checking in on the proposal I sent over.\n\nBest,\nQuibus Team")

        # Leads
        owners = [rep1, rep2, manager]
        demo = [
            ("Aarav", "Mehta", "aarav.mehta@technova.in", "TechNova Solutions", "CTO", "web_form", "qualified", 250000),
            ("Priya", "Iyer", "priya@brightedu.com", "BrightEdu Academy", "Founder", "google_ads", "negotiating", 480000),
            ("Karan", "Kapoor", "karan.k@stylehub.in", "StyleHub Retail", "Marketing Head", "facebook_ads", "contacted", 120000),
            ("Sneha", "Reddy", "sneha@greenleaf.org", "GreenLeaf Organics", "CEO", "referral", "won", 350000),
            ("Aditya", "Joshi", "aditya@finwise.co", "FinWise Advisors", "Partner", "linkedin", "new", 200000),
            ("Meera", "Nair", "meera.nair@oceanic.in", "Oceanic Exports", "Director", "cold_call", "contacted", 600000),
            ("Rahul", "Gupta", "rahul@speedlogix.com", "SpeedLogix", "Ops Manager", "web_form", "qualified", 175000),
            ("Divya", "Malhotra", "divya@craftnest.in", "CraftNest", "Owner", "manual", "lost", 90000),
            ("Arjun", "Bose", "arjun@medicare-plus.in", "MediCare Plus", "Admin Head", "google_ads", "negotiating", 320000),
            ("Ishita", "Chawla", "ishita@urbanbite.com", "UrbanBite Foods", "Co-founder", "referral", "new", 150000),
            ("Nikhil", "Rao", "nikhil@cloudpeak.io", "CloudPeak Systems", "VP Sales", "linkedin", "qualified", 420000),
            ("Tanvi", "Desai", "tanvi@blossomco.in", "Blossom Cosmetics", "Brand Manager", "facebook_ads", "new", 80000),
        ]
        industries = ["Technology", "Education", "Retail", "Healthcare", "Food"]
        now = timezone.now()

        for i, (first, last, email, company, title, source, slug, value) in enumerate(demo):
            stage = stages[slug]
            owner = owners[i % len(owners)]
            created = now - timedelta(days=random.randint(3, 45))
            lead = Lead.objects.create(
                first_name=first, last_name=last, email=email,
                phone=f"+91 9{random.randint(100000000, 999999999)}",
                company=company, job_title=title, source=source, stage=stage, owner=owner,
                value=value, custom_fields={"industry": industries[i % 5], "decision_maker": bool(i % 2)},
                converted_at=(created + timedelta(days=random.randint(5, 20))) if stage.is_won else None,
                lost_reason="Budget constraints" if stage.is_lost else "",
            )
            Lead.objects.filter(pk=lead.pk).update(created_at=created)

            Activity.objects.create(lead=lead, user=owner, type="system",
                                    subject=f"Lead created via {source.replace('_', ' ')}", occurred_at=created)
            if slug != "new":
                Activity.objects.create(lead=lead, user=owner, type="call", subject=f"Intro call with {first}",
                                        description="Discussed requirements and budget. Positive response.",
                                        occurred_at=created + timedelta(days=1))
                Activity.objects.create(lead=lead, user=owner, type="email", subject="Sent welcome email",
                                        occurred_at=created + timedelta(days=1, hours=2))
            if slug in ("qualified", "negotiating", "won"):
                Activity.objects.create(lead=lead, user=owner, type="meeting", subject="Discovery meeting",
                                        description="Demo of platform; stakeholders aligned.",
                                        occurred_at=created + timedelta(days=4))

            lead.refresh_from_db()
            lead.last_activity_at = lead.activities.order_by("-occurred_at").first().occurred_at
            lead.score = scoring.calculate(lead)
            lead.save(update_fields=["last_activity_at", "score"])

            if not stage.is_won and not stage.is_lost:
                Task.objects.create(lead=lead, assigned_to=owner, created_by=manager,
                                    title=f"Follow up with {first} ({company})",
                                    priority=["low", "medium", "high"][i % 3],
                                    due_at=now + timedelta(days=random.randint(-2, 7)))

        Task.objects.create(assigned_to=rep1, created_by=manager, title="Prepare Q3 outreach list",
                            priority="medium", due_at=now + timedelta(days=3))
        Task.objects.create(assigned_to=rep2, created_by=manager, title="Update proposal deck with new pricing",
                            priority="high", due_at=now + timedelta(days=1))

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {Lead.objects.count()} leads, {Activity.objects.count()} activities, "
            f"{Task.objects.count()} tasks, {User.objects.count()} users."))
