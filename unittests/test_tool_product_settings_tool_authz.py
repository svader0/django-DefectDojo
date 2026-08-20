"""
Regression: the Tool Product Settings form and REST serializer must not offer or
accept a Tool_Configuration the user lacks ``view_tool_configuration`` for, so a
narrowed <select> cannot be bypassed by POSTing the id -- via the UI or the API.
Mirrors unittests/test_api_scan_configuration_tool_authz.py.
"""
from types import SimpleNamespace

from rest_framework.exceptions import PermissionDenied

from dojo.models import Dojo_User, Tool_Configuration, Tool_Type
from dojo.tool_product.api.serializer import ToolProductSettingsSerializer
from dojo.tool_product.ui.forms import ToolProductSettingsForm

from .dojo_test_case import DojoTestCase


class ToolProductSettingsToolAuthzTest(DojoTestCase):
    def setUp(self):
        tool_type, _ = Tool_Type.objects.get_or_create(name="SonarQube")
        self.tool_config = Tool_Configuration.objects.create(
            name="prod-sonarqube", tool_type=tool_type, authentication_type="API",
            url="http://example.invalid/api", api_key="ADMIN-TOKEN",
        )
        self.unprivileged = Dojo_User.objects.create(
            username="toolprod_unprivileged", is_staff=False, is_superuser=False,
        )
        self.staff = Dojo_User.objects.create(
            username="toolprod_staff", is_staff=True, is_superuser=False,
        )
        self.product_type = self.create_product_type("toolprod-org")

    def _post(self, user):
        return ToolProductSettingsForm(
            {"name": "setting", "tool_configuration": self.tool_config.pk, "tool_project_id": "1"},
            user=user,
        )

    def test_unprivileged_user_is_offered_no_tool_configurations(self):
        form = ToolProductSettingsForm(user=self.unprivileged)
        self.assertNotIn(self.tool_config, form.fields["tool_configuration"].queryset)

    def test_unprivileged_user_cannot_submit_a_tool_configuration(self):
        form = self._post(self.unprivileged)
        self.assertFalse(form.is_valid())
        self.assertIn("tool_configuration", form.errors)

    def test_privileged_user_can_select_the_tool_configuration(self):
        form = self._post(self.staff)
        self.assertIn(self.tool_config, form.fields["tool_configuration"].queryset)
        self.assertNotIn("tool_configuration", form.errors)

    def _serializer(self, user):
        product = self.create_product("toolprod-product", prod_type=self.product_type)
        return ToolProductSettingsSerializer(
            data={
                "product": product.pk, "tool_configuration": self.tool_config.pk,
                "name": "setting", "setting_url": "http://www.example.com",
            },
            context={"request": SimpleNamespace(user=user)},
        )

    def test_rest_rejects_unauthorized_tool_configuration(self):
        serializer = self._serializer(self.unprivileged)
        with self.assertRaises(PermissionDenied):
            serializer.is_valid(raise_exception=True)

    def test_rest_allows_authorized_tool_configuration(self):
        serializer = self._serializer(self.staff)
        self.assertTrue(serializer.is_valid(), serializer.errors)
