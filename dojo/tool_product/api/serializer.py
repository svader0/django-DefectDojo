from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from dojo.models import Product
from dojo.tool_config.queries import get_authorized_tool_configurations
from dojo.tool_product.models import Tool_Product_Settings


class ToolProductSettingsSerializer(serializers.ModelSerializer):
    setting_url = serializers.CharField(source="url")
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), required=True,
    )

    class Meta:
        model = Tool_Product_Settings
        fields = "__all__"

    def validate(self, data):
        # A tool_configuration binds a stored third-party credential, so gate it by
        # view_tool_configuration (the same permission the tool-config views enforce),
        # not just the product permission this endpoint checks. Absent on PATCH -> no-op.
        tool_configuration = data.get("tool_configuration")
        if tool_configuration is not None:
            request_user = getattr(self.context.get("request"), "user", None)
            if not get_authorized_tool_configurations(request_user).filter(pk=tool_configuration.pk).exists():
                msg = "You do not have permission to use this tool configuration."
                raise PermissionDenied(msg)
        return data
