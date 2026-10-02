import secrets

from rest_framework import serializers

from .models import (
    Activity,
    CustomFieldDefinition,
    EmailTemplate,
    Lead,
    LeadComment,
    Notification,
    PipelineStage,
    Product,
    Task,
    User,
)


class MiniProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ["id", "name", "kind"]


class UserSerializer(serializers.ModelSerializer):
    leads_count = serializers.IntegerField(read_only=True, required=False)
    tasks_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = User
        fields = ["id", "name", "email", "role", "phone", "is_active", "leads_count", "tasks_count"]


class UserWriteSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, min_length=8)

    class Meta:
        model = User
        fields = ["id", "name", "email", "role", "phone", "is_active", "password"]

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        validated_data.setdefault("username", validated_data["email"])
        user = User(**validated_data)
        user.set_password(password or secrets.token_urlsafe(16))
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for k, v in validated_data.items():
            setattr(instance, k, v)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class PipelineStageSerializer(serializers.ModelSerializer):
    leads_count = serializers.IntegerField(read_only=True, required=False)
    total_value = serializers.FloatField(read_only=True, required=False)

    class Meta:
        model = PipelineStage
        fields = ["id", "name", "slug", "position", "color", "stage_type", "is_won", "is_lost", "leads_count", "total_value"]


class CustomFieldDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomFieldDefinition
        fields = "__all__"


class MiniUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "name"]


class ActivitySerializer(serializers.ModelSerializer):
    user = MiniUserSerializer(read_only=True)
    lead_id = serializers.PrimaryKeyRelatedField(
        source="lead", queryset=Lead.objects.all(), write_only=True
    )
    lead = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Activity
        fields = ["id", "lead", "lead_id", "user", "type", "subject", "description", "metadata", "occurred_at", "created_at"]

    def get_lead(self, obj):
        return {
            "id": obj.lead_id,
            "first_name": obj.lead.first_name,
            "last_name": obj.lead.last_name,
        }


class LeadSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    stage = PipelineStageSerializer(read_only=True)
    owner = MiniUserSerializer(read_only=True)
    stage_id = serializers.PrimaryKeyRelatedField(
        source="stage", queryset=PipelineStage.objects.all(), required=False
    )
    owner_id = serializers.PrimaryKeyRelatedField(
        source="owner", queryset=User.objects.all(), required=False, allow_null=True
    )
    activities_count = serializers.IntegerField(read_only=True, required=False)
    tasks_count = serializers.IntegerField(read_only=True, required=False)
    product = MiniProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        source="product", queryset=Product.objects.all(), required=False, allow_null=True
    )
    products = MiniProductSerializer(many=True, read_only=True)
    products_id = serializers.PrimaryKeyRelatedField(
        source="products", queryset=Product.objects.all(), required=False, many=True, write_only=True
    )

    class Meta:
        model = Lead
        fields = [
            "id", "first_name", "last_name", "email", "phone", "job_title",
            "source", "product", "product_id", "products", "products_id", "stage", "stage_id", "owner", "owner_id",
            "score", "value", "notes", "photo",
            "custom_fields", "lost_reason", "last_activity_at", "converted_at",
            "created_at", "updated_at", "full_name", "activities_count", "tasks_count",
        ]
        read_only_fields = ["score", "converted_at", "last_activity_at"]


class LeadDetailSerializer(LeadSerializer):
    activities = ActivitySerializer(many=True, read_only=True)
    tasks = serializers.SerializerMethodField()

    class Meta(LeadSerializer.Meta):
        fields = LeadSerializer.Meta.fields + ["activities", "tasks"]

    def get_tasks(self, obj):
        return TaskSerializer(obj.tasks.all(), many=True).data


class TaskSerializer(serializers.ModelSerializer):
    assignee = MiniUserSerializer(source="assigned_to", read_only=True)
    assigned_to = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    lead = serializers.SerializerMethodField(read_only=True)
    lead_id = serializers.PrimaryKeyRelatedField(
        source="lead", queryset=Lead.objects.all(), required=False, allow_null=True, write_only=True
    )

    class Meta:
        model = Task
        fields = [
            "id", "lead", "lead_id", "assigned_to", "assignee", "title", "description",
            "priority", "status", "due_at", "completed_at", "created_at",
        ]

    def get_lead(self, obj):
        if not obj.lead_id:
            return None
        return {
            "id": obj.lead_id,
            "first_name": obj.lead.first_name,
            "last_name": obj.lead.last_name,
        }


class EmailTemplateSerializer(serializers.ModelSerializer):
    creator = MiniUserSerializer(source="created_by", read_only=True)

    class Meta:
        model = EmailTemplate
        fields = ["id", "name", "subject", "body", "creator", "created_at"]


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "data", "read_at", "created_at"]


class LeadCommentSerializer(serializers.ModelSerializer):
    author = MiniUserSerializer(source="user", read_only=True)

    class Meta:
        model = LeadComment
        fields = ["id", "body", "author", "created_at"]
        read_only_fields = ["author", "created_at"]
